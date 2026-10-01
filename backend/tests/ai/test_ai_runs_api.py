"""Execuções persistentes: criação idempotente, visão, listagem e cancelamento.

Cobre AC-01 (isolamento por tenant, espaço e ator) e a parte de reenvio do
AC-15 (a mesma Idempotency-Key devolve a mesma execução).
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import date

import pytest

from services.ai import CONTRACT_VERSION, runs
from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.scope import resolve_scope
from services.ai.types import Privacy

from .support import orchestrator_kit as kit
from .support import seed


pytestmark = pytest.mark.integration

VIEW_KEYS = kit.VIEW_KEYS


def _create(pool, ctx, settings, **overrides):
    params = dict(task="finance_question", message="Quanto falta pagar em outubro?", settings=settings)
    params.update(overrides)
    return runs.create_run(pool, ctx, **params)


# ----------------------------------------------------------------- criação

@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"task": "relatorio_livre"}, "task"),
        # Tarefas do servidor nunca são pedidas diretamente.
        ({"task": "apply_proposal"}, "task"),
        ({"task": "reverse_operation"}, "task"),
        ({"message": ""}, "message"),
        ({"message": "   "}, "message"),
        ({"message": "x" * 2001}, "message"),
        ({"message": 123}, "message"),
        # Caracteres que o banco recusa (NUL), que não têm UTF-8 (substituto
        # isolado) ou que não são texto digitado (controle): erro do pedido,
        # nunca exceção de banco.
        ({"message": "oi\u0000tudo"}, "message"),
        ({"message": "quanto falta pagar?\u0007"}, "message"),
        ({"message": "valor \ud800 quebrado"}, "message"),
        ({"input_refs": ["sem-prefixo"]}, "input_refs"),
        ({"input_refs": ["shell:rm -rf"]}, "input_refs"),
        ({"input_refs": ["artifact:com espaco"]}, "input_refs"),
        ({"input_refs": ["artifact:abc\n"]}, "input_refs"),      # quebra de linha final
        ({"input_refs": ["artifact:a"] * 21}, "input_refs"),
        ({"input_refs": "artifact:a"}, "input_refs"),
        ({"idempotency_key": "curta"}, "Idempotency-Key"),
        ({"idempotency_key": "com espaco dentro"}, "Idempotency-Key"),
        ({"idempotency_key": "abcdefgh\n"}, "Idempotency-Key"),  # quebra de linha final
    ],
)
def test_create_run_rejects_invalid_request(pool, world, settings, overrides, field):
    ctx = world.context(pool)
    with pytest.raises(AiError) as excinfo:
        _create(pool, ctx, settings, **overrides)
    assert excinfo.value.code == "invalid_request"
    assert excinfo.value.details == {"field": field}
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 0


def test_create_run_accepts_multiline_message(pool, world, settings):
    """Quebra de linha e tabulação são texto legítimo; só controles são recusados."""
    ctx = world.context(pool)
    message = "Duas perguntas:\n\t1) quanto falta pagar?\r\n\t2) quanto já paguei?"
    created = _create(pool, ctx, settings, message=message)
    assert kit.run_row(pool, world.tenant_id, created["run_id"])["input"]["message"] == message


def test_create_run_accepts_boundary_message_and_refs(pool, world, settings):
    ctx = world.context(pool)
    created = _create(
        pool, ctx, settings, message="x" * 2000,
        input_refs=["artifact:%s" % seed.new_id(), "email:msg-sintetica-1"],
    )
    row = kit.run_row(pool, world.tenant_id, created["run_id"])
    assert len(row["input"]["message"]) == 2000
    assert len(row["input"]["input_refs"]) == 2


def test_create_run_persists_queue_state_deadline_and_audit_by_reference(pool, world, settings):
    ctx = world.context(pool)
    message = "Quanto gastei com o mercado Sintético em outubro?"
    created = _create(pool, ctx, settings, message=message, idempotency_key="chave-teste-0001")

    assert created["status"] == "queued" and created["created"] is True
    assert created["trace_id"] == ctx.trace_id
    row = kit.run_row(pool, world.tenant_id, created["run_id"])
    assert row["status"] == "queued" and row["task"] == "finance_question"
    assert row["contract_version"] == CONTRACT_VERSION
    assert str(row["actor_user_id"]) == world.user_id
    assert str(row["financial_space_id"]) == world.personal_space_id
    assert row["privacy"] == "local_only" and row["channel"] == "web"
    assert len(row["request_hash"]) == 64
    assert row["lease_owner"] is None and row["attempts"] == 0
    # O prazo é fixado na criação e vale run_timeout_s.
    window = (row["deadline_at"] - row["created_at"]).total_seconds()
    assert abs(window - settings.run_timeout_s) < 2

    events = kit.audit_events(pool, world.tenant_id, "ai.run.created")
    assert len(events) == 1
    metadata = events[0]["metadata"]
    assert str(events[0]["entity_id"]) == created["run_id"]
    assert metadata["request_hash"] == row["request_hash"]
    assert metadata["task"] == "finance_question"
    # Auditoria por referência: o texto do pedido não aparece em lugar nenhum dela.
    assert "mercado" not in str(metadata) and "Sintético" not in str(metadata)


def test_create_run_is_refused_when_ai_is_disabled(pool, world, settings):
    ctx = world.context(pool)
    with pytest.raises(AiError) as excinfo:
        _create(pool, ctx, replace(settings, enabled=False))
    assert excinfo.value.code == "ai_disabled"
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 0


def test_same_idempotency_key_and_body_returns_the_same_run(pool, world, settings):
    ctx = world.context(pool)
    first = _create(pool, ctx, settings, idempotency_key="chave-teste-0002")
    # O reenvio chega com outro request_id/trace_id (nova requisição HTTP).
    resend_ctx = world.context(pool)
    assert resend_ctx.request_id != ctx.request_id
    second = _create(pool, resend_ctx, settings, idempotency_key="chave-teste-0002")

    assert second["run_id"] == first["run_id"]
    assert second["created"] is False
    assert second["trace_id"] == first["trace_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 1
    assert len(kit.audit_events(pool, world.tenant_id, "ai.run.created")) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"message": "Outro pedido completamente diferente"},
        {"task": "statement_import"},
        {"input_refs": ["artifact:outro-arquivo"]},
    ],
)
def test_same_idempotency_key_with_different_body_conflicts(pool, world, settings, change):
    ctx = world.context(pool)
    first = _create(pool, ctx, settings, idempotency_key="chave-teste-0003")
    with pytest.raises(AiError) as excinfo:
        _create(pool, ctx, settings, idempotency_key="chave-teste-0003", **change)
    assert excinfo.value.code == "conflict" and excinfo.value.http_status == 409
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 1
    assert kit.run_row(pool, world.tenant_id, first["run_id"])["status"] == "queued"


def test_same_idempotency_key_in_another_space_conflicts(pool, world, settings):
    _create(pool, world.context(pool, "personal"), settings, idempotency_key="chave-teste-0004")
    with pytest.raises(AiError) as excinfo:
        _create(pool, world.context(pool, "business"), settings, idempotency_key="chave-teste-0004")
    assert excinfo.value.code == "conflict"


def test_same_idempotency_key_with_another_privacy_conflicts(pool, world, settings):
    """A privacidade muda o significado do pedido (para onde os dados podem ir):
    reenviar a mesma chave pedindo outra política não pode virar um "replay"."""
    first = _create(pool, world.context(pool), settings, idempotency_key="chave-teste-0006")
    with pytest.raises(AiError) as excinfo:
        _create(pool, world.context(pool, privacy=Privacy.CLOUD_ALLOWED), settings,
                idempotency_key="chave-teste-0006")
    assert excinfo.value.code == "conflict"
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 1
    assert kit.run_row(pool, world.tenant_id, first["run_id"])["privacy"] == "local_only"


def test_idempotency_key_is_scoped_to_the_actor(pool, world, settings):
    """AC-01: a mesma chave e o MESMO corpo enviados por outra pessoa do mesmo
    tenant e espaço criam outra execução; ninguém recebe o run_id alheio."""
    owner_ctx = world.context(pool)
    partner_ctx = _second_actor(pool, world)
    key = "chave-compartilhada-0001"

    mine = _create(pool, owner_ctx, settings, idempotency_key=key)
    theirs = _create(pool, partner_ctx, settings, idempotency_key=key)

    assert theirs["created"] is True and theirs["run_id"] != mine["run_id"]
    assert theirs["trace_id"] == partner_ctx.trace_id != mine["trace_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 2
    assert str(kit.run_row(pool, world.tenant_id, theirs["run_id"])["actor_user_id"]) == partner_ctx.actor_id
    # Cada um reenvia e recebe a PRÓPRIA execução.
    assert _create(pool, world.context(pool), settings, idempotency_key=key)["run_id"] == mine["run_id"]
    assert _create(pool, _context_of(pool, world, partner_ctx.actor_id), settings,
                   idempotency_key=key)["run_id"] == theirs["run_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 2


def test_user_key_never_collides_with_a_server_task_key(pool, world, settings):
    """O titular (ou um cliente com defeito) usa, em um pedido comum, exatamente
    a chave que o servidor usará ao aprovar uma proposta. A tarefa do servidor
    precisa ser agendada mesmo assim: as duas origens não dividem chaves."""
    ctx = world.context(pool)
    proposal_id = seed.new_id()
    key = "apply:%s:1" % proposal_id
    payload = {"proposal_id": proposal_id, "expected_version": 1}

    asked = _create(pool, ctx, settings, idempotency_key=key)
    scheduled = runs.create_system_run(
        pool, ctx, task="apply_proposal", input=payload, idempotency_key=key, settings=settings,
    )

    assert scheduled["created"] is True and scheduled["run_id"] != asked["run_id"]
    assert kit.run_row(pool, world.tenant_id, scheduled["run_id"])["task"] == "apply_proposal"
    # Dentro de cada origem a chave continua idempotente.
    assert _create(pool, ctx, settings, idempotency_key=key)["run_id"] == asked["run_id"]
    assert runs.create_system_run(
        pool, ctx, task="apply_proposal", input=payload, idempotency_key=key, settings=settings,
    )["run_id"] == scheduled["run_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 2
    # A chave escolhida pelo cliente não é gravada em texto puro.
    stored = {kit.run_row(pool, world.tenant_id, item["run_id"])["idempotency_key"] for item in (asked, scheduled)}
    assert len(stored) == 2 and all(key not in value for value in stored)


def test_without_idempotency_key_each_post_is_a_new_run(pool, world, settings):
    ctx = world.context(pool)
    first = _create(pool, ctx, settings)
    second = _create(pool, ctx, settings)
    assert first["run_id"] != second["run_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 2


def test_concurrent_posts_with_same_key_create_a_single_run(pool, world, settings):
    ctx = world.context(pool)
    barrier = threading.Barrier(6)
    results, errors = [], []

    def post():
        try:
            barrier.wait(timeout=10)
            results.append(_create(pool, ctx, settings, idempotency_key="chave-teste-0005"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=post) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len({item["run_id"] for item in results}) == 1
    assert sum(1 for item in results if item["created"]) == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 1


def test_system_run_validation_and_idempotency(pool, world, settings):
    ctx = world.context(pool)
    proposal_id = seed.new_id()
    for bad in (
        {"proposal_id": proposal_id},
        {"proposal_id": "nao-e-uuid", "expected_version": 1},
        {"proposal_id": proposal_id, "expected_version": 0},
        {"proposal_id": proposal_id, "expected_version": True},
        {"proposal_id": proposal_id, "expected_version": 1, "financial_space_id": world.business_space_id},
        "texto",
    ):
        with pytest.raises(AiError) as excinfo:
            runs.create_system_run(pool, ctx, task="apply_proposal", input=bad, settings=settings)
        assert excinfo.value.code == "invalid_request"
    with pytest.raises(AiError) as excinfo:
        runs.create_system_run(
            pool, ctx, task="finance_question", input={"proposal_id": proposal_id, "expected_version": 1},
            settings=settings,
        )
    assert excinfo.value.code == "invalid_request"
    with pytest.raises(AiError):
        runs.create_system_run(
            pool, ctx, task="reverse_operation", input={"operation_id": seed.new_id(), "reason": " "},
            settings=settings,
        )
    with pytest.raises(AiError):
        runs.create_system_run(
            pool, ctx, task="reverse_operation", input={"operation_id": seed.new_id(), "reason": "ab"},
            settings=settings,
        )
    with pytest.raises(AiError) as excinfo:
        runs.create_system_run(
            pool, ctx, task="reverse_operation",
            input={"operation_id": seed.new_id(), "reason": "lançado\u0000em dobro"}, settings=settings,
        )
    assert excinfo.value.code == "invalid_request"      # NUL não chega ao banco
    with pytest.raises(AiError) as excinfo:
        runs.create_system_run(
            pool, ctx, task="apply_proposal", input={"proposal_id": proposal_id, "expected_version": 1},
            settings=replace(settings, enabled=False),
        )
    assert excinfo.value.code == "ai_disabled"
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 0

    payload = {"proposal_id": proposal_id, "expected_version": 1}
    first = runs.create_system_run(
        pool, ctx, task="apply_proposal", input=payload, idempotency_key="apply:%s:1" % proposal_id,
        settings=settings,
    )
    again = runs.create_system_run(
        pool, ctx, task="apply_proposal", input=payload, idempotency_key="apply:%s:1" % proposal_id,
        settings=settings,
    )
    assert again["run_id"] == first["run_id"] and again["created"] is False
    row = kit.run_row(pool, world.tenant_id, first["run_id"])
    assert row["task"] == "apply_proposal" and row["input"] == payload
    # Tarefa do servidor tem prazo explícito e maior que o interativo.
    assert (row["deadline_at"] - row["created_at"]).total_seconds() >= runs.SYSTEM_RUN_TIMEOUT_S - 2


# ------------------------------------------------------------------- visão

def test_run_view_has_exact_spec_shape_while_queued(pool, world, settings):
    ctx = world.context(pool)
    created = _create(pool, ctx, settings)
    view = runs.get_run_view(pool, ctx, created["run_id"])

    assert set(view) == VIEW_KEYS
    assert view["run_id"] == created["run_id"]
    assert view["status"] == "queued" and view["task"] == "finance_question"
    assert view["contract_version"] == CONTRACT_VERSION
    assert view["trace_id"] == ctx.trace_id
    assert view["created_at"].endswith("Z") and view["finished_at"] is None
    assert view["cancel_requested"] is False
    assert view["scope"] == {
        "financial_space": {"id": world.personal_space_id, "name": "Pessoal", "kind": "personal"},
        "accounts": [{"id": world.personal_account_id, "name": "Conta pessoal alfa"}],
    }
    assert view["progress"] == {"stage": "searching", "steps": []}
    # Sem resultado ainda: nada de texto ou número inventado.
    assert view["summary_pt_br"] == ""
    assert view["facts"] == [] and view["sources"] == []
    assert view["proposal_ids"] == [] and view["operation_ids"] == [] and view["warnings"] == []
    assert view["model"] == {"alias": None, "provider": None, "fallback_used": False}
    assert view["error"] is None


def test_run_view_reports_steps_with_portuguese_labels_and_stage(pool, world, settings):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings)["run_id"]
    claimed = kit.claim(pool, settings, "worker-a")
    common = dict(lease_seconds=settings.lease_seconds)
    first = runs.begin_step(
        pool, run_id, world.tenant_id, "worker-a", step_key="001:inference:x", kind="inference",
        name=runs.INFERENCE_STEP_NAME, **common
    )
    runs.finish_step(pool, run_id, world.tenant_id, "worker-a", first["id"], status="succeeded", output={}, **common)
    runs.begin_step(
        pool, run_id, world.tenant_id, "worker-a", step_key="002:tool:finance.read:y", kind="tool",
        name="finance.read", **common
    )
    assert claimed["run_id"] == run_id

    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "running"
    assert view["progress"]["stage"] == "reading"
    steps = view["progress"]["steps"]
    assert [set(step) for step in steps] == [
        {"seq", "kind", "name", "label", "status", "started_at", "finished_at"}
    ] * 2
    assert steps[0] == {
        "seq": 1, "kind": "inference", "name": "model.inference", "label": "Interpretando o pedido",
        "status": "succeeded", "started_at": steps[0]["started_at"], "finished_at": steps[0]["finished_at"],
    }
    assert steps[0]["finished_at"] is not None
    assert steps[1]["label"] == "Consultando dados financeiros"
    assert steps[1]["status"] == "started" and steps[1]["finished_at"] is None


# ---------------------------------------------------------------- AC-01

def _context_of(pool, world, user_id):
    """Novo contexto (nova requisição) de uma pessoa no espaço pessoal."""
    return resolve_scope(
        pool, user_id=user_id, requested_tenant_id=world.tenant_id,
        requested_space_id=world.personal_space_id,
    )


def _second_actor(pool, world):
    """Outra pessoa da mesma organização e do mesmo espaço."""
    user_id = seed.create_user(pool, "familiar-%s@example.test" % seed.new_id()[:8], "Familiar Teste")
    seed.add_tenant_member(pool, world.tenant_id, user_id, "member")
    seed.add_space_member(pool, world.tenant_id, world.personal_space_id, user_id, "member")
    return _context_of(pool, world, user_id)


def _add_step(pool, tenant_id, run_id, owner, settings, *, step_key, name, kind="tool", finish=True):
    common = dict(lease_seconds=settings.lease_seconds)
    step = runs.begin_step(pool, run_id, tenant_id, owner, step_key=step_key, kind=kind, name=name, **common)
    if finish:
        runs.finish_step(pool, run_id, tenant_id, owner, step["id"], status="succeeded", output={}, **common)
    return step


def test_run_view_lists_only_the_steps_of_that_run(pool, world, settings):
    """AC-01: a visão de uma execução nunca traz etapas de outra execução do
    mesmo tenant — nem de outra pessoa, nem de outro espaço, nem da própria."""
    owner_ctx = world.context(pool, "personal")
    partner_ctx = _second_actor(pool, world)
    business_ctx = world.context(pool, "business")
    mine = _create(pool, owner_ctx, settings)["run_id"]
    theirs = _create(pool, partner_ctx, settings)["run_id"]
    business = _create(pool, business_ctx, settings, task="statement_import")["run_id"]
    untouched = _create(pool, owner_ctx, settings)["run_id"]

    plan = {
        mine: [("001:tool:finance.read:a", "finance.read")],
        theirs: [("001:tool:rag.search_personal:b", "rag.search_personal"),
                 ("002:tool:finance.read:c", "finance.read")],
        business: [("001:tool:email.search_financial:d", "email.search_financial"),
                   ("002:tool:email.get_message:e", "email.get_message"),
                   ("003:tool:imports.preview:f", "imports.preview")],
    }
    for index in range(3):
        claimed = kit.claim(pool, settings, "worker-%d" % index)
        for step_key, name in plan[claimed["run_id"]]:
            _add_step(pool, world.tenant_id, claimed["run_id"], "worker-%d" % index, settings,
                      step_key=step_key, name=name)

    def step_names(ctx, run_id):
        return [step["name"] for step in runs.get_run_view(pool, ctx, run_id)["progress"]["steps"]]

    assert step_names(owner_ctx, mine) == ["finance.read"]
    assert step_names(partner_ctx, theirs) == ["rag.search_personal", "finance.read"]
    assert step_names(business_ctx, business) == ["email.search_financial", "email.get_message", "imports.preview"]
    # Execução sem etapas continua sem etapas, mesmo com outras cheias no tenant.
    assert step_names(owner_ctx, untouched) == []


@pytest.mark.parametrize(
    "tool, stage",
    [
        ("email.search_financial", "searching"),
        ("rag.search_personal", "searching"),
        ("email.get_message", "reading"),
        ("finance.read", "reading"),
        ("imports.preview", "preparing"),
        ("finance.prepare_change", "preparing"),
        ("finance.apply_change", "applying"),
        ("finance.reverse_change", "applying"),
    ],
)
def test_progress_stage_follows_the_last_tool_while_running(pool, world, settings, tool, stage):
    """Estado real para a tela: buscando -> lendo -> preparando -> aplicando."""
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings)["run_id"]
    kit.claim(pool, settings, "worker-a")
    _add_step(pool, world.tenant_id, run_id, "worker-a", settings, step_key="001:inference:x",
              name=runs.INFERENCE_STEP_NAME, kind="inference")
    _add_step(pool, world.tenant_id, run_id, "worker-a", settings, step_key="002:tool:%s:y" % tool,
              name=tool, finish=False)

    view = runs.get_run_view(pool, ctx, run_id)

    assert view["status"] == "running"
    assert view["progress"]["stage"] == stage


def test_run_is_invisible_to_other_tenant_space_and_actor(pool, world, other_world, settings):
    owner_ctx = world.context(pool, "personal")
    run_id = _create(pool, owner_ctx, settings)["run_id"]

    intruders = {
        "outro tenant": other_world.context(pool, "personal"),
        "outro espaço": world.context(pool, "business"),
        "outro ator": _second_actor(pool, world),
    }
    for label, intruder in intruders.items():
        with pytest.raises(AiError) as excinfo:
            runs.get_run_view(pool, intruder, run_id)
        assert excinfo.value.code == "not_found", label
        with pytest.raises(AiError) as excinfo:
            runs.request_cancel(pool, intruder, run_id)
        assert excinfo.value.code == "not_found", label
        assert runs.list_runs(pool, intruder)["items"] == [], label

    # Nenhuma das tentativas alterou a execução do dono.
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "queued" and row["cancel_requested_at"] is None
    assert [item["run_id"] for item in runs.list_runs(pool, owner_ctx)["items"]] == [run_id]


def test_run_space_id_lets_the_route_pick_the_space_only_for_own_runs(pool, world, other_world, settings):
    run_id = _create(pool, world.context(pool, "business"), settings)["run_id"]

    space_id = runs.run_space_id(pool, tenant_id=world.tenant_id, actor_id=world.user_id, run_id=run_id)

    assert space_id == world.business_space_id
    partner = _second_actor(pool, world)
    for tenant_id, actor_id in (
        (world.tenant_id, partner.actor_id),               # outra pessoa do mesmo tenant
        (other_world.tenant_id, other_world.user_id),      # outro tenant
        (other_world.tenant_id, world.user_id),            # tenant trocado pelo cliente
    ):
        with pytest.raises(AiError) as excinfo:
            runs.run_space_id(pool, tenant_id=tenant_id, actor_id=actor_id, run_id=run_id)
        assert excinfo.value.code == "not_found"
    with pytest.raises(AiError) as excinfo:
        runs.run_space_id(pool, tenant_id=world.tenant_id, actor_id=world.user_id, run_id="nao-e-uuid")
    assert excinfo.value.code == "not_found"


def test_malformed_run_id_is_not_found(pool, world):
    ctx = world.context(pool)
    for bad in ("nao-e-uuid", "", None, "1; DROP TABLE ai_runs"):
        with pytest.raises(AiError) as excinfo:
            runs.get_run_view(pool, ctx, bad)
        assert excinfo.value.code == "not_found"


# -------------------------------------------------------------- listagem

def test_list_runs_paginates_with_opaque_cursor(pool, world, settings):
    ctx = world.context(pool)
    created = [_create(pool, ctx, settings, message="Pedido %d" % index)["run_id"] for index in range(5)]

    first = runs.list_runs(pool, ctx, limit=2)
    second = runs.list_runs(pool, ctx, limit=2, cursor=first["next_cursor"])
    third = runs.list_runs(pool, ctx, limit=2, cursor=second["next_cursor"])

    pages = [[item["run_id"] for item in page["items"]] for page in (first, second, third)]
    assert pages == [created[4:2:-1], created[2:0:-1], created[0:1]]  # mais recente primeiro
    assert third["next_cursor"] is None
    # O cursor não expõe ids nem datas em texto puro.
    assert created[3] not in first["next_cursor"]
    assert set(first["items"][0]) == {
        "run_id", "status", "task", "trace_id", "created_at", "finished_at", "cancel_requested", "summary_pt_br",
    }


@pytest.mark.parametrize("cursor", ["nao-e-cursor", "e30", "", "eyJjIjoiMjAyNiIsImkiOiJ4In0"])
def test_list_runs_rejects_invalid_cursor(pool, world, cursor):
    with pytest.raises(AiError) as excinfo:
        runs.list_runs(pool, world.context(pool), cursor=cursor)
    assert excinfo.value.code == "invalid_request"


@pytest.mark.parametrize("limit", [0, 51, -1, True, "10"])
def test_list_runs_rejects_invalid_limit(pool, world, limit):
    with pytest.raises(AiError) as excinfo:
        runs.list_runs(pool, world.context(pool), limit=limit)
    assert excinfo.value.code == "invalid_request"


def test_cursor_from_another_actor_does_not_leak_runs(pool, world, other_world, settings):
    owner_ctx = world.context(pool)
    for index in range(3):
        _create(pool, owner_ctx, settings, message="Pedido %d" % index)
    cursor = runs.list_runs(pool, owner_ctx, limit=1)["next_cursor"]
    # O cursor só carrega a posição. Quem o reutiliza continua preso ao próprio
    # escopo: outro tenant, outro espaço do mesmo tenant e outra pessoa do mesmo
    # espaço não enxergam as execuções mais antigas do dono.
    intruders = [other_world.context(pool), world.context(pool, "business"), _second_actor(pool, world)]
    for intruder in intruders:
        assert runs.list_runs(pool, intruder, cursor=cursor)["items"] == []
    assert len(runs.list_runs(pool, owner_ctx, cursor=cursor)["items"]) == 2


# ---------------------------------------------------------- cancelamento

def test_cancel_queued_run_is_immediate_and_run_is_never_claimed(pool, world, settings):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings)["run_id"]

    view = runs.request_cancel(pool, ctx, run_id)

    assert view["status"] == "cancelled"
    assert view["cancel_requested"] is True
    assert view["finished_at"] is not None
    assert view["progress"]["stage"] == "done"
    assert runs.claim_next(pool, "worker-a", settings.lease_seconds) is None
    events = kit.audit_events(pool, world.tenant_id, "ai.run.cancel_requested")
    assert [event["metadata"]["status"] for event in events] == ["cancelled"]


def test_cancel_running_run_only_records_the_request(pool, world, settings):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings)["run_id"]
    kit.claim(pool, settings, "worker-a")

    view = runs.request_cancel(pool, ctx, run_id)

    assert view["status"] == "running" and view["cancel_requested"] is True
    assert view["finished_at"] is None
    with scoped_tx(pool, world.tenant_id) as cursor:
        lease = runs.touch_lease(cursor, run_id, world.tenant_id, "worker-a", settings.lease_seconds)
    assert lease["cancel_requested"] is True


def test_cancel_is_idempotent_and_does_not_reopen_finished_runs(pool, world, settings):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings)["run_id"]
    first = runs.request_cancel(pool, ctx, run_id)
    second = runs.request_cancel(pool, ctx, run_id)
    assert first["status"] == second["status"] == "cancelled"
    assert first["finished_at"] == second["finished_at"]
    assert len(kit.audit_events(pool, world.tenant_id, "ai.run.cancel_requested")) == 1


# ------------------------------------------------- fim da revisão (spec 5)

def test_settle_waiting_review_closes_run_only_when_no_proposal_is_live(pool, world, settings):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings, task="statement_import")["run_id"]
    first = kit.approved_proposal(pool, world, "100.00", status="ready")
    second = kit.approved_proposal(pool, world, "200.00", status="ready")
    kit.claim(pool, settings, "worker-a")
    runs.finish_run(
        pool, run_id, world.tenant_id, "worker-a", status="waiting_review",
        result={"summary_pt_br": "", "proposal_ids": [first["proposal_id"], second["proposal_id"]]}, error=None,
    )

    def reject(proposal_id):
        with scoped_tx(pool, world.tenant_id) as cursor:
            cursor.execute(
                "UPDATE ai_proposals SET status = 'rejected', rejected_reason = 'teste' WHERE id = %s",
                (proposal_id,),
            )
            return runs.settle_waiting_review(cursor, world.tenant_id, proposal_id)

    assert reject(first["proposal_id"]) == []
    assert kit.run_row(pool, world.tenant_id, run_id)["status"] == "waiting_review"
    assert reject(second["proposal_id"]) == [run_id]
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "completed" and row["finished_at"] is not None


def _set_proposal_status(pool, tenant_id, proposal_id, status):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_proposals SET status = %s, rejected_reason = 'teste' WHERE id = %s AND tenant_id = %s",
            (status, proposal_id, tenant_id),
        )


def _finish_waiting(pool, world, settings, proposal_ids, owner="worker-a"):
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings, task="statement_import")["run_id"]
    kit.claim(pool, settings, owner)
    stored = runs.finish_run(
        pool, run_id, world.tenant_id, owner, status="waiting_review",
        result={"summary_pt_br": "", "proposal_ids": list(proposal_ids)}, error=None,
        actor_user_id=world.user_id, audit={"status": "waiting_review"},
    )
    return run_id, stored


def test_finish_run_does_not_park_a_run_whose_review_already_ended(pool, world, settings):
    """A revisão terminou entre a decisão do orquestrador e a gravação: quem
    fecharia a execução (settle_waiting_review) já passou e não volta. Gravar
    "waiting_review" agora a deixaria presa para sempre."""
    applied = kit.approved_proposal(pool, world, "100.00", status="applied")
    rejected = kit.approved_proposal(pool, world, "200.00", status="ready")
    _set_proposal_status(pool, world.tenant_id, rejected["proposal_id"], "rejected")

    run_id, stored = _finish_waiting(pool, world, settings, [applied["proposal_id"], rejected["proposal_id"]])

    assert stored == "completed"
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "completed" and row["finished_at"] is not None and row["lease_owner"] is None
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["status"] == "completed" and audit["review_settled_at_finish"] is True


def test_finish_run_keeps_waiting_review_without_proof_that_the_review_ended(pool, world, settings):
    live = kit.approved_proposal(pool, world, "100.00", status="ready")
    done = kit.approved_proposal(pool, world, "200.00", status="applied")

    cases = {
        "uma proposta ainda viva": [done["proposal_id"], live["proposal_id"]],
        "proposta que o banco não conhece": [done["proposal_id"], seed.new_id()],
        "aguardando sem proposta": [],
    }
    for index, (label, proposal_ids) in enumerate(cases.items()):
        run_id, stored = _finish_waiting(pool, world, settings, proposal_ids, owner="worker-%d" % index)
        assert stored == "waiting_review", label
        row = kit.run_row(pool, world.tenant_id, run_id)
        assert row["status"] == "waiting_review" and row["finished_at"] is None, label


def test_finish_run_only_looks_at_proposals_of_the_run_space(pool, world, settings):
    """Uma proposta resolvida em OUTRO espaço não serve de prova: sem a linha no
    espaço da execução, ela continua aguardando."""
    ctx = world.context(pool)
    payable_id = seed.create_payable(
        pool, world.tenant_id, world.business_space_id, title="Conta do negócio sintética",
        amount_expected="70.00", competency_month=date(2026, 10, 1),
    )
    foreign = kit.insert_proposal(
        pool, world.tenant_id, world.business_space_id, world.user_id,
        payable_id=payable_id, amount="70.00", status="applied",
    )
    run_id, stored = _finish_waiting(pool, world, settings, [foreign["proposal_id"]])
    assert stored == "waiting_review" and ctx.financial_space_id == world.personal_space_id
    assert kit.run_row(pool, world.tenant_id, run_id)["status"] == "waiting_review"


def test_finish_run_waits_for_a_concurrent_proposal_decision(pool, world, settings):
    """A corrida real, com duas transações de verdade.

    Transação A (rejeição): muda a proposta, procura execuções em
    "waiting_review" para fechar — não acha, a execução ainda está "running" —
    e só então confirma. Transação B (finish_run) começa no meio disso. Uma
    leitura simples da proposta veria "ready" e gravaria "waiting_review" para
    sempre. Com o lock compartilhado, B espera A confirmar e grava "completed".
    """
    proposal = kit.approved_proposal(pool, world, "100.00", status="ready")
    ctx = world.context(pool)
    run_id = _create(pool, ctx, settings, task="statement_import")["run_id"]
    kit.claim(pool, settings, "worker-a")
    rejected, release, errors, stored = threading.Event(), threading.Event(), [], []

    def reject():
        try:
            with scoped_tx(pool, world.tenant_id) as cursor:
                cursor.execute(
                    "UPDATE ai_proposals SET status = 'rejected', rejected_reason = 'teste' WHERE id = %s",
                    (proposal["proposal_id"],),
                )
                assert runs.settle_waiting_review(cursor, world.tenant_id, proposal["proposal_id"]) == []
                rejected.set()
                release.wait(timeout=20)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            rejected.set()

    def finish():
        try:
            stored.append(runs.finish_run(
                pool, run_id, world.tenant_id, "worker-a", status="waiting_review",
                result={"summary_pt_br": "", "proposal_ids": [proposal["proposal_id"]]}, error=None,
            ))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    rejecting = threading.Thread(target=reject)
    finishing = threading.Thread(target=finish)
    rejecting.start()
    assert rejected.wait(timeout=20)
    finishing.start()
    finishing.join(timeout=1.5)
    # B está parada no lock da proposta: ainda não gravou nada.
    blocked = finishing.is_alive()
    still_running = kit.run_row(pool, world.tenant_id, run_id)["status"]
    release.set()
    rejecting.join(timeout=20)
    finishing.join(timeout=20)

    assert errors == []
    assert blocked is True and still_running == "running"
    assert stored == ["completed"]
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "completed" and row["finished_at"] is not None
