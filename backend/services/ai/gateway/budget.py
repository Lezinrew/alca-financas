"""Teto de custo por execução, dia e mês com reserva atômica (contrato, seção 8).

Fluxo de uma chamada paga:

1. ``reserve``  - antes de falar com o provedor, reserva o custo MÁXIMO
   estimado da chamada. Se a reserva estourar algum teto, a chamada não
   acontece (``budget_exceeded``).
2. ``reconcile``- depois da resposta, troca a reserva pelo custo real.
3. ``release``  - se a chamada falhou sem cobrança, devolve a reserva.

Por que reservar antes, e não só somar depois: duas execuções em paralelo
leriam o mesmo "gasto até agora", as duas concluiriam que cabem no teto e as
duas gastariam. A reserva resolve isso com um lock de linha no PostgreSQL:
``SELECT ... FOR UPDATE`` na linha de ``ai_budget_limits`` do tenant faz as
reservas concorrentes entrarem em fila; cada uma soma o que já foi reservado
ou gasto, compara e só então insere. O lock é liberado no commit.

Regras fixas:

* sem linha de limite, ou com QUALQUER teto igual a zero, nenhum gasto externo
  é permitido (zero é o padrão: gastar exige decisão do titular);
* custo desconhecido não reserva: sem estimativa conservadora a rota paga fica
  bloqueada;
* reserva ainda aberta conta como gasto. Se o processo morrer entre a reserva
  e a reconciliação, o valor continua contando naquele dia/mês (erra para o
  lado seguro);
* "dia" e "mês" são datas locais no fuso ``settings.budget_timezone``: o gasto
  das 23h30 de São Paulo conta no dia em que o titular o viu acontecer, não no
  dia seguinte em UTC;
* valores são inteiros em micros (milionésimos) da moeda do orçamento. Nada de
  float.

Rotas locais não passam por aqui: não têm custo por chamada.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # stdlib desde o Python 3.9

import psycopg2

from ..db import scoped_tx, write_audit
from ..errors import AiError
from ..settings import AiSettings
from ..types import ExecutionContext, utc_now


logger = logging.getLogger("ai.gateway.budget")

# bigint do PostgreSQL; evita erro de faixa virar exceção de banco.
_MAX_MICROS = 9_000_000_000_000_000

_USAGE_SQL = """
    SELECT
        coalesce(sum(amount) FILTER (WHERE run_id = %(run_id)s::uuid), 0) AS run_used,
        coalesce(sum(amount) FILTER (WHERE budget_day = %(day)s), 0) AS day_used,
        coalesce(sum(amount) FILTER (WHERE budget_month = %(month)s), 0) AS month_used
    FROM (
        SELECT run_id, budget_day, budget_month,
               CASE status
                   WHEN 'reserved' THEN reserved_micros
                   WHEN 'reconciled' THEN actual_micros
                   ELSE 0
               END AS amount
        FROM ai_budget_entries
        WHERE tenant_id = %(tenant_id)s
          AND status <> 'released'
          AND (budget_month = %(month)s OR run_id = %(run_id)s::uuid)
    ) entries
"""


def _blocked(reason: str, safe_message: Optional[str] = None) -> AiError:
    return AiError("budget_exceeded", safe_message, details={"reason": reason})


def _as_micros(value: Any) -> Optional[int]:
    """Inteiro de micros válido, ou ``None``. ``bool`` e ``float`` não valem."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > _MAX_MICROS:
        return None
    return value


def _entry_uuid(entry_id: Any) -> str:
    try:
        return str(uuid.UUID(str(entry_id)))
    except (ValueError, AttributeError, TypeError):
        raise AiError("not_found", "Reserva de orçamento não encontrada.")


class BudgetLedger:
    """Livro de reservas e gastos externos de IA, por tenant.

    ``clock`` devolve o instante atual com fuso (UTC); existe para os testes
    exercitarem a virada de dia e de mês.
    """

    def __init__(
        self,
        pool,
        settings: AiSettings,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._pool = pool
        self._settings = settings
        self._clock = clock

    # -- período -----------------------------------------------------------

    def _period(self, cursor) -> Dict[str, Any]:
        """Dia e mês do orçamento no fuso configurado (datas locais).

        A conversão usa a base de fusos do Python (``zoneinfo``). Onde ela não
        existir (Windows sem o pacote ``tzdata``), tenta a do PostgreSQL. Se
        nenhuma das duas conhecer o fuso, a reserva é negada: sem saber que dia
        é, não se gasta.
        """
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        name = self._settings.budget_timezone
        try:
            day = now.astimezone(ZoneInfo(name)).date()
        except (ZoneInfoNotFoundError, ValueError, OSError):
            try:
                cursor.execute("SELECT (%s::timestamptz AT TIME ZONE %s)::date AS day", (now, name))
            except psycopg2.DataError:
                logger.error("budget_timezone_invalid")
                raise _blocked("timezone_invalid") from None
            day = cursor.fetchone()["day"]
        return {"day": day, "month": day.replace(day=1)}

    def _usage_row(self, cursor, ctx: ExecutionContext, period: Dict[str, Any]) -> Dict[str, int]:
        cursor.execute(
            _USAGE_SQL,
            {
                "tenant_id": ctx.tenant_id,
                "run_id": ctx.run_id,
                "day": period["day"],
                "month": period["month"],
            },
        )
        row = cursor.fetchone()
        return {key: int(row[key]) for key in ("run_used", "day_used", "month_used")}

    # -- reserva -----------------------------------------------------------

    def reserve(self, ctx: ExecutionContext, route_alias: str, max_micros: Any) -> str:
        """Reserva ``max_micros`` para uma chamada. Devolve o id da reserva.

        Levanta ``AiError("budget_exceeded")`` com ``details["reason"]``:
        ``cost_unknown``, ``no_limit``, ``zero_limit``, ``currency_mismatch``,
        ``per_run``, ``per_day`` ou ``per_month``.
        """
        amount = _as_micros(max_micros)
        if amount is None or amount == 0:
            # Sem estimativa conservadora de custo a rota paga não roda.
            raise _blocked("cost_unknown")

        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            # O lock desta linha é o que torna a reserva atômica: enquanto esta
            # transação não fizer commit, nenhuma outra reserva do mesmo tenant
            # passa daqui. Sem ele, N reservas simultâneas veriam o mesmo saldo.
            cursor.execute(
                """
                SELECT currency, per_run_micros, per_day_micros, per_month_micros
                FROM ai_budget_limits
                WHERE tenant_id = %s
                FOR UPDATE
                """,
                (ctx.tenant_id,),
            )
            limits = cursor.fetchone()
            if limits is None:
                raise _blocked("no_limit")
            per_run = int(limits["per_run_micros"])
            per_day = int(limits["per_day_micros"])
            per_month = int(limits["per_month_micros"])
            if per_run <= 0 or per_day <= 0 or per_month <= 0:
                raise _blocked("zero_limit")
            currency = str(limits["currency"]).strip().upper()
            if currency != self._settings.budget_currency:
                # Os custos das rotas estão na moeda de settings.budget_currency;
                # comparar com um teto em outra moeda seria comparar unidades diferentes.
                logger.error("budget_currency_mismatch limit=%s settings=%s", currency, self._settings.budget_currency)
                raise _blocked("currency_mismatch")

            period = self._period(cursor)
            used = self._usage_row(cursor, ctx, period)
            # Sem run_id não há execução para acumular: o teto por execução
            # vale para esta chamada isolada.
            if used["run_used"] + amount > per_run:
                raise _blocked("per_run")
            if used["day_used"] + amount > per_day:
                raise _blocked("per_day")
            if used["month_used"] + amount > per_month:
                raise _blocked("per_month")

            cursor.execute(
                """
                INSERT INTO ai_budget_entries
                    (tenant_id, run_id, route_alias, currency, reserved_micros, budget_day, budget_month)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (ctx.tenant_id, ctx.run_id, route_alias, currency, amount, period["day"], period["month"]),
            )
            entry_id = str(cursor.fetchone()["id"])
        logger.info(
            "budget_reserved alias=%s micros=%d run_id=%s trace_id=%s", route_alias, amount, ctx.run_id, ctx.trace_id
        )
        return entry_id

    def reconcile(self, ctx: ExecutionContext, entry_id: str, actual_micros: Any) -> None:
        """Troca a reserva pelo custo real. Repetir a chamada não muda nada."""
        actual = _as_micros(actual_micros)
        if actual is None:
            raise AiError("invalid_request", "Custo real inválido.")
        entry = _entry_uuid(entry_id)
        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            # Uma reserva liberada também pode ser reconciliada: se a cobrança
            # aparecer depois, a verdade do custo prevalece sobre a liberação.
            cursor.execute(
                """
                UPDATE ai_budget_entries
                SET status = 'reconciled', actual_micros = %s, settled_at = now()
                WHERE id = %s AND tenant_id = %s AND status IN ('reserved', 'released')
                RETURNING reserved_micros
                """,
                (actual, entry, ctx.tenant_id),
            )
            row = cursor.fetchone()
            if row is None:
                self._require_entry(cursor, ctx, entry)
                return
            reserved = int(row["reserved_micros"])
        if actual > reserved:
            # A estimativa "máxima" foi otimista. O gasto real fica registrado
            # (e conta nos tetos), mas o operador precisa corrigir a rota.
            logger.warning(
                "budget_overrun entry_id=%s reserved=%d actual=%d trace_id=%s", entry, reserved, actual, ctx.trace_id
            )

    def release(self, ctx: ExecutionContext, entry_id: str) -> None:
        """Devolve uma reserva de chamada que falhou sem cobrança. Idempotente."""
        entry = _entry_uuid(entry_id)
        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            cursor.execute(
                """
                UPDATE ai_budget_entries
                SET status = 'released', settled_at = now()
                WHERE id = %s AND tenant_id = %s AND status = 'reserved'
                """,
                (entry, ctx.tenant_id),
            )
            if cursor.rowcount == 0:
                self._require_entry(cursor, ctx, entry)

    @staticmethod
    def _require_entry(cursor, ctx: ExecutionContext, entry: str) -> None:
        cursor.execute(
            "SELECT 1 FROM ai_budget_entries WHERE id = %s AND tenant_id = %s",
            (entry, ctx.tenant_id),
        )
        if cursor.fetchone() is None:
            # Reserva de outro tenant responde como inexistente.
            raise AiError("not_found", "Reserva de orçamento não encontrada.")

    # -- configuração ------------------------------------------------------

    def set_limits(
        self,
        ctx: ExecutionContext,
        per_run: Any,
        per_day: Any,
        per_month: Any,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Define os tetos do tenant (em micros). Só titular/admin; auditado.

        Zero em qualquer teto bloqueia todo gasto externo.
        """
        values = {"per_run": _as_micros(per_run), "per_day": _as_micros(per_day), "per_month": _as_micros(per_month)}
        for field, value in values.items():
            if value is None:
                raise AiError(
                    "invalid_request",
                    "Teto de orçamento inválido: use um inteiro em micros, maior ou igual a zero.",
                    details={"field": field},
                )
        code = (currency or self._settings.budget_currency or "").strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise AiError("invalid_request", "Moeda inválida.", details={"field": "currency"})

        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            cursor.execute(
                "SELECT role FROM tenant_members WHERE tenant_id = %s AND user_id = %s",
                (ctx.tenant_id, ctx.actor_id),
            )
            member = cursor.fetchone()
            if member is None or member["role"] not in ("owner", "admin"):
                raise AiError("capability_denied", "Somente o titular define o orçamento da IA.")
            cursor.execute(
                """
                SELECT currency, per_run_micros, per_day_micros, per_month_micros
                FROM ai_budget_limits WHERE tenant_id = %s FOR UPDATE
                """,
                (ctx.tenant_id,),
            )
            before = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO ai_budget_limits
                    (tenant_id, currency, per_run_micros, per_day_micros, per_month_micros, updated_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id) DO UPDATE SET
                    currency = EXCLUDED.currency,
                    per_run_micros = EXCLUDED.per_run_micros,
                    per_day_micros = EXCLUDED.per_day_micros,
                    per_month_micros = EXCLUDED.per_month_micros,
                    updated_by_user_id = EXCLUDED.updated_by_user_id,
                    updated_at = now()
                """,
                (ctx.tenant_id, code, values["per_run"], values["per_day"], values["per_month"], ctx.actor_id),
            )
            after = {
                "currency": code,
                "per_run_micros": values["per_run"],
                "per_day_micros": values["per_day"],
                "per_month_micros": values["per_month"],
            }
            write_audit(
                cursor,
                tenant_id=ctx.tenant_id,
                actor_user_id=ctx.actor_id,
                event_type="ai.budget.limits_set",
                entity_type="ai_budget_limits",
                entity_id=ctx.tenant_id,
                metadata={
                    "before": self._limits_dict(before),
                    "after": after,
                    "trace_id": ctx.trace_id,
                },
            )
        return after

    @staticmethod
    def _limits_dict(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return {
            "currency": str(row["currency"]).strip(),
            "per_run_micros": int(row["per_run_micros"]),
            "per_day_micros": int(row["per_day_micros"]),
            "per_month_micros": int(row["per_month_micros"]),
        }

    def usage(self, ctx: ExecutionContext) -> Dict[str, Any]:
        """Tetos e consumo atuais (reservado em aberto + real reconciliado)."""
        with scoped_tx(self._pool, ctx.tenant_id) as cursor:
            cursor.execute(
                """
                SELECT currency, per_run_micros, per_day_micros, per_month_micros
                FROM ai_budget_limits WHERE tenant_id = %s
                """,
                (ctx.tenant_id,),
            )
            limits = self._limits_dict(cursor.fetchone())
            period = self._period(cursor)
            used = self._usage_row(cursor, ctx, period)
        return {
            "limits": limits,
            "run_micros": used["run_used"],
            "day_micros": used["day_used"],
            "month_micros": used["month_used"],
            "budget_day": period["day"].isoformat(),
            "budget_month": period["month"].isoformat(),
        }
