"""Worker: fila, lease em segundo plano, AC-11 e entrega do outbox."""

from __future__ import annotations

import sys
import threading
import time
import types
from dataclasses import replace

import pytest

from services.ai import runs
from services.ai import worker as worker_module
from services.ai.db import enqueue_outbox, queue_tx, scoped_tx
from services.ai.errors import AiError
from services.ai.orchestrator import Orchestrator
from services.ai.worker import Worker, deliver_outbox_once

from .support import orchestrator_kit as kit
from .support import seed
from .support.orchestrator_kit import ScriptedGateway, ToolKit, WorkerKilled, call, response


pytestmark = pytest.mark.integration

ALL_FINANCE = ["finance.read", "finance.prepare_change", "finance.apply_change", "finance.operation_status"]


def _simple_plan(request, ctx, budget):
    if not kit.tool_messages(request):
        return response(tool_calls=[call("finance.read", {"query": "a"})])
    return response(summary="O valor consultado é R$ 10,00.")


def _worker(pool, settings, gateway, owner="worker-a"):
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    return Worker(pool, settings, Orchestrator(pool, settings, tools.registry, gateway), owner=owner), tools


# ------------------------------------------------------------------ fila

def test_run_once_returns_none_when_queue_is_empty(pool, world, settings):
    worker, _ = _worker(pool, settings, ScriptedGateway(_simple_plan))
    assert worker.run_once() is None


def test_run_once_claims_and_executes_one_run(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    first = kit.enqueue(pool, ctx, settings)
    second = kit.enqueue(pool, ctx, settings)
    worker, tools = _worker(pool, settings, ScriptedGateway(_simple_plan))

    assert worker.run_once() == first

    assert runs.get_run_view(pool, ctx, first)["status"] == "completed"
    assert runs.get_run_view(pool, ctx, second)["status"] == "queued"
    assert tools.calls == {"finance.read": 1}
    assert worker.run_once() == second and worker.run_once() is None


def test_worker_owner_defaults_to_setting_or_unique_identity(pool, settings):
    assert Worker(pool, replace(settings, worker_id="worker-configurado"), None).owner == "worker-configurado"
    first, second = Worker(pool, settings, None).owner, Worker(pool, settings, None).owner
    assert first != second and first.startswith("worker-")


def test_gateway_unavailable_fails_the_run_safely_without_escaping_the_worker(pool, world, settings):
    """AC-11: modelo fora do ar não derruba o worker nem o resto do app."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    worker, tools = _worker(pool, settings, ScriptedGateway([AiError("model_unavailable")]))

    assert worker.run_once() == run_id        # nenhuma exceção escapa

    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed"
    assert view["error"] == {
        "code": "model_unavailable", "retryable": True,
        "safe_message": "Nenhum modelo autorizado está disponível agora.", "trace_id": view["trace_id"],
    }
    assert tools.total_calls() == 0
    # Execução encerrada não volta para a fila, e o worker continua de pé.
    assert worker.run_once() is None


def test_run_without_gateway_configured_fails_as_model_unavailable(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    worker, _ = _worker(pool, settings, None)

    assert worker.run_once() == run_id
    assert runs.get_run_view(pool, ctx, run_id)["error"]["code"] == "model_unavailable"


def test_apply_proposal_runs_through_worker_while_model_is_down(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ALL_FINANCE, mode="assisted")
    tools = ToolKit(pool, settings).with_finance_write()
    proposal = kit.approved_proposal(pool, world, "100.00")
    created = runs.create_system_run(
        pool, ctx, task="apply_proposal",
        input={"proposal_id": proposal["proposal_id"], "expected_version": 1}, settings=settings,
    )
    down = ScriptedGateway([AiError("model_unavailable")])
    worker = Worker(pool, settings, Orchestrator(pool, settings, tools.registry, down), owner="worker-a")

    assert worker.run_once() == created["run_id"]

    assert down.calls == 0
    assert runs.get_run_view(pool, ctx, created["run_id"])["status"] == "completed"
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 1


def test_orchestrator_exception_does_not_escape_and_run_is_retried_after_lease(pool, world, settings):
    class BrokenOrchestrator:
        def execute(self, run_id, tenant_id, owner):
            raise RuntimeError("banco indisponível ao finalizar")

    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    broken = Worker(pool, settings, BrokenOrchestrator(), owner="worker-a")

    assert broken.run_once() == run_id

    assert kit.run_row(pool, world.tenant_id, run_id)["status"] == "running"
    kit.expire_lease(pool, world.tenant_id, run_id)
    healthy, _ = _worker(pool, settings, ScriptedGateway(_simple_plan), owner="worker-b")
    assert healthy.run_once() == run_id
    assert runs.get_run_view(pool, ctx, run_id)["status"] == "completed"


def test_lease_is_renewed_in_background_during_a_long_inference(pool, world, settings):
    """Inferência mais longa que o lease: sem a renovação, outro worker assumiria
    uma execução que não caiu."""
    settings = replace(settings, lease_seconds=2)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    stolen = []

    def slow(request, ctx_, budget):
        if not kit.tool_messages(request):
            time.sleep(3.2)                       # bem mais que um lease inteiro
            stolen.append(runs.claim_next(pool, "worker-b", settings.lease_seconds))
        return _simple_plan(request, ctx_, budget)

    worker, tools = _worker(pool, settings, ScriptedGateway(slow))

    assert worker.run_once() == run_id

    assert stolen == [None]                       # ninguém assumiu no meio
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "completed" and row["attempts"] == 1
    assert tools.calls == {"finance.read": 1}


def test_lease_keeper_renews_while_healthy_and_stops_itself_when_overdue_or_lost(pool, world, settings):
    ctx = world.context(pool)
    healthy = kit.enqueue(pool, ctx, settings)
    overdue = kit.enqueue(pool, ctx, settings)
    assert runs.claim_next(pool, "worker-a", 1)["run_id"] == healthy
    assert runs.claim_next(pool, "worker-a", 1)["run_id"] == overdue
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("UPDATE ai_runs SET deadline_at = now() - interval '30 seconds' WHERE id = %s", (overdue,))
    granted = kit.run_row(pool, world.tenant_id, overdue)["lease_expires_at"]

    def keeper_for(run_id, owner="worker-a"):
        return worker_module._LeaseKeeper(pool, run_id, world.tenant_id, owner, 1)

    alive, late, stranger = keeper_for(healthy), keeper_for(overdue), keeper_for(healthy, owner="worker-x")
    for keeper in (alive, late, stranger):
        keeper.start()
    late.join(timeout=10)
    stranger.join(timeout=10)
    time.sleep(1.2)                     # mais que um lease inteiro
    untouched = kit.run_row(pool, world.tenant_id, overdue)["lease_expires_at"]
    taken = runs.claim_next(pool, "worker-b", 30)
    alive.stop()

    # Prazo estourado além da tolerância: a thread encerra sem renovar nada.
    assert not late.is_alive() and late.stopped_reason == "overdue" and late.renewals == 0
    assert untouched == granted
    # Quem não é o dono não renova o lease de ninguém.
    assert not stranger.is_alive() and stranger.stopped_reason == "lost" and stranger.renewals == 0
    # A execução saudável foi mantida; a vencida ficou disponível para outro worker.
    assert alive.renewals >= 2 and alive.stopped_reason is None
    assert taken is not None and taken["run_id"] == overdue
    assert kit.run_row(pool, world.tenant_id, healthy)["lease_owner"] == "worker-a"


def _stuck_worker_scenario(pool, world, settings, trigger):
    """Uma ferramenta que demora muito mais que o lease, com um gatilho (prazo
    vencido ou cancelamento) disparado logo que ela começa. Devolve o que um
    segundo worker conseguiu fazer ENQUANTO o primeiro ainda estava preso."""
    settings = replace(settings, lease_seconds=1)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    started, finished = threading.Event(), threading.Event()
    worker, tools = _worker(pool, settings, ScriptedGateway(_simple_plan))

    def stuck(ctx_, args):
        trigger(ctx, ctx_)
        started.set()
        time.sleep(4.0)
        finished.set()

    tools.before["finance.read"] = stuck
    thread = threading.Thread(target=worker.run_once)
    thread.start()
    try:
        assert started.wait(timeout=20)
        claimed, deadline = None, time.time() + 3.4
        while claimed is None and time.time() < deadline:
            claimed = runs.claim_next(pool, "worker-b", settings.lease_seconds)
            if claimed is None:
                time.sleep(0.1)
        taken_while_stuck = claimed is not None and not finished.is_set()
        outcome = None
        if claimed is not None:
            rescuer = Orchestrator(pool, settings, ToolKit(pool, settings).with_finance_read({"a": "10.00"}).registry,
                                   ScriptedGateway(_simple_plan))
            outcome = rescuer.execute(claimed["run_id"], claimed["tenant_id"], "worker-b")
    finally:
        thread.join(timeout=30)
    return ctx, run_id, taken_while_stuck, outcome


def test_stuck_tool_cannot_hold_a_run_past_its_deadline(pool, world, settings):
    """Contrato, seção 8: trabalho longo tem prazo e não se renova para sempre.
    A renovação do lease em segundo plano para depois do prazo (mais a
    tolerância), o lease vence e outro worker encerra a execução."""

    def expire_deadline(owner_ctx, handler_ctx):
        with scoped_tx(pool, handler_ctx.tenant_id) as cursor:
            cursor.execute(
                "UPDATE ai_runs SET deadline_at = now() - interval '30 seconds' WHERE id = %s", (handler_ctx.run_id,)
            )

    ctx, run_id, taken_while_stuck, outcome = _stuck_worker_scenario(pool, world, settings, expire_deadline)

    assert taken_while_stuck is True
    assert outcome == {"run_id": run_id, "status": "failed"}
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed" and view["error"]["code"] == "budget_exceeded"
    # O worker preso volta, descobre que perdeu a posse e não grava por cima.
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "failed" and row["attempts"] == 2 and row["lease_owner"] is None


def test_stuck_tool_cannot_ignore_a_cancellation_forever(pool, world, settings):
    def cancel(owner_ctx, handler_ctx):
        runs.request_cancel(pool, owner_ctx, handler_ctx.run_id)
        # O pedido foi feito há mais de um lease (a tolerância).
        with scoped_tx(pool, handler_ctx.tenant_id) as cursor:
            cursor.execute(
                "UPDATE ai_runs SET cancel_requested_at = now() - interval '30 seconds' WHERE id = %s",
                (handler_ctx.run_id,),
            )

    ctx, run_id, taken_while_stuck, outcome = _stuck_worker_scenario(pool, world, settings, cancel)

    assert taken_while_stuck is True
    assert outcome == {"run_id": run_id, "status": "cancelled"}
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "cancelled" and view["cancel_requested"] is True


def test_run_forever_processes_the_queue_and_stops_on_event(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_ids = [kit.enqueue(pool, ctx, settings, message="Pedido %d" % index) for index in range(3)]
    worker, tools = _worker(pool, settings, ScriptedGateway(_simple_plan))
    stop = threading.Event()
    thread = threading.Thread(target=worker.run_forever, args=(stop, 0.05))
    thread.start()
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            statuses = {runs.get_run_view(pool, ctx, run_id)["status"] for run_id in run_ids}
            if statuses == {"completed"}:
                break
            time.sleep(0.1)
    finally:
        stop.set()
        thread.join(timeout=10)

    assert not thread.is_alive()
    assert {runs.get_run_view(pool, ctx, run_id)["status"] for run_id in run_ids} == {"completed"}
    assert tools.calls == {"finance.read": 3}


def test_two_workers_share_the_queue_without_duplicating_work(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_ids = [kit.enqueue(pool, ctx, settings, message="Pedido %d" % index) for index in range(10)]
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway(_simple_plan)
    orchestrator = Orchestrator(pool, settings, tools.registry, gateway)
    handled = {"worker-a": [], "worker-b": []}
    barrier = threading.Barrier(2)

    def work(owner):
        worker = Worker(pool, settings, orchestrator, owner=owner)
        barrier.wait(timeout=10)
        while True:
            run_id = worker.run_once()
            if run_id is None:
                return
            handled[owner].append(run_id)

    threads = [threading.Thread(target=work, args=(owner,)) for owner in handled]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    everything = handled["worker-a"] + handled["worker-b"]
    assert sorted(everything) == sorted(run_ids)
    # Uma ferramenta por execução: nenhuma foi executada duas vezes.
    assert tools.calls == {"finance.read": 10}
    assert all(kit.run_row(pool, world.tenant_id, run_id)["attempts"] == 1 for run_id in run_ids)


# ---------------------------------------------------------------- main()

def test_main_does_nothing_when_ai_is_disabled(monkeypatch):
    built = []
    fake = types.ModuleType("services.ai.platform")
    fake.build_platform = lambda: built.append(True)
    monkeypatch.setitem(sys.modules, "services.ai.platform", fake)

    assert worker_module.main([], env={}) == 0
    assert worker_module.main([], env={"AI_ENABLED": "false"}) == 0
    # Com a IA desligada a plataforma nem chega a ser montada (sem pool, sem fila).
    assert built == []


def test_main_builds_the_platform_late_and_runs_once(pool, world, settings, monkeypatch):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    run_id = kit.enqueue(pool, ctx, settings)
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    built = []

    def build_platform(database_pool, platform_settings):
        assert database_pool is pool
        assert platform_settings.enabled
        built.append(True)
        return types.SimpleNamespace(
            pool=pool, settings=settings,
            orchestrator=Orchestrator(pool, settings, tools.registry, ScriptedGateway(_simple_plan)),
        )

    # Dublê do módulo de montagem, que pertence a outro componente.
    fake = types.ModuleType("services.ai.platform")
    fake.build_platform = build_platform
    monkeypatch.setitem(sys.modules, "services.ai.platform", fake)

    monkeypatch.setattr("database.v2_connection.init_v2_pool", lambda: pool)

    assert worker_module.main(["--once"], env={"AI_ENABLED": "true"}) == 0

    assert built == [True]
    assert runs.get_run_view(pool, ctx, run_id)["status"] == "completed"


# ---------------------------------------------------------------- outbox

class Consumer:
    """Consumidor de notificações que deduplica por ``dedup_key``."""

    def __init__(self):
        self.received = []
        self.notifications = []
        self._seen = set()
        self.fail_with = None

    def __call__(self, message):
        self.received.append(message)
        if self.fail_with is not None:
            raise self.fail_with
        if message["dedup_key"] in self._seen:
            return
        self._seen.add(message["dedup_key"])
        self.notifications.append(message["dedup_key"])


def _applied_operation(pool, world, settings):
    """Aplica uma proposta de verdade: efeito + operação + outbox na mesma transação."""
    ctx = world.context(pool)
    kit.grant(pool, world, ALL_FINANCE, mode="assisted")
    tools = ToolKit(pool, settings).with_finance_write()
    proposal = kit.approved_proposal(pool, world, "100.00")
    runs.create_system_run(
        pool, ctx, task="apply_proposal",
        input={"proposal_id": proposal["proposal_id"], "expected_version": 1}, settings=settings,
    )
    kit.execute_next(pool, settings, tools.registry, None)
    return tools, proposal


def _outbox(pool, tenant_id):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT *, available_at - now() AS wait FROM ai_outbox ORDER BY created_at")
        return [dict(row) for row in cursor.fetchall()]


def _make_available(pool, tenant_id):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("UPDATE ai_outbox SET available_at = now() WHERE status = 'pending'")


def test_outbox_delivery_marks_delivered_and_never_reexecutes_the_effect(pool, world, settings):
    tools, proposal = _applied_operation(pool, world, settings)
    consumer = Consumer()

    delivered_id = deliver_outbox_once(pool, consumer)

    row = _outbox(pool, world.tenant_id)[0]
    assert delivered_id == str(row["id"])
    assert row["status"] == "delivered" and row["delivered_at"] is not None and row["attempts"] == 1
    message = consumer.received[0]
    assert set(message) == {"id", "tenant_id", "topic", "payload", "dedup_key", "operation_id", "run_id", "attempts"}
    assert message["topic"] == "operation.applied" and message["operation_id"] == proposal["operation_id"]
    assert message["dedup_key"] == "operation:%s:applied" % proposal["operation_id"]
    # Nada mais a entregar, e o efeito financeiro continua único.
    assert deliver_outbox_once(pool, consumer) is None
    assert len(consumer.received) == 1
    assert tools.calls["finance.apply_change"] == 1
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_operations") == 1


def test_outbox_failure_is_rescheduled_with_backoff_and_effect_is_not_repeated(pool, world, settings):
    tools, proposal = _applied_operation(pool, world, settings)
    consumer = Consumer()
    consumer.fail_with = RuntimeError("resposta do webhook com SEGREDO-WEBHOOK-77cc")

    assert deliver_outbox_once(pool, consumer) is not None      # a falha não escapa

    row = _outbox(pool, world.tenant_id)[0]
    assert row["status"] == "pending" and row["attempts"] == 1 and row["delivered_at"] is None
    assert row["last_error_code"] == "RuntimeError"             # só o tipo, nunca o corpo
    assert "SEGREDO" not in str(row)
    assert 20 <= row["wait"].total_seconds() <= worker_module.OUTBOX_BACKOFF_BASE_S + 1
    # Ainda não está disponível: uma nova rodada não reentrega antes do backoff.
    assert deliver_outbox_once(pool, consumer) is None and len(consumer.received) == 1

    consumer.fail_with = RuntimeError("segunda falha")
    _make_available(pool, world.tenant_id)
    deliver_outbox_once(pool, consumer)
    second = _outbox(pool, world.tenant_id)[0]
    assert second["attempts"] == 2
    assert second["wait"].total_seconds() > worker_module.OUTBOX_BACKOFF_BASE_S + 5     # backoff cresce

    consumer.fail_with = None
    _make_available(pool, world.tenant_id)
    deliver_outbox_once(pool, consumer)
    final = _outbox(pool, world.tenant_id)[0]
    assert final["status"] == "delivered" and final["attempts"] == 3 and final["last_error_code"] is None
    assert consumer.notifications == ["operation:%s:applied" % proposal["operation_id"]]
    # Três tentativas de entrega, um único efeito financeiro.
    assert tools.calls["finance.apply_change"] == 1
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 1


def test_redelivery_after_worker_death_is_deduplicated_by_the_consumer(pool, world, settings):
    tools, proposal = _applied_operation(pool, world, settings)
    consumer = Consumer()
    died = []

    def handler(message):
        consumer(message)               # a notificação saiu...
        if not died:
            died.append(True)
            raise WorkerKilled()        # ...e o worker morreu antes de confirmar

    with pytest.raises(WorkerKilled):
        deliver_outbox_once(pool, handler)
    row = _outbox(pool, world.tenant_id)[0]
    assert row["status"] == "pending" and row["wait"].total_seconds() > 60   # invisível, não perdida

    _make_available(pool, world.tenant_id)                                    # o tempo passou
    assert deliver_outbox_once(pool, handler) == str(row["id"])

    assert len(consumer.received) == 2                    # a entrega se repetiu
    assert len(consumer.notifications) == 1               # o consumidor não duplicou
    assert _outbox(pool, world.tenant_id)[0]["status"] == "delivered"
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 1
    assert tools.calls["finance.apply_change"] == 1


def test_enqueue_with_same_dedup_key_does_not_create_a_second_message(pool, world):
    with scoped_tx(pool, world.tenant_id) as cursor:
        first = enqueue_outbox(cursor, tenant_id=world.tenant_id, topic="run.finished",
                               dedup_key="run:sintetica-1:finished", payload={"n": 1})
        second = enqueue_outbox(cursor, tenant_id=world.tenant_id, topic="run.finished",
                                dedup_key="run:sintetica-1:finished", payload={"n": 2})
    assert (first, second) == (True, False)
    consumer = Consumer()
    assert deliver_outbox_once(pool, consumer) is not None
    assert deliver_outbox_once(pool, consumer) is None
    assert [m["payload"] for m in consumer.received] == [{"n": 1}]


def test_outbox_gives_up_after_max_attempts(pool, world):
    with scoped_tx(pool, world.tenant_id) as cursor:
        enqueue_outbox(cursor, tenant_id=world.tenant_id, topic="run.finished", dedup_key="run:sintetica-2:x")
    consumer = Consumer()
    consumer.fail_with = RuntimeError("fora do ar")

    deliver_outbox_once(pool, consumer, max_attempts=2)
    _make_available(pool, world.tenant_id)
    deliver_outbox_once(pool, consumer, max_attempts=2)

    row = _outbox(pool, world.tenant_id)[0]
    assert row["status"] == "failed" and row["attempts"] == 2
    _make_available(pool, world.tenant_id)
    assert deliver_outbox_once(pool, consumer, max_attempts=2) is None
    assert len(consumer.received) == 2


def test_concurrent_deliverers_handle_each_message_once_across_tenants(pool, world, other_world):
    keys = []
    for tenant in (world, other_world):
        with scoped_tx(pool, tenant.tenant_id) as cursor:
            for index in range(6):
                key = "aviso:%s:%d" % (tenant.tenant_id[:8], index)
                keys.append(key)
                enqueue_outbox(cursor, tenant_id=tenant.tenant_id, topic="aviso", dedup_key=key)
    lock = threading.Lock()
    received = []
    barrier = threading.Barrier(3)

    def handler(message):
        with lock:
            received.append((message["tenant_id"], message["dedup_key"]))

    def work():
        barrier.wait(timeout=10)
        while deliver_outbox_once(pool, handler) is not None:
            pass

    threads = [threading.Thread(target=work) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert sorted(key for _, key in received) == sorted(keys)        # cada mensagem, uma vez
    # Cada mensagem foi confirmada no tenant dono dela.
    for tenant in (world, other_world):
        rows = _outbox(pool, tenant.tenant_id)
        assert len(rows) == 6 and all(row["status"] == "delivered" for row in rows)
        assert {t for t, key in received if key.startswith("aviso:%s" % tenant.tenant_id[:8])} == {tenant.tenant_id}


def test_queue_scope_cannot_read_delivered_messages(pool, world):
    with scoped_tx(pool, world.tenant_id) as cursor:
        enqueue_outbox(cursor, tenant_id=world.tenant_id, topic="aviso", dedup_key="aviso:entregue:1")
    deliver_outbox_once(pool, lambda message: None)
    with queue_tx(pool) as cursor:
        cursor.execute("SELECT count(*) AS total FROM ai_outbox")
        assert cursor.fetchone()["total"] == 0
