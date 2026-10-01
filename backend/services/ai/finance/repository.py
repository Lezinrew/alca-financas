"""Acesso financeiro ao PostgreSQL V2, sempre preso ao escopo da execução.

Por que um módulo só para SQL
-----------------------------
As tabelas financeiras de ``0001_core.sql`` (accounts, transactions, payables,
payable_payments, categories, import_batches) NÃO têm RLS: só as tabelas novas
da ``0002`` têm. Logo, o isolamento delas depende inteiramente dos filtros
escritos aqui. Concentrar esse SQL em um arquivo permite conferir, de uma vez,
que TODA consulta leva:

* ``tenant_id`` do contexto (``ctx.tenant_id``);
* o espaço financeiro do contexto, pelos vínculos da ``0002``:
  contas via ``financial_space_accounts`` E dentro de
  ``ctx.allowed_account_ids``; contas a pagar via ``financial_space_payables``.

Conta ou conta a pagar sem vínculo fica invisível: os ``JOIN`` com as tabelas
de vínculo são internos, então ausência de vínculo nunca vira acesso amplo.

Nenhuma função daqui engole exceção. Falha de consulta sobe como erro; devolver
lista vazia em caso de falha faria a IA dizer "não há dados" quando a verdade é
"não consegui consultar".

As funções recebem um ``cursor`` já aberto por ``services.ai.db.scoped_tx``:
quem chama decide o tamanho da transação (uma leitura isolada ou o efeito
financeiro inteiro, com auditoria e outbox).
"""

from __future__ import annotations

import functools
import logging
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import psycopg2
import psycopg2.extensions

from ..db import jsonb
from ..errors import AiError
from ..types import ExecutionContext


logger = logging.getLogger("ai.finance")


# ---------------------------------------------------------------------------
# Regra canônica do realizado (NÃO alterar sem decisão do titular).
#
# Só entra em total realizado a transação cujo ``source_file`` termina em
# ".ofx" e cujo status é 'paid'. ``entry_source`` NÃO é o critério: o script de
# sincronização rebaixa OFX não canônico trocando o ``source_file`` para
# "legacy:...:excluded" sem mexer em ``entry_source``.
#
# Este é o ÚNICO lugar em que a regra é escrita. Toda consulta de realizado usa
# ``realized_sql``; toda decisão em Python usa ``is_canonical_source_file``.
# ---------------------------------------------------------------------------
CANONICAL_SOURCE_SUFFIX = ".ofx"
REALIZED_STATUS = "paid"


def realized_sql(alias: str = "t") -> str:
    """Predicado SQL da regra canônica para a tabela ``transactions``.

    O ``%%`` é o escape de ``%`` do psycopg2: o fragmento só pode ser usado em
    consultas executadas COM parâmetros (todas as daqui levam ``tenant_id``).
    """
    return "(lower({a}.source_file) LIKE '%%{suffix}' AND {a}.status = '{status}')".format(
        a=alias, suffix=CANONICAL_SOURCE_SUFFIX, status=REALIZED_STATUS
    )


def is_canonical_source_file(name: Any) -> bool:
    """Versão em Python do mesmo sufixo, para validar o nome antes de gravar."""
    return isinstance(name, str) and name.lower().endswith(CANONICAL_SOURCE_SUFFIX)


# ---------------------------------------------------------------------------
# Status derivado de conta a pagar. ``payables`` não tem coluna de status: ele
# sai de ``canceled_at`` e da soma dos pagamentos não revertidos.
# A regra existe em SQL (listas e somas) e em Python (cálculo do "depois" de
# uma proposta, que ainda não está no banco). Um teste compara as duas.
# ---------------------------------------------------------------------------
PAYABLE_STATUSES = ("pending", "partial", "paid", "canceled")

_PAYABLE_STATUS_SQL = (
    "CASE WHEN s.canceled_at IS NOT NULL THEN 'canceled' "
    "WHEN s.paid >= s.amount_expected THEN 'paid' "
    "WHEN s.paid > 0 THEN 'partial' "
    "ELSE 'pending' END"
)


def derive_payable_status(amount_expected: Decimal, paid: Decimal, canceled: bool) -> str:
    if canceled:
        return "canceled"
    if paid >= amount_expected:
        return "paid"
    if paid > 0:
        return "partial"
    return "pending"


def remaining_amount(amount_expected: Decimal, paid: Decimal) -> Decimal:
    """Saldo restante, nunca negativo (pagamento acima do previsto não gera crédito)."""
    return max(amount_expected - paid, Decimal("0"))


# ---------------------------------------------------------------------------
# Erros de banco.
# ---------------------------------------------------------------------------
def guarded(area: str) -> Callable:
    """Converte erro do driver em ``AiError("internal_error")``.

    A mensagem do PostgreSQL pode conter valores das linhas (ex.: a chave que
    violou um índice). Por isso o log leva só o SQLSTATE e a exceção original
    fica encadeada para depuração local, sem ir para resposta nem auditoria.
    """

    def decorator(function: Callable) -> Callable:
        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return function(*args, **kwargs)
            except psycopg2.Error as exc:
                logger.error("finance_db_error area=%s pgcode=%s", area, getattr(exc, "pgcode", None))
                raise AiError("internal_error") from exc

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Leitura de colunas ``uuid[]``.
# ---------------------------------------------------------------------------
# O psycopg2 só converte ``uuid[]`` em lista se alguém registrar um conversor;
# sem isso a coluna chega como o TEXTO cru ``"{id1,id2}"``. ``policy.Grant``
# monta ``account_ids`` iterando esse valor, e iterar um texto devolve
# caracteres: o grant restrito a contas ficava com um conjunto de letras e
# nunca reconhecia conta nenhuma.
#
# A correção definitiva é da política (pedido registrado para a espinha). Aqui
# o contorno é local e estreito: o conversor é registrado só no CURSOR da
# transação do efeito. Não muda o que outras partes do sistema recebem das
# mesmas conexões do pool, e some quando o cursor fecha. 2951 é o OID fixo do
# tipo ``uuid[]`` no PostgreSQL.
_UUID_ARRAY_AS_TEXT_LIST = psycopg2.extensions.new_array_type((2951,), "UUID_ARRAY_AS_TEXT_LIST", psycopg2.STRING)


def read_uuid_arrays_as_lists(cursor) -> None:
    """Faz ESTE cursor devolver colunas ``uuid[]`` como lista de strings."""
    psycopg2.extensions.register_type(_UUID_ARRAY_AS_TEXT_LIST, cursor)


# ---------------------------------------------------------------------------
# Escopo.
# ---------------------------------------------------------------------------
def _scope(ctx: ExecutionContext) -> Dict[str, Any]:
    """Parâmetros de escopo comuns. Vêm sempre do contexto do servidor."""
    return {
        "tenant_id": ctx.tenant_id,
        "space_id": ctx.financial_space_id,
        # Lista ordenada só para o SQL ficar determinístico nos logs do banco.
        "accounts": sorted(ctx.allowed_account_ids),
    }


def _date_range(column: str, start: Optional[date], end: Optional[date], params: Dict[str, Any]) -> str:
    """Filtro de período com as duas pontas INCLUSIVAS (datas locais)."""
    clause = ""
    if start is not None:
        clause += " AND {c} >= %(period_start)s".format(c=column)
        params["period_start"] = start
    if end is not None:
        clause += " AND {c} <= %(period_end)s".format(c=column)
        params["period_end"] = end
    return clause


def database_now(cursor) -> datetime:
    """Relógio do banco, lido DEPOIS das consultas da leitura.

    Serve de ``as_of``: é um limite superior do que foi lido (nenhum dado
    confirmado depois desse instante entrou no resultado).
    """
    cursor.execute("SELECT clock_timestamp() AS as_of")
    return cursor.fetchone()["as_of"]


# ---------------------------------------------------------------------------
# Contas a pagar.
# ---------------------------------------------------------------------------
# Subconsulta-base: contas a pagar DO ESPAÇO, com a soma dos pagamentos
# válidos (``reversed_at IS NULL``). O LATERAL soma por conta a pagar e evita
# multiplicar linhas.
_PAYABLES_SCOPED = """
    SELECT p.id, p.title, p.amount_expected, p.currency, p.due_date, p.competency_month,
           p.canceled_at, p.updated_at,
           COALESCE(pay.paid, 0) AS paid,
           COALESCE(pay.payment_count, 0) AS payment_count
    FROM payables p
    JOIN financial_space_payables l
      ON l.payable_id = p.id AND l.tenant_id = p.tenant_id
    LEFT JOIN LATERAL (
        SELECT sum(pp.amount) AS paid, count(*) AS payment_count
        FROM payable_payments pp
        WHERE pp.tenant_id = p.tenant_id
          AND pp.payable_id = p.id
          AND pp.reversed_at IS NULL
    ) pay ON true
    WHERE p.tenant_id = %(tenant_id)s
      AND l.tenant_id = %(tenant_id)s
      AND l.financial_space_id = %(space_id)s
"""


def payables_summary(cursor, ctx: ExecutionContext, start: Optional[date], end: Optional[date]) -> List[Dict[str, Any]]:
    """Previsto, pago, restante e contagem por status, por moeda.

    Uma única instrução SQL: todos os números saem do mesmo snapshot, então
    previsto, pago e restante nunca ficam inconsistentes entre si.

    * canceladas não entram em nenhuma soma;
    * ``paid`` inclui o que já foi pago nas parciais;
    * ``remaining`` soma só ``pending`` e ``partial``.
    """
    params = _scope(ctx)
    period = _date_range("p.competency_month", start, end, params)
    cursor.execute(
        """
        SELECT q.currency,
               count(*) AS total,
               count(*) FILTER (WHERE q.status = 'pending') AS pending,
               count(*) FILTER (WHERE q.status = 'partial') AS partial,
               count(*) FILTER (WHERE q.status = 'paid') AS paid_count,
               count(*) FILTER (WHERE q.status = 'canceled') AS canceled,
               sum(q.amount_expected) FILTER (WHERE q.status <> 'canceled') AS expected,
               sum(q.paid) FILTER (WHERE q.status <> 'canceled') AS paid,
               sum(q.amount_expected - q.paid) FILTER (WHERE q.status IN ('pending', 'partial')) AS remaining
        FROM (
            SELECT s.*, """ + _PAYABLE_STATUS_SQL + """ AS status
            FROM (""" + _PAYABLES_SCOPED + period + """) s
        ) q
        GROUP BY q.currency
        ORDER BY q.currency
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def payables_count(cursor, ctx: ExecutionContext, start: Optional[date], end: Optional[date]) -> int:
    params = _scope(ctx)
    period = _date_range("p.competency_month", start, end, params)
    cursor.execute("SELECT count(*) AS total FROM (" + _PAYABLES_SCOPED + period + ") s", params)
    return int(cursor.fetchone()["total"])


def payables_page(
    cursor,
    ctx: ExecutionContext,
    start: Optional[date],
    end: Optional[date],
    after: Optional[Tuple[Optional[date], str]],
    limit: int,
) -> List[Dict[str, Any]]:
    """Página de contas a pagar por keyset (vencimento, id).

    Keyset em vez de OFFSET: a página seguinte continua correta mesmo se
    alguém criar ou cancelar contas entre uma chamada e outra. Sem vencimento
    vai para o fim ('infinity'), o que mantém a ordenação total e estável.
    """
    params = _scope(ctx)
    period = _date_range("p.competency_month", start, end, params)
    keyset = ""
    if after is not None:
        keyset = (
            " WHERE (COALESCE(s.due_date, 'infinity'::date), s.id)"
            " > (COALESCE(%(after_due)s::date, 'infinity'::date), %(after_id)s::uuid)"
        )
        params["after_due"] = after[0]
        params["after_id"] = after[1]
    params["limit"] = int(limit)
    cursor.execute(
        "SELECT s.*, " + _PAYABLE_STATUS_SQL + " AS status FROM (" + _PAYABLES_SCOPED + period + ") s"
        + keyset
        + " ORDER BY COALESCE(s.due_date, 'infinity'::date), s.id LIMIT %(limit)s",
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_payable(
    cursor, ctx: ExecutionContext, payable_id: str, *, for_update: bool = False
) -> Optional[Dict[str, Any]]:
    """Conta a pagar do espaço, com pago/restante/status. ``None`` fora do escopo.

    ``for_update`` trava a linha de ``payables`` até o fim da transação. O banco
    não limita a soma dos pagamentos por constraint; é esse lock que impede duas
    baixas simultâneas de calcularem o saldo sobre o mesmo valor antigo.
    """
    params = _scope(ctx)
    params["payable_id"] = str(payable_id)
    cursor.execute(
        """
        SELECT p.id, p.title, p.amount_expected, p.currency, p.due_date, p.competency_month,
               p.canceled_at, p.updated_at
        FROM payables p
        JOIN financial_space_payables l
          ON l.payable_id = p.id AND l.tenant_id = p.tenant_id
        WHERE p.tenant_id = %(tenant_id)s
          AND l.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND p.id = %(payable_id)s
        """ + (" FOR UPDATE OF p" if for_update else ""),
        params,
    )
    row = cursor.fetchone()
    if row is None:
        return None
    payable = dict(row)
    # A soma vem em instrução separada porque agregação não combina com
    # FOR UPDATE. Com a linha de ``payables`` travada, a soma é estável.
    cursor.execute(
        """
        SELECT COALESCE(sum(amount), 0) AS paid, count(*) AS payment_count
        FROM payable_payments
        WHERE tenant_id = %(tenant_id)s AND payable_id = %(payable_id)s AND reversed_at IS NULL
        """,
        params,
    )
    totals = cursor.fetchone()
    payable["paid"] = Decimal(totals["paid"])
    payable["payment_count"] = int(totals["payment_count"])
    payable["status"] = derive_payable_status(
        payable["amount_expected"], payable["paid"], payable["canceled_at"] is not None
    )
    payable["remaining"] = remaining_amount(payable["amount_expected"], payable["paid"])
    return payable


def insert_payable_payment(
    cursor,
    ctx: ExecutionContext,
    *,
    payable_id: str,
    amount: Decimal,
    paid_on: date,
    transaction_id: Optional[str],
    payment_method: Optional[str],
    notes: Optional[str],
) -> str:
    """Insere UMA linha de pagamento. Baixa parcial preserva cada lançamento.

    ``paid_at`` é ``timestamptz``, mas o que o titular informa é uma DATA local.
    Gravamos meio-dia UTC desse dia: assim a data lida de volta é a mesma em
    qualquer fuso entre UTC-11 e UTC+11 (inclui America/Sao_Paulo), sem
    depender de base de fusos instalada no servidor.
    """
    paid_at = datetime.combine(paid_on, time(12, 0), tzinfo=timezone.utc)
    cursor.execute(
        """
        INSERT INTO payable_payments (
            tenant_id, payable_id, created_by_user_id, transaction_id, amount, paid_at, payment_method, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (ctx.tenant_id, str(payable_id), ctx.actor_id, transaction_id, amount, paid_at, payment_method, notes),
    )
    return str(cursor.fetchone()["id"])


def fetch_payment(cursor, ctx: ExecutionContext, payment_id: str, payable_id: str) -> Optional[Dict[str, Any]]:
    """Pagamento de uma conta a pagar DO ESPAÇO (o vínculo é conferido no JOIN)."""
    params = _scope(ctx)
    params.update({"payment_id": str(payment_id), "payable_id": str(payable_id)})
    cursor.execute(
        """
        SELECT pp.id, pp.payable_id, pp.transaction_id, pp.amount, pp.paid_at, pp.reversed_at
        FROM payable_payments pp
        JOIN financial_space_payables l
          ON l.payable_id = pp.payable_id AND l.tenant_id = pp.tenant_id
        WHERE pp.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND pp.id = %(payment_id)s
          AND pp.payable_id = %(payable_id)s
        """,
        params,
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def count_equal_active_payments(
    cursor, ctx: ExecutionContext, payable_id: str, amount: Decimal, paid_on: date
) -> int:
    """Pagamentos ATIVOS da conta a pagar com o mesmo valor na mesma data.

    Serve para avisar de possível duplicidade: a mesma baixa descrita de outro
    jeito (outra evidência, com ou sem transação) não pode entrar duas vezes
    sem o titular ver. O vínculo da conta a pagar com o espaço é reconferido no
    JOIN, como em toda consulta daqui.

    A data é comparada em UTC. Para os pagamentos gravados pela IA isso é
    exato (``insert_payable_payment`` grava meio-dia UTC da data informada);
    para os lançados pelo app é uma aproximação, e errar para o lado de
    "avisar" só custa uma revisão a mais.
    """
    params = _scope(ctx)
    params.update({"payable_id": str(payable_id), "amount": amount, "paid_on": paid_on})
    cursor.execute(
        """
        SELECT count(*) AS total
        FROM payable_payments pp
        JOIN financial_space_payables l
          ON l.payable_id = pp.payable_id AND l.tenant_id = pp.tenant_id
        WHERE pp.tenant_id = %(tenant_id)s
          AND l.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND pp.payable_id = %(payable_id)s
          AND pp.reversed_at IS NULL
          AND pp.amount = %(amount)s
          AND (pp.paid_at AT TIME ZONE 'UTC')::date = %(paid_on)s
        """,
        params,
    )
    return int(cursor.fetchone()["total"])


def reverse_payable_payment(cursor, ctx: ExecutionContext, payment_id: str, payable_id: str, reason: str) -> int:
    """Marca o pagamento como revertido. A linha nunca é apagada."""
    cursor.execute(
        """
        UPDATE payable_payments
        SET reversed_at = now(), reversal_reason = %s
        WHERE tenant_id = %s AND id = %s AND payable_id = %s AND reversed_at IS NULL
        """,
        (reason, ctx.tenant_id, str(payment_id), str(payable_id)),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Transações: realizado.
# ---------------------------------------------------------------------------
# Base de toda consulta de realizado: transação do tenant, em conta vinculada
# ao espaço E presente em ``ctx.allowed_account_ids``, pela regra canônica.
_REALIZED_JOINS = """
    FROM transactions t
    JOIN financial_space_accounts l
      ON l.account_id = t.account_id AND l.tenant_id = t.tenant_id
    JOIN accounts a
      ON a.id = t.account_id AND a.tenant_id = t.tenant_id
"""

_REALIZED_WHERE = """
    WHERE t.tenant_id = %(tenant_id)s
      AND l.tenant_id = %(tenant_id)s
      AND l.financial_space_id = %(space_id)s
      AND t.account_id = ANY(%(accounts)s::uuid[])
      AND """ + realized_sql("t")

_REALIZED_FROM = _REALIZED_JOINS + _REALIZED_WHERE


def _account_filter(account_id: Optional[str], params: Dict[str, Any]) -> str:
    if account_id is None:
        return ""
    params["account_id"] = str(account_id)
    return " AND t.account_id = %(account_id)s"


def realized_by_type(
    cursor,
    ctx: ExecutionContext,
    start: Optional[date],
    end: Optional[date],
    account_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Soma e contagem do realizado por moeda e tipo (income/expense/transfer).

    Transferência vem em linha própria: nunca é somada como receita ou despesa.
    """
    params = _scope(ctx)
    extra = _date_range("t.occurred_on", start, end, params) + _account_filter(account_id, params)
    cursor.execute(
        "SELECT a.currency, t.type, count(*) AS items, sum(t.amount) AS total"
        + _REALIZED_FROM + extra
        + " GROUP BY a.currency, t.type ORDER BY a.currency, t.type",
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def realized_expense_by_category(
    cursor,
    ctx: ExecutionContext,
    start: Optional[date],
    end: Optional[date],
    account_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params = _scope(ctx)
    extra = _date_range("t.occurred_on", start, end, params) + _account_filter(account_id, params)
    cursor.execute(
        "SELECT a.currency, c.id AS category_id, c.name AS category_name,"
        " count(*) AS items, sum(t.amount) AS total"
        + _REALIZED_JOINS
        # O JOIN de categoria repete o tenant: categoria de outro tenant jamais casa.
        + " JOIN categories c ON c.id = t.category_id AND c.tenant_id = t.tenant_id"
        + _REALIZED_WHERE + extra
        + " AND t.type = 'expense'"
        " GROUP BY a.currency, c.id, c.name ORDER BY a.currency, sum(t.amount) DESC, c.name, c.id",
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def realized_by_space(
    cursor,
    ctx: ExecutionContext,
    space_ids: Sequence[str],
    start: Optional[date],
    end: Optional[date],
) -> List[Dict[str, Any]]:
    """Realizado por espaço, moeda e tipo, para o relatório consolidado.

    Quem chama já conferiu participação e grant em CADA espaço da lista. Aqui o
    filtro continua completo: tenant do contexto, vínculo conta-espaço e, para o
    espaço da própria execução, as contas permitidas do contexto. Nos demais
    espaços valem as contas vinculadas e não arquivadas (mesmo critério que o
    servidor usa para montar ``allowed_account_ids``).
    """
    params = _scope(ctx)
    params["space_ids"] = [str(item) for item in space_ids]
    period = _date_range("t.occurred_on", start, end, params)
    cursor.execute(
        """
        SELECT l.financial_space_id, a.currency, t.type, count(*) AS items, sum(t.amount) AS total
        FROM transactions t
        JOIN financial_space_accounts l
          ON l.account_id = t.account_id AND l.tenant_id = t.tenant_id
        JOIN accounts a
          ON a.id = t.account_id AND a.tenant_id = t.tenant_id
        WHERE t.tenant_id = %(tenant_id)s
          AND l.tenant_id = %(tenant_id)s
          AND l.financial_space_id = ANY(%(space_ids)s::uuid[])
          AND a.archived_at IS NULL
          AND (l.financial_space_id <> %(space_id)s OR t.account_id = ANY(%(accounts)s::uuid[]))
          AND """ + realized_sql("t") + period + """
        GROUP BY l.financial_space_id, a.currency, t.type
        ORDER BY l.financial_space_id, a.currency, t.type
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def tenant_spaces(cursor, ctx: ExecutionContext) -> List[Dict[str, Any]]:
    """Espaços ativos do tenant e se o ator participa de cada um."""
    cursor.execute(
        """
        SELECT s.id, s.kind, s.name,
               EXISTS (
                   SELECT 1 FROM financial_space_members m
                   WHERE m.tenant_id = s.tenant_id AND m.financial_space_id = s.id AND m.user_id = %s
               ) AS is_member
        FROM financial_spaces s
        WHERE s.tenant_id = %s AND s.archived_at IS NULL
        ORDER BY s.created_at, s.id
        """,
        (ctx.actor_id, ctx.tenant_id),
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_transaction_for_link(
    cursor, ctx: ExecutionContext, transaction_id: str, *, for_update: bool = False
) -> Optional[Dict[str, Any]]:
    """Transação candidata a conciliar um pagamento. ``None`` fora do escopo.

    Devolve também ``is_realized`` (regra canônica) e ``linked`` (já existe
    pagamento ativo apontando para ela).
    """
    params = _scope(ctx)
    params["transaction_id"] = str(transaction_id)
    cursor.execute(
        """
        SELECT t.id, t.account_id, t.amount, t.type, t.status, t.occurred_on, t.updated_at,
               """ + realized_sql("t") + """ AS is_realized
        FROM transactions t
        JOIN financial_space_accounts l
          ON l.account_id = t.account_id AND l.tenant_id = t.tenant_id
        WHERE t.tenant_id = %(tenant_id)s
          AND l.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND t.account_id = ANY(%(accounts)s::uuid[])
          AND t.id = %(transaction_id)s
        """ + (" FOR UPDATE OF t" if for_update else ""),
        params,
    )
    row = cursor.fetchone()
    if row is None:
        return None
    transaction = dict(row)
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM payable_payments
            WHERE tenant_id = %(tenant_id)s AND transaction_id = %(transaction_id)s AND reversed_at IS NULL
        ) AS linked
        """,
        params,
    )
    transaction["linked"] = bool(cursor.fetchone()["linked"])
    return transaction


# ---------------------------------------------------------------------------
# Contas e anexos.
# ---------------------------------------------------------------------------
def space_accounts(cursor, ctx: ExecutionContext, account_ids: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Contas do espaço (vinculadas, permitidas no contexto e não arquivadas)."""
    params = _scope(ctx)
    extra = ""
    if account_ids is not None:
        params["wanted"] = [str(item) for item in account_ids]
        extra = " AND a.id = ANY(%(wanted)s::uuid[])"
    cursor.execute(
        """
        SELECT a.id, a.name, a.type, a.institution, a.currency
        FROM accounts a
        JOIN financial_space_accounts l
          ON l.account_id = a.id AND l.tenant_id = a.tenant_id
        WHERE a.tenant_id = %(tenant_id)s
          AND l.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND a.id = ANY(%(accounts)s::uuid[])
          AND a.archived_at IS NULL
        """ + extra + " ORDER BY a.name, a.id",
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def fetch_artifact(cursor, ctx: ExecutionContext, artifact_id: str) -> Optional[Dict[str, Any]]:
    """Anexo em quarentena DO ESPAÇO. Anexo de outro espaço responde ``None``."""
    cursor.execute(
        """
        SELECT id, source_kind, sha256, original_filename, detected_kind
        FROM ai_artifacts
        WHERE tenant_id = %s AND financial_space_id = %s AND id = %s
        """,
        (ctx.tenant_id, ctx.financial_space_id, str(artifact_id)),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Importação de extrato.
# ---------------------------------------------------------------------------
# Situação da linha que já ocupa a chave de um lançamento do extrato.
LEDGER_REALIZED = "realized"
LEDGER_CANCELED = "canceled"
LEDGER_OUTSIDE = "outside"


def existing_import_keys(
    cursor,
    ctx: ExecutionContext,
    account_id: str,
    fitids: Sequence[str],
    dedup_keys: Sequence[str],
) -> Dict[str, Dict[str, str]]:
    """FITIDs e chaves de deduplicação que já existem na conta, com a situação.

    Espelha os dois índices únicos de ``transactions``: (conta, fitid) para
    lançamentos OFX e (conta, dedup_key). Linhas canceladas também contam:
    o histórico é preservado e continua ocupando a chave.

    Só que "já existe" não quer dizer "já está no realizado". Uma linha
    cancelada (ex.: importação revertida) ou vinda de CSV/manual ocupa a chave
    e faz o lançamento do novo extrato ser ignorado, mas NÃO entra no realizado
    (regra canônica). Por isso cada chave encontrada vem com a situação da
    linha dona dela, e a proposta avisa o titular nos dois últimos casos:

    * ``realized``: a linha está no realizado (ignorar o duplicado é seguro);
    * ``canceled``: a linha está cancelada;
    * ``outside``: a linha não está cancelada, mas está fora do realizado
      (status diferente de pago ou arquivo de origem que não é .ofx).

    Devolve ``{"fitids": {fitid: situação}, "dedup_keys": {chave: situação}}``.
    Os índices únicos garantem uma linha por chave, logo uma situação por chave.
    """
    params = _scope(ctx)
    params.update({"account_id": str(account_id), "fitids": list(fitids), "dedup_keys": list(dedup_keys)})
    cursor.execute(
        """
        SELECT t.fitid, t.dedup_key, t.entry_source,
               (t.status = 'canceled') AS is_canceled,
               COALESCE(""" + realized_sql("t") + """, false) AS is_realized
        FROM transactions t
        WHERE t.tenant_id = %(tenant_id)s
          AND t.account_id = %(account_id)s
          AND t.account_id = ANY(%(accounts)s::uuid[])
          AND (
              (t.entry_source = 'ofx' AND t.fitid = ANY(%(fitids)s::text[]))
              OR t.dedup_key = ANY(%(dedup_keys)s::text[])
          )
        """,
        params,
    )
    found = {"fitids": {}, "dedup_keys": {}}  # type: Dict[str, Dict[str, str]]
    wanted_fitids = set(fitids)
    for row in cursor.fetchall():
        if row["is_canceled"]:
            situation = LEDGER_CANCELED
        elif row["is_realized"]:
            situation = LEDGER_REALIZED
        else:
            situation = LEDGER_OUTSIDE
        if row["entry_source"] == "ofx" and row["fitid"] in wanted_fitids:
            found["fitids"][row["fitid"]] = situation
        if row["dedup_key"] is not None:
            found["dedup_keys"][row["dedup_key"]] = situation
    return found


def ledger_situation(entry: Dict[str, Any], keys: Dict[str, Dict[str, str]]) -> Optional[str]:
    """Situação de um lançamento do extrato frente ao que já existe na conta.

    ``None`` = não existe (é novo). Se a chave e o FITID caírem em linhas
    diferentes, basta UMA delas estar no realizado para o duplicado ser
    seguro; cancelada pesa mais que "fora do realizado" no aviso.
    """
    situations = set()
    if entry["dedup_key"] in keys["dedup_keys"]:
        situations.add(keys["dedup_keys"][entry["dedup_key"]])
    if entry.get("fitid") and entry["fitid"] in keys["fitids"]:
        situations.add(keys["fitids"][entry["fitid"]])
    if not situations:
        return None
    if LEDGER_REALIZED in situations:
        return LEDGER_REALIZED
    return LEDGER_CANCELED if LEDGER_CANCELED in situations else LEDGER_OUTSIDE


UNCLASSIFIED_CATEGORY_NAME = "Não classificado"


def ensure_unclassified_category(cursor, ctx: ExecutionContext, category_type: str) -> str:
    """Categoria "Não classificado" do tipo pedido; cria se faltar.

    A IA não escolhe categoria na importação: classificar é decisão posterior
    do titular. ``ON CONFLICT`` cobre dois importadores criando ao mesmo tempo.
    """
    if category_type not in ("income", "expense"):
        raise ValueError("tipo de categoria inválido")
    cursor.execute(
        """
        INSERT INTO categories (tenant_id, created_by_user_id, name, type)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id, type, normalized_name) DO NOTHING
        """,
        (ctx.tenant_id, ctx.actor_id, UNCLASSIFIED_CATEGORY_NAME, category_type),
    )
    cursor.execute(
        "SELECT id FROM categories WHERE tenant_id = %s AND type = %s AND normalized_name = lower(trim(%s))",
        (ctx.tenant_id, category_type, UNCLASSIFIED_CATEGORY_NAME),
    )
    return str(cursor.fetchone()["id"])


def insert_import_batch(
    cursor, ctx: ExecutionContext, *, account_id: str, filename: str, total_parsed: int, metadata: Dict[str, Any]
) -> str:
    cursor.execute(
        """
        INSERT INTO import_batches (tenant_id, created_by_user_id, account_id, filename, file_format,
                                    total_parsed, status, metadata)
        VALUES (%s, %s, %s, %s, 'ofx', %s, 'processing', %s)
        RETURNING id
        """,
        (ctx.tenant_id, ctx.actor_id, str(account_id), filename, int(total_parsed), jsonb(metadata)),
    )
    return str(cursor.fetchone()["id"])


def insert_import_transaction(
    cursor,
    ctx: ExecutionContext,
    *,
    account_id: str,
    category_id: str,
    import_batch_id: str,
    description: str,
    amount: Decimal,
    tx_type: str,
    occurred_on: date,
    fitid: Optional[str],
    dedup_key: str,
    source_file: str,
) -> bool:
    """Insere um lançamento do extrato. ``False`` = já existia (duplicado).

    ``ON CONFLICT DO NOTHING`` sem alvo cobre os dois índices únicos parciais
    (fitid e dedup_key). Duplicado é contado, não é erro: anexos diferentes
    podem trazer as mesmas transações.
    """
    cursor.execute(
        """
        INSERT INTO transactions (
            tenant_id, created_by_user_id, account_id, category_id, import_batch_id, description,
            amount, type, occurred_on, status, entry_source, fitid, dedup_key, source_file
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'paid', 'ofx', %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            ctx.tenant_id, ctx.actor_id, str(account_id), category_id, import_batch_id, description,
            amount, tx_type, occurred_on, fitid, dedup_key, source_file,
        ),
    )
    return cursor.rowcount == 1


def complete_import_batch(
    cursor,
    ctx: ExecutionContext,
    batch_id: str,
    *,
    imported: int,
    duplicates: int,
    ignored: int,
    total_income: Decimal,
    total_expense: Decimal,
    total_transfer: Decimal,
) -> None:
    cursor.execute(
        """
        UPDATE import_batches
        SET imported_count = %s, duplicate_count = %s, ignored_count = %s, unclassified_count = %s,
            total_income = %s, total_expense = %s, total_transfer = %s,
            status = 'completed', completed_at = now()
        WHERE tenant_id = %s AND id = %s
        """,
        (imported, duplicates, ignored, imported, total_income, total_expense, total_transfer,
         ctx.tenant_id, str(batch_id)),
    )


def fetch_import_batch(
    cursor, ctx: ExecutionContext, batch_id: str, *, for_update: bool = False
) -> Optional[Dict[str, Any]]:
    """Lote de importação de uma conta DO ESPAÇO, com contagem de lançamentos ativos.

    ``for_update`` trava o lote E os lançamentos dele, nesta ordem, antes de
    contar os vínculos com pagamentos. Travar só o lote não basta: uma baixa
    conciliada trava a TRANSAÇÃO (não o lote) e insere o pagamento. Sem o lock
    das transações aqui, a reversão contaria "nenhum vínculo" enquanto o
    pagamento ainda não foi confirmado, esperaria no UPDATE e depois cancelaria
    um lançamento que acabou de virar lastro de um pagamento ativo.

    Com o lock, quem chega depois espera o outro confirmar e só então conta
    (em READ COMMITTED cada instrução enxerga o que já foi confirmado): ou a
    reversão vê o vínculo e é recusada, ou a baixa vê a transação cancelada.
    """
    params = _scope(ctx)
    params["batch_id"] = str(batch_id)
    cursor.execute(
        """
        SELECT b.id, b.account_id, b.filename, b.status
        FROM import_batches b
        JOIN financial_space_accounts l
          ON l.account_id = b.account_id AND l.tenant_id = b.tenant_id
        WHERE b.tenant_id = %(tenant_id)s
          AND l.financial_space_id = %(space_id)s
          AND b.account_id = ANY(%(accounts)s::uuid[])
          AND b.id = %(batch_id)s
        """ + (" FOR UPDATE OF b" if for_update else ""),
        params,
    )
    row = cursor.fetchone()
    if row is None:
        return None
    batch = dict(row)
    if for_update:
        # ORDER BY id: locks sempre na mesma ordem, para duas transações que
        # travem vários lançamentos nunca se esperarem em círculo.
        cursor.execute(
            """
            SELECT t.id FROM transactions t
            WHERE t.tenant_id = %(tenant_id)s AND t.import_batch_id = %(batch_id)s
            ORDER BY t.id
            FOR UPDATE OF t
            """,
            params,
        )
        cursor.fetchall()
    cursor.execute(
        """
        SELECT count(*) AS active,
               COALESCE(sum(t.amount) FILTER (WHERE t.type = 'income'), 0) AS income,
               COALESCE(sum(t.amount) FILTER (WHERE t.type = 'expense'), 0) AS expense,
               count(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM payable_payments pp
                   WHERE pp.tenant_id = t.tenant_id AND pp.transaction_id = t.id AND pp.reversed_at IS NULL
               )) AS linked
        FROM transactions t
        WHERE t.tenant_id = %(tenant_id)s AND t.import_batch_id = %(batch_id)s AND t.status <> 'canceled'
        """,
        params,
    )
    totals = cursor.fetchone()
    batch["active_transactions"] = int(totals["active"])
    batch["active_income"] = Decimal(totals["income"])
    batch["active_expense"] = Decimal(totals["expense"])
    batch["linked_transactions"] = int(totals["linked"])
    return batch


def cancel_batch_transactions(cursor, ctx: ExecutionContext, batch_id: str) -> int:
    """Cancela (não apaga) os lançamentos de um lote. Devolve quantos mudaram.

    Lançamento que lastreia um pagamento ativo NÃO é cancelado, mesmo que
    alguém chame esta função sem ter conferido os vínculos: quem chama compara
    o número devolvido com o de lançamentos ativos do lote e desiste se
    faltar algum (ver ``operations._apply_reversal``).
    """
    cursor.execute(
        """
        UPDATE transactions t
        SET status = 'canceled', canceled_at = now()
        WHERE t.tenant_id = %s AND t.import_batch_id = %s AND t.status <> 'canceled'
          AND NOT EXISTS (
              SELECT 1 FROM payable_payments pp
              WHERE pp.tenant_id = t.tenant_id AND pp.transaction_id = t.id AND pp.reversed_at IS NULL
          )
        """,
        (ctx.tenant_id, str(batch_id)),
    )
    return cursor.rowcount


def rollback_import_batch(cursor, ctx: ExecutionContext, batch_id: str) -> None:
    cursor.execute(
        """
        UPDATE import_batches
        SET status = 'rolled_back', rolled_back_at = now()
        WHERE tenant_id = %s AND id = %s AND status <> 'rolled_back'
        """,
        (ctx.tenant_id, str(batch_id)),
    )
