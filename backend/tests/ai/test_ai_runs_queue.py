"""Fila com lease e checkpoints de etapa (contrato, seções 8 e 9)."""

from __future__ import annotations

import threading
import time

import pytest

from services.ai import runs
from services.ai.db import queue_tx, scoped_tx

from .support import orchestrator_kit as kit
from .support import seed


pytestmark = pytest.mark.integration


def _enqueue(pool, world, settings, count=1, space="personal"):
    ctx = world.context(pool, space)
    return [kit.enqueue(pool, ctx, settings, message="Pedido %d" % index) for index in range(count)]


def test_claim_next_takes_oldest_queued_run_and_sets_lease(pool, world, settings):
    first, second = _enqueue(pool, world, settings, 2)

    claimed = runs.claim_next(pool, "worker-a", settings.lease_seconds)

    assert claimed == {
        "run_id": first, "tenant_id": world.tenant_id, "task": "finance_question",
        "attempts": 1, "trace_id": claimed["trace_id"],
    }
    row = kit.run_row(pool, world.tenant_id, first)
    assert row["status"] == "running" and row["lease_owner"] == "worker-a"
    assert row["started_at"] is not None
    remaining = (row["lease_expires_at"] - row["updated_at"]).total_seconds()
    assert abs(remaining - settings.lease_seconds) < 2
    assert kit.run_row(pool, world.tenant_id, second)["status"] == "queued"


def test_claim_next_returns_none_on_empty_queue(pool, world, settings):
    assert runs.claim_next(pool, "worker-a", settings.lease_seconds) is None


def test_running_run_with_valid_lease_is_not_claimed_by_another_worker(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    assert runs.claim_next(pool, "worker-a", settings.lease_seconds)["run_id"] == run_id

    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    assert kit.run_row(pool, world.tenant_id, run_id)["lease_owner"] == "worker-a"


def test_expired_lease_is_reclaimed_and_attempts_increment(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    # Lease real de 2 segundos: o worker-a "cai" e o tempo passa de verdade.
    assert runs.claim_next(pool, "worker-a", 2)["attempts"] == 1
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    time.sleep(2.3)

    reclaimed = runs.claim_next(pool, "worker-b", settings.lease_seconds)

    assert reclaimed["run_id"] == run_id and reclaimed["attempts"] == 2
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["lease_owner"] == "worker-b" and row["status"] == "running"


def test_finished_and_cancelled_runs_are_never_claimed(pool, world, settings):
    done, cancelled = _enqueue(pool, world, settings, 2)
    ctx = world.context(pool)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    runs.finish_run(pool, done, world.tenant_id, "worker-a", status="completed", result={}, error=None)
    runs.request_cancel(pool, ctx, cancelled)

    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    finished = kit.run_row(pool, world.tenant_id, done)
    assert finished["lease_owner"] is None and finished["finished_at"] is not None


def test_two_concurrent_workers_claim_each_run_exactly_once(pool, world, other_world, settings):
    run_ids = _enqueue(pool, world, settings, 12) + _enqueue(pool, other_world, settings, 8)
    barrier = threading.Barrier(2)
    claimed = {"worker-a": [], "worker-b": []}
    errors = []

    def work(owner):
        try:
            barrier.wait(timeout=10)
            while True:
                item = runs.claim_next(pool, owner, settings.lease_seconds)
                if item is None:
                    return
                claimed[owner].append(item["run_id"])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(owner,)) for owner in claimed]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    everything = claimed["worker-a"] + claimed["worker-b"]
    # Cada execução foi assumida por um único worker; nenhuma ficou para trás.
    assert sorted(everything) == sorted(run_ids)
    assert len(set(everything)) == len(run_ids)
    for owner, items in claimed.items():
        for run_id in items:
            tenant = world.tenant_id if run_id in run_ids[:12] else other_world.tenant_id
            row = kit.run_row(pool, tenant, run_id)
            assert row["lease_owner"] == owner and row["attempts"] == 1


def test_queue_transaction_only_sees_pending_runs(pool, world, settings):
    queued, finished = _enqueue(pool, world, settings, 2)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    runs.finish_run(pool, queued, world.tenant_id, "worker-a", status="completed", result={}, error=None)

    with queue_tx(pool) as cursor:
        cursor.execute("SELECT id FROM ai_runs")
        visible = {str(row["id"]) for row in cursor.fetchall()}
    # A política da fila não dá acesso a execuções encerradas de nenhum tenant.
    assert visible == {finished}


# ------------------------------------------------------------------ lease

def test_heartbeat_renews_only_for_the_owner(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", 5)
    before = kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"]

    assert runs.heartbeat(pool, run_id, world.tenant_id, "worker-a", 120) == {
        "renewed": True, "overdue": False, "cancel_requested": False, "deadline_passed": False,
    }
    after = kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"]
    assert (after - before).total_seconds() > 60

    assert runs.heartbeat(pool, run_id, world.tenant_id, "worker-b", 120) is None
    assert kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"] == after


def _shift(pool, tenant_id, run_id, column, seconds_ago):
    assert column in ("deadline_at", "cancel_requested_at")
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_runs SET " + column + " = now() - make_interval(secs => %s) WHERE id = %s AND tenant_id = %s",
            (seconds_ago, run_id, tenant_id),
        )


@pytest.mark.parametrize("column, flag", [("deadline_at", "deadline_passed"), ("cancel_requested_at", "cancel_requested")])
def test_heartbeat_stops_renewing_after_deadline_or_cancel_plus_grace(pool, world, settings, column, flag):
    """Prazo e cancelamento valem mesmo se o orquestrador nunca chegar à próxima
    ação: passada a tolerância, o lease deixa de ser renovado e pode vencer."""
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", 30)
    granted = kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"]

    # Dentro da tolerância (prazo vencido há 10 s, tolerância de 60 s): ainda renova.
    _shift(pool, world.tenant_id, run_id, column, 10)
    within = runs.heartbeat(pool, run_id, world.tenant_id, "worker-a", 120, grace_seconds=60)
    assert within["renewed"] is True and within["overdue"] is False and within[flag] is True
    renewed = kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"]
    assert (renewed - granted).total_seconds() > 60

    # Fora da tolerância: o estado é devolvido, mas o lease fica como estava.
    _shift(pool, world.tenant_id, run_id, column, 90)
    beyond = runs.heartbeat(pool, run_id, world.tenant_id, "worker-a", 120, grace_seconds=60)
    assert beyond["renewed"] is False and beyond["overdue"] is True and beyond[flag] is True
    assert kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"] == renewed

    # Sem tolerância informada, a renovação é incondicional (uso fora do worker).
    unconditional = runs.heartbeat(pool, run_id, world.tenant_id, "worker-a", 300)
    assert unconditional["renewed"] is True and unconditional[flag] is True
    assert kit.run_row(pool, world.tenant_id, run_id)["lease_expires_at"] > renewed


def test_worker_that_lost_the_lease_cannot_write_steps_or_finish(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    step = runs.begin_step(
        pool, run_id, world.tenant_id, "worker-a", step_key="001:tool:finance.read:a", kind="tool",
        name="finance.read", lease_seconds=settings.lease_seconds,
    )
    kit.expire_lease(pool, world.tenant_id, run_id)
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds)["run_id"] == run_id

    # O worker-a ainda está vivo (só lento) e tenta continuar: tudo é recusado.
    with pytest.raises(runs.LeaseLost):
        runs.begin_step(
            pool, run_id, world.tenant_id, "worker-a", step_key="002:tool:finance.read:b", kind="tool",
            name="finance.read", lease_seconds=settings.lease_seconds,
        )
    with pytest.raises(runs.LeaseLost):
        runs.finish_step(
            pool, run_id, world.tenant_id, "worker-a", step["id"], status="succeeded", output={"x": 1},
            lease_seconds=settings.lease_seconds,
        )
    with pytest.raises(runs.LeaseLost):
        runs.finish_run(pool, run_id, world.tenant_id, "worker-a", status="completed", result={}, error=None)
    with pytest.raises(runs.LeaseLost):
        runs.finish_run(pool, run_id, world.tenant_id, "worker-a", status="waiting_review", result={}, error=None)
    # Reabrir a etapa também é escrita: sem a cerca, o worker antigo zeraria a
    # contagem e o resultado de uma etapa que agora pertence a outro worker.
    with pytest.raises(runs.LeaseLost):
        runs.restart_step(pool, run_id, world.tenant_id, "worker-a", step["id"], lease_seconds=settings.lease_seconds)
    assert runs.load_for_execution(pool, world.tenant_id, run_id, "worker-a") is None

    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert [(item["step_key"], item["status"], item["attempts"]) for item in steps] == [
        ("001:tool:finance.read:a", "started", 1)
    ]
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "running" and row["lease_owner"] == "worker-b"


# ------------------------------------------------------------ checkpoints

def test_step_key_is_unique_and_succeeded_step_is_returned_for_reuse(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    common = dict(lease_seconds=settings.lease_seconds)
    args = (pool, run_id, world.tenant_id, "worker-a")

    new = runs.begin_step(*args, step_key="001:tool:finance.read:abc", kind="tool", name="finance.read",
                          version="1.0.0", args_hash="a" * 64, **common)
    assert new["state"] == "new" and new["seq"] == 1 and new["output"] is None

    # Mesma chave antes de concluir: é a mesma etapa, vista como interrompida.
    again = runs.begin_step(*args, step_key="001:tool:finance.read:abc", kind="tool", name="finance.read", **common)
    assert again["state"] == "interrupted" and again["id"] == new["id"]

    runs.finish_step(*args, new["id"], status="succeeded", output={"result": {"data": {"valor": "10.00"}}},
                     duration_ms=7, **common)
    reused = runs.begin_step(*args, step_key="001:tool:finance.read:abc", kind="tool", name="finance.read", **common)
    assert reused["state"] == "succeeded" and reused["id"] == new["id"]
    assert reused["output"] == {"result": {"data": {"valor": "10.00"}}}

    other = runs.begin_step(*args, step_key="002:tool:finance.read:def", kind="tool", name="finance.read", **common)
    assert other["state"] == "new" and other["seq"] == 2
    assert seed.count_rows(pool, world.tenant_id, "ai_run_steps", "run_id = %s", (run_id,)) == 2


def test_finished_step_is_not_overwritten_and_failed_step_keeps_its_error(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    common = dict(lease_seconds=settings.lease_seconds)
    args = (pool, run_id, world.tenant_id, "worker-a")
    step = runs.begin_step(*args, step_key="001:tool:x", kind="tool", name="finance.read", **common)
    runs.finish_step(*args, step["id"], status="succeeded", output={"result": {"n": 1}}, **common)

    # Segunda conclusão e reabertura não alteram um checkpoint concluído.
    runs.finish_step(*args, step["id"], status="failed", output={"error": {"code": "x"}}, error_code="x", **common)
    runs.restart_step(*args, step["id"], **common)
    row = kit.step_rows(pool, world.tenant_id, run_id)[0]
    assert row["status"] == "succeeded" and row["output"] == {"result": {"n": 1}} and row["attempts"] == 1

    failed = runs.begin_step(*args, step_key="002:tool:y", kind="tool", name="finance.read", **common)
    runs.finish_step(*args, failed["id"], status="failed", error_code="invalid_request",
                     output={"error": {"code": "invalid_request"}}, **common)
    seen = runs.begin_step(*args, step_key="002:tool:y", kind="tool", name="finance.read", **common)
    assert seen["state"] == "failed" and seen["error_code"] == "invalid_request"
    runs.restart_step(*args, failed["id"], **common)
    restarted = kit.step_rows(pool, world.tenant_id, run_id)[1]
    assert restarted["status"] == "started" and restarted["attempts"] == 2 and restarted["output"] is None


def test_step_output_rejects_float(pool, world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    step = runs.begin_step(pool, run_id, world.tenant_id, "worker-a", step_key="001:tool:x", kind="tool",
                           name="finance.read", lease_seconds=settings.lease_seconds)
    with pytest.raises(TypeError):
        runs.finish_step(pool, run_id, world.tenant_id, "worker-a", step["id"], status="succeeded",
                         output={"valor": 10.5}, lease_seconds=settings.lease_seconds)
    assert kit.step_rows(pool, world.tenant_id, run_id)[0]["status"] == "started"


def test_step_and_run_text_that_the_database_refuses_is_stored_sanitized(pool, world, settings):
    """NUL (recusado pelo PostgreSQL) e substituto isolado (sem UTF-8) viram
    U+FFFD na gravação, em qualquer nível: chave, valor, lista, erro, modelo."""
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    common = dict(lease_seconds=settings.lease_seconds)
    args = (pool, run_id, world.tenant_id, "worker-a")
    dirty = {"result": {"data": {"corpo": "antes\u0000depois", "lista": ["a\ud800b", {"ch\u0000ave": "ok"}]}}}

    assert runs.has_unstorable(dirty) is True
    assert runs.storable(dirty) == {
        "result": {"data": {"corpo": "antes�depois", "lista": ["a�b", {"ch�ave": "ok"}]}}
    }
    assert runs.has_unstorable(runs.storable(dirty)) is False
    assert runs.storable({"n": 1, "ok": True, "nada": None}) == {"n": 1, "ok": True, "nada": None}

    step = runs.begin_step(*args, step_key="001:tool:x", kind="tool", name="email.get_message", **common)
    runs.finish_step(*args, step["id"], status="succeeded", output=dirty, **common)
    stored = kit.step_rows(pool, world.tenant_id, run_id)[0]
    assert stored["status"] == "succeeded"
    assert stored["output"] == runs.storable(dirty)

    runs.finish_run(
        *args, status="failed", result={"summary_pt_br": "texto\u0000final", "warnings": ["aviso\ud800"]},
        error={"code": "internal_error", "safe_message": "falha\u0000"},
        model={"alias": "rota\u0000a", "provider": "ollama", "model_id": "modelo\u0000x"},
        actor_user_id=world.user_id, audit={"route_attempts": [{"alias": "rota\u0000a"}]},
    )
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "failed"
    assert row["result"] == {"summary_pt_br": "texto�final", "warnings": ["aviso�"]}
    assert row["error"]["safe_message"] == "falha�"
    assert (row["model_alias"], row["model_id"]) == ("rota�a", "modelo�x")
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["route_attempts"] == [{"alias": "rota�a"}]


def test_steps_of_a_run_are_invisible_from_another_tenant(pool, world, other_world, settings):
    (run_id,) = _enqueue(pool, world, settings)
    runs.claim_next(pool, "worker-a", settings.lease_seconds)
    runs.begin_step(pool, run_id, world.tenant_id, "worker-a", step_key="001:tool:x", kind="tool",
                    name="finance.read", lease_seconds=settings.lease_seconds)

    with scoped_tx(pool, other_world.tenant_id) as cursor:
        cursor.execute("SELECT count(*) AS total FROM ai_run_steps")
        assert cursor.fetchone()["total"] == 0
    # Um worker que informe o tenant errado não consegue gravar na execução.
    with pytest.raises(runs.LeaseLost):
        runs.begin_step(pool, run_id, other_world.tenant_id, "worker-a", step_key="002:tool:y", kind="tool",
                        name="finance.read", lease_seconds=settings.lease_seconds)
