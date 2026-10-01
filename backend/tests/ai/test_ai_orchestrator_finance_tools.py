"""Orquestrador com as ferramentas financeiras REAIS (``services.ai.finance``).

Os outros arquivos deste componente usam ferramentas de teste. Aqui o
orquestrador conduz as ferramentas de verdade do componente financeiro, para
provar que as duas pontas concordam nos nomes, nos argumentos e no significado
dos resultados: proposta -> revisão -> aprovação -> aplicação -> reversão.

Se o componente financeiro não estiver presente, o arquivo é pulado (e isso deve
ser relatado como não executado).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from services.ai import orchestrator as orchestrator_module
from services.ai import policy, runs
from services.ai.orchestrator import Orchestrator
from services.ai.registry import ToolRegistry

from .support import orchestrator_kit as kit
from .support import seed
from .support.orchestrator_kit import ForbiddenGateway, ScriptedGateway, WorkerKilled, call, response

finance_tools = pytest.importorskip("services.ai.finance.tools")
finance_proposals = pytest.importorskip("services.ai.finance.proposals")


pytestmark = pytest.mark.integration


def _no_preview(ctx, artifact_id, account_id):
    raise AssertionError("prévia de importação não faz parte destes cenários")


def _registry(pool, settings, wrap=None):
    """Registro com as ferramentas financeiras reais; ``wrap`` embrulha handlers."""
    registry = ToolRegistry(settings)
    for definition in finance_tools.build_finance_tools(pool, settings, _no_preview):
        if wrap and definition.name in wrap:
            definition = replace(definition, handler=wrap[definition.name](definition.handler))
        registry.register(definition)
    return registry


def _payable(pool, world, amount="300.00"):
    return seed.create_payable(
        pool, world.tenant_id, world.personal_space_id, title="Condomínio sintético",
        amount_expected=amount, competency_month=date(2026, 10, 1), due_date=date(2026, 10, 10),
    )


def _prepare_through_model(pool, world, settings, registry, payable_id, amount="100.00"):
    ctx = world.context(pool)
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.prepare_change", {
            "kind": "payable_payment", "payable_id": payable_id, "amount": amount, "paid_on": "2026-10-05",
            "evidence": [{"kind": "manual", "ref": "manual:titular"}],
        })]),
        response(summary="Preparei a proposta de pagamento para a sua revisão."),
    ])
    run_id = kit.enqueue(pool, ctx, settings, task="statement_import", message="Registre o pagamento do condomínio")
    done = kit.execute_next(pool, settings, registry, gateway)
    return ctx, run_id, done, gateway


def _approve(pool, ctx, proposal_id):
    view = finance_proposals.get_proposal_view(pool, ctx, proposal_id)
    return finance_proposals.approve(
        pool, ctx, proposal_id, payload_hash=view["payload_hash"], version=view["version"]
    )


def _apply_run(pool, ctx, settings, proposal_id, version):
    return runs.create_system_run(
        pool, ctx, task="apply_proposal", input={"proposal_id": proposal_id, "expected_version": version},
        idempotency_key="apply:%s:%d" % (proposal_id, version), settings=settings,
    )["run_id"]


def _payments(pool, tenant_id, where="reversed_at IS NULL"):
    return seed.count_rows(pool, tenant_id, "payable_payments", where)


def test_prepare_review_approve_apply_with_real_finance_tools(pool, world, settings):
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="assisted")
    registry = _registry(pool, settings)
    payable_id = _payable(pool, world)

    ctx, origin_id, done, gateway = _prepare_through_model(pool, world, settings, registry, payable_id)

    # A proposta real deixa a execução aguardando revisão; nada foi pago.
    assert done["outcome"]["status"] == "waiting_review"
    origin = runs.get_run_view(pool, ctx, origin_id)
    assert len(origin["proposal_ids"]) == 1 and origin["operation_ids"] == []
    assert _payments(pool, world.tenant_id) == 0
    assert "finance.apply_change" not in gateway.tool_names_offered()[0]     # assistido: o modelo não aplica
    proposal_id = origin["proposal_ids"][0]

    approved = _approve(pool, ctx, proposal_id)
    apply_id = _apply_run(pool, ctx, settings, proposal_id, approved["version"])
    applied = kit.execute_next(pool, settings, registry, ForbiddenGateway())

    assert applied["run_id"] == apply_id and applied["outcome"]["status"] == "completed"
    view = runs.get_run_view(pool, ctx, apply_id)
    assert len(view["operation_ids"]) == 1 and view["proposal_ids"] == [proposal_id]
    assert view["error"] is None and view["summary_pt_br"] == "1 operação foi registrada."
    assert _payments(pool, world.tenant_id) == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_operations") == 1
    # A execução que aguardava revisão é encerrada pela aplicação.
    assert runs.get_run_view(pool, ctx, origin_id)["status"] == "completed"

    # Reenvio da aprovação: mesma execução, nenhum efeito novo.
    assert _apply_run(pool, ctx, settings, proposal_id, approved["version"]) == apply_id
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    assert _payments(pool, world.tenant_id) == 1


def test_crash_after_real_commit_is_confirmed_by_real_operation_status(pool, world, settings):
    """AC-04 com o backend financeiro real: a escrita foi confirmada, o worker
    caiu antes de registrar a etapa, e a retomada não reaplica."""
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="assisted")
    calls = {"finance.apply_change": 0, "finance.operation_status": 0}
    died = []

    def dying_apply(handler):
        def wrapped(ctx, args):
            calls["finance.apply_change"] += 1
            result = handler(ctx, args)          # efeito + operação + outbox confirmados
            if not died:
                died.append(True)
                raise WorkerKilled()
            return result
        return wrapped

    def counting_status(handler):
        def wrapped(ctx, args):
            calls["finance.operation_status"] += 1
            return handler(ctx, args)
        return wrapped

    registry = _registry(pool, settings, {"finance.apply_change": dying_apply,
                                          "finance.operation_status": counting_status})
    payable_id = _payable(pool, world)
    ctx, origin_id, _, _ = _prepare_through_model(pool, world, settings, registry, payable_id)
    proposal_id = runs.get_run_view(pool, ctx, origin_id)["proposal_ids"][0]
    approved = _approve(pool, ctx, proposal_id)
    apply_id = _apply_run(pool, ctx, settings, proposal_id, approved["version"])

    claimed = kit.claim(pool, settings, "worker-a")
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, registry, None).execute(apply_id, claimed["tenant_id"], "worker-a")
    assert _payments(pool, world.tenant_id) == 1
    kit.expire_lease(pool, world.tenant_id, apply_id)

    done = kit.execute_next(pool, settings, registry, None, owner="worker-b")

    assert done["outcome"]["status"] == "completed"
    assert calls == {"finance.apply_change": 1, "finance.operation_status": 1}
    assert _payments(pool, world.tenant_id) == 1 and seed.count_rows(pool, world.tenant_id, "ai_operations") == 1
    view = runs.get_run_view(pool, ctx, apply_id)
    assert len(view["operation_ids"]) == 1
    assert orchestrator_module.WARN_RECONCILED in view["warnings"]


def test_crash_before_real_effect_asks_status_and_applies_once(pool, world, settings):
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="assisted")
    calls = {"finance.apply_change": 0, "finance.operation_status": 0}
    died = []

    def dying_apply(handler):
        def wrapped(ctx, args):
            calls["finance.apply_change"] += 1
            if not died:
                died.append(True)
                raise WorkerKilled()             # cai antes de qualquer escrita
            return handler(ctx, args)
        return wrapped

    def counting_status(handler):
        def wrapped(ctx, args):
            calls["finance.operation_status"] += 1
            return handler(ctx, args)
        return wrapped

    registry = _registry(pool, settings, {"finance.apply_change": dying_apply,
                                          "finance.operation_status": counting_status})
    payable_id = _payable(pool, world)
    ctx, origin_id, _, _ = _prepare_through_model(pool, world, settings, registry, payable_id)
    proposal_id = runs.get_run_view(pool, ctx, origin_id)["proposal_ids"][0]
    approved = _approve(pool, ctx, proposal_id)
    apply_id = _apply_run(pool, ctx, settings, proposal_id, approved["version"])
    claimed = kit.claim(pool, settings, "worker-a")
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, registry, None).execute(apply_id, claimed["tenant_id"], "worker-a")
    assert _payments(pool, world.tenant_id) == 0
    kit.expire_lease(pool, world.tenant_id, apply_id)

    done = kit.execute_next(pool, settings, registry, None, owner="worker-b")

    assert done["outcome"]["status"] == "completed"
    assert _payments(pool, world.tenant_id) == 1 and seed.count_rows(pool, world.tenant_id, "ai_operations") == 1
    assert calls["finance.apply_change"] == 2          # a 1ª morreu antes do efeito
    # A proposta real anota a operação planejada: a retomada pergunta por ela
    # ("not_applied") antes de tentar de novo.
    assert calls["finance.operation_status"] == 1


def test_reverse_operation_with_real_tools_waits_for_review_then_compensates(pool, world, settings):
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="assisted")
    registry = _registry(pool, settings)
    payable_id = _payable(pool, world)
    ctx, origin_id, _, _ = _prepare_through_model(pool, world, settings, registry, payable_id)
    proposal_id = runs.get_run_view(pool, ctx, origin_id)["proposal_ids"][0]
    approved = _approve(pool, ctx, proposal_id)
    apply_id = _apply_run(pool, ctx, settings, proposal_id, approved["version"])
    kit.execute_next(pool, settings, registry, None)
    operation_id = runs.get_run_view(pool, ctx, apply_id)["operation_ids"][0]

    # Pedido de reversão: a tarefa do servidor só CRIA a compensação.
    reverse_id = runs.create_system_run(
        pool, ctx, task="reverse_operation",
        input={"operation_id": operation_id, "reason": "pagamento lançado em duplicidade"}, settings=settings,
    )["run_id"]
    pending = kit.execute_next(pool, settings, registry, ForbiddenGateway())
    assert pending["run_id"] == reverse_id and pending["outcome"]["status"] == "waiting_review"
    reversal = runs.get_run_view(pool, ctx, reverse_id)
    assert len(reversal["proposal_ids"]) == 1 and reversal["operation_ids"] == []
    assert _payments(pool, world.tenant_id) == 1       # nada foi desfeito sem aprovação

    compensation_id = reversal["proposal_ids"][0]
    approved_reversal = _approve(pool, ctx, compensation_id)
    final_id = runs.create_system_run(
        pool, ctx, task="reverse_operation",
        input={"proposal_id": compensation_id, "expected_version": approved_reversal["version"]},
        settings=settings,
    )["run_id"]
    final = kit.execute_next(pool, settings, registry, ForbiddenGateway())

    assert final["run_id"] == final_id and final["outcome"]["status"] == "completed"
    assert _payments(pool, world.tenant_id) == 0       # compensado; o histórico continua lá
    assert _payments(pool, world.tenant_id, "reversed_at IS NOT NULL") == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_operations") == 2
    # A execução que aguardava a revisão da compensação também é encerrada.
    assert runs.get_run_view(pool, ctx, reverse_id)["status"] == "completed"
