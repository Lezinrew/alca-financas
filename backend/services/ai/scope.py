"""Resolução do contexto autenticado no servidor (contrato, seções 3 e 4).

Entrada: o usuário da sessão V2 já validada. Saída: ``ExecutionContext`` com
tenant, espaço financeiro e contas permitidas. O corpo da requisição pode
*escolher* entre os espaços de que o usuário é membro, mas nunca substituir a
verificação: espaço de outro tenant ou sem vínculo responde como inexistente.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .db import plain_tx, scoped_tx
from .errors import AiError
from .types import ExecutionContext, Privacy


def _as_uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("invalid_request", "Identificador inválido em %s." % field)


def list_memberships(pool, user_id: str) -> List[Dict[str, Any]]:
    """Tenants ativos de que o usuário participa, com o papel."""
    with plain_tx(pool) as cursor:
        cursor.execute(
            """
            SELECT m.tenant_id, m.role, t.name
            FROM tenant_members m
            JOIN tenants t ON t.id = m.tenant_id
            WHERE m.user_id = %s AND t.archived_at IS NULL
            ORDER BY t.created_at, t.id
            """,
            (str(user_id),),
        )
        return [dict(row) for row in cursor.fetchall()]


def resolve_tenant(pool, user_id: str, requested_tenant_id: Optional[str] = None) -> Dict[str, Any]:
    memberships = list_memberships(pool, user_id)
    if not memberships:
        raise AiError("scope_denied", "Usuário sem organização vinculada.")
    if requested_tenant_id:
        wanted = _as_uuid(requested_tenant_id, "X-Tenant-Id")
        for membership in memberships:
            if str(membership["tenant_id"]) == wanted:
                return membership
        raise AiError("scope_denied", "Organização fora do seu acesso.")
    if len(memberships) > 1:
        raise AiError("invalid_request", "Informe a organização no cabeçalho X-Tenant-Id.")
    return memberships[0]


def list_spaces(pool, tenant_id: str, user_id: str) -> List[Dict[str, Any]]:
    """Espaços financeiros ativos do tenant em que o usuário é membro."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            SELECT s.id, s.kind, s.name, m.role
            FROM financial_spaces s
            JOIN financial_space_members m
              ON m.financial_space_id = s.id AND m.tenant_id = s.tenant_id
            WHERE s.tenant_id = %s AND m.user_id = %s AND s.archived_at IS NULL
            ORDER BY s.created_at, s.id
            """,
            (str(tenant_id), str(user_id)),
        )
        return [dict(row) for row in cursor.fetchall()]


def list_space_accounts(pool, tenant_id: str, financial_space_id: str) -> List[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            SELECT a.id, a.name, a.type, a.institution, a.currency
            FROM financial_space_accounts l
            JOIN accounts a ON a.id = l.account_id AND a.tenant_id = l.tenant_id
            WHERE l.tenant_id = %s AND l.financial_space_id = %s AND a.archived_at IS NULL
            ORDER BY a.name
            """,
            (str(tenant_id), str(financial_space_id)),
        )
        return [dict(row) for row in cursor.fetchall()]


def resolve_scope(
    pool,
    *,
    user_id: str,
    requested_tenant_id: Optional[str] = None,
    requested_space_id: Optional[str] = None,
    channel: str = "web",
    privacy: Privacy = Privacy.LOCAL_ONLY,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> ExecutionContext:
    membership = resolve_tenant(pool, user_id, requested_tenant_id)
    tenant_id = str(membership["tenant_id"])
    spaces = list_spaces(pool, tenant_id, user_id)
    if not spaces:
        raise AiError("scope_denied", "Nenhum espaço financeiro está vinculado a você.")

    if requested_space_id:
        wanted = _as_uuid(requested_space_id, "financial_space_id")
        space = next((item for item in spaces if str(item["id"]) == wanted), None)
        if space is None:
            # Fora de escopo responde como inexistente (contrato, seção 12).
            raise AiError("not_found", "Espaço financeiro não encontrado.")
    elif len(spaces) == 1:
        space = spaces[0]
    else:
        raise AiError(
            "invalid_request",
            "Escolha o espaço financeiro deste pedido.",
            details={"field": "financial_space_id"},
        )

    accounts = list_space_accounts(pool, tenant_id, str(space["id"]))
    return ExecutionContext(
        tenant_id=tenant_id,
        actor_id=str(user_id),
        financial_space_id=str(space["id"]),
        space_kind=space["kind"],
        space_name=space["name"],
        allowed_account_ids=frozenset(str(account["id"]) for account in accounts),
        channel=channel,
        privacy=privacy,
        request_id=request_id or str(uuid.uuid4()),
        trace_id=trace_id or str(uuid.uuid4()),
    )


def context_for_run(pool, run: Dict[str, Any]) -> ExecutionContext:
    """Reconstrói o contexto de uma execução persistida (worker/retomada).

    O escopo é relido do banco a cada retomada: se o usuário perdeu o vínculo
    com o espaço enquanto a execução estava na fila, ela não prossegue.
    """
    context = resolve_scope(
        pool,
        user_id=str(run["actor_user_id"]),
        requested_tenant_id=str(run["tenant_id"]),
        requested_space_id=str(run["financial_space_id"]),
        channel=run["channel"],
        privacy=Privacy(run["privacy"]),
        request_id=str(run["request_id"]),
        trace_id=str(run["trace_id"]),
    )
    return context.with_run(str(run["id"]))
