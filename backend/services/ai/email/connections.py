"""Vínculo entre uma caixa de e-mail e o titular (tabela ``ai_email_connections``).

O que este módulo faz: registra, consulta e revoga o VÍNCULO já autorizado. A
linha guarda só a referência da credencial (``credential_ref``); o token fica
no cofre (``services.ai.email.credentials``).

O que este módulo NÃO faz: o fluxo OAuth com o provedor. A autorização do
titular (redirecionamento, ``state``, PKCE S256, troca do código, validação de
``iss``, guarda e renovação do refresh token) não está implementada nesta
entrega. Quem chama ``register_connection`` precisa ter concluído esse fluxo
por outro meio e depositado o token no cofre. Enquanto o fluxo não existir,
uma conexão só nasce por configuração manual do operador.

Regras:

* a conexão vale para um espaço financeiro e pertence a quem a criou
  (``owner_user_id``): outro integrante do mesmo espaço não lê a caixa dela;
* no máximo uma conexão ativa por titular em cada espaço;
* conexão ausente, revogada ou com erro -> ``connector_unavailable`` em
  qualquer chamada. Como as ferramentas consultam a conexão a cada uso, a
  revogação interrompe as tarefas pendentes dela (AC-05).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..db import scoped_tx, write_audit
from ..errors import AiError
from ..types import ExecutionContext, iso_utc
from .base import clean_text
from .credentials import credential_scheme, validate_credential_ref


logger = logging.getLogger("ai.email.connections")

_COLUMNS = (
    "id, tenant_id, financial_space_id, owner_user_id, provider, mailbox_label, status, "
    "credential_ref, scopes, last_error_code, connected_at, revoked_at, created_at"
)
# Para listagens: a coluna nem sai do banco (não basta escondê-la depois).
_LIST_COLUMNS = _COLUMNS.replace("credential_ref", "NULL::text AS credential_ref")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_.-]{1,40}$")
_SCOPE = re.compile(r"^[\x21-\x7e]{1,200}$")  # ASCII visível, sem espaço
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_MAX_SCOPES = 20

# Escopos que permitem enviar, apagar ou alterar mensagens. O contrato só
# autoriza leitura; pedir menos privilégio é mais barato do que confiar apenas
# na lista de permissão de ferramentas do conector.
_WRITE_SCOPE_MARKERS = (
    "gmail.send", "gmail.compose", "gmail.modify", "gmail.insert", "gmail.labels",
    "gmail.settings", "mail.send", "mail.readwrite", "imap.accessasuser", "smtp.",
)
_FULL_ACCESS_SCOPES = ("https://mail.google.com/", "https://mail.google.com")


@dataclass(frozen=True)
class EmailConnection:
    id: str
    tenant_id: str
    financial_space_id: str
    owner_user_id: str
    provider: str
    mailbox_label: str
    status: str
    # Referência ao cofre, nunca o token. Fica fora do ``repr`` e do dicionário
    # público só para não circular sem necessidade.
    credential_ref: Optional[str] = field(default=None, repr=False)
    scopes: Tuple[str, ...] = ()
    last_error_code: Optional[str] = None
    connected_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "EmailConnection":
        return cls(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            financial_space_id=str(row["financial_space_id"]),
            owner_user_id=str(row["owner_user_id"]),
            provider=row["provider"],
            mailbox_label=row["mailbox_label"],
            status=row["status"],
            credential_ref=row["credential_ref"],
            scopes=tuple(row["scopes"] or ()),
            last_error_code=row["last_error_code"],
            connected_at=row["connected_at"],
            revoked_at=row["revoked_at"],
        )

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.id,
            "financial_space_id": self.financial_space_id,
            "owner_user_id": self.owner_user_id,
            "provider": self.provider,
            "mailbox_label": self.mailbox_label,
            "status": self.status,
            "scopes": list(self.scopes),
            "last_error_code": self.last_error_code,
            "connected_at": iso_utc(self.connected_at) if self.connected_at else None,
            "revoked_at": iso_utc(self.revoked_at) if self.revoked_at else None,
        }


def _as_uuid(value: object) -> str:
    """Id malformado responde como inexistente, sem chegar ao banco."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("not_found", "Conexão não encontrada.")


def _no_connection() -> AiError:
    return AiError(
        "connector_unavailable",
        "Não há caixa de e-mail ativa conectada a este espaço.",
        retryable=False,
    )


def _space_role(cursor, ctx: ExecutionContext) -> Optional[str]:
    cursor.execute(
        """
        SELECT role FROM financial_space_members
        WHERE tenant_id = %s AND financial_space_id = %s AND user_id = %s
        """,
        (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
    )
    row = cursor.fetchone()
    return row["role"] if row else None


def _validate_scopes(scopes: Optional[Sequence[str]]) -> List[str]:
    if scopes is None or isinstance(scopes, (str, bytes)):
        raise AiError("invalid_request", "Informe os escopos autorizados.", details={"field": "scopes"})
    cleaned = sorted({str(item).strip() for item in scopes if str(item).strip()})
    if not cleaned or len(cleaned) > _MAX_SCOPES or any(not _SCOPE.match(item) for item in cleaned):
        raise AiError("invalid_request", "Lista de escopos inválida.", details={"field": "scopes"})
    for scope in cleaned:
        lowered = scope.lower()
        if lowered in _FULL_ACCESS_SCOPES or any(marker in lowered for marker in _WRITE_SCOPE_MARKERS):
            raise AiError(
                "invalid_request",
                "A conexão de e-mail aceita somente escopos de leitura.",
                details={"field": "scopes"},
            )
    return cleaned


def register_connection(
    pool,
    ctx: ExecutionContext,
    *,
    provider: str,
    mailbox_label: str,
    credential_ref: str,
    scopes: Sequence[str],
) -> EmailConnection:
    """Registra uma conexão já autorizada, no espaço e para o ator do contexto.

    Não executa OAuth (ver docstring do módulo). Só o titular do espaço
    registra conexões.
    """
    provider = (provider or "").strip().lower()
    if not _PROVIDER.match(provider):
        raise AiError("invalid_request", "Provedor inválido.", details={"field": "provider"})
    label = clean_text(mailbox_label, 120)
    if not label:
        raise AiError("invalid_request", "Informe um nome para a caixa.", details={"field": "mailbox_label"})
    reference = validate_credential_ref(credential_ref)
    scope_list = _validate_scopes(scopes)

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        role = _space_role(cursor, ctx)
        if role is None:
            raise AiError("not_found", "Espaço financeiro não encontrado.")
        if role != "owner":
            raise AiError("capability_denied", "Somente o titular do espaço conecta uma caixa de e-mail.")
        # Serializa registros concorrentes do mesmo titular no mesmo espaço: a
        # tabela não tem índice único para "uma ativa por titular", então a
        # garantia vem deste lock de transação.
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("ai_email_connection:%s:%s:%s" % (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),),
        )
        cursor.execute(
            """
            SELECT 1 FROM ai_email_connections
            WHERE tenant_id = %s AND financial_space_id = %s AND owner_user_id = %s AND status = 'active'
            """,
            (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
        )
        if cursor.fetchone() is not None:
            raise AiError("conflict", "Já existe uma caixa ativa neste espaço. Revogue-a antes de conectar outra.")
        cursor.execute(
            "INSERT INTO ai_email_connections ("
            " tenant_id, financial_space_id, owner_user_id, provider, mailbox_label, status,"
            " credential_ref, scopes, connected_at"
            ") VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, now()) RETURNING " + _COLUMNS,
            (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, provider, label, reference, scope_list),
        )
        connection = EmailConnection.from_row(cursor.fetchone())
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.email_connection.registered",
            entity_type="ai_email_connection",
            entity_id=connection.id,
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "provider": provider,
                "scopes": scope_list,
                # Só o esquema da referência; nunca o valor da credencial.
                "credential_scheme": credential_scheme(reference),
                "trace_id": ctx.trace_id,
            },
        )
    logger.info("event=connection_registered connection_id=%s provider=%s", connection.id, provider)
    return connection


def get_active_connection(pool, ctx: ExecutionContext) -> EmailConnection:
    """Conexão ativa do ator neste espaço, ou ``connector_unavailable``."""
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT " + _COLUMNS + " FROM ai_email_connections "
            "WHERE tenant_id = %s AND financial_space_id = %s AND owner_user_id = %s "
            "AND status = 'active' AND revoked_at IS NULL "
            "ORDER BY connected_at DESC NULLS LAST, id LIMIT 1",
            (ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
        )
        row = cursor.fetchone()
    if row is None or not row["credential_ref"]:
        raise _no_connection()
    return EmailConnection.from_row(row)


def require_active(pool, ctx: ExecutionContext, connection_id: str) -> EmailConnection:
    """Revalida UMA conexão específica imediatamente antes de um efeito.

    Usada entre o download e a gravação do anexo: se a conexão foi revogada
    enquanto o arquivo baixava, nada é gravado.
    """
    try:
        connection_id = _as_uuid(connection_id)
    except AiError:
        raise _no_connection()
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT " + _COLUMNS + " FROM ai_email_connections "
            "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s AND owner_user_id = %s "
            "AND status = 'active' AND revoked_at IS NULL",
            (str(connection_id), ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
        )
        row = cursor.fetchone()
    if row is None:
        raise _no_connection()
    return EmailConnection.from_row(row)


def list_connections(pool, ctx: ExecutionContext) -> List[EmailConnection]:
    """Conexões do espaço que o ator pode ver, SEM a referência da credencial.

    * o titular do espaço vê todas (é ele quem pode revogar a de qualquer um);
    * os demais integrantes veem só as próprias: a caixa de e-mail de outra
      pessoa não é assunto deles, nem para saber que existe;
    * ``credential_ref`` vem sempre ``None``. Listar serve para mostrar e
      revogar; quem precisa da referência é só o caminho que abre o conector
      (``get_active_connection``), que já filtra pelo dono.
    """
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        role = _space_role(cursor, ctx)
        if role is None:
            return []
        query = (
            "SELECT " + _LIST_COLUMNS + " FROM ai_email_connections "
            "WHERE tenant_id = %s AND financial_space_id = %s"
        )
        params: List[Any] = [ctx.tenant_id, ctx.financial_space_id]
        if role != "owner":
            query += " AND owner_user_id = %s"
            params.append(ctx.actor_id)
        cursor.execute(query + " ORDER BY created_at DESC, id", tuple(params))
        return [EmailConnection.from_row(row) for row in cursor.fetchall()]


def revoke_connection(pool, ctx: ExecutionContext, connection_id: str, reason: str) -> EmailConnection:
    """Revoga a conexão. Idempotente. Pode revogar: o dono dela ou o titular do espaço.

    A referência da credencial é apagada da linha: mesmo um defeito futuro que
    ignorasse o ``status`` não teria como localizar o token. Atenção: isto NÃO
    revoga o token no provedor nem o remove do cofre; essa etapa pertence ao
    fluxo OAuth, ainda não implementado.
    """
    reason = clean_text(reason, 500)
    if not reason:
        raise AiError("invalid_request", "Informe o motivo da revogação.", details={"field": "reason"})
    connection_id = _as_uuid(connection_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT " + _COLUMNS + " FROM ai_email_connections "
            "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s FOR UPDATE",
            (str(connection_id), ctx.tenant_id, ctx.financial_space_id),
        )
        row = cursor.fetchone()
        if row is None:
            # Outro tenant ou outro espaço responde como inexistente.
            raise AiError("not_found", "Conexão não encontrada.")
        if str(row["owner_user_id"]) != ctx.actor_id and _space_role(cursor, ctx) != "owner":
            raise AiError("capability_denied", "Você não pode revogar esta conexão.")
        if row["status"] == "revoked":
            return EmailConnection.from_row(row)
        cursor.execute(
            "UPDATE ai_email_connections SET status = 'revoked', revoked_at = now(), credential_ref = NULL "
            "WHERE id = %s AND tenant_id = %s RETURNING " + _COLUMNS,
            (str(connection_id), ctx.tenant_id),
        )
        connection = EmailConnection.from_row(cursor.fetchone())
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.email_connection.revoked",
            entity_type="ai_email_connection",
            entity_id=connection.id,
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "reason": reason,
                "previous_status": row["status"],
                "trace_id": ctx.trace_id,
            },
        )
    logger.info("event=connection_revoked connection_id=%s", connection.id)
    return connection


def mark_connection_error(pool, ctx: ExecutionContext, connection_id: str, error_code: str) -> None:
    """Tira a conexão de uso depois de uma recusa do provedor (ex.: HTTP 401).

    A conexão passa a ``error`` e deixa de ser devolvida por
    ``get_active_connection``; o titular precisa reconectar.
    """
    code = error_code if _ERROR_CODE.match(error_code or "") else "connector_error"
    connection_id = _as_uuid(connection_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_email_connections SET status = 'error', last_error_code = %s "
            "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s AND status = 'active'",
            (code, str(connection_id), ctx.tenant_id, ctx.financial_space_id),
        )
        marked = cursor.rowcount == 1
        if marked:
            write_audit(
                cursor,
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.actor_id,
                event_type="ai.email_connection.error",
                entity_type="ai_email_connection",
                entity_id=str(connection_id),
                metadata={"error_code": code, "trace_id": ctx.trace_id},
            )
    # Só registra o que aconteceu: uma conexão de outro espaço (ou já fora de
    # uso) não é alterada, e dizer "connection_error" no log seria falso.
    if marked:
        logger.warning("event=connection_error connection_id=%s code=%s", connection_id, code)
