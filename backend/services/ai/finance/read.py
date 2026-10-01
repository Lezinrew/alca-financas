"""Consultas financeiras ENUMERADAS (``finance.read``).

Não existe SQL livre: o modelo escolhe uma consulta de uma lista fechada e
alguns filtros; o escopo (tenant, espaço, contas) vem do ``ExecutionContext``.

Cada consulta devolve um ``ToolResult`` com:

* ``facts``: números calculados pelo banco, em string decimal, com moeda,
  período, escopo DECLARADO, fontes e ``as_of``;
* ``sources``: de onde cada fato saiu (toda ``source_ref`` de um fato aponta
  para uma fonte desta lista);
* ``data``: detalhe para o modelo (itens de lista, composição), como dado.

Duas regras que os testes protegem:

1. Ausência de dados é ``value=None`` + ``missing_reason``. Nunca "0.00":
   zero é uma afirmação ("você não gastou nada"); ausência é outra ("não há
   lançamentos de extrato nesse período").
2. O escopo aplicado é declarado no próprio fato. Mensal, anual e global usam
   textos e referências diferentes, para um número do mês nunca ser lido como
   total geral.
"""

from __future__ import annotations

import base64
import binascii
import calendar
import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .. import policy
from ..db import scoped_tx
from ..errors import AiError
from ..registry import ToolResult
from ..types import ExecutionContext, Fact, Source, canonical_json, iso_utc, money_str
from . import repository


QUERIES = (
    "payables_overview",
    "payables_list",
    "realized_totals",
    "spending_by_category",
    "accounts",
    "consolidated_realized_totals",
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

_MONTHS_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

_STATUS_LABELS = {
    "pending": "pendentes",
    "partial": "parcialmente pagas",
    "paid": "quitadas",
    "canceled": "canceladas",
}


# ---------------------------------------------------------------------------
# Período.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Period:
    """Período resolvido de uma consulta, com o texto que o declara."""

    kind: str               # month | year | range | all
    start: Optional[date]   # inclusivo
    end: Optional[date]     # inclusivo
    label: str
    declared: str
    ref: str                # parte estável das referências de fonte

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "label": self.label,
        }


def _as_date(value: Any, field: str) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise AiError("invalid_request", "Data inválida em %s." % field, details={"field": field})


def _as_int(value: Any, field: str) -> Optional[int]:
    """Inteiro vindo de fora (mês, ano, limite), ou ``None`` se ausente.

    Pela ferramenta o schema pydantic já garante o tipo, mas estas funções
    também são chamadas direto (ex.: uma rota repassando a query string).
    ``int("abc")`` levantaria ``ValueError`` cru, que não é ``AiError`` e
    sairia como erro 500 com stacktrace.

    A conversão passa pelo TEXTO do valor de propósito: ``int(True)`` daria 1 e
    ``int(2.7)`` daria 2 sem ninguém perceber, enquanto ``int("True")`` e
    ``int("2.7")`` falham, que é o que queremos para ``bool`` e ``float``.
    """
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise AiError("invalid_request", "Número inteiro inválido em %s." % field, details={"field": field})


def resolve_period(
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Any = None,
    date_to: Any = None,
    competency: bool = False,
) -> Period:
    """Traduz os filtros em um período explícito.

    ``competency=True`` é o modo das contas a pagar: o filtro é a competência
    (mês/ano), não a data de ocorrência; intervalo de datas não se aplica.

    * mês + ano -> mensal; só ano -> anual; nada -> global.
    * mês sem ano é erro: "outubro" de qual ano? Não adivinhamos.
    """
    start = _as_date(date_from, "date_from")
    end = _as_date(date_to, "date_to")
    month = _as_int(month, "month")
    year = _as_int(year, "year")
    if month is not None and year is None:
        raise AiError("invalid_request", "Informe o ano junto com o mês.", details={"field": "year"})
    if (month is not None or year is not None) and (start is not None or end is not None):
        raise AiError("invalid_request", "Use mês/ano OU intervalo de datas, não os dois.")
    if month is not None and not 1 <= month <= 12:
        raise AiError("invalid_request", "Mês inválido.", details={"field": "month"})
    if year is not None and not 2000 <= year <= 2100:
        raise AiError("invalid_request", "Ano inválido.", details={"field": "year"})

    basis = "competência" if competency else "ocorrência"
    if month is not None:
        last_day = calendar.monthrange(year, month)[1]
        return Period(
            kind="month",
            start=date(year, month, 1),
            end=date(year, month, last_day),
            label="%s/%d" % (_MONTHS_PT[month - 1], year),
            declared="competência mensal" if competency else "mês de ocorrência",
            ref="%04d-%02d" % (year, month),
        )
    if year is not None:
        year = int(year)
        return Period(
            kind="year",
            start=date(year, 1, 1),
            end=date(year, 12, 31),
            label="ano de %d" % year,
            declared="%s anual" % basis,
            ref="%04d" % year,
        )
    if start is not None or end is not None:
        if competency:
            raise AiError(
                "invalid_request",
                "Contas a pagar são filtradas por competência (mês e ano), não por intervalo de datas.",
            )
        if start is None or end is None:
            raise AiError("invalid_request", "Informe o início e o fim do intervalo.")
        if end < start:
            raise AiError("invalid_request", "O fim do intervalo é anterior ao início.", details={"field": "date_to"})
        return Period(
            kind="range",
            start=start,
            end=end,
            label="%s a %s" % (start.strftime("%d/%m/%Y"), end.strftime("%d/%m/%Y")),
            declared="intervalo de datas de ocorrência",
            ref="%s..%s" % (start.isoformat(), end.isoformat()),
        )
    return Period(
        kind="all",
        start=None,
        end=None,
        label="todo o histórico",
        declared="global (todas as competências)" if competency else "global (todo o histórico)",
        ref="all",
    )


# ---------------------------------------------------------------------------
# Montagem de fatos e fontes.
# ---------------------------------------------------------------------------
def _space_scope(ctx: ExecutionContext, period: Period) -> Dict[str, Any]:
    return {
        "financial_space_id": ctx.financial_space_id,
        "kind": ctx.space_kind,
        "name": ctx.space_name,
        "declared": period.declared,
    }


def _fact(
    *,
    key: str,
    label: str,
    value: Optional[str],
    unit: str,
    period: Period,
    scope: Dict[str, Any],
    source_ref: str,
    as_of: str,
    currency: Optional[str] = None,
    missing_reason: Optional[str] = None,
) -> Fact:
    # Invariante: ou há valor, ou há o motivo da ausência. Nunca os dois vazios
    # (viraria "zero" na leitura) e nunca os dois preenchidos.
    if (value is None) == (missing_reason is None):
        raise AiError("internal_error")
    return Fact(
        key=key,
        label=label,
        value=value,
        unit=unit,
        period=period.to_dict(),
        scope=dict(scope),
        source_refs=[source_ref],
        as_of=as_of,
        currency=currency if value is not None and unit == "money" else None,
        missing_reason=missing_reason,
    )


def _money_fact(
    key: str,
    label: str,
    amount: Optional[Decimal],
    currency: Optional[str],
    missing_reason: str,
    **common: Any
) -> Fact:
    if amount is None:
        return _fact(key=key, label=label, value=None, unit="money", missing_reason=missing_reason, **common)
    return _fact(key=key, label=label, value=money_str(amount), unit="money", currency=currency, **common)


def _count_fact(key: str, label: str, count: Optional[int], missing_reason: str, **common: Any) -> Fact:
    if count is None:
        return _fact(key=key, label=label, value=None, unit="count", missing_reason=missing_reason, **common)
    return _fact(key=key, label=label, value=str(int(count)), unit="count", **common)


def _require_no(value: Any, field: str, query: str) -> None:
    """Filtro que não se aplica à consulta é erro, não é ignorado em silêncio.

    Ignorar faria o modelo acreditar que o número já está filtrado por conta ou
    por data quando não está.
    """
    if value is not None:
        raise AiError(
            "invalid_request",
            "O filtro %s não se aplica à consulta %s." % (field, query),
            details={"field": field},
        )


def _account_in_scope(ctx: ExecutionContext, account_id: Any) -> Optional[str]:
    if account_id is None:
        return None
    try:
        normalized = str(uuid.UUID(str(account_id)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("invalid_request", "Identificador de conta inválido.", details={"field": "account_id"})
    if normalized not in ctx.allowed_account_ids:
        # Conta de outro espaço ou tenant responde como inexistente.
        raise AiError("not_found", "Conta não encontrada neste espaço.")
    return normalized


# ---------------------------------------------------------------------------
# payables_overview
# ---------------------------------------------------------------------------
@repository.guarded("read.payables_overview")
def payables_overview(
    pool, ctx: ExecutionContext, *, month: Optional[int] = None, year: Optional[int] = None
) -> ToolResult:
    """Previsto, pago, restante e contagem por status das contas a pagar."""
    period = resolve_period(month=month, year=year, competency=True)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        rows = repository.payables_summary(cursor, ctx, period.start, period.end)
        as_of = iso_utc(repository.database_now(cursor))

    source_ref = "sql:payables:%s:%s" % (ctx.financial_space_id, period.ref)
    common = {"period": period, "scope": _space_scope(ctx, period), "source_ref": source_ref, "as_of": as_of}
    facts = []  # type: List[Fact]
    total_rows = sum(int(row["total"]) for row in rows)

    if not rows:
        reason = "Não há contas a pagar neste espaço para %s (%s)." % (period.label, period.declared)
        for key, label in (
            ("payables.expected", "Previsto"),
            ("payables.paid", "Pago"),
            ("payables.remaining", "Falta pagar"),
        ):
            facts.append(_money_fact(key, label, None, None, reason, **common))
        for status in repository.PAYABLE_STATUSES:
            facts.append(
                _count_fact("payables.count.%s" % status, "Contas %s" % _STATUS_LABELS[status], None, reason, **common)
            )
    for row in rows:
        currency = row["currency"]
        active = int(row["total"]) - int(row["canceled"])
        only_canceled = "Só há contas canceladas em %s (%s)." % (period.label, period.declared)
        # Com contas ativas, "nada resta" é um zero verdadeiro; sem contas
        # ativas, não há o que somar e o valor fica ausente.
        expected = row["expected"] if active else None
        paid = row["paid"] if active else None
        remaining = (row["remaining"] if row["remaining"] is not None else Decimal("0")) if active else None
        facts.append(_money_fact("payables.expected", "Previsto", expected, currency, only_canceled, **common))
        facts.append(_money_fact("payables.paid", "Pago", paid, currency, only_canceled, **common))
        facts.append(_money_fact("payables.remaining", "Falta pagar", remaining, currency, only_canceled, **common))
        counts = {
            "pending": row["pending"],
            "partial": row["partial"],
            "paid": row["paid_count"],
            "canceled": row["canceled"],
        }
        for status in repository.PAYABLE_STATUSES:
            fact = _count_fact(
                "payables.count.%s" % status, "Contas %s" % _STATUS_LABELS[status], counts[status], "", **common
            )
            # Com mais de uma moeda, a contagem é por moeda; o escopo diz qual.
            fact.scope["currency"] = currency
            facts.append(fact)

    source = Source(
        ref=source_ref,
        kind="sql",
        label="Contas a pagar de %s (%s)" % (period.label, period.declared),
        as_of=as_of,
        extra={
            "financial_space_id": ctx.financial_space_id,
            "rows": total_rows,
            "tables": ["payables", "payable_payments"],
            # ``complete`` afirma que a soma cobriu TODAS as linhas do escopo:
            # é uma agregação no banco, sem paginação nem limite de linhas.
            "complete": True,
        },
    )
    return ToolResult(
        data={"query": "payables_overview", "period": period.to_dict(), "declared_scope": period.declared},
        facts=facts,
        sources=[source],
    )


# ---------------------------------------------------------------------------
# payables_list (paginada)
# ---------------------------------------------------------------------------
def _cursor_binding(ctx: ExecutionContext, query: str, period: Period) -> str:
    material = canonical_json(
        {"tenant_id": ctx.tenant_id, "financial_space_id": ctx.financial_space_id, "query": query, "period": period.ref}
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _encode_cursor(binding: str, due_date: Optional[date], payable_id: str) -> str:
    raw = canonical_json({"b": binding, "k": [due_date.isoformat() if due_date else None, str(payable_id)]})
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(token: str, binding: str) -> Tuple[Optional[date], str]:
    """Abre o cursor e confere que ele pertence a ESTE escopo e a ESTA consulta.

    O cursor não é assinado e não precisa ser: ele só carrega a posição
    (vencimento, id) da última linha. Forjar um cursor não amplia o acesso,
    porque a consulta reaplica tenant e espaço do contexto. O vínculo serve
    para recusar o reuso em outra consulta ou outro escopo, que devolveria uma
    página sem sentido.
    """
    invalid = AiError("invalid_request", "Cursor inválido.", details={"field": "cursor"})
    if not isinstance(token, str) or not 1 <= len(token) <= 400:
        raise invalid
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeError):
        raise invalid
    if not isinstance(payload, dict) or not isinstance(payload.get("k"), list) or len(payload["k"]) != 2:
        raise invalid
    if payload.get("b") != binding:
        raise AiError(
            "invalid_request",
            "Este cursor pertence a outra consulta ou a outro escopo.",
            details={"field": "cursor"},
        )
    due_raw, id_raw = payload["k"]
    try:
        due = date.fromisoformat(due_raw) if due_raw is not None else None
        payable_id = str(uuid.UUID(str(id_raw)))
    except (ValueError, TypeError, AttributeError):
        raise invalid
    return due, payable_id


@repository.guarded("read.payables_list")
def payables_list(
    pool,
    ctx: ExecutionContext,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    cursor: Optional[str] = None,
    limit: Optional[int] = None,
) -> ToolResult:
    """Lista paginada de contas a pagar, por vencimento."""
    period = resolve_period(month=month, year=year, competency=True)
    requested = _as_int(limit, "limit")
    size = DEFAULT_PAGE_SIZE if requested is None else requested
    if not 1 <= size <= MAX_PAGE_SIZE:
        raise AiError("invalid_request", "Limite de página inválido.", details={"field": "limit"})
    binding = _cursor_binding(ctx, "payables_list", period)
    after = _decode_cursor(cursor, binding) if cursor is not None else None

    with scoped_tx(pool, ctx.tenant_id) as db_cursor:
        total = repository.payables_count(db_cursor, ctx, period.start, period.end)
        # Uma linha a mais só para saber se existe próxima página.
        rows = repository.payables_page(db_cursor, ctx, period.start, period.end, after, size + 1)
        as_of = iso_utc(repository.database_now(db_cursor))

    has_more = len(rows) > size
    rows = rows[:size]
    source_ref = "sql:payables:%s:%s:list" % (ctx.financial_space_id, period.ref)
    items = []
    for row in rows:
        canceled = row["status"] == "canceled"
        items.append(
            {
                "payable_id": str(row["id"]),
                "title": row["title"],
                "status": row["status"],
                "currency": row["currency"],
                "amount_expected": money_str(row["amount_expected"]),
                "paid": money_str(row["paid"]),
                "remaining": None if canceled else money_str(
                    repository.remaining_amount(row["amount_expected"], row["paid"])
                ),
                "due_date": row["due_date"].isoformat() if row["due_date"] else None,
                "competency_month": row["competency_month"].strftime("%Y-%m"),
                "source_ref": source_ref,
            }
        )
    next_cursor = _encode_cursor(binding, rows[-1]["due_date"], rows[-1]["id"]) if has_more and rows else None

    common = {"period": period, "scope": _space_scope(ctx, period), "source_ref": source_ref, "as_of": as_of}
    facts = [
        _count_fact(
            "payables.list.total",
            "Contas a pagar encontradas",
            total if total else None,
            "Não há contas a pagar neste espaço para %s (%s)." % (period.label, period.declared),
            **common
        )
    ]
    source = Source(
        ref=source_ref,
        kind="sql",
        label="Lista de contas a pagar de %s (%s)" % (period.label, period.declared),
        as_of=as_of,
        extra={"financial_space_id": ctx.financial_space_id, "rows": len(items), "total": total},
    )
    return ToolResult(
        data={
            "query": "payables_list",
            "period": period.to_dict(),
            "declared_scope": period.declared,
            "items": items,
            "next_cursor": next_cursor,
        },
        facts=facts,
        sources=[source],
    )


# ---------------------------------------------------------------------------
# Realizado.
# ---------------------------------------------------------------------------
_REALIZED_RULE = "somente lançamentos de extrato OFX com status pago"

_REALIZED_KEYS = (
    # (tipo no banco, chave do fato, rótulo, motivo de ausência)
    ("income", "realized.income", "Receitas realizadas", "Não há receitas de extrato OFX pagas"),
    ("expense", "realized.expense", "Despesas realizadas", "Não há despesas de extrato OFX pagas"),
    (
        "transfer",
        "realized.transfers",
        "Transferências enviadas (não são receita nem despesa)",
        "Não há transferências de extrato OFX",
    ),
)


def _totals_by_currency(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Decimal]]:
    """{moeda: {tipo: total}} somente com os tipos que têm linhas."""
    result = {}  # type: Dict[str, Dict[str, Decimal]]
    for row in rows:
        result.setdefault(row["currency"], {})[row["type"]] = Decimal(row["total"])
    return result


def _realized_facts(
    totals: Dict[str, Dict[str, Decimal]], prefix: str, where: str, common: Dict[str, Any]
) -> List[Fact]:
    """Fatos de receita, despesa, transferência e resultado, por moeda.

    Receita, despesa e transferência são fatos separados. O resultado é
    receitas − despesas; transferência não entra nele.
    """
    facts = []  # type: List[Fact]
    currencies = sorted(totals) or [None]
    for currency in currencies:
        by_type = totals.get(currency, {}) if currency else {}
        for tx_type, key, label, missing in _REALIZED_KEYS:
            facts.append(
                _money_fact(prefix + key, label, by_type.get(tx_type), currency, "%s %s." % (missing, where), **common)
            )
        income, expense = by_type.get("income"), by_type.get("expense")
        # O resultado existe se houver ao menos uma receita ou despesa. O lado
        # sem lançamentos contribui com nada, e o fato desse lado segue ausente.
        net = None if income is None and expense is None else (income or Decimal("0")) - (expense or Decimal("0"))
        facts.append(
            _money_fact(
                prefix + "realized.net",
                "Resultado realizado (receitas − despesas, sem transferências)",
                net,
                currency,
                "Não há receitas nem despesas de extrato OFX pagas %s." % where,
                **common
            )
        )
    return facts


def _transactions_ref(ctx: ExecutionContext, period: Period, account_id: Optional[str]) -> str:
    ref = "sql:transactions:%s:%s" % (ctx.financial_space_id, period.ref)
    return ref + (":account:%s" % account_id if account_id else "")


@repository.guarded("read.realized_totals")
def realized_totals(
    pool,
    ctx: ExecutionContext,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Any = None,
    date_to: Any = None,
    account_id: Optional[str] = None,
) -> ToolResult:
    """Receitas e despesas realizadas (regra canônica), opcionalmente por conta."""
    period = resolve_period(month=month, year=year, date_from=date_from, date_to=date_to)
    account = _account_in_scope(ctx, account_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        rows = repository.realized_by_type(cursor, ctx, period.start, period.end, account)
        as_of = iso_utc(repository.database_now(cursor))

    source_ref = _transactions_ref(ctx, period, account) + ":realized"
    scope = _space_scope(ctx, period)
    if account:
        scope["account_id"] = account
    common = {"period": period, "scope": scope, "source_ref": source_ref, "as_of": as_of}
    where = "em %s" % period.label if period.kind != "all" else "no histórico"
    facts = _realized_facts(_totals_by_currency(rows), "", where, common)
    source = Source(
        ref=source_ref,
        kind="sql",
        label="Realizado de %s (%s)" % (period.label, _REALIZED_RULE),
        as_of=as_of,
        extra={
            "financial_space_id": ctx.financial_space_id,
            "rows": sum(int(row["items"]) for row in rows),
            "rule": _REALIZED_RULE,
            "account_id": account,
            "tables": ["transactions"],
        },
    )
    return ToolResult(
        data={
            "query": "realized_totals",
            "period": period.to_dict(),
            "declared_scope": period.declared,
            "rule": _REALIZED_RULE,
        },
        facts=facts,
        sources=[source],
    )


@repository.guarded("read.spending_by_category")
def spending_by_category(
    pool,
    ctx: ExecutionContext,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Any = None,
    date_to: Any = None,
    account_id: Optional[str] = None,
) -> ToolResult:
    """Despesas realizadas por categoria (regra canônica)."""
    period = resolve_period(month=month, year=year, date_from=date_from, date_to=date_to)
    account = _account_in_scope(ctx, account_id)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        rows = repository.realized_expense_by_category(cursor, ctx, period.start, period.end, account)
        as_of = iso_utc(repository.database_now(cursor))

    source_ref = _transactions_ref(ctx, period, account) + ":by_category"
    scope = _space_scope(ctx, period)
    if account:
        scope["account_id"] = account
    common = {"period": period, "scope": scope, "source_ref": source_ref, "as_of": as_of}
    facts = []  # type: List[Fact]
    categories = []
    totals = {}  # type: Dict[str, Decimal]
    for row in rows:
        amount = Decimal(row["total"])
        totals[row["currency"]] = totals.get(row["currency"], Decimal("0")) + amount
        facts.append(
            _money_fact(
                "spending.category.%s" % row["category_id"],
                "Despesas em %s" % row["category_name"],
                amount,
                row["currency"],
                "",
                **common
            )
        )
        categories.append(
            {
                "category_id": str(row["category_id"]),
                "name": row["category_name"],
                "currency": row["currency"],
                "total": money_str(amount),
                "items": int(row["items"]),
            }
        )
    if not rows:
        where = "em %s" % period.label if period.kind != "all" else "no histórico"
        facts.append(
            _money_fact(
                "spending.total", "Despesas realizadas", None, None,
                "Não há despesas de extrato OFX pagas %s." % where, **common
            )
        )
    for currency in sorted(totals):
        # O total é a soma exata (Decimal) das categorias devolvidas.
        facts.append(_money_fact("spending.total", "Despesas realizadas", totals[currency], currency, "", **common))

    source = Source(
        ref=source_ref,
        kind="sql",
        label="Despesas por categoria de %s (%s)" % (period.label, _REALIZED_RULE),
        as_of=as_of,
        extra={
            "financial_space_id": ctx.financial_space_id,
            "rows": sum(int(row["items"]) for row in rows),
            "rule": _REALIZED_RULE,
            "account_id": account,
            "tables": ["transactions", "categories"],
        },
    )
    return ToolResult(
        data={
            "query": "spending_by_category",
            "period": period.to_dict(),
            "declared_scope": period.declared,
            "rule": _REALIZED_RULE,
            "categories": categories,
        },
        facts=facts,
        sources=[source],
    )


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------
@repository.guarded("read.accounts")
def accounts(pool, ctx: ExecutionContext) -> ToolResult:
    """Contas vinculadas ao espaço da execução."""
    period = resolve_period()
    period = replace(period, declared="contas vinculadas a este espaço")
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        rows = repository.space_accounts(cursor, ctx)
        as_of = iso_utc(repository.database_now(cursor))
    source_ref = "sql:accounts:%s" % ctx.financial_space_id
    common = {"period": period, "scope": _space_scope(ctx, period), "source_ref": source_ref, "as_of": as_of}
    facts = [
        _count_fact(
            "accounts.count",
            "Contas neste espaço",
            len(rows) if rows else None,
            "Nenhuma conta está vinculada a este espaço financeiro.",
            **common
        )
    ]
    source = Source(
        ref=source_ref,
        kind="sql",
        label="Contas do espaço %s" % ctx.space_name,
        as_of=as_of,
        extra={"financial_space_id": ctx.financial_space_id, "rows": len(rows), "tables": ["accounts"]},
    )
    # Saldo fica de fora de propósito: o V2 só guarda ``initial_balance`` e
    # ainda não há fórmula de saldo aprovada. Melhor não informar do que
    # informar um número que o app não reconhece.
    data_accounts = [
        {
            "account_id": str(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "institution": row["institution"],
            "currency": row["currency"],
        }
        for row in rows
    ]
    return ToolResult(data={"query": "accounts", "accounts": data_accounts}, facts=facts, sources=[source])


# ---------------------------------------------------------------------------
# consolidated_realized_totals
# ---------------------------------------------------------------------------
@repository.guarded("read.consolidated_realized_totals")
def consolidated_realized_totals(
    pool,
    ctx: ExecutionContext,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Any = None,
    date_to: Any = None,
) -> ToolResult:
    """Realizado somado entre TODOS os espaços ativos do tenant.

    Só é atendido se o ator participa e tem grant ativo com ``finance.read`` em
    cada espaço incluído. Faltando um, a resposta é ``capability_denied``: um
    consolidado parcial apresentado como total seria um número errado.

    A resposta traz a composição por espaço (pessoal x negócio) e mantém
    receita, despesa, transferência e resultado como fatos distintos.
    """
    period = resolve_period(month=month, year=year, date_from=date_from, date_to=date_to)
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        spaces = repository.tenant_spaces(cursor, ctx)
        for space in spaces:
            space_ctx = replace(ctx, financial_space_id=str(space["id"]))
            # Reusa a definição de "grant ativo" da política (uma só no projeto).
            grants = policy.load_active_grants(cursor, space_ctx)
            if not space["is_member"] or policy.best_grant(grants, "finance.read") is None:
                raise AiError(
                    "capability_denied",
                    "O relatório consolidado exige autorização de leitura em todos os espaços financeiros.",
                )
        if len(spaces) < 2:
            raise AiError("invalid_request", "Só há um espaço financeiro: não há o que consolidar.")
        rows = repository.realized_by_space(cursor, ctx, [space["id"] for space in spaces], period.start, period.end)
        as_of = iso_utc(repository.database_now(cursor))

    where = "em %s" % period.label if period.kind != "all" else "no histórico"
    facts = []  # type: List[Fact]
    sources = []  # type: List[Source]
    composition = []
    consolidated = {}  # type: Dict[str, Dict[str, Decimal]]
    for space in spaces:
        space_id = str(space["id"])
        space_rows = [row for row in rows if str(row["financial_space_id"]) == space_id]
        totals = _totals_by_currency(space_rows)
        source_ref = "sql:transactions:%s:%s:realized" % (space_id, period.ref)
        scope = {
            "financial_space_id": space_id,
            "kind": space["kind"],
            "name": space["name"],
            "declared": "%s; parcela do espaço %s" % (period.declared, space["name"]),
        }
        common = {"period": period, "scope": scope, "source_ref": source_ref, "as_of": as_of}
        facts.extend(_realized_facts(totals, "", where, common))
        sources.append(
            Source(
                ref=source_ref,
                kind="sql",
                label="Realizado do espaço %s em %s (%s)" % (space["name"], period.label, _REALIZED_RULE),
                as_of=as_of,
                extra={
                    "financial_space_id": space_id,
                    "space_kind": space["kind"],
                    "rows": sum(int(row["items"]) for row in space_rows),
                    "rule": _REALIZED_RULE,
                },
            )
        )
        entry = {"financial_space_id": space_id, "kind": space["kind"], "name": space["name"], "by_currency": {}}
        for currency, by_type in sorted(totals.items()):
            entry["by_currency"][currency] = {
                tx_type: money_str(by_type[tx_type]) if tx_type in by_type else None
                for tx_type in ("income", "expense", "transfer")
            }
            target = consolidated.setdefault(currency, {})
            for tx_type, amount in by_type.items():
                # Soma exata em Decimal, tipo a tipo: receita só soma com receita.
                target[tx_type] = target.get(tx_type, Decimal("0")) + amount
        composition.append(entry)

    names = " + ".join("%s (%s)" % (space["name"], space["kind"]) for space in spaces)
    consolidated_ref = "sql:transactions:consolidated:%s:%s:realized" % (ctx.tenant_id, period.ref)
    consolidated_scope = {
        "financial_space_id": None,
        "kind": "consolidated",
        "declared": "%s; consolidado de %d espaços: %s" % (period.declared, len(spaces), names),
        "composition": [
            {"financial_space_id": str(space["id"]), "kind": space["kind"], "name": space["name"]}
            for space in spaces
        ],
    }
    common = {"period": period, "scope": consolidated_scope, "source_ref": consolidated_ref, "as_of": as_of}
    facts.extend(_realized_facts(consolidated, "consolidated.", where + " em nenhum dos espaços", common))
    sources.append(
        Source(
            ref=consolidated_ref,
            kind="sql",
            label="Realizado consolidado em %s: %s" % (period.label, names),
            as_of=as_of,
            extra={
                "composition": [source.ref for source in sources],
                "rows": sum(int(row["items"]) for row in rows),
                "rule": _REALIZED_RULE,
            },
        )
    )
    return ToolResult(
        data={
            "query": "consolidated_realized_totals",
            "period": period.to_dict(),
            "declared_scope": consolidated_scope["declared"],
            "rule": _REALIZED_RULE,
            "composition": composition,
        },
        facts=facts,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Despacho da ferramenta.
# ---------------------------------------------------------------------------
def run_query(
    pool,
    ctx: ExecutionContext,
    query: str,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    account_id: Optional[str] = None,
    date_from: Any = None,
    date_to: Any = None,
    cursor: Optional[str] = None,
    limit: Optional[int] = None,
) -> ToolResult:
    """Executa uma consulta da lista fechada ``QUERIES``."""
    if query not in QUERIES:
        raise AiError("invalid_request", "Consulta desconhecida.", details={"field": "query"})

    if query in ("payables_overview", "payables_list"):
        _require_no(account_id, "account_id", query)
        _require_no(date_from, "date_from", query)
        _require_no(date_to, "date_to", query)
        if query == "payables_overview":
            _require_no(cursor, "cursor", query)
            _require_no(limit, "limit", query)
            return payables_overview(pool, ctx, month=month, year=year)
        return payables_list(pool, ctx, month=month, year=year, cursor=cursor, limit=limit)

    _require_no(cursor, "cursor", query)
    _require_no(limit, "limit", query)
    if query == "accounts":
        for field, value in (
            ("month", month), ("year", year), ("account_id", account_id),
            ("date_from", date_from), ("date_to", date_to),
        ):
            _require_no(value, field, query)
        return accounts(pool, ctx)
    if query == "consolidated_realized_totals":
        _require_no(account_id, "account_id", query)
        return consolidated_realized_totals(
            pool, ctx, month=month, year=year, date_from=date_from, date_to=date_to
        )
    handler = realized_totals if query == "realized_totals" else spending_by_category
    return handler(
        pool, ctx, month=month, year=year, date_from=date_from, date_to=date_to, account_id=account_id
    )
