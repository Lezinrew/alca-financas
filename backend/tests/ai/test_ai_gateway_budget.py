"""Livro de orçamento: reserva atômica, tetos e reconciliação (AC-13).

Banco PostgreSQL real, papel sem superusuário (RLS ativo) e threads reais.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.gateway.budget import BudgetLedger

from .support import seed
from .support.gateway_harness import WARM_CONNECTIONS, gateway_settings, slow_clock
from .support.gateway_harness import warm_pool  # noqa: F401 - fixture do pytest


pytestmark = pytest.mark.integration

COST = 100


def run_ctx(world, pool):
    return world.context(pool).with_run(seed.new_id())


def blocked(call):
    with pytest.raises(AiError) as excinfo:
        call()
    assert excinfo.value.code == "budget_exceeded"
    return excinfo.value.details["reason"]


def entries(pool, tenant_id):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            SELECT id, run_id, route_alias, currency, reserved_micros, actual_micros, status,
                   budget_day, budget_month, settled_at
            FROM ai_budget_entries WHERE tenant_id = %s ORDER BY created_at, id
            """,
            (tenant_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Sem decisão do titular não há gasto
# ---------------------------------------------------------------------------

def test_no_limit_row_blocks_every_reservation(pool, world):
    ledger = BudgetLedger(pool, gateway_settings())
    assert blocked(lambda: ledger.reserve(run_ctx(world, pool), "externa", COST)) == "no_limit"
    assert entries(pool, world.tenant_id) == []


@pytest.mark.parametrize("limits", [(0, 1000, 1000), (1000, 0, 1000), (1000, 1000, 0), (0, 0, 0)])
def test_zero_ceiling_blocks_external_spend(pool, world, limits):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx = run_ctx(world, pool)
    ledger.set_limits(ctx, *limits)
    assert blocked(lambda: ledger.reserve(ctx, "externa", 1)) == "zero_limit"
    assert entries(pool, world.tenant_id) == []


@pytest.mark.parametrize("unknown", [None, 0, -5, 1.5, True, "100"])
def test_unknown_cost_blocks_the_paid_route(pool, world, unknown):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx = run_ctx(world, pool)
    ledger.set_limits(ctx, 10_000, 10_000, 10_000)
    assert blocked(lambda: ledger.reserve(ctx, "externa", unknown)) == "cost_unknown"
    assert entries(pool, world.tenant_id) == []


def test_currency_mismatch_blocks(pool, world):
    ledger = BudgetLedger(pool, gateway_settings(budget_currency="USD"))
    ctx = run_ctx(world, pool)
    ledger.set_limits(ctx, 10_000, 10_000, 10_000, "BRL")
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "currency_mismatch"


def test_invalid_timezone_fails_closed(pool, world):
    ledger = BudgetLedger(pool, gateway_settings(budget_timezone="Marte/Olympus"))
    ctx = run_ctx(world, pool)
    BudgetLedger(pool, gateway_settings()).set_limits(ctx, 10_000, 10_000, 10_000)
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "timezone_invalid"
    assert entries(pool, world.tenant_id) == []


# ---------------------------------------------------------------------------
# Reserva, reconciliação e liberação
# ---------------------------------------------------------------------------

def test_reserve_reconcile_and_release_change_what_counts(pool, world):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx = run_ctx(world, pool)
    ledger.set_limits(ctx, 250, 10_000, 10_000)

    first = ledger.reserve(ctx, "externa", COST)
    second = ledger.reserve(ctx, "externa", COST)
    assert ledger.usage(ctx)["run_micros"] == 200
    # 200 reservados + 100 passaria do teto de 250 por execução.
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_run"

    # O custo real foi menor que a reserva: sobra espaço.
    ledger.reconcile(ctx, first, 30)
    assert ledger.usage(ctx)["run_micros"] == 130
    third = ledger.reserve(ctx, "externa", COST)
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_run"

    # Chamada que falhou sem cobrança devolve a reserva inteira.
    ledger.release(ctx, second)
    assert ledger.usage(ctx)["run_micros"] == 130
    ledger.reserve(ctx, "externa", COST)

    rows = {str(row["id"]): row for row in entries(pool, world.tenant_id)}
    assert (rows[first]["status"], rows[first]["actual_micros"]) == ("reconciled", 30)
    assert (rows[second]["status"], rows[second]["actual_micros"]) == ("released", None)
    assert rows[third]["status"] == "reserved" and rows[third]["settled_at"] is None
    assert all(row["currency"] == "USD" and str(row["run_id"]) == ctx.run_id for row in rows.values())


def test_reconcile_is_idempotent_and_overrun_is_recorded(pool, world, caplog):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx = run_ctx(world, pool)
    ledger.set_limits(ctx, 10_000, 10_000, 10_000)
    entry = ledger.reserve(ctx, "externa", COST)
    caplog.set_level(logging.WARNING)

    ledger.reconcile(ctx, entry, 180)
    ledger.reconcile(ctx, entry, 999)  # repetição não muda o que já foi fechado
    ledger.release(ctx, entry)  # nem a liberação tardia apaga um custo real
    assert ledger.usage(ctx)["run_micros"] == 180
    # Estimativa "máxima" otimista: o gasto real conta e o operador é avisado.
    assert "budget_overrun" in caplog.text

    released = ledger.reserve(ctx, "externa", COST)
    ledger.release(ctx, released)
    ledger.release(ctx, released)
    assert ledger.usage(ctx)["run_micros"] == 180
    # A cobrança apareceu depois da liberação: passa a contar.
    ledger.reconcile(ctx, released, 40)
    assert ledger.usage(ctx)["run_micros"] == 220

    for bad_amount in (-1, 1.5, None, True):
        with pytest.raises(AiError) as excinfo:
            ledger.reconcile(ctx, entry, bad_amount)
        assert excinfo.value.code == "invalid_request"
    for missing in (seed.new_id(), "nao-e-uuid"):
        with pytest.raises(AiError) as excinfo:
            ledger.reconcile(ctx, missing, 1)
        assert excinfo.value.code == "not_found"
        with pytest.raises(AiError) as excinfo:
            ledger.release(ctx, missing)
        assert excinfo.value.code == "not_found"


def test_per_run_per_day_and_per_month_are_independent_ceilings(pool, world):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx_a, ctx_b, ctx_c = run_ctx(world, pool), run_ctx(world, pool), run_ctx(world, pool)
    ledger.set_limits(ctx_a, 200, 300, 10_000)

    ledger.reserve(ctx_a, "externa", COST)
    ledger.reserve(ctx_a, "externa", COST)
    assert blocked(lambda: ledger.reserve(ctx_a, "externa", COST)) == "per_run"
    # Outra execução tem o próprio teto por execução, mas divide o do dia.
    ledger.reserve(ctx_b, "externa", COST)
    assert blocked(lambda: ledger.reserve(ctx_b, "externa", COST)) == "per_day"
    assert blocked(lambda: ledger.reserve(ctx_c, "externa", 1)) == "per_day"
    usage = ledger.usage(ctx_b)
    assert (usage["run_micros"], usage["day_micros"], usage["month_micros"]) == (100, 300, 300)
    assert usage["limits"] == {
        "currency": "USD", "per_run_micros": 200, "per_day_micros": 300, "per_month_micros": 10_000,
    }


def test_day_and_month_follow_the_budget_timezone(pool, world):
    moment = {"now": datetime(2026, 10, 2, 2, 30, tzinfo=timezone.utc)}  # 01/10 23:30 em São Paulo
    ledger = BudgetLedger(pool, gateway_settings(budget_timezone="America/Sao_Paulo"), clock=lambda: moment["now"])
    ctx = world.context(pool)  # sem run_id: o teto por execução vale por chamada
    ledger.set_limits(ctx, 100, 100, 250)

    ledger.reserve(ctx, "externa", COST)
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_day"

    # 03:30 UTC já é dia 02 em São Paulo: o teto diário recomeça, o mensal não.
    moment["now"] = datetime(2026, 10, 2, 3, 30, tzinfo=timezone.utc)
    ledger.reserve(ctx, "externa", COST)
    moment["now"] = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_month"

    # 01/11 02:30 UTC ainda é 31/10 em São Paulo: continua no mês de outubro.
    moment["now"] = datetime(2026, 11, 1, 2, 30, tzinfo=timezone.utc)
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_month"
    moment["now"] = datetime(2026, 11, 1, 3, 30, tzinfo=timezone.utc)
    ledger.reserve(ctx, "externa", COST)

    days = [(row["budget_day"].isoformat(), row["budget_month"].isoformat()) for row in entries(pool, world.tenant_id)]
    assert days == [("2026-10-01", "2026-10-01"), ("2026-10-02", "2026-10-01"), ("2026-11-01", "2026-11-01")]
    # Com UTC como fuso do orçamento, o mesmo instante cairia no dia seguinte.
    instant = datetime(2026, 10, 2, 2, 30, tzinfo=timezone.utc)
    utc_ledger = BudgetLedger(pool, gateway_settings(budget_timezone="UTC"), clock=lambda: instant)
    assert utc_ledger.usage(ctx)["budget_day"] == "2026-10-02"


# ---------------------------------------------------------------------------
# AC-13: concorrência
# ---------------------------------------------------------------------------

def reserve_concurrently(ledger, contexts, amount=COST):
    barrier = threading.Barrier(len(contexts))
    results, lock = [], threading.Lock()

    def worker(ctx):
        barrier.wait(10)
        try:
            outcome = ("ok", ledger.reserve(ctx, "externa", amount))
        except AiError as error:
            outcome = (error.code, error.details.get("reason"))
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(ctx,)) for ctx in contexts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert all(not thread.is_alive() for thread in threads)
    return results


def test_ac13_concurrent_reservations_never_exceed_the_daily_ceiling(pool, warm_pool, world):
    ledger = BudgetLedger(warm_pool, gateway_settings(), clock=slow_clock())
    owner = run_ctx(world, pool)
    ledger.set_limits(owner, 10_000, 4 * COST, 10_000)
    # Execuções diferentes reservando ao mesmo tempo contra um teto que comporta 4.
    contexts = [run_ctx(world, pool) for _ in range(WARM_CONNECTIONS)]

    results = reserve_concurrently(ledger, contexts)

    succeeded = [item for item in results if item[0] == "ok"]
    assert len(succeeded) == 4
    assert [item for item in results if item[0] != "ok"] == [("budget_exceeded", "per_day")] * (WARM_CONNECTIONS - 4)
    rows = entries(pool, world.tenant_id)
    # A soma reservada nunca passa do teto.
    assert len(rows) == 4 and sum(row["reserved_micros"] for row in rows) == 4 * COST
    assert ledger.usage(owner)["day_micros"] == 4 * COST


def test_ac13_concurrent_reservations_never_exceed_the_run_ceiling(pool, warm_pool, world):
    ledger = BudgetLedger(warm_pool, gateway_settings(), clock=slow_clock())
    ctx = run_ctx(world, pool)
    # Teto que não é múltiplo do custo: cabem 3 reservas de 100 em 350.
    ledger.set_limits(ctx, 350, 10_000, 10_000)

    results = reserve_concurrently(ledger, [ctx] * WARM_CONNECTIONS)

    assert sorted(item[0] for item in results) == ["budget_exceeded"] * (WARM_CONNECTIONS - 3) + ["ok"] * 3
    assert {item[1] for item in results if item[0] != "ok"} == {"per_run"}
    assert ledger.usage(ctx)["run_micros"] == 300


def test_ac13_concurrent_reservations_never_exceed_the_monthly_ceiling(pool, warm_pool, world):
    ledger = BudgetLedger(warm_pool, gateway_settings(), clock=slow_clock())
    owner = run_ctx(world, pool)
    ledger.set_limits(owner, 10_000, 10_000, 2 * COST)
    results = reserve_concurrently(ledger, [run_ctx(world, pool) for _ in range(WARM_CONNECTIONS)])
    assert sorted(item[0] for item in results) == ["budget_exceeded"] * (WARM_CONNECTIONS - 2) + ["ok"] * 2
    assert ledger.usage(owner)["month_micros"] == 2 * COST


# ---------------------------------------------------------------------------
# Isolamento e administração
# ---------------------------------------------------------------------------

def test_budget_is_isolated_per_tenant(pool, world, other_world):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx, other = run_ctx(world, pool), run_ctx(other_world, pool)
    ledger.set_limits(ctx, 100, 100, 100)

    # O teto de um tenant não autoriza o outro.
    assert blocked(lambda: ledger.reserve(other, "externa", COST)) == "no_limit"
    ledger.set_limits(other, 100, 100, 100)
    entry = ledger.reserve(ctx, "externa", COST)
    # O gasto de um tenant não consome o teto do outro.
    other_entry = ledger.reserve(other, "externa", COST)
    assert ledger.usage(other)["month_micros"] == COST

    for call in (lambda: ledger.reconcile(other, entry, 1), lambda: ledger.release(other, entry)):
        with pytest.raises(AiError) as excinfo:
            call()
        assert excinfo.value.code == "not_found"
    assert [row["status"] for row in entries(pool, world.tenant_id)] == ["reserved"]
    assert str(entries(pool, other_world.tenant_id)[0]["id"]) == other_entry


def test_tenant_filter_is_explicit_and_does_not_depend_on_rls(pool, admin_pool, world, other_world):
    # Conexão administrativa: IGNORA o RLS. É assim que se prova que cada
    # consulta do livro tem o próprio ``WHERE tenant_id``; com o papel de
    # aplicação o RLS esconderia a falta do filtro.
    ledger = BudgetLedger(admin_pool, gateway_settings())
    ctx, other = run_ctx(world, pool), run_ctx(other_world, pool)
    ledger.set_limits(ctx, 150, 150, 150)
    ledger.set_limits(other, 10_000, 10_000, 10_000)
    other_entry = ledger.reserve(other, "externa", COST)
    ledger.reserve(other, "externa", COST)

    # Premissa do teste: esta conexão enxerga linhas de qualquer tenant.
    with scoped_tx(admin_pool, world.tenant_id) as cursor:
        cursor.execute("SELECT count(*) AS total FROM ai_budget_entries")
        assert cursor.fetchone()["total"] == 2

    # O gasto do outro tenant (200) não entra na soma deste, cujo teto é 150.
    usage = ledger.usage(ctx)
    assert (usage["run_micros"], usage["day_micros"], usage["month_micros"]) == (0, 0, 0)
    assert usage["limits"]["per_day_micros"] == 150
    ledger.reserve(ctx, "externa", COST)
    assert ledger.usage(ctx)["month_micros"] == COST
    assert ledger.usage(other)["month_micros"] == 2 * COST
    assert blocked(lambda: ledger.reserve(ctx, "externa", COST)) == "per_run"

    # Fechar a reserva de outro tenant: responde "não existe" e não altera nada.
    for call in (lambda: ledger.reconcile(ctx, other_entry, 1), lambda: ledger.release(ctx, other_entry)):
        with pytest.raises(AiError) as excinfo:
            call()
        assert excinfo.value.code == "not_found"
    assert [row["status"] for row in entries(admin_pool, other_world.tenant_id)] == ["reserved", "reserved"]


def test_set_limits_is_owner_only_validated_and_audited(pool, world):
    ledger = BudgetLedger(pool, gateway_settings())
    ctx = run_ctx(world, pool)

    first = ledger.set_limits(ctx, 1000, 2000, 3000)
    assert first == {"currency": "USD", "per_run_micros": 1000, "per_day_micros": 2000, "per_month_micros": 3000}
    ledger.set_limits(ctx, 0, 0, 0, "usd")

    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute(
            """
            SELECT actor_user_id, entity_type, entity_id, metadata FROM audit_events
            WHERE tenant_id = %s AND event_type = 'ai.budget.limits_set' ORDER BY created_at, id
            """,
            (world.tenant_id,),
        )
        events = cursor.fetchall()
    assert len(events) == 2
    assert str(events[0]["actor_user_id"]) == world.user_id and str(events[0]["entity_id"]) == world.tenant_id
    assert events[0]["metadata"]["before"] is None and events[0]["metadata"]["after"] == first
    assert events[1]["metadata"]["before"] == first
    assert events[1]["metadata"]["after"]["per_day_micros"] == 0 and events[1]["metadata"]["trace_id"] == ctx.trace_id

    member = seed.create_user(pool, "integrante-alfa@example.test", "Integrante")
    seed.add_tenant_member(pool, world.tenant_id, member, "member")
    with pytest.raises(AiError) as excinfo:
        ledger.set_limits(replace(ctx, actor_id=member), 9_000_000, 9_000_000, 9_000_000)
    assert excinfo.value.code == "capability_denied"
    assert ledger.usage(ctx)["limits"]["per_run_micros"] == 0

    for bad in ((-1, 1, 1), (1, 1.5, 1), (1, 1, True), (None, 1, 1), ("10", 1, 1)):
        with pytest.raises(AiError) as excinfo:
            ledger.set_limits(ctx, *bad)
        assert excinfo.value.code == "invalid_request"
    with pytest.raises(AiError) as excinfo:
        ledger.set_limits(ctx, 1, 1, 1, "DOLAR")
    assert excinfo.value.code == "invalid_request"
    assert seed.count_rows(pool, world.tenant_id, "audit_events", "event_type = 'ai.budget.limits_set'") == 2
