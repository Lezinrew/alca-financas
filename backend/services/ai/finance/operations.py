"""Operações financeiras idempotentes (``finance.apply_change``).

``apply_proposal`` é o ÚNICO ponto da plataforma de IA que altera dados
financeiros. Tudo acontece em UMA transação do banco:

    lock da proposta -> autorização -> revalidação do grant (com lock)
    -> conferência de expiração e dos alvos -> linha em ``ai_operations``
    -> efeito financeiro -> auditoria -> outbox -> proposta ``applied``

Ou tudo é confirmado junto, ou nada é. Não existe "efeito aplicado sem
auditoria" nem "operação registrada sem efeito".

Por que não há efeito duplicado (AC-03 e AC-04)
-----------------------------------------------
1. ``SELECT ... FOR UPDATE`` na proposta: dois workers com a mesma proposta
   entram em fila; o segundo já a encontra ``applied`` e devolve o resultado
   do primeiro.
2. Índice único ``(tenant_id, operation_key)`` em ``ai_operations``: mesmo que
   duas propostas diferentes descrevam a mesma ação, só uma vira operação.
3. O id da operação é determinístico (UUIDv5 da chave). Quem sofreu timeout
   depois do commit consulta ``operation_status`` com esse id e descobre que o
   efeito já existe, em vez de repetir a escrita.

Histórico nunca é apagado: reverter é uma nova operação que marca o pagamento
como revertido ou cancela os lançamentos importados.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from .. import CONTRACT_VERSION, policy
from ..db import enqueue_outbox, jsonb, scoped_tx, write_audit
from ..errors import AiError
from ..settings import AiSettings
from ..types import ExecutionContext, canonical_json, iso_utc, money_str
from . import proposals, repository
from .proposals import KIND_IMPORT, KIND_PAYMENT, KIND_REVERSAL, operation_id_for


logger = logging.getLogger("ai.finance")

APPLIED_EVENT = "ai.operation.applied"
OUTBOX_TOPIC = "ai.operation.applied"

__all__ = [
    "apply_proposal",
    "operation_status",
    "get_operation_view",
    "operation_id_for",
    "outbox_dedup_key",
]

_OPERATION_COLUMNS = """
    id, tenant_id, financial_space_id, proposal_id, run_id, actor_user_id, grant_id, kind,
    operation_key, payload_hash, status, effect, reverses_operation_id, reversed_by_operation_id,
    applied_at, reversed_at
"""


def outbox_dedup_key(operation_id: str) -> str:
    """Chave de deduplicação da notificação de uma operação aplicada."""
    return "operation:%s:applied" % operation_id


# ---------------------------------------------------------------------------
# Autorização do efeito.
# ---------------------------------------------------------------------------
def _effect_requests(payload: Dict[str, Any]) -> List[policy.EffectRequest]:
    """Traduz o bloco ``authorization`` da proposta em pedidos de efeito.

    Um pedido por combinação de origem e data: o grant precisa cobrir TODAS as
    origens das evidências e, numa importação, a menor e a maior data.
    """
    authorization = payload["authorization"]
    amount = Decimal(authorization["amount"]) if authorization.get("amount") else None
    dates = [date.fromisoformat(item) for item in authorization.get("dates") or []] or [None]
    sources = list(authorization.get("source_kinds") or []) or [None]
    return [
        policy.EffectRequest(
            capability=authorization["capability"],
            amount=amount,
            account_ids=tuple(authorization.get("account_ids") or ()),
            source_kind=source,
            effect_date=effect_date,
        )
        for source in sources
        for effect_date in dates
    ]


def _identifies_accounts(grant: policy.Grant, effects: List[policy.EffectRequest]) -> bool:
    """Grant restrito a contas só cobre efeito que diz EM QUE conta acontece.

    ``policy.grant_violation`` recusa conta fora da lista, mas um efeito sem
    conta nenhuma (baixa "registrado pago", que não aponta para transação, ou a
    reversão dela) passa por essa checagem: não há conta "fora". O titular que
    limitou a autonomia a uma conta não autorizou baixas automáticas em
    qualquer conta a pagar do espaço. Sem conta identificada, o grant restrito
    não cobre, e a proposta vai para a aprovação específica.
    """
    if grant.account_ids is None:
        return True
    return all(effect.account_ids for effect in effects)


def _delegated_grant(grants: List[policy.Grant], effects: List[policy.EffectRequest]) -> Optional[policy.Grant]:
    """Grant delegado que cobre integralmente TODOS os pedidos de efeito."""
    for grant in grants:
        if not _identifies_accounts(grant, effects):
            continue
        if all(policy.delegated_grant_for([grant], effect) is not None for effect in effects):
            return grant
    return None


# ---------------------------------------------------------------------------
# Leitura de operações.
# ---------------------------------------------------------------------------
def _load_operation(cursor, ctx: ExecutionContext, *, operation_id: Optional[str] = None,
                    operation_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Operação do espaço, por id ou por chave. ``None`` fora do escopo."""
    column, value = ("id", operation_id) if operation_id is not None else ("operation_key", operation_key)
    cursor.execute(
        "SELECT " + _OPERATION_COLUMNS + " FROM ai_operations "
        "WHERE " + column + " = %s AND tenant_id = %s AND financial_space_id = %s",
        (str(value), ctx.tenant_id, ctx.financial_space_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _applied_result(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Resultado durável de uma aplicação. É montado SEMPRE a partir da linha
    gravada, para a primeira chamada e as repetições devolverem o mesmo dado."""
    return {
        "status": "applied",
        "operation_id": str(operation["id"]),
        "proposal_id": str(operation["proposal_id"]),
        "kind": operation["kind"],
        # "applied" ou "reversed": a operação pode ter sido revertida depois.
        "operation_status": operation["status"],
        "effect": operation["effect"],
        "applied_at": iso_utc(operation["applied_at"]),
    }


def _waiting(row: Dict[str, Any], reason: str, operation_id: str) -> Dict[str, Any]:
    return {
        "status": "waiting_review",
        "proposal_id": str(row["id"]),
        "reason": reason,
        "planned_operation_id": operation_id,
    }


# ---------------------------------------------------------------------------
# Efeitos. Cada um recebe as linhas já travadas por ``load_targets(lock=True)``.
# ---------------------------------------------------------------------------
def _apply_payment(cursor, ctx: ExecutionContext, payload: Dict[str, Any], rows: Dict[str, Any]) -> Dict[str, Any]:
    payable = rows["payable"]
    amount = Decimal(payload["amount"])
    # O saldo é recalculado AQUI, com a linha de ``payables`` travada: o banco
    # não tem constraint que limite a soma dos pagamentos ao valor previsto.
    if payable is None or payable["canceled_at"] is not None:
        raise AiError("ambiguous_evidence", "A conta a pagar não está disponível para baixa.")
    if amount > payable["remaining"]:
        raise AiError("ambiguous_evidence", "O valor é maior que o saldo restante da conta. Nada foi aplicado.")
    transaction = rows.get("transaction")
    if payload.get("transaction_id") and (transaction is None or not proposals.transaction_eligible(transaction)):
        raise AiError("ambiguous_evidence", "A transação do extrato não está mais disponível para conciliar.")

    before = proposals.payable_state(payable)
    payment_id = repository.insert_payable_payment(
        cursor,
        ctx,
        payable_id=payload["payable_id"],
        amount=amount,
        paid_on=date.fromisoformat(payload["paid_on"]),
        transaction_id=payload.get("transaction_id"),
        payment_method=payload.get("payment_method"),
        notes=payload.get("notes"),
    )
    new_paid = payable["paid"] + amount
    after = {
        "paid": money_str(new_paid),
        "remaining": money_str(repository.remaining_amount(payable["amount_expected"], new_paid)),
        "status": repository.derive_payable_status(payable["amount_expected"], new_paid, False),
    }
    return {
        "effect": {
            "kind": KIND_PAYMENT,
            "payable_id": payload["payable_id"],
            "payment_id": payment_id,
            "amount": money_str(amount),
            "currency": payload.get("currency"),
            "paid_on": payload["paid_on"],
            "transaction_id": payload.get("transaction_id"),
            "state_after": payload["state_after"],
            "before": before,
            "after": after,
            "authorization": payload["authorization"],
        },
        "before_ref": {
            "payable_id": payload["payable_id"],
            "status": before["status"],
            "payment_count": payable["payment_count"],
        },
        "after_ref": {"payable_id": payload["payable_id"], "status": after["status"], "payment_id": payment_id},
    }


def _apply_import(
    cursor, ctx: ExecutionContext, payload: Dict[str, Any], rows: Dict[str, Any], row: Dict[str, Any], operation_id: str
) -> Dict[str, Any]:
    if rows["account"] is None:
        raise AiError("not_found", "Conta não encontrada neste espaço.")
    source_file = payload["filename"]
    if not repository.is_canonical_source_file(source_file):
        # Defesa em profundidade: sem o sufixo .ofx os lançamentos ficariam
        # fora do realizado, e a importação pareceria ter "sumido".
        raise AiError("invalid_request", "Somente extrato OFX pode ser importado.")
    items = payload["items"]
    batch_id = repository.insert_import_batch(
        cursor,
        ctx,
        account_id=payload["account_id"],
        filename=source_file,
        total_parsed=len(items) + int(payload.get("transfers_skipped") or 0),
        metadata={
            "operation_id": operation_id,
            "proposal_id": str(row["id"]),
            "artifact_id": payload["artifact_id"],
            "artifact_sha256": payload["artifact_sha256"],
            "source_kind": payload["source_kind"],
        },
    )
    categories = {}  # type: Dict[str, str]
    imported, duplicates = 0, 0
    totals = {"income": Decimal("0"), "expense": Decimal("0")}
    for item in items:
        tx_type = item["type"]
        if tx_type not in categories:
            categories[tx_type] = repository.ensure_unclassified_category(cursor, ctx, tx_type)
        amount = Decimal(item["amount"])
        inserted = repository.insert_import_transaction(
            cursor,
            ctx,
            account_id=payload["account_id"],
            category_id=categories[tx_type],
            import_batch_id=batch_id,
            description=item["description"],
            amount=amount,
            tx_type=tx_type,
            occurred_on=date.fromisoformat(item["occurred_on"]),
            fitid=item.get("fitid"),
            dedup_key=item["dedup_key"],
            source_file=source_file,
        )
        if inserted:
            imported += 1
            totals[tx_type] += amount
        else:
            duplicates += 1
    transfers = int(payload.get("transfers_skipped") or 0)
    repository.complete_import_batch(
        cursor,
        ctx,
        batch_id,
        imported=imported,
        duplicates=duplicates,
        ignored=transfers,
        total_income=totals["income"],
        total_expense=totals["expense"],
        # Transferências não são gravadas; o total delas fica só na proposta.
        total_transfer=Decimal("0"),
    )
    return {
        "effect": {
            "kind": KIND_IMPORT,
            "import_batch_id": batch_id,
            "account_id": payload["account_id"],
            "source_file": source_file,
            "items_new": imported,
            "items_duplicate": duplicates,
            "items_transfer_skipped": transfers,
            "totals": {
                "income": money_str(totals["income"]),
                "expense": money_str(totals["expense"]),
                "net": money_str(totals["income"] - totals["expense"]),
            },
            "state_after": proposals.STATE_IMPORTED,
            "authorization": payload["authorization"],
        },
        "before_ref": {"account_id": payload["account_id"]},
        "after_ref": {"import_batch_id": batch_id, "items_new": imported, "items_duplicate": duplicates},
    }


def _apply_reversal(
    cursor, ctx: ExecutionContext, payload: Dict[str, Any], rows: Dict[str, Any], operation_id: str
) -> Dict[str, Any]:
    original = rows.get("operation")
    if original is None or original["status"] != "applied":
        raise AiError("stale_proposal")
    original_effect = original["effect"] or {}
    effect = {
        "kind": KIND_REVERSAL,
        "reverses_operation_id": str(original["id"]),
        "original_kind": original["kind"],
        "reason": payload["reason"],
        "state_after": proposals.STATE_REVERSED,
        "authorization": payload["authorization"],
    }  # type: Dict[str, Any]
    if original["kind"] == KIND_PAYMENT:
        payable, payment = rows.get("payable"), rows.get("payment")
        if payable is None or payment is None:
            raise AiError("stale_proposal")
        changed = repository.reverse_payable_payment(
            cursor, ctx, original_effect["payment_id"], original_effect["payable_id"], payload["reason"]
        )
        if changed != 1:
            raise AiError("stale_proposal")
        new_paid = payable["paid"] - payment["amount"]
        after = {
            "paid": money_str(new_paid),
            "remaining": money_str(repository.remaining_amount(payable["amount_expected"], new_paid)),
            "status": repository.derive_payable_status(
                payable["amount_expected"], new_paid, payable["canceled_at"] is not None
            ),
        }
        effect.update(
            {
                "payable_id": original_effect["payable_id"],
                "payment_id": original_effect["payment_id"],
                "amount": money_str(payment["amount"]),
                "currency": payable["currency"],
                "before": proposals.payable_state(payable),
                "after": after,
            }
        )
        after_ref = {"payment_id": original_effect["payment_id"], "payable_status": after["status"]}
    else:
        batch = rows.get("batch")
        if batch is None:
            raise AiError("stale_proposal")
        if batch["linked_transactions"]:
            raise AiError(
                "conflict", "Há pagamentos conciliados com lançamentos deste extrato. Reverta esses pagamentos antes."
            )
        canceled = repository.cancel_batch_transactions(cursor, ctx, original_effect["import_batch_id"])
        if canceled != batch["active_transactions"]:
            # Segunda barreira (a primeira é o lock das transações do lote em
            # ``fetch_import_batch``): o cancelamento pula lançamento com
            # pagamento ativo. Se sobrou algum, a reversão inteira é desfeita;
            # reverter "pela metade" deixaria o lote num estado sem nome.
            raise AiError(
                "conflict", "Há pagamentos conciliados com lançamentos deste extrato. Reverta esses pagamentos antes."
            )
        repository.rollback_import_batch(cursor, ctx, original_effect["import_batch_id"])
        effect.update(
            {
                "import_batch_id": original_effect["import_batch_id"],
                "account_id": original_effect.get("account_id"),
                "items_canceled": canceled,
            }
        )
        after_ref = {"import_batch_id": original_effect["import_batch_id"], "items_canceled": canceled}

    # A original vira "reversed" apontando para ESTA operação. O filtro por
    # status impede marcar duas vezes; o índice único de reversão é a barreira
    # final no banco.
    cursor.execute(
        """
        UPDATE ai_operations
        SET status = 'reversed', reversed_at = now(), reversed_by_operation_id = %s
        WHERE id = %s AND tenant_id = %s AND financial_space_id = %s AND status = 'applied'
        """,
        (operation_id, str(original["id"]), ctx.tenant_id, ctx.financial_space_id),
    )
    if cursor.rowcount != 1:
        raise AiError("stale_proposal")
    return {
        "effect": effect,
        "before_ref": {"operation_id": str(original["id"]), "status": "applied"},
        "after_ref": dict(after_ref, operation_id=str(original["id"]), status="reversed"),
    }


# ---------------------------------------------------------------------------
# apply_proposal
# ---------------------------------------------------------------------------
def _mark_applied(cursor, ctx: ExecutionContext, row: Dict[str, Any], approval: Dict[str, Any]) -> None:
    cursor.execute(
        """
        UPDATE ai_proposals
        SET status = 'applied', approval_kind = %s, approved_by_user_id = %s, approved_grant_id = %s,
            approved_grant_version = %s, approved_hash = payload_hash,
            approved_at = COALESCE(approved_at, now())
        WHERE id = %s AND tenant_id = %s
        """,
        (
            approval["kind"], approval.get("user_id"), approval.get("grant_id"), approval.get("grant_version"),
            str(row["id"]), ctx.tenant_id,
        ),
    )


def _apply_locked(
    cursor, ctx: ExecutionContext, proposal_id: str, expected_version: int
) -> Union[Dict[str, Any], AiError]:
    """Corpo de ``apply_proposal`` dentro da transação.

    Devolve o resultado, ou um ``AiError`` quando é preciso CONFIRMAR uma
    mudança de estado (``expired``/``stale``) antes de avisar o chamador:
    levantar a exceção aqui dentro desfaria essa mudança junto com o resto.
    Qualquer outro erro é levantado normalmente e desfaz tudo.
    """
    # (a) Lock da proposta: aplicações concorrentes da mesma proposta enfileiram.
    row = proposals.lock_proposal(cursor, ctx, proposal_id)
    kind, payload = row["kind"], row["payload"]
    operation_id = operation_id_for(ctx.tenant_id, row["operation_key"])

    # (b) Já aplicada: devolve o resultado anterior, sem novo efeito.
    if row["status"] == "applied":
        operation = _load_operation(cursor, ctx, operation_key=row["operation_key"])
        if operation is None:
            raise AiError("internal_error")
        return _applied_result(operation)

    if int(row["version"]) != int(expected_version):
        raise AiError("stale_proposal", "A versão informada não é a versão atual da proposta.")
    if row["status"] == "draft":
        raise AiError("ambiguous_evidence", "A proposta tem pendências que impedem a aplicação. Gere uma nova prévia.")
    if row["status"] in ("expired", "stale"):
        raise AiError("stale_proposal")
    if row["status"] not in ("ready", "approved"):
        raise AiError("conflict", "A proposta foi rejeitada.")
    if row["is_expired"]:
        proposals.set_status(cursor, ctx, row, "expired")
        return AiError("stale_proposal", "A proposta expirou. Gere uma nova prévia.")

    # (c) Autorização. Sem grant com a capacidade, ou só em modo observe,
    # nada é aplicado. Ausência de grant nunca é permissão.
    capability = proposals.capability_for(kind)
    grants = policy.load_active_grants(cursor, ctx)
    policy.authorize(grants, capability)
    effects = _effect_requests(payload)

    if row["status"] == "ready":
        if row["requires_review"]:
            # Ambiguidade, comprovante sozinho ou baixa sem lastro em extrato:
            # nenhum grant aplica isso, nem ilimitado. Só a aprovação
            # específica do titular.
            return _waiting(row, "requires_review", operation_id)
        delegated = _delegated_grant(grants, effects)
        if delegated is None:
            return _waiting(row, "needs_specific_approval", operation_id)
        approval = {
            "kind": "grant",
            "grant_id": delegated.id,
            "grant_version": delegated.version,
            "user_id": None,
        }  # type: Dict[str, Any]
    else:
        approval = {
            "kind": row["approval_kind"],
            "grant_id": str(row["approved_grant_id"]) if row["approved_grant_id"] else None,
            "grant_version": row["approved_grant_version"],
            "user_id": str(row["approved_by_user_id"]) if row["approved_by_user_id"] else None,
        }
        if approval["kind"] == "grant" and row["requires_review"]:
            return _waiting(row, "requires_review", operation_id)

    # (d) Revalidação do grant DENTRO desta transação, com lock de linha. Se o
    # grant foi revogado ou alterado depois da aprovação, o efeito é negado.
    # O lock faz uma revogação concorrente esperar o fim desta transação: não
    # sobra janela em que o efeito é gravado depois de a revogação valer.
    locked = None  # type: Optional[policy.Grant]
    for effect_request in effects:
        if approval["kind"] == "grant":
            grant = policy.lock_grant_for_effect(
                cursor, ctx, effect_request, grant_id=approval["grant_id"], grant_version=approval["grant_version"]
            )
        else:
            grant = policy.lock_grant_for_effect(cursor, ctx, effect_request)
        locked = locked or grant
    if approval["kind"] == "grant" and locked is not None and not _identifies_accounts(locked, effects):
        # Mesma regra de ``_delegated_grant``, agora sobre o grant travado:
        # vale também para proposta que já chegou aprovada por grant.
        raise AiError("capability_denied", "Efeito fora da autorização: a conta do efeito não está identificada.")

    # (e) Alvos: relê (travando as linhas) e compara com o retrato da prévia.
    targets, rows = proposals.load_targets(cursor, ctx, kind, payload, lock=True)
    if canonical_json(targets) != canonical_json(row["target_versions"]):
        proposals.set_status(cursor, ctx, row, "stale")
        return AiError("stale_proposal")

    # (f) Linha da operação ANTES do efeito: o índice único é a barreira final
    # contra duplicidade entre propostas diferentes da mesma ação.
    cursor.execute(
        """
        INSERT INTO ai_operations (
            id, tenant_id, financial_space_id, proposal_id, run_id, actor_user_id, grant_id, kind,
            operation_key, payload_hash, status, effect, reverses_operation_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied', %s, %s)
        ON CONFLICT (tenant_id, operation_key) DO NOTHING
        """,
        (
            operation_id, ctx.tenant_id, ctx.financial_space_id, str(row["id"]), ctx.run_id, ctx.actor_id,
            locked.id if locked else None, kind, row["operation_key"], row["payload_hash"], jsonb({}),
            payload["operation_id"] if kind == KIND_REVERSAL else None,
        ),
    )
    if cursor.rowcount == 0:
        existing = _load_operation(cursor, ctx, operation_key=row["operation_key"])
        if existing is None or existing["payload_hash"] != row["payload_hash"]:
            # Mesma chave, conteúdo diferente: não é reenvio, é outro pedido.
            raise AiError("conflict", "Esta ação já foi aplicada com outros dados.")
        _mark_applied(cursor, ctx, row, approval)
        return _applied_result(existing)

    # (g) Efeito financeiro.
    if kind == KIND_PAYMENT:
        outcome = _apply_payment(cursor, ctx, payload, rows)
    elif kind == KIND_IMPORT:
        outcome = _apply_import(cursor, ctx, payload, rows, row, operation_id)
    else:
        outcome = _apply_reversal(cursor, ctx, payload, rows, operation_id)
    cursor.execute(
        "UPDATE ai_operations SET effect = %s WHERE id = %s AND tenant_id = %s",
        (jsonb(outcome["effect"]), operation_id, ctx.tenant_id),
    )

    # (h) Auditoria e outbox na mesma transação do efeito. A auditoria leva
    # referências (ids, hashes, versões, estados); os valores ficam em
    # ``ai_operations.effect``, alcançável pelo ``operation_id``.
    write_audit(
        cursor,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.actor_id,
        event_type=APPLIED_EVENT,
        entity_type="ai_operation",
        entity_id=operation_id,
        metadata={
            "financial_space_id": ctx.financial_space_id,
            "operation_id": operation_id,
            "proposal_id": str(row["id"]),
            "kind": kind,
            "operation_key": row["operation_key"],
            "payload_hash": row["payload_hash"],
            "proposal_version": row["version"],
            "approval_kind": approval["kind"],
            "approved_by_user_id": approval.get("user_id"),
            "grant_id": locked.id if locked else None,
            "grant_version": locked.version if locked else None,
            "grant_mode": locked.mode if locked else None,
            "policy_version": locked.policy_version if locked else ctx.policy_version,
            "contract_version": CONTRACT_VERSION,
            "channel": ctx.channel,
            "run_id": ctx.run_id,
            "trace_id": ctx.trace_id,
            "before": outcome["before_ref"],
            "after": outcome["after_ref"],
        },
    )
    enqueue_outbox(
        cursor,
        tenant_id=ctx.tenant_id,
        topic=OUTBOX_TOPIC,
        dedup_key=outbox_dedup_key(operation_id),
        payload={
            "operation_id": operation_id,
            "proposal_id": str(row["id"]),
            "kind": kind,
            "financial_space_id": ctx.financial_space_id,
            "state_after": outcome["effect"].get("state_after"),
        },
        operation_id=operation_id,
        run_id=ctx.run_id,
    )

    # (i) Proposta aplicada.
    _mark_applied(cursor, ctx, row, approval)
    operation = _load_operation(cursor, ctx, operation_id=operation_id)
    if operation is None:
        raise AiError("internal_error")
    return _applied_result(operation)


@repository.guarded("operations.apply_proposal")
def apply_proposal(
    pool, ctx: ExecutionContext, proposal_id: Any, *, expected_version: int, settings: AiSettings
) -> Dict[str, Any]:
    """Aplica uma proposta. Devolve ``applied`` ou ``waiting_review``.

    ``waiting_review`` não é erro: significa que a proposta precisa da
    aprovação específica do titular (não há grant delegado que cubra o efeito,
    ou a proposta exige revisão). Nenhum dado é alterado nesse caso.
    """
    # A flag de escrita é conferida aqui também, não só no registro de
    # ferramentas: a rota de aprovação chama esta função sem passar por ele.
    if not settings.write_enabled:
        raise AiError("capability_denied", "A escrita financeira pela IA está desativada.")
    proposal_uuid = proposals.as_uuid(proposal_id, "proposal_id")
    try:
        version = int(expected_version)
    except (TypeError, ValueError):
        raise AiError("invalid_request", "Versão inválida.", details={"field": "expected_version"})

    started = time.monotonic()
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        # Sem isto, a restrição de contas de um grant é lida errado (ver o
        # comentário em ``repository``) e a decisão abaixo sai trocada.
        repository.read_uuid_arrays_as_lists(cursor)
        outcome = _apply_locked(cursor, ctx, proposal_uuid, version)
    duration_ms = int((time.monotonic() - started) * 1000)
    if isinstance(outcome, AiError):
        logger.info(
            "apply_refused proposal_id=%s code=%s duration_ms=%d", proposal_uuid, outcome.code, duration_ms
        )
        raise outcome
    logger.info(
        "apply_done proposal_id=%s status=%s operation_id=%s duration_ms=%d",
        proposal_uuid, outcome["status"], outcome.get("operation_id"), duration_ms,
    )
    return outcome


# ---------------------------------------------------------------------------
# Consulta de estado e rastreio.
# ---------------------------------------------------------------------------
def _operation_uuid(operation_id: Any) -> str:
    try:
        return str(uuid.UUID(str(operation_id)))
    except (ValueError, AttributeError, TypeError):
        # Id malformado e id de outro escopo recebem a mesma resposta.
        raise AiError("operation_unknown")


def _status_dict(operation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "operation_id": str(operation["id"]),
        "status": operation["status"],  # applied | reversed
        "kind": operation["kind"],
        "proposal_id": str(operation["proposal_id"]),
        "effect": operation["effect"],
        "applied_at": iso_utc(operation["applied_at"]),
        "reversed_at": iso_utc(operation["reversed_at"]) if operation["reversed_at"] else None,
        "reverses_operation_id": (
            str(operation["reverses_operation_id"]) if operation["reverses_operation_id"] else None
        ),
        "reversed_by_operation_id": (
            str(operation["reversed_by_operation_id"]) if operation["reversed_by_operation_id"] else None
        ),
    }


@repository.guarded("operations.operation_status")
def operation_status(pool, ctx: ExecutionContext, operation_id: Any) -> Dict[str, Any]:
    """Estado durável de uma operação: ``applied``, ``reversed`` ou ``not_applied``.

    ``not_applied`` responde a quem pergunta, depois de um timeout, por um id
    PLANEJADO (o da prévia) cuja operação não chegou a ser gravada: é seguro
    tentar de novo. Id que não pertence a este espaço: ``operation_unknown``.
    """
    operation_uuid = _operation_uuid(operation_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        operation = _load_operation(cursor, ctx, operation_id=operation_uuid)
        if operation is not None:
            return _status_dict(operation)
        cursor.execute(
            """
            SELECT id, status, kind FROM ai_proposals
            WHERE tenant_id = %s AND financial_space_id = %s
              AND expected_effect->>'planned_operation_id' = %s
            ORDER BY created_at DESC, id
            LIMIT 1
            """,
            (ctx.tenant_id, ctx.financial_space_id, operation_uuid),
        )
        planned = cursor.fetchone()
    if planned is None:
        raise AiError("operation_unknown")
    return {
        "operation_id": operation_uuid,
        "status": "not_applied",
        "kind": planned["kind"],
        "proposal_id": str(planned["id"]),
        "proposal_status": planned["status"],
        "effect": None,
        "applied_at": None,
        "reversed_at": None,
        "reverses_operation_id": None,
        "reversed_by_operation_id": None,
    }


def _operation_summary(operation: Dict[str, Any]) -> str:
    effect = operation["effect"] or {}
    currency = effect.get("currency") or "BRL"
    if operation["kind"] == KIND_PAYMENT:
        text = "Pagamento de %s registrado (%s)." % (
            proposals.format_money(effect.get("amount", "0"), currency),
            proposals.STATE_TEXT.get(effect.get("state_after"), ""),
        )
    elif operation["kind"] == KIND_IMPORT:
        text = "Extrato importado: %d lançamento(s) novo(s), %d duplicado(s) ignorado(s)." % (
            effect.get("items_new", 0), effect.get("items_duplicate", 0)
        )
    else:
        text = "Reversão aplicada sobre a operação %s." % effect.get("reverses_operation_id")
    if operation["status"] == "reversed":
        text += " Esta operação foi revertida depois."
    return text


@repository.guarded("operations.get_operation_view")
def get_operation_view(pool, ctx: ExecutionContext, operation_id: Any) -> Dict[str, Any]:
    """Operação para a tela de rastreio (``GET /operations/{id}``)."""
    operation_uuid = _operation_uuid(operation_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        operation = _load_operation(cursor, ctx, operation_id=operation_uuid)
    if operation is None:
        raise AiError("operation_unknown")
    view = _status_dict(operation)
    view.update(
        {
            "summary_pt_br": _operation_summary(operation),
            "actor_user_id": str(operation["actor_user_id"]),
            "grant_id": str(operation["grant_id"]) if operation["grant_id"] else None,
            "run_id": str(operation["run_id"]) if operation["run_id"] else None,
            "scope": {
                "financial_space": {"id": ctx.financial_space_id, "name": ctx.space_name, "kind": ctx.space_kind}
            },
            "state": (operation["effect"] or {}).get("state_after"),
        }
    )
    return view
