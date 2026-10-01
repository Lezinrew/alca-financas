"""Propostas de alteração financeira (``finance.prepare_change``).

Uma proposta descreve UMA ação (baixar uma conta, importar um extrato,
reverter uma operação), o efeito esperado e as dúvidas encontradas. Ela não
muda nenhum dado financeiro: o efeito só acontece em
``finance.operations.apply_proposal``.

Ciclo de vida: ``draft -> ready -> approved -> applied`` ou
``rejected/expired/stale``.

* ``draft``: há ambiguidade IMPEDITIVA (valor ou data ausentes, conta
  cancelada, pagamento maior que o saldo, vínculo incerto). Não pode ser
  aprovada nem aplicada; é preciso corrigir e gerar outra prévia.
* ``ready``: pode ser aplicada por aprovação específica do titular ou, se
  ``requires_review`` for falso, por um grant delegado que cubra o efeito.

Três identificadores, todos calculados só pelo backend:

* ``operation_key``: SHA-256 de escopo + fonte + tipo + identidade estável da
  ação. A mesma ação gera a mesma chave, logo a mesma proposta viva (índice
  único parcial) e, depois, a mesma operação.
* ``payload_hash``: SHA-256 do payload canônico. É o que a aprovação
  específica assina: mudar qualquer campo do payload invalida a aprovação.
* ``target_versions``: retrato dos alvos (conta a pagar, transação, lote) no
  momento da prévia. Se mudar até a aplicação, a proposta vira ``stale``.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import policy
from ..db import jsonb, scoped_tx, write_audit
from ..errors import AiError
from ..imports_types import ImportPreview
from ..settings import AiSettings
from ..types import ExecutionContext, canonical_json, iso_utc, money_str, to_decimal, utc_now
from . import repository


logger = logging.getLogger("ai.finance")

KIND_PAYMENT = "payable_payment"
KIND_IMPORT = "statement_import"
KIND_REVERSAL = "reverse_operation"

LIVE_STATUSES = ("draft", "ready", "approved")

# Estados exibidos ao titular. São distintos de propósito (contrato, seção 12):
# "registrado pago" é um lançamento sem lastro no extrato; "conciliado" está
# amarrado a uma transação vinda de OFX.
STATE_REGISTERED = "registrado_pago"
STATE_RECONCILED = "conciliado"
STATE_IMPORTED = "importado"
STATE_REVERSED = "revertido"

EVIDENCE_KINDS = ("ofx_transaction", "receipt", "email", "manual")
MAX_EVIDENCE_ITEMS = 10
MAX_IMPORT_ITEMS = 5000
MAX_REAPPLY_ATTEMPTS = 20

# Referência de evidência é um identificador (artifact:<uuid>, email:<id>...),
# não texto livre: sem espaços nem quebras, para ninguém embutir conteúdo nela.
_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/@+=-]{0,199}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CENT = Decimal("0.01")
_MAX_AMOUNT = Decimal("999999999999999.99")

# Namespace fixo do UUIDv5 das operações. Derivado de um nome estável em vez de
# um literal hexadecimal solto no código.
OPERATION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "operations.ai.alca-financas")

_COLUMNS = """
    id, tenant_id, financial_space_id, created_by_user_id, run_id, kind, status, version,
    payload, payload_hash, target_versions, expected_effect, evidence, ambiguities, requires_review,
    operation_key, approval_kind, approved_by_user_id, approved_grant_id, approved_grant_version,
    approved_hash, approved_at, rejected_reason, expires_at, created_at,
    (expires_at <= now()) AS is_expired
"""


# ---------------------------------------------------------------------------
# Identificadores determinísticos.
# ---------------------------------------------------------------------------
def operation_key_for(
    ctx: ExecutionContext, *, kind: str, source: Sequence[str], identity: Dict[str, Any], attempt: int = 0
) -> str:
    """Chave de operação: escopo + fonte + tipo + identidade estável da ação.

    Nada aqui vem do modelo sem validação e nada depende de horário ou de id
    de requisição: reenviar o mesmo pedido produz a mesma chave.
    """
    material = canonical_json(
        {
            "v": 1,
            "tenant_id": ctx.tenant_id,
            "financial_space_id": ctx.financial_space_id,
            "source": sorted(source),
            "kind": kind,
            "identity": identity,
            "attempt": int(attempt),
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def payload_hash_for(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def operation_id_for(tenant_id: str, operation_key: str) -> str:
    """Id determinístico da operação (UUIDv5 da chave).

    Por ser calculável ANTES do efeito, o executor que sofreu timeout consegue
    perguntar "essa operação existe?" sem depender da resposta que se perdeu.
    """
    return str(uuid.uuid5(OPERATION_NAMESPACE, "%s:%s" % (tenant_id, operation_key)))


def capability_for(kind: str) -> str:
    """Capacidade que o grant precisa ter para o EFEITO deste tipo de proposta."""
    return "finance.reverse_change" if kind == KIND_REVERSAL else "finance.apply_change"


# ---------------------------------------------------------------------------
# Validação de entrada.
# ---------------------------------------------------------------------------
def as_uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("invalid_request", "Identificador inválido em %s." % field, details={"field": field})


def parse_amount(value: Any, field: str = "amount") -> Optional[Decimal]:
    """Valor monetário positivo com até duas casas, ou ``None`` se ausente.

    ``float`` é recusado: 0.1 + 0.2 em binário não é 0.30. Mais de duas casas
    também é recusado em vez de arredondado, para o valor gravado ser
    exatamente o que foi informado.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    invalid = AiError("invalid_request", "Valor monetário inválido em %s." % field, details={"field": field})
    if isinstance(value, (bool, float)):
        raise invalid
    try:
        amount = to_decimal(value)
    except ValueError:
        raise invalid
    if not amount.is_finite() or amount <= 0 or amount > _MAX_AMOUNT:
        raise invalid
    if amount != amount.quantize(_CENT):
        raise invalid
    return amount.quantize(_CENT)


def parse_local_date(value: Any, field: str) -> Optional[date]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise AiError("invalid_request", "Data inválida em %s." % field, details={"field": field})


# Caracteres que não podem chegar ao banco dentro de um texto: controles C0
# (inclui NUL, que o PostgreSQL recusa em ``text`` e ``jsonb``), DEL e
# substitutos UTF-16 soltos (não têm representação em UTF-8). ``str.split()``
# já troca tabulação e quebra de linha por espaço; o que sobra aqui é lixo.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f\ud800-\udfff]")
# Subconjunto que o banco realmente não grava (NUL e substitutos soltos). É o
# critério dos campos de identidade, que não podem ser alterados nem recusados
# só por serem "feios".
_UNSTORABLE_CHARS = re.compile(r"[\x00\ud800-\udfff]")


def _clean_text(value: Any, field: str, limit: int) -> Optional[str]:
    """Texto curto vindo dos argumentos (forma de pagamento, anotação, motivo).

    Caractere de controle é ``invalid_request``, não é removido em silêncio: se
    deixássemos passar, o INSERT falharia no banco e o erro sairia como 500
    "retentável", fazendo o executor repetir um pedido que nunca vai passar.
    """
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if _CONTROL_CHARS.search(text):
        raise AiError("invalid_request", "Texto com caracteres inválidos em %s." % field, details={"field": field})
    if len(text) > limit:
        raise AiError("invalid_request", "Texto longo demais em %s." % field, details={"field": field})
    return text


def _plain_text(value: Any, limit: int) -> str:
    """Texto de conteúdo NÃO confiável (extrato, prévia) sem caracteres de controle.

    Diferente de ``_clean_text``: aqui o texto é cosmético (descrição de um
    lançamento, nome do banco) e vem de um arquivo, não do pedido. Um byte
    estranho no memo do banco não deve derrubar a importação inteira; ele é
    trocado por espaço.
    """
    return " ".join(_CONTROL_CHARS.sub(" ", str(value or "")).split())[:limit]


def _required_reason(value: Any, field: str = "reason") -> str:
    text = _clean_text(value, field, 500)
    if not text:
        raise AiError("invalid_request", "Informe o motivo.", details={"field": field})
    return text


def _normalize_evidence(evidence: Any) -> List[Dict[str, str]]:
    if evidence is None:
        return []
    if not isinstance(evidence, (list, tuple)) or len(evidence) > MAX_EVIDENCE_ITEMS:
        raise AiError("invalid_request", "Lista de evidências inválida.", details={"field": "evidence"})
    unique = set()
    for item in evidence:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            raise AiError("invalid_request", "Evidência inválida.", details={"field": "evidence"})
        kind = str(item.get("kind") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if kind not in EVIDENCE_KINDS or not _REF_PATTERN.match(ref):
            raise AiError("invalid_request", "Evidência inválida.", details={"field": "evidence"})
        unique.add((kind, ref))
    # Ordenar torna o payload (e o hash) independente da ordem recebida.
    return [{"kind": kind, "ref": ref} for kind, ref in sorted(unique)]


def _ttl_hours(settings: Optional[AiSettings]) -> int:
    return int((settings or AiSettings.from_env()).proposal_ttl_hours)


# ---------------------------------------------------------------------------
# Texto para o titular (pt-BR). Sempre a partir de números do banco.
# ---------------------------------------------------------------------------
def format_money(value: Any, currency: str = "BRL") -> str:
    quantized = to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
    integer, _, cents = str(abs(quantized)).partition(".")
    groups = []  # type: List[str]
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    symbol = "R$" if currency == "BRL" else currency
    return "%s%s %s,%s" % ("-" if quantized < 0 else "", symbol, ".".join(groups), cents)


def _format_date(value: Optional[str]) -> str:
    if not value:
        return "data não informada"
    return date.fromisoformat(value).strftime("%d/%m/%Y")


_STATUS_TEXT = {"pending": "pendente", "partial": "parcial", "paid": "quitada", "canceled": "cancelada"}
STATE_TEXT = {
    STATE_REGISTERED: "registrado pago (sem vínculo com o extrato)",
    STATE_RECONCILED: "conciliado no extrato",
    STATE_IMPORTED: "importado",
    STATE_REVERSED: "revertido",
}


def _summary(kind: str, payload: Dict[str, Any], effect: Dict[str, Any], ambiguities: List[Dict[str, Any]]) -> str:
    target = effect.get("target") or {}
    currency = payload.get("currency") or target.get("currency") or "BRL"
    parts = []  # type: List[str]
    if kind == KIND_PAYMENT:
        amount = format_money(payload["amount"], currency) if payload.get("amount") else "valor não informado"
        parts.append(
            'Registrar pagamento de %s em "%s" em %s.'
            % (amount, target.get("title", ""), _format_date(payload.get("paid_on")))
        )
        before, after = effect.get("before"), effect.get("after")
        if before and after:
            parts.append(
                "Pago passa de %s para %s; resta %s (%s)."
                % (
                    format_money(before["paid"], currency),
                    format_money(after["paid"], currency),
                    format_money(after["remaining"], currency),
                    _STATUS_TEXT[after["status"]],
                )
            )
        elif before:
            parts.append(
                "Hoje: pago %s, resta %s (%s). O efeito não pôde ser calculado."
                % (
                    format_money(before["paid"], currency),
                    format_money(before["remaining"], currency),
                    _STATUS_TEXT[before["status"]],
                )
            )
        parts.append("Estado após aplicar: %s." % STATE_TEXT[effect["state_after"]])
    elif kind == KIND_IMPORT:
        totals = effect.get("totals") or {}
        parts.append(
            'Importar %d lançamento(s) do extrato "%s": receitas %s, despesas %s.'
            % (
                effect.get("items_new", 0),
                target.get("filename", ""),
                format_money(totals.get("income", "0"), currency),
                format_money(totals.get("expense", "0"), currency),
            )
        )
        if effect.get("items_duplicate"):
            parts.append("%d já existente(s) será(ão) ignorado(s)." % effect["items_duplicate"])
        # "Já existente" não é "já no realizado": o titular precisa saber
        # quando o duplicado ignorado está cancelado ou veio de outra origem.
        if effect.get("items_duplicate_canceled"):
            parts.append(
                "Atenção: %d desse(s) existe(m) como CANCELADO(S) e continua(m) fora do realizado."
                % effect["items_duplicate_canceled"]
            )
        if effect.get("items_duplicate_outside_realized"):
            parts.append(
                "Atenção: %d desse(s) existe(m) com outra origem ou situação e continua(m) fora do realizado."
                % effect["items_duplicate_outside_realized"]
            )
        if effect.get("items_transfer_skipped"):
            parts.append("%d transferência(s) não será(ão) importada(s)." % effect["items_transfer_skipped"])
    else:
        original = target.get("original_kind")
        if original == KIND_PAYMENT:
            parts.append(
                'Reverter o pagamento de %s em "%s".'
                % (format_money(target.get("amount", "0"), currency), target.get("title", ""))
            )
            before, after = effect.get("before"), effect.get("after")
            if before and after:
                parts.append(
                    "Pago volta de %s para %s; resta %s (%s)."
                    % (
                        format_money(before["paid"], currency),
                        format_money(after["paid"], currency),
                        format_money(after["remaining"], currency),
                        _STATUS_TEXT[after["status"]],
                    )
                )
        else:
            parts.append(
                'Reverter a importação do extrato "%s": %d lançamento(s) serão cancelados.'
                % (target.get("filename", ""), effect.get("items_new", 0))
            )
        parts.append("O histórico é preservado; nada é apagado.")
    if ambiguities:
        parts.append("Pontos a revisar: %d." % len(ambiguities))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Leitura e visão.
# ---------------------------------------------------------------------------
def _fetch(cursor, ctx: ExecutionContext, proposal_id: str, *, lock: bool = False) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT " + _COLUMNS + " FROM ai_proposals "
        "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s" + (" FOR UPDATE" if lock else ""),
        (str(proposal_id), ctx.tenant_id, ctx.financial_space_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def lock_proposal(cursor, ctx: ExecutionContext, proposal_id: str) -> Dict[str, Any]:
    """Trava a proposta até o fim da transação. Fora do escopo: ``not_found``."""
    row = _fetch(cursor, ctx, proposal_id, lock=True)
    if row is None:
        raise AiError("not_found", "Proposta não encontrada.")
    return row


def set_status(cursor, ctx: ExecutionContext, row: Dict[str, Any], status: str, actor_id: Optional[str] = None) -> None:
    """Transições sem aprovação (``expired``, ``stale``), com auditoria."""
    cursor.execute(
        "UPDATE ai_proposals SET status = %s WHERE id = %s AND tenant_id = %s",
        (status, str(row["id"]), ctx.tenant_id),
    )
    write_audit(
        cursor,
        tenant_id=ctx.tenant_id,
        actor_user_id=actor_id,
        event_type="ai.proposal.%s" % status,
        entity_type="ai_proposal",
        entity_id=str(row["id"]),
        metadata={
            "financial_space_id": str(row["financial_space_id"]),
            "kind": row["kind"],
            "payload_hash": row["payload_hash"],
            "version": row["version"],
            "trace_id": ctx.trace_id,
        },
    )


def _origin(kind: str, payload: Dict[str, Any], effect: Dict[str, Any]) -> Dict[str, Any]:
    authorization = payload.get("authorization") or {}
    sources = authorization.get("source_kinds") or ["manual"]
    target = effect.get("target") or {}
    if kind == KIND_PAYMENT:
        label, start, end = target.get("title"), payload.get("paid_on"), payload.get("paid_on")
    elif kind == KIND_IMPORT:
        period = target.get("period") or {}
        label, start, end = target.get("filename"), period.get("start"), period.get("end")
    else:
        label, start, end = "Reversão da operação %s" % payload.get("operation_id"), None, None
    return {
        "source_kind": sources[0],
        "source_kinds": list(sources),
        "label": label,
        "period": {"start": start, "end": end},
    }


def build_view(cursor, ctx: ExecutionContext, row: Dict[str, Any]) -> Dict[str, Any]:
    """Proposta no formato de ``GET /proposals/{id}`` (spec, seção 4.3)."""
    payload = row["payload"]
    effect = dict(row["expected_effect"])
    planned_operation_id = effect.pop("planned_operation_id", None)
    status = row["status"]
    if status in LIVE_STATUSES and row["is_expired"]:
        # Ainda não passou o ``expire_due``, mas para o titular já expirou.
        status = "expired"

    operation_id = None
    if row["status"] == "applied":
        cursor.execute(
            "SELECT id FROM ai_operations WHERE tenant_id = %s AND financial_space_id = %s AND operation_key = %s",
            (ctx.tenant_id, ctx.financial_space_id, row["operation_key"]),
        )
        found = cursor.fetchone()
        operation_id = str(found["id"]) if found else None

    account_ids = (payload.get("authorization") or {}).get("account_ids") or []
    accounts = repository.space_accounts(cursor, ctx, account_ids) if account_ids else []
    ambiguities = list(row["ambiguities"] or [])
    return {
        "proposal_id": str(row["id"]),
        "kind": row["kind"],
        "status": status,
        "version": int(row["version"]),
        "payload_hash": row["payload_hash"],
        "requires_review": bool(row["requires_review"]),
        "expires_at": iso_utc(row["expires_at"]),
        "created_at": iso_utc(row["created_at"]),
        "summary_pt_br": _summary(row["kind"], payload, effect, ambiguities),
        "origin": _origin(row["kind"], payload, effect),
        "scope": {
            "financial_space": {"id": ctx.financial_space_id, "name": ctx.space_name, "kind": ctx.space_kind},
            "accounts": [{"id": str(account["id"]), "name": account["name"]} for account in accounts],
        },
        "effect": effect,
        "ambiguities": ambiguities,
        "evidence": list(row["evidence"] or []),
        "operation_id": operation_id,
        # Id que a operação TERÁ se for aplicada. Serve para consultar
        # ``finance.operation_status`` depois de um timeout de escrita.
        "planned_operation_id": planned_operation_id,
        "run_id": str(row["run_id"]) if row["run_id"] else None,
    }


@repository.guarded("proposals.get_proposal_view")
def get_proposal_view(pool, ctx: ExecutionContext, proposal_id: str) -> Dict[str, Any]:
    proposal_uuid = as_uuid(proposal_id, "proposal_id")
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        row = _fetch(cursor, ctx, proposal_uuid)
        if row is None:
            # Proposta de outro espaço ou tenant responde como inexistente.
            raise AiError("not_found", "Proposta não encontrada.")
        return build_view(cursor, ctx, row)


# ---------------------------------------------------------------------------
# Gravação com idempotência.
# ---------------------------------------------------------------------------
def _ambiguity(code: str, message: str, blocking: bool, **extra: Any) -> Dict[str, Any]:
    item = {"code": code, "message": message, "blocking": bool(blocking)}
    item.update(extra)
    return item


_SELECT_LIVE = (
    "SELECT " + _COLUMNS + " FROM ai_proposals "
    "WHERE tenant_id = %s AND financial_space_id = %s AND operation_key = %s "
    "AND status IN ('draft', 'ready', 'approved')"
)


def _same_request(kind: str, stored: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """O pedido de agora é o MESMO que gerou a proposta/operação que já existe?

    Só é chamada quando a chave de operação coincide, isto é, quando a
    identidade da ação já é igual. O que pode divergir é o resto do payload:

    * reversão: o motivo é anotação; reverter a operação X é uma ação só;
    * baixa: comparam-se apenas os campos LIVRES do pedido (forma de pagamento
      e anotação). O restante do payload ou faz parte da identidade (conta a
      pagar, valor, data, transação, anexos) ou é DERIVADO do banco e muda
      depois que a própria ação é aplicada: a transação conciliada passa a
      estar "vinculada" e deixaria de parecer elegível. Comparar o hash inteiro
      faria o reenvio de uma baixa já aplicada responder "conflito" em vez de
      devolver o resultado anterior;
    * importação: o payload inteiro (ele sai só do arquivo, não do banco).
    """
    if kind == KIND_REVERSAL:
        return True
    if kind == KIND_PAYMENT:
        return (stored.get("payment_method"), stored.get("notes")) == (
            payload.get("payment_method"), payload.get("notes")
        )
    return payload_hash_for(stored) == payload_hash_for(payload)


def _store(
    cursor,
    ctx: ExecutionContext,
    *,
    kind: str,
    payload: Dict[str, Any],
    operation_key: str,
    target_versions: Dict[str, Any],
    expected_effect: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    ambiguities: List[Dict[str, Any]],
    run_id: Optional[str],
    ttl_hours: int,
) -> Dict[str, Any]:
    """Grava a proposta ou devolve a proposta viva da MESMA ação.

    * mesma chave, mesmo pedido, alvos iguais -> devolve a existente;
    * proposta viva vencida -> marca ``expired`` e cria outra;
    * alvos mudaram -> marca ``stale`` e cria outra (os números mostrados
      antes já não valem);
    * mesma chave com pedido diferente (ver ``_same_request``) -> ``conflict``:
      o titular rejeita a anterior antes de propor a variação.
    """
    payload_hash = payload_hash_for(payload)
    cursor.execute(_SELECT_LIVE + " FOR UPDATE", (ctx.tenant_id, ctx.financial_space_id, operation_key))
    live = cursor.fetchone()
    if live is not None:
        live = dict(live)
        if live["is_expired"]:
            set_status(cursor, ctx, live, "expired")
        elif canonical_json(live["target_versions"]) != canonical_json(target_versions):
            set_status(cursor, ctx, live, "stale")
        elif not _same_request(kind, live["payload"], payload):
            raise AiError("conflict", "Já existe uma proposta ativa para esta ação com outros dados. Rejeite-a antes.")
        else:
            return live

    # A consulta acima pode ter ESPERADO a aplicação concorrente desta mesma
    # ação terminar (ela segura o lock da proposta). Nesse caso a proposta dela
    # já saiu do conjunto "vivo" e a operação agora existe: devolvemos a
    # proposta aplicada em vez de abrir uma segunda proposta para o mesmo efeito.
    operation = _existing_operation(cursor, ctx, operation_key)
    if operation is not None:
        if operation["status"] == "reversed":
            raise AiError("conflict", "Esta ação já foi aplicada e revertida. Gere uma nova prévia.")
        return _applied_row(cursor, ctx, operation, kind, payload)

    blocking = any(item.get("blocking") for item in ambiguities)
    status = "draft" if blocking else "ready"
    # Regra única: qualquer ambiguidade, impeditiva ou não, exige revisão humana.
    requires_review = bool(ambiguities)
    expected_effect = dict(expected_effect)
    expected_effect["planned_operation_id"] = operation_id_for(ctx.tenant_id, operation_key)
    cursor.execute(
        """
        INSERT INTO ai_proposals (
            tenant_id, financial_space_id, created_by_user_id, run_id, kind, status, payload, payload_hash,
            target_versions, expected_effect, evidence, ambiguities, requires_review, operation_key, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(hours => %s))
        ON CONFLICT (tenant_id, operation_key) WHERE status IN ('draft', 'ready', 'approved') DO NOTHING
        RETURNING """ + _COLUMNS,
        (
            ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, run_id or ctx.run_id, kind, status,
            jsonb(payload), payload_hash, jsonb(target_versions), jsonb(expected_effect),
            jsonb(evidence), jsonb(ambiguities), requires_review, operation_key, int(ttl_hours),
        ),
    )
    row = cursor.fetchone()
    if row is None:
        # Corrida: outra transação gravou a mesma ação entre o SELECT e o
        # INSERT. O índice único parcial segurou; devolvemos a dela.
        cursor.execute(_SELECT_LIVE, (ctx.tenant_id, ctx.financial_space_id, operation_key))
        row = cursor.fetchone()
        if row is None or not _same_request(kind, row["payload"], payload):
            raise AiError("conflict", "Outra proposta para esta ação foi criada ao mesmo tempo.")
        return dict(row)
    row = dict(row)
    write_audit(
        cursor,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.actor_id,
        event_type="ai.proposal.created",
        entity_type="ai_proposal",
        entity_id=str(row["id"]),
        metadata={
            "financial_space_id": ctx.financial_space_id,
            "kind": kind,
            "status": status,
            "payload_hash": payload_hash,
            "operation_key": operation_key,
            "requires_review": requires_review,
            "ambiguity_codes": sorted({item["code"] for item in ambiguities}),
            "run_id": run_id or ctx.run_id,
            "trace_id": ctx.trace_id,
        },
    )
    logger.info(
        "proposal_created proposal_id=%s kind=%s status=%s requires_review=%s",
        row["id"], kind, status, requires_review,
    )
    return row


def _existing_operation(cursor, ctx: ExecutionContext, operation_key: str) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT id, proposal_id, payload_hash, status FROM ai_operations "
        "WHERE tenant_id = %s AND financial_space_id = %s AND operation_key = %s",
        (ctx.tenant_id, ctx.financial_space_id, operation_key),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _applied_row(
    cursor, ctx: ExecutionContext, operation: Dict[str, Any], kind: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """A ação já virou operação: devolve a proposta aplicada (ou conflito)."""
    row = _fetch(cursor, ctx, str(operation["proposal_id"]))
    if row is None:
        raise AiError("conflict", "Esta ação já foi aplicada.")
    if not _same_request(kind, row["payload"], payload):
        raise AiError("conflict", "Esta ação já foi aplicada com outros dados.")
    return row


def _view_of_applied(
    cursor, ctx: ExecutionContext, operation: Dict[str, Any], kind: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    return build_view(cursor, ctx, _applied_row(cursor, ctx, operation, kind, payload))


# ---------------------------------------------------------------------------
# Alvos: retrato usado para detectar proposta desatualizada.
# ---------------------------------------------------------------------------
def payable_state(payable: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "paid": money_str(payable["paid"]),
        "remaining": money_str(payable["remaining"]),
        "status": payable["status"],
    }


def _payable_version(payable: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if payable is None:
        return None
    return {
        "id": str(payable["id"]),
        "updated_at": iso_utc(payable["updated_at"]),
        "canceled": payable["canceled_at"] is not None,
        "amount_expected": money_str(payable["amount_expected"]),
        "paid": money_str(payable["paid"]),
        "payment_count": int(payable["payment_count"]),
    }


def transaction_eligible(transaction: Dict[str, Any]) -> bool:
    """Só concilia: despesa realizada (regra canônica OFX) ainda sem vínculo.

    "Em conta permitida" já foi garantido pela consulta, que só devolve
    transação de conta do espaço.
    """
    return bool(transaction["is_realized"]) and transaction["type"] == "expense" and not transaction["linked"]


def _transaction_version(transaction: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if transaction is None:
        return None
    return {
        "id": str(transaction["id"]),
        "updated_at": iso_utc(transaction["updated_at"]),
        "eligible": transaction_eligible(transaction),
    }


def _fetch_operation(
    cursor, ctx: ExecutionContext, operation_id: str, *, lock: bool = False
) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT id, kind, status, effect, proposal_id, payload_hash, reversed_by_operation_id FROM ai_operations "
        "WHERE id = %s AND tenant_id = %s AND financial_space_id = %s" + (" FOR UPDATE" if lock else ""),
        (str(operation_id), ctx.tenant_id, ctx.financial_space_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def load_targets(
    cursor, ctx: ExecutionContext, kind: str, payload: Dict[str, Any], *, lock: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Relê os alvos da proposta. Devolve ``(target_versions, linhas)``.

    É a MESMA função na prévia e na aplicação: comparar os dois retratos é o
    que detecta proposta desatualizada. Com ``lock=True`` (aplicação) as linhas
    ficam travadas até o fim da transação do efeito.
    """
    if kind == KIND_PAYMENT:
        payable = repository.fetch_payable(cursor, ctx, payload["payable_id"], for_update=lock)
        transaction = None
        if payload.get("transaction_id"):
            transaction = repository.fetch_transaction_for_link(
                cursor, ctx, payload["transaction_id"], for_update=lock
            )
        versions = {"payable": _payable_version(payable), "transaction": _transaction_version(transaction)}
        if payload.get("transaction_id") and transaction is None:
            versions["transaction"] = {"id": payload["transaction_id"], "missing": True}
        return versions, {"payable": payable, "transaction": transaction}

    if kind == KIND_IMPORT:
        accounts = repository.space_accounts(cursor, ctx, [payload["account_id"]])
        items = payload["items"]
        # Os duplicados que a prévia já tinha apontado também são reconferidos:
        # se a linha que "já existia" for cancelada entre a prévia e a
        # aplicação, o aviso mostrado ao titular deixa de valer.
        known = payload.get("known_duplicates") or []
        entries = list(items) + list(known)
        keys = repository.existing_import_keys(
            cursor,
            ctx,
            payload["account_id"],
            [entry["fitid"] for entry in entries if entry.get("fitid")],
            [entry["dedup_key"] for entry in entries],
        )
        matches = sum(1 for item in items if repository.ledger_situation(item, keys) is not None)
        unrealized = sum(
            1 for entry in entries
            if repository.ledger_situation(entry, keys) in (repository.LEDGER_CANCELED, repository.LEDGER_OUTSIDE)
        )
        versions = {
            "account": {"id": payload["account_id"], "linked": bool(accounts)},
            "ledger_matches": matches,
            # Quantos lançamentos do extrato "já existem" só como linha que
            # NÃO está no realizado. Mudou -> proposta desatualizada.
            "ledger_unrealized_matches": unrealized,
        }
        return versions, {"account": accounts[0] if accounts else None, "keys": keys}

    operation = _fetch_operation(cursor, ctx, payload["operation_id"], lock=lock)
    versions = {"operation": None, "detail": None}  # type: Dict[str, Any]
    rows = {"operation": operation}  # type: Dict[str, Any]
    if operation is None:
        return versions, rows
    versions["operation"] = {"id": str(operation["id"]), "status": operation["status"]}
    effect = operation["effect"] or {}
    if operation["kind"] == KIND_PAYMENT:
        payable = repository.fetch_payable(cursor, ctx, effect["payable_id"], for_update=lock)
        payment = repository.fetch_payment(cursor, ctx, effect["payment_id"], effect["payable_id"])
        rows.update({"payable": payable, "payment": payment})
        versions["detail"] = {
            "payable": _payable_version(payable),
            "payment": None if payment is None else {
                "id": str(payment["id"]),
                "reversed": payment["reversed_at"] is not None,
            },
        }
    elif operation["kind"] == KIND_IMPORT:
        batch = repository.fetch_import_batch(cursor, ctx, effect["import_batch_id"], for_update=lock)
        rows["batch"] = batch
        versions["detail"] = None if batch is None else {
            "import_batch_id": str(batch["id"]),
            "status": batch["status"],
            "active_transactions": batch["active_transactions"],
            "linked_transactions": batch["linked_transactions"],
        }
    return versions, rows


# ---------------------------------------------------------------------------
# prepare_payable_payment
# ---------------------------------------------------------------------------
# Prefixos RESERVADOS de referência: só valem o que o backend encontra no banco.
_ARTIFACT_PREFIX = "artifact:"
_TRANSACTION_PREFIX = "transaction:"
# Arquivo de imagem ou PDF é comprovante, venha com o rótulo que vier.
_RECEIPT_FILE_KINDS = frozenset({"pdf", "png", "jpeg"})


def _claims_statement(item: Dict[str, str]) -> bool:
    return item["kind"] == "ofx_transaction" or item["ref"].startswith(_TRANSACTION_PREFIX)


def _resolve_evidence(
    cursor, ctx: ExecutionContext, declared: List[Dict[str, str]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Confere as evidências e deriva, NO BACKEND, o tipo e a origem de cada uma.

    O rótulo ``kind`` chega dos argumentos da ferramenta, ou seja, é texto do
    modelo (e o modelo pode estar repetindo uma instrução escondida dentro do
    próprio comprovante). Regra de segurança não pode depender dele. Então:

    * ``artifact:<id>``: o anexo precisa existir na quarentena DESTE espaço
      (anexo de outro espaço não serve de evidência, AC-01). O tipo sai do
      arquivo: imagem/PDF, ou qualquer coisa vinda do WhatsApp, é
      ``receipt``, mesmo que o modelo tenha escrito "manual". A origem
      (email/upload/whatsapp) também sai do anexo;
    * ``transaction:<id>``: fica de fora daqui; a transação validada é
      acrescentada por quem chama, e só se for elegível;
    * qualquer outra referência: não há como conferir. Ela é guardada como
      anotação (``verified: False``) para o titular ver, mas não define
      origem, não entra na identidade da ação e não dispensa revisão. Um
      "email:qualquer-coisa" inventado não vira origem ``email``.

    Devolve ``(itens, origens)``. Sem anexo conferido, a origem é o canal.
    """
    channel_source = "whatsapp" if ctx.channel == "whatsapp" else "manual"
    resolved = {}  # type: Dict[Tuple[str, str], Dict[str, Any]]
    sources = set()
    for item in declared:
        ref = item["ref"]
        if _claims_statement(item):
            continue
        if ref.startswith(_ARTIFACT_PREFIX):
            artifact = repository.fetch_artifact(cursor, ctx, as_uuid(ref[len(_ARTIFACT_PREFIX):], "evidence"))
            if artifact is None:
                raise AiError("not_found", "Evidência não encontrada neste espaço.")
            is_receipt = artifact["detected_kind"] in _RECEIPT_FILE_KINDS or artifact["source_kind"] == "whatsapp"
            if is_receipt:
                kind = "receipt"
            else:
                kind = "email" if artifact["source_kind"] == "email" else "manual"
            canonical_ref = _ARTIFACT_PREFIX + str(artifact["id"])
            resolved[("artifact", canonical_ref)] = {
                "kind": kind,
                "ref": canonical_ref,
                "verified": True,
                # O anexo sai da quarentena em dias; o hash continua
                # identificando o arquivo que serviu de evidência.
                "sha256": artifact["sha256"],
            }
            sources.add(artifact["source_kind"])
        else:
            resolved[(item["kind"], ref)] = {"kind": item["kind"], "ref": ref, "verified": False}
    items = sorted(resolved.values(), key=lambda entry: (entry["kind"], entry["ref"]))
    return items, sorted(sources or {channel_source})


def _count_live_twins(
    cursor, ctx: ExecutionContext, operation_key: str, payable_id: str, amount: str, paid_on: str
) -> int:
    """Outras propostas aplicáveis para a mesma conta a pagar, valor e data."""
    cursor.execute(
        """
        SELECT count(*) AS total FROM ai_proposals
        WHERE tenant_id = %s AND financial_space_id = %s AND kind = %s
          AND status IN ('ready', 'approved') AND expires_at > now()
          AND operation_key <> %s
          AND payload->>'payable_id' = %s AND payload->>'amount' = %s AND payload->>'paid_on' = %s
        """,
        (ctx.tenant_id, ctx.financial_space_id, KIND_PAYMENT, operation_key, payable_id, amount, paid_on),
    )
    return int(cursor.fetchone()["total"])


@repository.guarded("proposals.prepare_payable_payment")
def prepare_payable_payment(
    pool,
    ctx: ExecutionContext,
    *,
    payable_id: Any,
    amount: Any,
    paid_on: Any,
    evidence: Any,
    transaction_id: Any = None,
    payment_method: Any = None,
    notes: Any = None,
    run_id: Optional[str] = None,
    settings: Optional[AiSettings] = None,
) -> Dict[str, Any]:
    """Prepara a baixa (total ou parcial) de uma conta a pagar.

    Nunca presume quitação integral: o valor aplicado é exatamente o
    informado, e o "depois" é calculado com ``Decimal`` a partir do que está
    no banco agora.

    O que dispensa revisão
    ----------------------
    Só uma coisa: a baixa estar amarrada a uma transação canônica de extrato
    OFX, conferida aqui no banco (``transaction_id`` elegível). Qualquer outra
    evidência (comprovante, e-mail, pedido manual) chega descrita pelo modelo
    e não pode ser conferida; a proposta nasce ``requires_review`` e nenhum
    grant, nem ilimitado, a aplica sozinho. É isso que mantém a Fase 1 sem
    baixa automática por comprovante, e não um rótulo que o modelo escolhe.
    """
    payable_uuid = as_uuid(payable_id, "payable_id")
    transaction_uuid = as_uuid(transaction_id, "transaction_id") if transaction_id else None
    amount_value = parse_amount(amount)
    paid_date = parse_local_date(paid_on, "paid_on")
    declared = _normalize_evidence(evidence)
    method = _clean_text(payment_method, "payment_method", 60)
    note = _clean_text(notes, "notes", 500)
    ttl_hours = _ttl_hours(settings)

    transaction_ref = _TRANSACTION_PREFIX + transaction_uuid if transaction_uuid else None
    for item in declared:
        # O modelo não pode "declarar" lastro em extrato: evidência de extrato
        # só vale se for a própria transação validada no banco.
        if _claims_statement(item) and item["ref"] != transaction_ref:
            raise AiError(
                "invalid_request",
                "Evidência de extrato exige o transaction_id correspondente.",
                details={"field": "evidence"},
            )

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        payable = repository.fetch_payable(cursor, ctx, payable_uuid)
        if payable is None:
            # Outro tenant, outro espaço ou sem vínculo: mesma resposta.
            raise AiError("not_found", "Conta a pagar não encontrada neste espaço.")
        transaction = None
        if transaction_uuid:
            transaction = repository.fetch_transaction_for_link(cursor, ctx, transaction_uuid)
            if transaction is None:
                raise AiError("not_found", "Transação não encontrada neste espaço.")
        evidence_items, sources = _resolve_evidence(cursor, ctx, declared)

        currency = payable["currency"]
        ambiguities = []  # type: List[Dict[str, Any]]
        if amount_value is None:
            ambiguities.append(
                _ambiguity("missing_amount", "O valor pago não foi informado ou não está legível.", True)
            )
        if paid_date is None:
            ambiguities.append(
                _ambiguity("missing_date", "A data do pagamento não foi informada ou não está legível.", True)
            )
        elif paid_date > utc_now().date() + timedelta(days=1):
            ambiguities.append(_ambiguity("future_date", "A data do pagamento está no futuro.", False))
        canceled = payable["canceled_at"] is not None
        if canceled:
            ambiguities.append(_ambiguity("payable_canceled", "A conta a pagar está cancelada.", True))

        overpayment = amount_value is not None and not canceled and amount_value > payable["remaining"]
        if overpayment:
            ambiguities.append(
                _ambiguity(
                    "overpayment",
                    "O valor informado (%s) é maior que o saldo restante (%s). A quitação integral não é presumida: "
                    "confira o valor ou ajuste o valor previsto da conta."
                    % (format_money(amount_value, currency), format_money(payable["remaining"], currency)),
                    True,
                )
            )

        eligible = transaction is not None and transaction_eligible(transaction)
        if transaction is not None and not eligible:
            ambiguities.append(
                _ambiguity(
                    "uncertain_link",
                    "A transação indicada não serve para conciliar: precisa ser uma despesa paga vinda de extrato "
                    "OFX, em conta deste espaço e ainda sem vínculo com outro pagamento.",
                    True,
                )
            )
        if eligible and amount_value is not None and amount_value != transaction["amount"]:
            ambiguities.append(
                _ambiguity(
                    "transaction_amount_mismatch",
                    "O valor do pagamento (%s) é diferente do valor da transação do extrato (%s)."
                    % (format_money(amount_value, currency), format_money(transaction["amount"], currency)),
                    False,
                )
            )
        if eligible:
            # Lastro em extrato: a transação foi lida e conferida agora. É a
            # ÚNICA evidência que dispensa revisão. Quem a acrescenta é o
            # backend; o que o modelo declarou sobre extrato já foi descartado.
            evidence_items = sorted(
                evidence_items + [{"kind": "ofx_transaction", "ref": transaction_ref, "verified": True}],
                key=lambda item: (item["kind"], item["ref"]),
            )
        elif not evidence_items:
            ambiguities.append(
                _ambiguity("missing_evidence", "Nenhuma evidência acompanha este pagamento.", False)
            )
        elif any(item["kind"] == "receipt" for item in evidence_items) and not any(
            item["verified"] and item["kind"] != "receipt" for item in evidence_items
        ):
            # Fase 1: comprovante (imagem/PDF/WhatsApp) é conferência, não
            # baixa. Nenhum grant aplica isso sozinho. Uma referência que o
            # backend não consegue conferir (ex.: um e-mail citado pelo modelo)
            # não muda isso: o lastro continua sendo só o comprovante.
            ambiguities.append(
                _ambiguity(
                    "receipt_only",
                    "A única evidência é um comprovante. Comprovante serve para conferência; a baixa precisa da "
                    "sua aprovação.",
                    False,
                )
            )
        else:
            ambiguities.append(
                _ambiguity(
                    "no_statement_backing",
                    "Este pagamento não está vinculado a um lançamento do extrato OFX. Sem esse lastro a baixa não "
                    "é automática: precisa da sua aprovação.",
                    False,
                )
            )

        state_after = STATE_RECONCILED if eligible else STATE_REGISTERED
        amount_text = money_str(amount_value) if amount_value is not None else None
        paid_text = paid_date.isoformat() if paid_date else None
        payload = {
            "kind": KIND_PAYMENT,
            "payable_id": payable_uuid,
            "amount": amount_text,
            "currency": currency,
            "paid_on": paid_text,
            "transaction_id": transaction_uuid,
            "payment_method": method,
            "notes": note,
            "state_after": state_after,
            # No payload (logo, no hash que o titular aprova) só entra o que o
            # backend conferiu. As anotações não conferidas ficam na coluna
            # ``evidence`` da proposta, marcadas como ``verified: False``.
            "evidence": [
                {key: value for key, value in item.items() if key != "verified"}
                for item in evidence_items if item["verified"]
            ],
            # Dados que a política usa para decidir se um grant cobre o efeito.
            "authorization": {
                "capability": capability_for(KIND_PAYMENT),
                "amount": amount_text,
                "account_ids": [str(transaction["account_id"])] if eligible else [],
                "source_kinds": sources,
                "dates": [paid_text] if paid_text else [],
            },
        }
        # Identidade estável da ação: o QUE está sendo baixado, só com dados
        # que o backend conferiu. O rótulo e a referência livre que o modelo
        # escolhe para a evidência ficam de fora de propósito: se entrassem, a
        # mesma baixa descrita de outro jeito (reenvio, troca de modelo) teria
        # outra chave e viraria um SEGUNDO pagamento.
        identity = {
            "payable_id": payable_uuid,
            "amount": amount_text,
            "paid_on": paid_text,
            "transaction_id": transaction_uuid,
            "artifacts": sorted(item["sha256"] for item in evidence_items if item.get("sha256")),
        }

        # A mesma ação já aplicada devolve o resultado anterior. Se ela foi
        # aplicada E revertida, o titular pode propô-la de novo: nasce uma
        # operação nova (tentativa seguinte), sempre com revisão, para que o
        # reenvio de uma mensagem antiga não refaça sozinho o que ele desfez.
        operation_key = ""
        for attempt in range(MAX_REAPPLY_ATTEMPTS + 1):
            operation_key = operation_key_for(
                ctx, kind=KIND_PAYMENT, source=sources, identity=identity, attempt=attempt
            )
            operation = _existing_operation(cursor, ctx, operation_key)
            if operation is None:
                break
            if operation["status"] != "reversed":
                return _view_of_applied(cursor, ctx, operation, KIND_PAYMENT, payload)
        else:
            raise AiError("conflict", "Esta ação já foi aplicada e revertida vezes demais.")
        if attempt > 0:
            ambiguities.append(
                _ambiguity("previously_reversed", "Este mesmo pagamento já foi aplicado e revertido antes.", False)
            )

        # Mesma conta a pagar, mesmo valor e mesma data, mas OUTRA chave (outro
        # anexo, com ou sem transação): pode ser o mesmo pagamento chegando por
        # outro caminho. Não bloqueia (duas parcelas iguais no mesmo dia
        # existem), mas nenhum grant aplica sem o titular olhar.
        if amount_value is not None and paid_date is not None:
            equal_payments = repository.count_equal_active_payments(
                cursor, ctx, payable_uuid, amount_value, paid_date
            )
            twins = _count_live_twins(cursor, ctx, operation_key, payable_uuid, amount_text, paid_text)
            if equal_payments or twins:
                ambiguities.append(
                    _ambiguity(
                        "possible_duplicate",
                        "Já existe pagamento ou proposta em aberto para esta conta a pagar com o mesmo valor e a "
                        "mesma data. Confira se não é o mesmo pagamento antes de aprovar.",
                        False,
                        payments=equal_payments,
                        proposals=twins,
                    )
                )

        after = None
        if amount_value is not None and not canceled and not overpayment:
            new_paid = payable["paid"] + amount_value
            after = {
                "paid": money_str(new_paid),
                "remaining": money_str(repository.remaining_amount(payable["amount_expected"], new_paid)),
                "status": repository.derive_payable_status(payable["amount_expected"], new_paid, False),
            }
        expected_effect = {
            "state_after": state_after,
            "before": payable_state(payable),
            "after": after,
            "items_new": 0,
            "items_duplicate": 0,
            "totals": {},
            "target": {
                "payable_id": payable_uuid,
                "title": payable["title"],
                "amount_expected": money_str(payable["amount_expected"]),
                "currency": currency,
                "due_date": payable["due_date"].isoformat() if payable["due_date"] else None,
            },
        }
        target_versions = {
            "payable": _payable_version(payable),
            "transaction": _transaction_version(transaction),
        }
        row = _store(
            cursor,
            ctx,
            kind=KIND_PAYMENT,
            payload=payload,
            operation_key=operation_key,
            target_versions=target_versions,
            expected_effect=expected_effect,
            evidence=evidence_items,
            ambiguities=ambiguities,
            run_id=run_id,
            ttl_hours=ttl_hours,
        )
        return build_view(cursor, ctx, row)


# ---------------------------------------------------------------------------
# prepare_statement_import
# ---------------------------------------------------------------------------
def _import_items(preview: ImportPreview) -> Tuple[List[Dict[str, Any]], int, Decimal]:
    """Itens aplicáveis (receita/despesa), nº de transferências e total delas."""
    invalid = AiError("ambiguous_evidence", "A prévia do extrato tem lançamentos sem valor, data ou tipo válidos.")
    applicable = []  # type: List[Dict[str, Any]]
    transfers, transfer_total = 0, Decimal("0")
    for item in preview.items:
        try:
            amount = parse_amount(item.amount)
            occurred_on = parse_local_date(item.occurred_on, "occurred_on")
        except AiError:
            raise invalid
        dedup_key = _import_key(item.dedup_key)
        if amount is None or occurred_on is None or not dedup_key:
            raise invalid
        if item.type == "transfer":
            transfers += 1
            transfer_total += amount
            continue
        if item.type not in ("income", "expense"):
            raise invalid
        fitid = _import_key(item.fitid) if item.fitid else None
        if item.fitid and not fitid:
            raise invalid
        # A descrição é cosmética e vem do memo do banco: caractere de
        # controle é trocado por espaço em vez de derrubar o extrato.
        description = _plain_text(item.description, 500) or "Sem descrição"
        applicable.append(
            {
                "dedup_key": dedup_key,
                "occurred_on": occurred_on.isoformat(),
                "description": description,
                "amount": money_str(amount),
                "type": item.type,
                "fitid": fitid or None,
            }
        )
    return applicable, transfers, transfer_total


def _import_key(value: Any) -> Optional[str]:
    """FITID ou chave de deduplicação válidos, ou ``None``.

    São campos de IDENTIDADE: não podem ser "limpos", porque mudar um
    caractere mudaria com quem o lançamento é comparado e abriria caminho para
    duplicar. Se vierem com algo que o banco não consegue gravar, o extrato é
    recusado como evidência ambígua (erro do arquivo, não falha do sistema).
    """
    text = str(value or "").strip()
    if not text or len(text) > 200 or _UNSTORABLE_CHARS.search(text):
        return None
    return text


def _known_duplicates(preview: ImportPreview) -> List[Dict[str, Any]]:
    """Duplicados que a prévia já apontou, reduzidos a chave, FITID e valor.

    O importador tira de ``items`` o que já existe na conta e lista em
    ``duplicates``. Eles não são aplicados, mas precisam ser conferidos: se a
    linha que "já existe" estiver cancelada, ignorar o lançamento deixa o
    realizado incompleto sem ninguém perceber.
    """
    invalid = AiError("ambiguous_evidence", "A prévia do extrato tem lançamentos duplicados sem identificação válida.")
    unique = {}  # type: Dict[Tuple[str, Optional[str]], Dict[str, Any]]
    for entry in preview.duplicates or []:
        item = entry.get("item") if isinstance(entry, dict) else None
        if not isinstance(item, dict):
            raise invalid
        dedup_key = _import_key(item.get("dedup_key"))
        fitid = _import_key(item.get("fitid")) if item.get("fitid") else None
        if not dedup_key or (item.get("fitid") and not fitid):
            # Sem identificação não há como conferir a situação no banco.
            raise invalid
        try:
            amount = parse_amount(item.get("amount"))
        except AiError:
            amount = None
        # O valor só entra no total do aviso. Um duplicado com valor ilegível
        # não derruba a importação: conta no aviso com 0.00.
        unique[(dedup_key, fitid)] = {
            "dedup_key": dedup_key, "fitid": fitid, "amount": money_str(amount if amount is not None else 0),
        }
    return [unique[key] for key in sorted(unique, key=lambda pair: (pair[0], pair[1] or ""))]


def _period_bound(value: Any, fallback: str) -> str:
    """Início/fim do período declarado pela prévia, como data ISO.

    O período é só rótulo da proposta. Se a prévia trouxer algo que não é
    data, vale a menor/maior data dos próprios lançamentos.
    """
    try:
        parsed = parse_local_date(value, "period")
    except AiError:
        return fallback
    return parsed.isoformat() if parsed else fallback


def _clean_filename(name: Any) -> str:
    # Só o nome do arquivo: caminho de quem enviou não interessa nem deve ficar gravado.
    # Caractere de controle some do nome (é cosmético); a regra do sufixo .ofx
    # é conferida depois, sobre o nome já limpo.
    return _CONTROL_CHARS.sub("", re.split(r"[\\/]", str(name or "").strip())[-1]).strip()[:200]


@repository.guarded("proposals.prepare_statement_import")
def prepare_statement_import(
    pool,
    ctx: ExecutionContext,
    *,
    preview: ImportPreview,
    source_kind: str,
    run_id: Optional[str] = None,
    settings: Optional[AiSettings] = None,
) -> Dict[str, Any]:
    """Prepara a importação de um extrato a partir de uma prévia do importador.

    Só OFX é fonte canônica do realizado. CSV, PDF e imagem geram prévia ou
    evidência, mas não podem virar lançamentos de extrato por decisão do modelo.
    """
    if not isinstance(preview, ImportPreview):
        raise AiError("invalid_request", "Prévia de importação inválida.")
    if source_kind not in policy.SOURCE_KINDS:
        raise AiError("invalid_request", "Origem inválida.", details={"field": "source_kind"})
    filename = _clean_filename(preview.filename)
    if not preview.canonical or preview.file_kind != "ofx" or not repository.is_canonical_source_file(filename):
        raise AiError(
            "invalid_request",
            "Somente extrato OFX (arquivo .ofx) pode ser importado. CSV, PDF e imagem servem apenas de prévia.",
        )
    account_id = as_uuid(preview.account_id, "account_id")
    artifact_id = as_uuid(preview.artifact_id, "artifact_id")
    sha256 = str(preview.artifact_sha256 or "")
    if not _SHA256_PATTERN.match(sha256):
        raise AiError("invalid_request", "Prévia de importação inválida.")
    if account_id not in ctx.allowed_account_ids:
        raise AiError("not_found", "Conta não encontrada neste espaço.")
    if len(preview.items) + len(preview.duplicates or []) > MAX_IMPORT_ITEMS:
        raise AiError("payload_too_large", "O extrato tem lançamentos demais para uma única importação.")
    ttl_hours = _ttl_hours(settings)

    items, transfers, transfer_total = _import_items(preview)
    known_duplicates = _known_duplicates(preview)
    if not items:
        raise AiError("conflict", "Não há receitas nem despesas neste extrato para importar.")
    dates = sorted(item["occurred_on"] for item in items)
    volume = sum((Decimal(item["amount"]) for item in items), Decimal("0"))
    period = {
        "start": _period_bound(preview.period_start, dates[0]),
        "end": _period_bound(preview.period_end, dates[-1]),
    }

    payload = {
        "kind": KIND_IMPORT,
        "account_id": account_id,
        "artifact_id": artifact_id,
        "artifact_sha256": sha256,
        "filename": filename,
        "file_kind": "ofx",
        "source_kind": source_kind,
        "items": items,
        # Não são aplicados; ficam no payload para a aplicação reconferir a
        # situação deles no banco (ver ``load_targets``).
        "known_duplicates": [
            {"dedup_key": entry["dedup_key"], "fitid": entry["fitid"]} for entry in known_duplicates
        ],
        "transfers_skipped": transfers,
        "transfer_total": money_str(transfer_total),
        "period": period,
        "authorization": {
            "capability": capability_for(KIND_IMPORT),
            # Para o limite de valor do grant conta o volume total movimentado
            # pelo extrato (receitas + despesas), não o maior lançamento.
            "amount": money_str(volume),
            "account_ids": [account_id],
            "source_kinds": [source_kind],
            # Menor e maior data: o período do grant precisa cobrir as duas.
            "dates": sorted({dates[0], dates[-1]}),
        },
    }
    # Identidade = arquivo + conta. O mesmo arquivo na mesma conta é a mesma
    # ação, venha de onde vier o reenvio.
    operation_key = operation_key_for(
        ctx, kind=KIND_IMPORT, source=[source_kind], identity={"artifact_sha256": sha256, "account_id": account_id}
    )

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        operation = _existing_operation(cursor, ctx, operation_key)
        if operation is not None:
            if operation["status"] == "reversed":
                raise AiError("conflict", "Este extrato já foi importado e a importação foi revertida.")
            return _view_of_applied(cursor, ctx, operation, KIND_IMPORT, payload)

        target_versions, rows = load_targets(cursor, ctx, KIND_IMPORT, payload)
        if rows["account"] is None:
            raise AiError("not_found", "Conta não encontrada neste espaço.")
        keys = rows["keys"]

        # Duplicados cuja linha existente NÃO está no realizado, por situação:
        # {situação: [quantidade, total]}. Soma os que a prévia já tinha
        # apontado e os que só aparecem agora, ao conferir no banco.
        unrealized = {
            repository.LEDGER_CANCELED: [0, Decimal("0")],
            repository.LEDGER_OUTSIDE: [0, Decimal("0")],
        }

        def note_duplicate(entry: Dict[str, Any]) -> None:
            situation = repository.ledger_situation(entry, keys)
            if situation in unrealized:
                unrealized[situation][0] += 1
                unrealized[situation][1] += Decimal(entry["amount"])

        for entry in known_duplicates:
            note_duplicate(entry)

        seen = set()
        new_items, duplicates = [], 0
        for item in items:
            in_ledger = repository.ledger_situation(item, keys) is not None
            repeated = item["dedup_key"] in seen or (item["fitid"] and ("fitid", item["fitid"]) in seen)
            if in_ledger or repeated:
                duplicates += 1
                if in_ledger:
                    note_duplicate(item)
                continue
            seen.add(item["dedup_key"])
            if item["fitid"]:
                seen.add(("fitid", item["fitid"]))
            new_items.append(item)
        canceled_count, canceled_total = unrealized[repository.LEDGER_CANCELED]
        outside_count, outside_total = unrealized[repository.LEDGER_OUTSIDE]
        if not new_items:
            if canceled_count or outside_count:
                # Nada a importar, mas o titular precisa saber que "já
                # registrado" aqui não significa "no realizado".
                raise AiError(
                    "conflict",
                    "Todos os lançamentos deste extrato já existem no sistema, mas %d deles estão cancelados ou "
                    "fora do realizado e não são reativados pela importação." % (canceled_count + outside_count),
                )
            raise AiError("conflict", "Todos os lançamentos deste extrato já estão registrados.")

        income = sum((Decimal(item["amount"]) for item in new_items if item["type"] == "income"), Decimal("0"))
        expense = sum((Decimal(item["amount"]) for item in new_items if item["type"] == "expense"), Decimal("0"))
        currency = rows["account"]["currency"]

        ambiguities = []  # type: List[Dict[str, Any]]
        if canceled_count:
            # Ex.: importação revertida e extrato novo com os mesmos
            # lançamentos. A linha cancelada ocupa a chave, o lançamento é
            # ignorado e o realizado fica SEM ele. Não reativamos por conta
            # própria (seria desfazer uma reversão do titular): pedimos revisão.
            ambiguities.append(
                _ambiguity(
                    "duplicate_of_canceled",
                    "%d lançamento(s) deste extrato, no total de %s, já existe(m) no sistema como CANCELADO(S). "
                    "Eles não serão importados de novo e continuam fora do realizado."
                    % (canceled_count, format_money(canceled_total, currency)),
                    False,
                    count=canceled_count,
                    total=money_str(canceled_total),
                )
            )
        if outside_count:
            ambiguities.append(
                _ambiguity(
                    "duplicate_outside_realized",
                    "%d lançamento(s) deste extrato, no total de %s, já existe(m) no sistema com outra origem ou "
                    "situação (não é extrato OFX pago). Eles não serão importados de novo e continuam fora do "
                    "realizado." % (outside_count, format_money(outside_total, currency)),
                    False,
                    count=outside_count,
                    total=money_str(outside_total),
                )
            )
        if transfers:
            # O OFX não diz a conta de destino, e o banco exige destino em
            # transferência. Inventar um seria pior do que não importar.
            ambiguities.append(
                _ambiguity(
                    "transfer_without_destination",
                    "%d transferência(s), no total de %s, não serão importadas: o extrato não informa a conta de "
                    "destino." % (transfers, format_money(transfer_total, currency)),
                    False,
                    count=transfers,
                    total=money_str(transfer_total),
                )
            )
        for item in (preview.ambiguities or [])[:20]:
            if not isinstance(item, dict):
                continue
            code = _plain_text(item.get("code"), 60) or "preview_ambiguity"
            if code == "transfer_without_destination":
                continue
            # Só código e mensagem: o item bruto do extrato não vai para a proposta.
            ambiguities.append(
                _ambiguity(code, _plain_text(item.get("message"), 300) or "Ponto a revisar na prévia.", False)
            )

        expected_effect = {
            "state_after": STATE_IMPORTED,
            "before": None,
            "after": None,
            "items_new": len(new_items),
            "items_duplicate": duplicates + len(preview.duplicates or []),
            "items_duplicate_canceled": canceled_count,
            "items_duplicate_outside_realized": outside_count,
            "items_transfer_skipped": transfers,
            "totals": {
                "income": money_str(income),
                "expense": money_str(expense),
                "net": money_str(income - expense),
                "transfer_skipped": money_str(transfer_total),
            },
            "target": {
                "account_id": account_id,
                "account_name": rows["account"]["name"],
                "currency": currency,
                "filename": filename,
                "institution": _plain_text(preview.institution, 120) or None,
                "period": period,
            },
        }
        evidence = [
            {
                "kind": "email" if source_kind == "email" else "manual",
                "ref": "artifact:%s" % artifact_id,
                "sha256": sha256,
                "label": filename,
            }
        ]
        row = _store(
            cursor,
            ctx,
            kind=KIND_IMPORT,
            payload=payload,
            operation_key=operation_key,
            target_versions=target_versions,
            expected_effect=expected_effect,
            evidence=evidence,
            ambiguities=ambiguities,
            run_id=run_id,
            ttl_hours=ttl_hours,
        )
        return build_view(cursor, ctx, row)


# ---------------------------------------------------------------------------
# prepare_reversal
# ---------------------------------------------------------------------------
@repository.guarded("proposals.prepare_reversal")
def prepare_reversal(
    pool,
    ctx: ExecutionContext,
    operation_id: Any,
    reason: Any,
    run_id: Optional[str] = None,
    settings: Optional[AiSettings] = None,
) -> Dict[str, Any]:
    """Cria a proposta de compensação de uma operação aplicada.

    Não aplica nada: a reversão passa pelo mesmo caminho de aprovação e de
    idempotência de qualquer outro efeito. Pedir de novo a reversão de uma
    operação já revertida devolve a proposta que a reverteu.
    """
    try:
        operation_uuid = str(uuid.UUID(str(operation_id)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("operation_unknown")
    reason_text = _required_reason(reason)
    ttl_hours = _ttl_hours(settings)
    source = "whatsapp" if ctx.channel == "whatsapp" else "manual"

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        operation = _fetch_operation(cursor, ctx, operation_uuid)
        if operation is None:
            # Operação de outro espaço ou tenant responde como desconhecida.
            raise AiError("operation_unknown")
        if operation["kind"] == KIND_REVERSAL:
            raise AiError("invalid_request", "Uma reversão não pode ser revertida. Prepare a alteração novamente.")

        operation_key = operation_key_for(
            ctx, kind=KIND_REVERSAL, source=[source], identity={"operation_id": operation_uuid}
        )
        if operation["status"] == "reversed":
            cursor.execute(
                "SELECT proposal_id FROM ai_operations WHERE id = %s AND tenant_id = %s AND financial_space_id = %s",
                (str(operation["reversed_by_operation_id"]), ctx.tenant_id, ctx.financial_space_id),
            )
            reversal = cursor.fetchone()
            row = _fetch(cursor, ctx, str(reversal["proposal_id"])) if reversal else None
            if row is None:
                raise AiError("conflict", "Esta operação já foi revertida.")
            return build_view(cursor, ctx, row)

        original_payload = {"operation_id": operation_uuid}
        target_versions, rows = load_targets(cursor, ctx, KIND_REVERSAL, original_payload)
        effect = operation["effect"] or {}
        original_authorization = effect.get("authorization") or {}
        ambiguities = []  # type: List[Dict[str, Any]]

        if operation["kind"] == KIND_PAYMENT:
            payable, payment = rows.get("payable"), rows.get("payment")
            if payable is None or payment is None:
                raise AiError("conflict", "O pagamento desta operação não está mais disponível neste espaço.")
            if payment["reversed_at"] is not None:
                raise AiError("conflict", "O pagamento desta operação já foi revertido por outro caminho.")
            new_paid = payable["paid"] - payment["amount"]
            canceled = payable["canceled_at"] is not None
            expected_effect = {
                "state_after": STATE_REVERSED,
                "before": payable_state(payable),
                "after": {
                    "paid": money_str(new_paid),
                    "remaining": money_str(repository.remaining_amount(payable["amount_expected"], new_paid)),
                    "status": repository.derive_payable_status(payable["amount_expected"], new_paid, canceled),
                },
                "items_new": 0,
                "items_duplicate": 0,
                "totals": {},
                "target": {
                    "original_kind": KIND_PAYMENT,
                    "operation_id": operation_uuid,
                    "payable_id": str(payable["id"]),
                    "title": payable["title"],
                    "amount": money_str(payment["amount"]),
                    "currency": payable["currency"],
                },
            }
        else:
            batch = rows.get("batch")
            if batch is None:
                raise AiError("conflict", "O lote desta importação não está mais disponível neste espaço.")
            if batch["linked_transactions"]:
                # Cancelar um lançamento que lastreia um pagamento conciliado
                # deixaria o pagamento apontando para uma transação cancelada.
                raise AiError(
                    "conflict",
                    "Há pagamentos conciliados com lançamentos deste extrato. Reverta esses pagamentos antes.",
                )
            expected_effect = {
                "state_after": STATE_REVERSED,
                "before": None,
                "after": None,
                "items_new": batch["active_transactions"],
                "items_duplicate": 0,
                "totals": {
                    "income": money_str(batch["active_income"]),
                    "expense": money_str(batch["active_expense"]),
                    "net": money_str(batch["active_income"] - batch["active_expense"]),
                },
                "target": {
                    "original_kind": KIND_IMPORT,
                    "operation_id": operation_uuid,
                    "import_batch_id": str(batch["id"]),
                    "account_id": str(batch["account_id"]),
                    "filename": batch["filename"],
                },
            }

        payload = {
            "kind": KIND_REVERSAL,
            "operation_id": operation_uuid,
            "original_kind": operation["kind"],
            "reason": reason_text,
            "authorization": {
                "capability": capability_for(KIND_REVERSAL),
                "amount": original_authorization.get("amount"),
                "account_ids": list(original_authorization.get("account_ids") or []),
                "source_kinds": [source],
                "dates": list(original_authorization.get("dates") or []),
            },
        }
        row = _store(
            cursor,
            ctx,
            kind=KIND_REVERSAL,
            payload=payload,
            operation_key=operation_key,
            target_versions=target_versions,
            expected_effect=expected_effect,
            evidence=[{"kind": "manual", "ref": "operation:%s" % operation_uuid}],
            ambiguities=ambiguities,
            run_id=run_id,
            ttl_hours=ttl_hours,
        )
        return build_view(cursor, ctx, row)


# ---------------------------------------------------------------------------
# Aprovação específica, rejeição e expiração.
# ---------------------------------------------------------------------------
@repository.guarded("proposals.approve")
def approve(pool, ctx: ExecutionContext, proposal_id: Any, *, payload_hash: str, version: int) -> Dict[str, Any]:
    """Aprovação específica do titular.

    A aprovação vale para UM conteúdo: o hash e a versão que o titular viu na
    tela. Se a proposta mudou, expirou ou tem pendência impeditiva, não aprova.
    Aprovar não aplica: o efeito continua dependendo da revalidação do grant e
    dos alvos em ``apply_proposal``.
    """
    proposal_uuid = as_uuid(proposal_id, "proposal_id")
    try:
        wanted_version = int(version)
    except (TypeError, ValueError):
        raise AiError("invalid_request", "Versão inválida.", details={"field": "version"})
    deferred = None  # type: Optional[AiError]
    view = None  # type: Optional[Dict[str, Any]]
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        row = lock_proposal(cursor, ctx, proposal_uuid)
        # Quem só observa não aprova efeito: exige grant assisted ou delegated.
        policy.authorize(policy.load_active_grants(cursor, ctx), capability_for(row["kind"]))
        status = row["status"]
        same_content = row["payload_hash"] == payload_hash and int(row["version"]) == wanted_version
        if status == "approved" and row["approval_kind"] == "specific" and same_content:
            return build_view(cursor, ctx, row)  # clique repetido
        if status == "draft":
            raise AiError(
                "ambiguous_evidence", "A proposta tem pendências que impedem a aprovação. Gere uma nova prévia."
            )
        if status in ("expired", "stale"):
            raise AiError("stale_proposal")
        if status != "ready":
            raise AiError("conflict", "A proposta não está aguardando aprovação.")
        if row["is_expired"]:
            # A mudança de estado precisa ser confirmada; o erro sobe depois do
            # commit (levantar aqui desfaria o UPDATE).
            set_status(cursor, ctx, row, "expired")
            deferred = AiError("stale_proposal", "A proposta expirou. Gere uma nova prévia.")
        elif int(row["version"]) != wanted_version:
            raise AiError("stale_proposal", "A versão aprovada não é a versão atual da proposta.")
        elif row["payload_hash"] != payload_hash:
            raise AiError("conflict", "O conteúdo aprovado não confere com o conteúdo da proposta.")
        else:
            cursor.execute(
                """
                UPDATE ai_proposals
                SET status = 'approved', approval_kind = 'specific', approved_by_user_id = %s,
                    approved_hash = payload_hash, approved_at = now(),
                    approved_grant_id = NULL, approved_grant_version = NULL
                WHERE id = %s AND tenant_id = %s
                RETURNING """ + _COLUMNS,
                (ctx.actor_id, proposal_uuid, ctx.tenant_id),
            )
            updated = dict(cursor.fetchone())
            write_audit(
                cursor,
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.actor_id,
                event_type="ai.proposal.approved",
                entity_type="ai_proposal",
                entity_id=proposal_uuid,
                metadata={
                    "financial_space_id": ctx.financial_space_id,
                    "approval_kind": "specific",
                    "payload_hash": updated["payload_hash"],
                    "version": updated["version"],
                    "trace_id": ctx.trace_id,
                },
            )
            view = build_view(cursor, ctx, updated)
    if deferred is not None:
        raise deferred
    return view  # type: ignore[return-value]


@repository.guarded("proposals.reject")
def reject(pool, ctx: ExecutionContext, proposal_id: Any, reason: Any) -> Dict[str, Any]:
    proposal_uuid = as_uuid(proposal_id, "proposal_id")
    reason_text = _required_reason(reason)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        row = lock_proposal(cursor, ctx, proposal_uuid)
        if row["status"] == "rejected":
            return build_view(cursor, ctx, row)
        if row["status"] == "applied":
            raise AiError("conflict", "A proposta já foi aplicada. Use a reversão da operação.")
        if row["status"] not in LIVE_STATUSES:
            raise AiError("stale_proposal", "A proposta não está mais ativa.")
        cursor.execute(
            "UPDATE ai_proposals SET status = 'rejected', rejected_reason = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING " + _COLUMNS,
            (reason_text, proposal_uuid, ctx.tenant_id),
        )
        updated = dict(cursor.fetchone())
        write_audit(
            cursor,
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.actor_id,
            event_type="ai.proposal.rejected",
            entity_type="ai_proposal",
            entity_id=proposal_uuid,
            metadata={
                "financial_space_id": ctx.financial_space_id,
                "payload_hash": updated["payload_hash"],
                "trace_id": ctx.trace_id,
            },
        )
        return build_view(cursor, ctx, updated)


@repository.guarded("proposals.expire_due")
def expire_due(pool, tenant_id: str) -> int:
    """Marca como ``expired`` as propostas vivas vencidas do tenant."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            UPDATE ai_proposals
            SET status = 'expired'
            WHERE tenant_id = %s AND status IN ('draft', 'ready', 'approved') AND expires_at <= now()
            RETURNING id, financial_space_id, kind, payload_hash, version
            """,
            (str(tenant_id),),
        )
        rows = cursor.fetchall()
        for row in rows:
            write_audit(
                cursor,
                tenant_id=str(tenant_id),
                actor_user_id=None,
                event_type="ai.proposal.expired",
                entity_type="ai_proposal",
                entity_id=str(row["id"]),
                metadata={
                    "financial_space_id": str(row["financial_space_id"]),
                    "kind": row["kind"],
                    "payload_hash": row["payload_hash"],
                    "version": row["version"],
                },
            )
    if rows:
        logger.info("proposals_expired tenant_id=%s count=%d", tenant_id, len(rows))
    return len(rows)
