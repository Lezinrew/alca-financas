"""Execuções persistentes: criação idempotente, visão, fila com lease e checkpoints.

Contrato, seções 6, 8 e 9. Este módulo só conhece PostgreSQL: não chama modelo
nem ferramenta. Três ideias sustentam o resto da plataforma:

* **Idempotência do pedido.** ``request_hash`` é o SHA-256 do pedido canônico.
  A mesma ``Idempotency-Key`` com o mesmo pedido devolve a execução anterior;
  com pedido diferente responde ``conflict``. Reenviar o POST nunca cria uma
  segunda execução (AC-15).
* **Lease com cerca (fencing).** Um worker só escreve em uma execução enquanto
  for o ``lease_owner``. Toda escrita de etapa renova o lease *na mesma
  transação* e falha com ``LeaseLost`` se outro worker assumiu. Sem isso, um
  worker lento (não morto) poderia gravar por cima de quem o substituiu.
* **Checkpoint por ``step_key``.** Cada inferência e cada ferramenta é uma
  linha em ``ai_run_steps``. Etapa concluída é devolvida para reuso; etapa
  encontrada ``started`` denuncia uma queda no meio, e quem decide o que fazer
  é o orquestrador (releitura repete; escrita consulta o estado antes).

O texto do pedido fica em ``ai_runs.input``; a auditoria guarda só referências.

Dois cuidados que atravessam o módulo:

* **Texto que o banco recusa.** NUL e substitutos isolados são barrados na
  entrada do pedido (``invalid_request``) e trocados por U+FFFD em toda
  gravação de etapa e de resultado (``storable``). Conteúdo de e-mail, PDF ou
  modelo nunca vira exceção de banco.
* **Revisão que termina durante o encerramento.** ``finish_run`` só grava
  ``waiting_review`` depois de conferir as propostas com lock; ver
  ``_review_already_settled``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from . import CONTRACT_VERSION
from .db import jsonb, queue_tx, scoped_tx, write_audit
from .errors import AiError
from .settings import AiSettings
from .types import ExecutionContext, RunStatus, canonical_json, iso_utc


logger = logging.getLogger("ai.runs")

# Tarefas pedidas pelo titular e tarefas criadas pelo servidor (aprovação e
# reversão). As segundas nunca chegam por ``create_run``.
USER_TASKS = ("finance_question", "statement_import")
SYSTEM_TASKS = ("apply_proposal", "reverse_operation")

MESSAGE_MAX_CHARS = 2000
INPUT_REFS_MAX = 20
INPUT_REF_KINDS = ("artifact", "email", "proposal", "operation")
# Uma referência é "tipo:identificador". Sem espaços nem caracteres de
# controle: referências viajam para a auditoria e para o prompt como dado.
# Estes padrões são usados com ``fullmatch``. Com ``match`` e "$" no fim, o
# Python aceitaria uma quebra de linha final ("artifact:abc\n"), porque "$"
# também casa ANTES de um "\n" que encerra o texto.
_INPUT_REF = re.compile(r"([a-z_]{1,20}):([A-Za-z0-9][A-Za-z0-9_.@:+=/\-]{0,199})")
_IDEMPOTENCY_KEY = re.compile(r"[\x21-\x7e]{8,200}")

# Higiene de texto. Dois tipos de caractere não podem ser gravados:
# * NUL (U+0000): o PostgreSQL recusa em ``text`` e em ``jsonb``;
# * substituto isolado (U+D800 a U+DFFF): existe em ``str`` do Python (um JSON
#   com "\ud800" produz um), mas não tem codificação UTF-8; o driver falha
#   antes mesmo de falar com o banco.
# Sem tratamento, um único caractere desses em um e-mail, PDF ou resposta de
# modelo viraria exceção de banco no meio da execução.
_UNSTORABLE = re.compile(r"[\x00\ud800-\udfff]")
# Controles C0 (menos TAB, LF e CR) e DEL: não fazem sentido em texto digitado.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
REPLACEMENT_CHAR = "�"

# Origem da chave de idempotência. Pedidos do titular e tarefas criadas pelo
# servidor vivem em espaços de nomes separados (ver ``_stored_key``).
KEY_ORIGIN_USER = "user"
KEY_ORIGIN_SYSTEM = "system"

# Tarefas do servidor são determinísticas e ficam na fila até um worker
# aparecer. O prazo é explícito (não se renova), mas maior que o interativo:
# uma aprovação não deve se perder porque o worker ficou alguns minutos fora.
SYSTEM_RUN_TIMEOUT_S = 3600

# Teto de vezes que uma execução pode ser assumida. Protege contra a execução
# "venenosa" que derruba o worker a cada tentativa e voltaria à fila para sempre.
MAX_RUN_ATTEMPTS = 5

LIST_DEFAULT_LIMIT = 20
LIST_MAX_LIMIT = 50

INFERENCE_STEP_NAME = "model.inference"
UNKNOWN_TOOL_NAME = "tool.unknown"

_TERMINAL = (RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value)
_LIVE_PROPOSAL_STATUSES = ("draft", "ready", "approved")

# Rótulos mostrados ao titular. O nome técnico da etapa nunca é o texto exibido.
_STEP_LABELS = {
    INFERENCE_STEP_NAME: "Interpretando o pedido",
    UNKNOWN_TOOL_NAME: "Ferramenta não reconhecida (recusada)",
    "email.search_financial": "Buscando e-mails financeiros",
    "email.get_message": "Lendo mensagem de e-mail",
    "email.download_attachment": "Baixando anexo para a quarentena",
    "imports.preview": "Preparando prévia da importação",
    "finance.read": "Consultando dados financeiros",
    "finance.prepare_change": "Preparando proposta de alteração",
    "finance.apply_change": "Aplicando alteração autorizada",
    "finance.operation_status": "Conferindo o estado da operação",
    "finance.reverse_change": "Preparando reversão",
    "rag.search_personal": "Buscando nos seus documentos",
    "whatsapp.respond": "Respondendo pelo WhatsApp",
}

# Estágio de progresso (spec 4.2): buscando -> lendo -> preparando -> aplicando.
_STAGE_BY_TOOL = {
    "email.search_financial": "searching",
    "rag.search_personal": "searching",
    "email.get_message": "reading",
    "email.download_attachment": "reading",
    "finance.read": "reading",
    "imports.preview": "preparing",
    "finance.prepare_change": "preparing",
    "finance.apply_change": "applying",
    "finance.reverse_change": "applying",
    "finance.operation_status": "applying",
}


class LeaseLost(Exception):
    """O worker não é mais o dono da execução; deve parar sem gravar nada."""


# ---------------------------------------------------------------------------
# Higiene de texto
# ---------------------------------------------------------------------------

def has_unstorable(value: Any) -> bool:
    """Há, em qualquer nível, texto que o banco não consegue gravar?"""
    if isinstance(value, str):
        return _UNSTORABLE.search(value) is not None
    if isinstance(value, dict):
        return any(has_unstorable(key) or has_unstorable(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_unstorable(item) for item in value)
    return False


def storable(value: Any) -> Any:
    """Cópia de ``value`` em que todo texto pode ser gravado em ``text``/``jsonb``.

    NUL e substitutos isolados viram U+FFFD (o caractere de substituição do
    Unicode): quem lê percebe que havia algo ali, e nada some em silêncio. É
    aplicado em toda escrita de etapa e de resultado; o orquestrador também o
    aplica ANTES de usar um resultado de ferramenta, para que o modelo veja
    exatamente o que ficou no checkpoint.
    """
    if isinstance(value, str):
        return _UNSTORABLE.sub(REPLACEMENT_CHAR, value)
    if isinstance(value, dict):
        return {(storable(key) if isinstance(key, str) else key): storable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [storable(item) for item in value]
    return value


def has_control_chars(text: str) -> bool:
    """Texto digitado por uma pessoa não traz controles (fora TAB e quebra de linha)."""
    return _CONTROL.search(text) is not None or _UNSTORABLE.search(text) is not None


def replace_control_chars(text: str, replacement: str = " ") -> str:
    """Troca controles e caracteres não graváveis por ``replacement``.

    Para texto extraído de arquivo (PDF, OCR), em que um NUL ou um avanço de
    página no meio do conteúdo é ruído, não motivo para recusar o documento.
    """
    return _UNSTORABLE.sub(replacement, _CONTROL.sub(replacement, text))


# ---------------------------------------------------------------------------
# Validação do pedido
# ---------------------------------------------------------------------------

def _as_uuid(value: Any) -> Optional[str]:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _require_run_id(run_id: Any) -> str:
    parsed = _as_uuid(run_id)
    if parsed is None:
        # Identificador malformado responde igual a recurso fora de escopo.
        raise AiError("not_found", "Execução não encontrada.")
    return parsed


def _validate_message(message: Any) -> str:
    if not isinstance(message, str):
        raise AiError("invalid_request", "Informe o pedido em texto.", details={"field": "message"})
    text = message.strip()
    if not 1 <= len(text) <= MESSAGE_MAX_CHARS:
        raise AiError(
            "invalid_request",
            "O pedido deve ter entre 1 e %d caracteres." % MESSAGE_MAX_CHARS,
            details={"field": "message"},
        )
    if has_control_chars(text):
        # Recusado AQUI, como erro do pedido (400). Sem esta checagem o NUL só
        # seria barrado pelo PostgreSQL, e a exceção do banco viraria um 500.
        raise AiError(
            "invalid_request",
            "O pedido contém caracteres de controle que não são aceitos.",
            details={"field": "message"},
        )
    return text


def _validate_input_refs(input_refs: Any) -> List[str]:
    if input_refs is None:
        return []
    if not isinstance(input_refs, (list, tuple)) or len(input_refs) > INPUT_REFS_MAX:
        raise AiError("invalid_request", "Referências de entrada inválidas.", details={"field": "input_refs"})
    result: List[str] = []
    for item in input_refs:
        match = _INPUT_REF.fullmatch(item) if isinstance(item, str) else None
        if match is None or match.group(1) not in INPUT_REF_KINDS:
            raise AiError("invalid_request", "Referência de entrada inválida.", details={"field": "input_refs"})
        if item not in result:
            result.append(item)
    return result


def _validate_idempotency_key(key: Any) -> Optional[str]:
    if key is None:
        return None
    if not isinstance(key, str) or _IDEMPOTENCY_KEY.fullmatch(key) is None:
        raise AiError(
            "invalid_request",
            "Idempotency-Key deve ter de 8 a 200 caracteres visíveis.",
            details={"field": "Idempotency-Key"},
        )
    return key


def _validate_system_input(task: str, payload: Any) -> Dict[str, Any]:
    """Entrada das tarefas criadas pelo servidor: só ids e versão.

    ``apply_proposal``: ``{proposal_id, expected_version}``.
    ``reverse_operation``: ``{operation_id, reason}`` (cria a compensação) ou
    ``{proposal_id, expected_version}`` (compensação já aprovada).
    """
    if not isinstance(payload, dict):
        raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})

    def proposal_form() -> Dict[str, Any]:
        proposal_id = _as_uuid(payload.get("proposal_id"))
        version = payload.get("expected_version")
        if proposal_id is None or isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})
        return {"proposal_id": proposal_id, "expected_version": version}

    if task == "apply_proposal":
        if set(payload) != {"proposal_id", "expected_version"}:
            raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})
        return proposal_form()

    if set(payload) == {"proposal_id", "expected_version"}:
        return proposal_form()
    if set(payload) != {"operation_id", "reason"}:
        raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})
    operation_id = _as_uuid(payload.get("operation_id"))
    reason = payload.get("reason")
    # Mesmos limites do schema de finance.reverse_change (3 a 500 caracteres).
    if operation_id is None or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
        raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})
    if has_control_chars(reason):
        raise AiError("invalid_request", "Entrada da tarefa inválida.", details={"field": "input"})
    return {"operation_id": operation_id, "reason": reason.strip()}


def request_hash(ctx: ExecutionContext, task: str, payload: Dict[str, Any]) -> str:
    """SHA-256 do pedido canônico.

    Entra tudo o que muda o significado do pedido (tarefa, espaço, privacidade,
    canal e conteúdo). Não entram ``request_id``/``trace_id`` (mudam a cada
    reenvio) nem a versão do contrato (um deploy entre dois reenvios não pode
    transformar um reenvio legítimo em conflito).
    """
    material = canonical_json(
        {
            "task": task,
            "financial_space_id": ctx.financial_space_id,
            "privacy": ctx.privacy.value,
            "channel": ctx.channel,
            "input": payload,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

def _stored_key(origin: str, key: Optional[str]) -> Optional[str]:
    """Valor gravado em ``ai_runs.idempotency_key``: ``origem:sha256(chave)``.

    Por que não gravar a chave como veio? O índice único é por (tenant, ator,
    chave). Se o titular enviasse ``Idempotency-Key: apply:<proposta>:1`` em um
    pedido comum, a tarefa que o servidor cria ao aprovar essa proposta — com a
    mesma chave — bateria na linha do titular e responderia ``conflict``: a
    aprovação não seria agendada. O prefixo de origem separa os dois espaços de
    nomes. O hash deixa o valor com tamanho fixo (o prefixo nunca estoura o
    limite de 200 caracteres da coluna) e evita guardar texto escolhido pelo
    cliente.
    """
    if key is None:
        return None
    return "%s:%s" % (origin, hashlib.sha256(key.encode("utf-8")).hexdigest())


def _find_by_idempotency_key(cursor, ctx: ExecutionContext, key: str) -> Optional[Dict[str, Any]]:
    # O filtro por ator é a regra: a chave só vale para quem a enviou. Outra
    # pessoa do mesmo tenant com a mesma chave cria a PRÓPRIA execução.
    cursor.execute(
        """
        SELECT id, status, trace_id, request_hash
        FROM ai_runs
        WHERE tenant_id = %s AND actor_user_id = %s AND idempotency_key = %s
        """,
        (ctx.tenant_id, ctx.actor_id, key),
    )
    return cursor.fetchone()


def _replay(existing: Dict[str, Any], wanted_hash: str) -> Dict[str, Any]:
    if existing["request_hash"] != wanted_hash:
        raise AiError("conflict", "Esta Idempotency-Key já foi usada com um pedido diferente.")
    return {
        "run_id": str(existing["id"]),
        "status": existing["status"],
        "trace_id": str(existing["trace_id"]),
        "created": False,
    }


def _insert_run(
    pool,
    ctx: ExecutionContext,
    *,
    task: str,
    payload: Dict[str, Any],
    idempotency_key: Optional[str],
    timeout_s: int,
    origin: str,
) -> Dict[str, Any]:
    key = _stored_key(origin, _validate_idempotency_key(idempotency_key))
    wanted_hash = request_hash(ctx, task, payload)
    run_id = str(uuid.uuid4())

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        if key is not None:
            existing = _find_by_idempotency_key(cursor, ctx, key)
            if existing is not None:
                return _replay(existing, wanted_hash)
        # ON CONFLICT cobre a corrida de dois POSTs simultâneos com a mesma
        # chave: o segundo espera o commit do primeiro e não insere nada.
        cursor.execute(
            """
            INSERT INTO ai_runs (
                id, tenant_id, financial_space_id, actor_user_id, request_id, trace_id,
                idempotency_key, request_hash, contract_version, policy_version, channel,
                locale, timezone, task, privacy, status, input, deadline_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s,
                now() + make_interval(secs => %s)
            )
            ON CONFLICT (tenant_id, actor_user_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL DO NOTHING
            RETURNING id
            """,
            (
                run_id, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, ctx.request_id, ctx.trace_id,
                key, wanted_hash, CONTRACT_VERSION, ctx.policy_version, ctx.channel,
                ctx.locale, ctx.timezone, task, ctx.privacy.value, jsonb(payload), int(timeout_s),
            ),
        )
        if cursor.fetchone() is None:
            existing = _find_by_idempotency_key(cursor, ctx, key) if key is not None else None
            if existing is None:
                raise AiError("conflict")
            return _replay(existing, wanted_hash)
        # Auditoria por referência: hash e ids, nunca o texto do pedido.
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.run.created",
            entity_type="ai_run",
            entity_id=run_id,
            metadata={
                "task": task,
                "financial_space_id": ctx.financial_space_id,
                "request_hash": wanted_hash,
                "input_refs": payload.get("input_refs", []),
                "privacy": ctx.privacy.value,
                "channel": ctx.channel,
                "idempotent": key is not None,
                "contract_version": CONTRACT_VERSION,
                "policy_version": ctx.policy_version,
                "trace_id": ctx.trace_id,
            },
        )
    logger.info("run_created run_id=%s task=%s channel=%s", run_id, task, ctx.channel)
    return {"run_id": run_id, "status": RunStatus.QUEUED.value, "trace_id": ctx.trace_id, "created": True}


def create_run(
    pool,
    ctx: ExecutionContext,
    *,
    task: str,
    message: str,
    input_refs: Optional[Sequence[str]] = None,
    idempotency_key: Optional[str] = None,
    settings: AiSettings,
) -> Dict[str, Any]:
    """Enfileira um pedido do titular. Devolve ``{run_id, status, trace_id, created}``."""
    if not settings.enabled:
        raise AiError("ai_disabled")
    if task not in USER_TASKS:
        # Inclui apply_proposal/reverse_operation: só o servidor cria essas.
        raise AiError("invalid_request", "Tarefa inválida.", details={"field": "task"})
    payload = {"message": _validate_message(message), "input_refs": _validate_input_refs(input_refs)}
    return _insert_run(
        pool, ctx, task=task, payload=payload, idempotency_key=idempotency_key,
        timeout_s=settings.run_timeout_s, origin=KEY_ORIGIN_USER,
    )


def create_system_run(
    pool,
    ctx: ExecutionContext,
    *,
    task: str,
    input: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    settings: AiSettings,
) -> Dict[str, Any]:
    """Enfileira uma tarefa criada pelo servidor (aprovação ou reversão)."""
    if not settings.enabled:
        raise AiError("ai_disabled")
    if task not in SYSTEM_TASKS:
        raise AiError("invalid_request", "Tarefa inválida.", details={"field": "task"})
    payload = _validate_system_input(task, input)
    return _insert_run(
        pool, ctx, task=task, payload=payload, idempotency_key=idempotency_key,
        timeout_s=max(settings.run_timeout_s, SYSTEM_RUN_TIMEOUT_S), origin=KEY_ORIGIN_SYSTEM,
    )


# ---------------------------------------------------------------------------
# Visão do titular (spec 4.2)
# ---------------------------------------------------------------------------

def _iso(value: Optional[datetime]) -> Optional[str]:
    return iso_utc(value) if value is not None else None


def step_label(name: str) -> str:
    return _STEP_LABELS.get(name, _STEP_LABELS[UNKNOWN_TOOL_NAME])


def _stage(status: str, steps: Sequence[Dict[str, Any]]) -> str:
    if status in _TERMINAL:
        return "done"
    if status == RunStatus.WAITING_REVIEW.value:
        return "waiting_review"
    if status == RunStatus.NEEDS_RECONCILIATION.value:
        # O efeito pode ou não ter sido aplicado: continua "aplicando" até
        # a conciliação confirmar.
        return "applying"
    for step in reversed(list(steps)):
        if step["kind"] == "tool":
            return _STAGE_BY_TOOL.get(step["name"], "reading")
    return "searching"


def _scope_view(cursor, ctx: ExecutionContext) -> Dict[str, Any]:
    cursor.execute(
        """
        SELECT a.id, a.name
        FROM financial_space_accounts l
        JOIN accounts a ON a.id = l.account_id AND a.tenant_id = l.tenant_id
        WHERE l.tenant_id = %s AND l.financial_space_id = %s AND a.archived_at IS NULL
        ORDER BY a.name, a.id
        """,
        (ctx.tenant_id, ctx.financial_space_id),
    )
    accounts = [{"id": str(row["id"]), "name": row["name"]} for row in cursor.fetchall()]
    return {
        "financial_space": {"id": ctx.financial_space_id, "name": ctx.space_name, "kind": ctx.space_kind},
        "accounts": accounts,
    }


def _list_of(result: Dict[str, Any], key: str) -> List[Any]:
    value = result.get(key)
    return list(value) if isinstance(value, list) else []


def _build_view(row: Dict[str, Any], steps: Sequence[Dict[str, Any]], scope: Dict[str, Any]) -> Dict[str, Any]:
    result = row["result"] if isinstance(row["result"], dict) else {}
    return {
        "run_id": str(row["id"]),
        "status": row["status"],
        "task": row["task"],
        "contract_version": row["contract_version"],
        "trace_id": str(row["trace_id"]),
        "created_at": _iso(row["created_at"]),
        "finished_at": _iso(row["finished_at"]),
        "cancel_requested": row["cancel_requested_at"] is not None,
        "scope": scope,
        "progress": {
            "stage": _stage(row["status"], steps),
            "steps": [
                {
                    "seq": step["seq"],
                    "kind": step["kind"],
                    "name": step["name"],
                    "label": step_label(step["name"]),
                    "status": step["status"],
                    "started_at": _iso(step["started_at"]),
                    "finished_at": _iso(step["finished_at"]),
                }
                for step in steps
            ],
        },
        # Enquanto não há resultado o resumo é vazio: nunca um texto inventado.
        "summary_pt_br": result.get("summary_pt_br") or "",
        "facts": _list_of(result, "facts"),
        "sources": _list_of(result, "sources"),
        "proposal_ids": _list_of(result, "proposal_ids"),
        "operation_ids": _list_of(result, "operation_ids"),
        "warnings": _list_of(result, "warnings"),
        "model": {
            "alias": row["model_alias"],
            "provider": row["model_provider"],
            "fallback_used": bool(row["fallback_used"]),
        },
        "error": row["error"] if isinstance(row["error"], dict) else None,
    }


_VIEW_COLUMNS = """
    id, status, task, contract_version, trace_id, created_at, finished_at, cancel_requested_at,
    result, error, model_alias, model_provider, fallback_used
"""


def _select_owned_run(cursor, ctx: ExecutionContext, run_id: str, for_update: bool = False) -> Dict[str, Any]:
    """Execução do próprio ator, no próprio tenant e espaço; senão ``not_found``.

    O filtro explícito por ator e espaço é a regra de negócio; RLS só garante o
    tenant. Recurso fora de escopo responde como inexistente (contrato, seção 12).
    """
    cursor.execute(
        "SELECT " + _VIEW_COLUMNS + " FROM ai_runs "
        "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s AND actor_user_id = %s"
        + (" FOR UPDATE" if for_update else ""),
        (run_id, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise AiError("not_found", "Execução não encontrada.")
    return row


def _view_in_tx(cursor, ctx: ExecutionContext, run_id: str) -> Dict[str, Any]:
    row = _select_owned_run(cursor, ctx, run_id)
    cursor.execute(
        """
        SELECT seq, kind, name, status, started_at, finished_at
        FROM ai_run_steps
        WHERE tenant_id = %s AND run_id = %s
        ORDER BY seq
        """,
        (ctx.tenant_id, run_id),
    )
    steps = cursor.fetchall()
    return _build_view(row, steps, _scope_view(cursor, ctx))


def run_space_id(pool, *, tenant_id: str, actor_id: str, run_id: str) -> str:
    """Espaço financeiro de uma execução do próprio ator.

    ``GET /runs/{id}`` e ``POST /runs/{id}/cancel`` não trazem o espaço na
    requisição. A rota usa este id só para ESCOLHER o espaço ao resolver o
    contexto (``scope.resolve_scope``), que continua conferindo o vínculo do
    usuário. Execução de outro ator ou de outro tenant responde ``not_found``.
    """
    parsed = _require_run_id(run_id)
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT financial_space_id FROM ai_runs WHERE id = %s AND tenant_id = %s AND actor_user_id = %s",
            (parsed, str(tenant_id), str(actor_id)),
        )
        row = cursor.fetchone()
    if row is None:
        raise AiError("not_found", "Execução não encontrada.")
    return str(row["financial_space_id"])


def get_run_view(pool, ctx: ExecutionContext, run_id: str) -> Dict[str, Any]:
    """Estado da execução no formato exato da seção 4.2 da spec."""
    run_id = _require_run_id(run_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        return _view_in_tx(cursor, ctx, run_id)


def _encode_cursor(created_at: datetime, run_id: str) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(run_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor_value: str) -> Dict[str, str]:
    invalid = AiError("invalid_request", "Cursor inválido.", details={"field": "cursor"})
    if not isinstance(cursor_value, str) or not 1 <= len(cursor_value) <= 400:
        raise invalid
    try:
        padded = cursor_value + "=" * (-len(cursor_value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["c"])
        run_id = _as_uuid(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error, UnicodeError):
        raise invalid
    if run_id is None or created_at.tzinfo is None:
        raise invalid
    return {"created_at": created_at.isoformat(), "id": run_id}


def list_runs(
    pool,
    ctx: ExecutionContext,
    *,
    cursor: Optional[str] = None,
    limit: int = LIST_DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Execuções recentes do ator no espaço. Devolve ``{items, next_cursor}``.

    O cursor é opaco para o cliente e só carrega a posição (instante e id); o
    escopo é sempre o do contexto autenticado, então um cursor copiado de outro
    usuário não revela nada.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= LIST_MAX_LIMIT:
        raise AiError("invalid_request", "Limite inválido.", details={"field": "limit"})
    params: List[Any] = [ctx.tenant_id, ctx.financial_space_id, ctx.actor_id]
    position = ""
    if cursor is not None:
        decoded = _decode_cursor(cursor)
        position = " AND (created_at, id) < (%s::timestamptz, %s::uuid)"
        params.extend([decoded["created_at"], decoded["id"]])
    params.append(limit + 1)

    with scoped_tx(pool, ctx.tenant_id) as db_cursor:
        db_cursor.execute(
            "SELECT id, status, task, trace_id, created_at, finished_at, cancel_requested_at, "
            "result ->> 'summary_pt_br' AS summary "
            "FROM ai_runs WHERE tenant_id = %s AND financial_space_id = %s AND actor_user_id = %s"
            + position
            + " ORDER BY created_at DESC, id DESC LIMIT %s",
            tuple(params),
        )
        rows = db_cursor.fetchall()

    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        next_cursor = _encode_cursor(page[-1]["created_at"], str(page[-1]["id"]))
    return {
        "items": [
            {
                "run_id": str(row["id"]),
                "status": row["status"],
                "task": row["task"],
                "trace_id": str(row["trace_id"]),
                "created_at": _iso(row["created_at"]),
                "finished_at": _iso(row["finished_at"]),
                "cancel_requested": row["cancel_requested_at"] is not None,
                "summary_pt_br": row["summary"] or "",
            }
            for row in page
        ],
        "next_cursor": next_cursor,
    }


def request_cancel(pool, ctx: ExecutionContext, run_id: str) -> Dict[str, Any]:
    """Solicita o cancelamento e devolve a visão atualizada.

    * em fila: vira ``cancelled`` na hora (nenhum worker chega a assumir);
    * em andamento: marca ``cancel_requested_at``; o orquestrador para antes da
      próxima ação. O que já foi confirmado permanece (e pode ser revertido);
    * estados finais, ``waiting_review`` e ``needs_reconciliation``: nada muda.
      Uma proposta pendente se resolve rejeitando a proposta, não a execução.
    """
    run_id = _require_run_id(run_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        row = _select_owned_run(cursor, ctx, run_id, for_update=True)
        previous = row["status"]
        if previous in (RunStatus.QUEUED.value, RunStatus.RUNNING.value):
            # O CASE usa o estado sob lock: se um worker assumiu a execução um
            # instante antes, ela fica "running" com o pedido registrado.
            cursor.execute(
                """
                UPDATE ai_runs
                SET cancel_requested_at = COALESCE(cancel_requested_at, now()),
                    status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                    finished_at = CASE WHEN status = 'queued' THEN now() ELSE finished_at END
                WHERE id = %s AND tenant_id = %s AND status IN ('queued', 'running')
                RETURNING status
                """,
                (run_id, ctx.tenant_id),
            )
            updated = cursor.fetchone()
            write_audit(
                cursor,
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.actor_id,
                event_type="ai.run.cancel_requested",
                entity_type="ai_run",
                entity_id=run_id,
                metadata={
                    "previous_status": previous,
                    "status": updated["status"] if updated else previous,
                    "trace_id": str(row["trace_id"]),
                },
            )
        return _view_in_tx(cursor, ctx, run_id)


# ---------------------------------------------------------------------------
# Fila com lease
# ---------------------------------------------------------------------------

def claim_next(pool, owner: str, lease_seconds: int) -> Optional[Dict[str, Any]]:
    """Assume a próxima execução pendente de qualquer tenant.

    Candidatas: ``queued`` ou ``running`` com lease vencido (worker anterior
    caiu). ``FOR UPDATE SKIP LOCKED`` faz dois workers simultâneos pegarem
    linhas diferentes em vez de esperarem um pelo outro; o ``UPDATE`` na mesma
    instrução garante que a escolha e a posse são atômicas.
    """
    if not owner:
        raise ValueError("owner é obrigatório")
    with queue_tx(pool) as cursor:
        cursor.execute(
            """
            WITH candidate AS (
                SELECT id FROM ai_runs
                WHERE status = 'queued'
                   OR (status = 'running' AND (lease_expires_at IS NULL OR lease_expires_at < now()))
                ORDER BY created_at, id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE ai_runs AS r
            SET status = 'running',
                lease_owner = %s,
                lease_expires_at = now() + make_interval(secs => %s),
                attempts = r.attempts + 1,
                started_at = COALESCE(r.started_at, now())
            FROM candidate
            WHERE r.id = candidate.id
            RETURNING r.id, r.tenant_id, r.task, r.attempts, r.trace_id
            """,
            (owner, int(lease_seconds)),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    claimed = {
        "run_id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "task": row["task"],
        "attempts": int(row["attempts"]),
        "trace_id": str(row["trace_id"]),
    }
    logger.info(
        "run_claimed run_id=%s owner=%s task=%s attempts=%d",
        claimed["run_id"], owner, claimed["task"], claimed["attempts"],
    )
    return claimed


def touch_lease(cursor, run_id: str, tenant_id: str, owner: str, lease_seconds: int) -> Dict[str, bool]:
    """Renova o lease na transação corrente e confirma a posse.

    É a cerca de todas as escritas do orquestrador: o ``UPDATE`` trava a linha
    da execução até o commit, então ninguém assume a execução no meio de uma
    gravação de etapa. Sem linha afetada, o worker perdeu a posse.
    """
    cursor.execute(
        """
        UPDATE ai_runs
        SET lease_expires_at = now() + make_interval(secs => %s)
        WHERE id = %s AND tenant_id = %s AND lease_owner = %s AND status = 'running'
        RETURNING cancel_requested_at IS NOT NULL AS cancel_requested,
                  (deadline_at IS NOT NULL AND deadline_at <= now()) AS deadline_passed
        """,
        (int(lease_seconds), str(run_id), str(tenant_id), owner),
    )
    row = cursor.fetchone()
    if row is None:
        raise LeaseLost("run %s não pertence mais a %s" % (run_id, owner))
    return {"cancel_requested": bool(row["cancel_requested"]), "deadline_passed": bool(row["deadline_passed"])}


def heartbeat(
    pool,
    run_id: str,
    tenant_id: str,
    owner: str,
    lease_seconds: int,
    *,
    grace_seconds: Optional[int] = None,
) -> Optional[Dict[str, bool]]:
    """Renova o lease fora de uma etapa (ex.: inferência longa).

    Devolve ``None`` se a posse foi perdida; senão o estado
    ``{renewed, overdue, cancel_requested, deadline_passed}``.

    ``grace_seconds`` é o limite da renovação em segundo plano. Depois que o
    prazo da execução venceu, ou que o titular pediu o cancelamento, há mais de
    ``grace_seconds``, o lease NÃO é renovado (``overdue``). Motivo: quem
    aplica prazo e cancelamento é o orquestrador, entre uma ação e outra. Se
    uma ferramenta ou o modelo nunca retornam, não existe "próxima ação"; uma
    renovação incondicional manteria a execução ``running`` para sempre, sem
    prazo e sem cancelamento (contrato, seção 8: trabalho longo tem prazo
    explícito e não se renova indefinidamente). Sem a renovação o lease vence
    e outro worker assume e encerra a execução.

    Com ``grace_seconds=None`` a renovação é incondicional.
    """
    with scoped_tx(pool, tenant_id) as cursor:
        # Decisão e renovação na MESMA instrução: não há janela entre "ler o
        # prazo" e "renovar".
        cursor.execute(
            """
            WITH state AS (
                SELECT id,
                       cancel_requested_at IS NOT NULL AS cancel_requested,
                       (deadline_at IS NOT NULL AND deadline_at <= now()) AS deadline_passed,
                       (
                           %s::int IS NOT NULL AND (
                               (deadline_at IS NOT NULL
                                AND deadline_at + make_interval(secs => %s::int) <= now())
                               OR (cancel_requested_at IS NOT NULL
                                   AND cancel_requested_at + make_interval(secs => %s::int) <= now())
                           )
                       ) AS overdue
                FROM ai_runs
                WHERE id = %s AND tenant_id = %s AND lease_owner = %s AND status = 'running'
                FOR UPDATE
            )
            UPDATE ai_runs AS r
            SET lease_expires_at = CASE
                    WHEN state.overdue THEN r.lease_expires_at
                    ELSE now() + make_interval(secs => %s)
                END
            FROM state
            WHERE r.id = state.id
            RETURNING state.cancel_requested, state.deadline_passed, state.overdue
            """,
            (
                grace_seconds, grace_seconds, grace_seconds,
                str(run_id), str(tenant_id), owner, int(lease_seconds),
            ),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    overdue = bool(row["overdue"])
    return {
        "renewed": not overdue,
        "overdue": overdue,
        "cancel_requested": bool(row["cancel_requested"]),
        "deadline_passed": bool(row["deadline_passed"]),
    }


def load_for_execution(pool, tenant_id: str, run_id: str, owner: str) -> Optional[Dict[str, Any]]:
    """Linha completa da execução, se ``owner`` ainda for o dono do lease."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            SELECT id, tenant_id, financial_space_id, actor_user_id, request_id, trace_id,
                   contract_version, policy_version, channel, locale, timezone, task, privacy,
                   status, input, attempts, deadline_at, created_at
            FROM ai_runs
            WHERE id = %s AND tenant_id = %s AND lease_owner = %s AND status = 'running'
            """,
            (str(run_id), str(tenant_id), owner),
        )
        row = cursor.fetchone()
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Checkpoints de etapa
# ---------------------------------------------------------------------------

_STEP_COLUMNS = "id, seq, step_key, kind, name, status, output, error_code, attempts"


def _step_dict(row: Dict[str, Any], state: str) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "seq": int(row["seq"]),
        "step_key": row["step_key"],
        "kind": row["kind"],
        "name": row["name"],
        # new | succeeded | failed | interrupted
        "state": state,
        "output": row["output"],
        "error_code": row["error_code"],
        "attempts": int(row["attempts"]),
    }


def begin_step(
    pool,
    run_id: str,
    tenant_id: str,
    owner: str,
    *,
    step_key: str,
    kind: str,
    name: str,
    version: Optional[str] = None,
    args_hash: Optional[str] = None,
    lease_seconds: int,
) -> Dict[str, Any]:
    """Abre (ou reencontra) a etapa identificada por ``step_key``.

    ``state`` no retorno:

    * ``new``: etapa criada agora, em ``started``;
    * ``succeeded`` / ``failed``: etapa já concluída em uma tentativa anterior;
      ``output`` traz o checkpoint para reuso — nada é executado de novo;
    * ``interrupted``: havia uma linha ``started`` sem conclusão, ou seja, o
      worker anterior caiu no meio. O chamador decide como recuperar.
    """
    if kind not in ("inference", "tool"):
        raise ValueError("kind inválido")
    with scoped_tx(pool, tenant_id) as cursor:
        # A cerca também serializa a numeração de ``seq`` (lock na execução).
        touch_lease(cursor, run_id, tenant_id, owner, lease_seconds)
        cursor.execute(
            "SELECT " + _STEP_COLUMNS + " FROM ai_run_steps "
            "WHERE tenant_id = %s AND run_id = %s AND step_key = %s FOR UPDATE",
            (str(tenant_id), str(run_id), step_key),
        )
        row = cursor.fetchone()
        if row is not None:
            state = "interrupted" if row["status"] == "started" else row["status"]
            return _step_dict(row, state)
        cursor.execute(
            "INSERT INTO ai_run_steps (tenant_id, run_id, seq, step_key, kind, name, version, status, args_hash) "
            "SELECT %s::uuid, %s::uuid, COALESCE(max(seq), 0) + 1, %s::text, %s::text, %s::text, "
            "%s::text, 'started', %s::text "
            "FROM ai_run_steps WHERE tenant_id = %s AND run_id = %s "
            "RETURNING " + _STEP_COLUMNS,
            (
                str(tenant_id), str(run_id), step_key, kind, name, version, args_hash,
                str(tenant_id), str(run_id),
            ),
        )
        return _step_dict(cursor.fetchone(), "new")


def restart_step(pool, run_id: str, tenant_id: str, owner: str, step_id: str, *, lease_seconds: int) -> None:
    """Reabre uma etapa interrompida ou falha para nova tentativa (conta em ``attempts``)."""
    with scoped_tx(pool, tenant_id) as cursor:
        touch_lease(cursor, run_id, tenant_id, owner, lease_seconds)
        cursor.execute(
            """
            UPDATE ai_run_steps
            SET status = 'started', attempts = attempts + 1, started_at = now(),
                finished_at = NULL, output = NULL, error_code = NULL, duration_ms = NULL
            WHERE id = %s AND tenant_id = %s AND run_id = %s AND status <> 'succeeded'
            """,
            (str(step_id), str(tenant_id), str(run_id)),
        )


def finish_step(
    pool,
    run_id: str,
    tenant_id: str,
    owner: str,
    step_id: str,
    *,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    duration_ms: Optional[int] = None,
    cost_micros: int = 0,
    lease_seconds: int,
) -> None:
    """Conclui a etapa com o checkpoint (``output`` em JSON, sem float)."""
    if status not in ("succeeded", "failed"):
        raise ValueError("status de etapa inválido")
    with scoped_tx(pool, tenant_id) as cursor:
        touch_lease(cursor, run_id, tenant_id, owner, lease_seconds)
        cursor.execute(
            """
            UPDATE ai_run_steps
            SET status = %s, output = %s, error_code = %s, duration_ms = %s,
                cost_micros = %s, finished_at = now()
            WHERE id = %s AND tenant_id = %s AND run_id = %s AND status = 'started'
            """,
            (
                status,
                # ``storable``: última barreira. Conteúdo vindo de e-mail, PDF
                # ou modelo pode trazer NUL, que o jsonb recusa; a etapa ficaria
                # "started" para sempre e a execução cairia com erro interno.
                jsonb(storable(output)) if output is not None else None,
                storable(error_code) if error_code is not None else None,
                max(0, int(duration_ms)) if duration_ms is not None else None,
                max(0, int(cost_micros or 0)),
                str(step_id), str(tenant_id), str(run_id),
            ),
        )


# ---------------------------------------------------------------------------
# Encerramento
# ---------------------------------------------------------------------------

def finish_run(
    pool,
    run_id: str,
    tenant_id: str,
    owner: str,
    *,
    status: str,
    result: Optional[Dict[str, Any]],
    error: Optional[Dict[str, Any]],
    model: Optional[Dict[str, Any]] = None,
    inference_calls: int = 0,
    tool_calls: int = 0,
    cost_micros: int = 0,
    cost_currency: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    audit: Optional[Dict[str, Any]] = None,
) -> str:
    """Grava o estado final, solta o lease e audita, tudo em uma transação.

    Cercado pelo dono do lease: se outro worker assumiu, levanta ``LeaseLost``
    e nada é gravado. ``finished_at`` só é preenchido em estado final de fato;
    ``waiting_review`` e ``needs_reconciliation`` ainda têm continuação.

    Devolve o estado efetivamente gravado. Ele só difere do pedido em um caso:
    foi pedido ``waiting_review``, mas a revisão já terminou (ver
    ``_review_already_settled``); então a execução é gravada como ``completed``.
    """
    allowed = (
        RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value,
        RunStatus.WAITING_REVIEW.value, RunStatus.NEEDS_RECONCILIATION.value,
    )
    if status not in allowed:
        raise ValueError("estado final inválido")
    model = storable(model or {})
    result = storable(result) if result is not None else None
    error = storable(error) if error is not None else None
    audit = storable(audit) if audit is not None else None
    with scoped_tx(pool, tenant_id) as cursor:
        if status == RunStatus.WAITING_REVIEW.value:
            cursor.execute(
                "SELECT financial_space_id FROM ai_runs "
                "WHERE id = %s AND tenant_id = %s AND lease_owner = %s AND status = 'running'",
                (str(run_id), str(tenant_id), owner),
            )
            row = cursor.fetchone()
            if row is None:
                raise LeaseLost("run %s não pertence mais a %s" % (run_id, owner))
            proposal_ids = _list_of(result or {}, "proposal_ids")
            if _review_already_settled(cursor, tenant_id, str(row["financial_space_id"]), proposal_ids):
                status = RunStatus.COMPLETED.value
                if audit is not None:
                    audit = dict(audit, status=status, review_settled_at_finish=True)
                logger.info("run_review_settled_at_finish run_id=%s", run_id)
        cursor.execute(
            """
            UPDATE ai_runs
            SET status = %s, result = %s, error = %s,
                model_alias = %s, model_provider = %s, model_id = %s, fallback_used = %s,
                inference_calls = %s, tool_calls = %s, cost_micros = %s, cost_currency = %s,
                lease_owner = NULL, lease_expires_at = NULL,
                finished_at = CASE WHEN %s THEN now() ELSE NULL END
            WHERE id = %s AND tenant_id = %s AND lease_owner = %s AND status = 'running'
            """,
            (
                status,
                jsonb(result) if result is not None else None,
                jsonb(error) if error is not None else None,
                model.get("alias"), model.get("provider"), model.get("model_id"),
                bool(model.get("fallback_used")),
                max(0, int(inference_calls)), max(0, int(tool_calls)), max(0, int(cost_micros)),
                cost_currency,
                status in _TERMINAL,
                str(run_id), str(tenant_id), owner,
            ),
        )
        if cursor.rowcount != 1:
            raise LeaseLost("run %s não pertence mais a %s" % (run_id, owner))
        if audit is not None:
            write_audit(
                cursor,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                event_type="ai.run.finished",
                entity_type="ai_run",
                entity_id=run_id,
                metadata=audit,
            )
    return status


def _review_already_settled(cursor, tenant_id: str, financial_space_id: str, proposal_ids: Sequence[Any]) -> bool:
    """A revisão desta execução já terminou? Decide COM as propostas travadas.

    O problema que isto resolve: o orquestrador conclui "aguardando revisão"
    olhando as propostas e só depois grava o estado. Nesse intervalo o titular
    pode aprovar e outro worker aplicar a proposta. ``settle_waiting_review``
    procura execuções em ``waiting_review``, não acha esta (ainda está
    ``running``) e segue; logo depois ela seria gravada como ``waiting_review``
    e ficaria presa para sempre, com a proposta já aplicada.

    Por que ``FOR SHARE``? Uma leitura simples só encurtaria a janela. O lock
    compartilhado na linha da proposta conflita com qualquer ``UPDATE`` dela e
    obriga uma ordem entre as duas transações:

    * quem muda a proposta chegou primeiro -> esta leitura ESPERA o commit
      dele, enxerga o estado novo e a execução é gravada como ``completed``;
    * esta transação chegou primeiro -> a mudança da proposta espera o nosso
      commit; o ``settle_waiting_review`` que vem depois dela já encontra a
      execução em ``waiting_review`` e a fecha.

    As propostas são travadas ANTES da linha da execução, a mesma ordem de
    quem rejeita uma proposta e fecha a execução na mesma transação; ordens
    opostas poderiam terminar em deadlock.

    Só responde ``True`` com prova no banco: todas as propostas existem e
    nenhuma está viva. Proposta que o banco não conhece, ou execução que
    aguarda revisão sem proposta, continua aguardando.
    """
    ids = sorted({item for item in (_as_uuid(value) for value in proposal_ids) if item})
    if not ids:
        return False
    cursor.execute(
        "SELECT id, status FROM ai_proposals "
        "WHERE tenant_id = %s AND financial_space_id = %s AND id = ANY(%s::uuid[]) "
        "ORDER BY id FOR SHARE",
        (str(tenant_id), str(financial_space_id), ids),
    )
    rows = cursor.fetchall()
    if len(rows) != len(ids):
        return False
    return all(row["status"] not in _LIVE_PROPOSAL_STATUSES for row in rows)


def settle_waiting_review(cursor, tenant_id: str, proposal_id: str) -> List[str]:
    """Fecha execuções em ``waiting_review`` cuja revisão terminou.

    Chamado (na transação do chamador) depois que uma proposta é aplicada ou
    rejeitada. Uma execução só vira ``completed`` quando NENHUMA das propostas
    que ela produziu continua viva. Devolve os ids das execuções fechadas.
    """
    proposal = _as_uuid(proposal_id)
    if proposal is None:
        return []
    cursor.execute(
        """
        SELECT id, result FROM ai_runs
        WHERE tenant_id = %s AND status = 'waiting_review'
          AND result -> 'proposal_ids' @> %s::jsonb
        ORDER BY created_at, id
        FOR UPDATE
        """,
        (str(tenant_id), json.dumps([proposal])),
    )
    closed: List[str] = []
    for row in cursor.fetchall():
        result = row["result"] if isinstance(row["result"], dict) else {}
        ids = [item for item in (_as_uuid(value) for value in _list_of(result, "proposal_ids")) if item]
        cursor.execute(
            "SELECT count(*) AS total FROM ai_proposals "
            "WHERE tenant_id = %s AND id = ANY(%s::uuid[]) AND status = ANY(%s)",
            (str(tenant_id), ids, list(_LIVE_PROPOSAL_STATUSES)),
        )
        if cursor.fetchone()["total"] > 0:
            continue
        cursor.execute(
            "UPDATE ai_runs SET status = 'completed', finished_at = now() "
            "WHERE id = %s AND tenant_id = %s AND status = 'waiting_review'",
            (row["id"], str(tenant_id)),
        )
        closed.append(str(row["id"]))
    return closed
