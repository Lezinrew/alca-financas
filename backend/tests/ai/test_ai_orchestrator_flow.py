"""Orquestrador: laço de ferramentas, checkpoints, retomada, failover e orçamento.

AC-15 (reinício de worker preserva checkpoint e resultado), AC-09 (orçamento
global) e a parte de execução do AC-11. Banco, registro, política e fila são
reais; o gateway é roteirizado e conta chamadas.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from datetime import date

import pytest

from services.ai import db as ai_db
from services.ai import orchestrator as orchestrator_module
from services.ai import prompts, runs, summary
from services.ai import policy
from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.gateway.base import AttemptRecord
from services.ai.orchestrator import Orchestrator

from .support import orchestrator_kit as kit
from .support import seed
from .support.orchestrator_kit import ScriptedGateway, ToolKit, WorkerKilled, call, response


pytestmark = pytest.mark.integration

VIEW_KEYS = kit.VIEW_KEYS
FACT_KEYS = {
    "key", "label", "value", "unit", "currency", "period", "scope", "source_refs", "as_of",
    "missing_reason", "confidence",
}
THREE_VALUES = {"a": "10.00", "b": "20.00", "c": "30.00"}
THREE_SUMMARY = "Os valores consultados foram R$ 10,00, R$ 20,00 e R$ 30,00."


def three_step_plan(request, ctx, budget):
    """Modelo roteirizado que decide pela conversa: uma consulta por vez (a, b, c)
    e depois o resumo. Funciona igual em uma retomada, porque só olha as
    mensagens que recebeu."""
    done = len(kit.tool_messages(request))
    if done < 3:
        query = "abc"[done]
        return response(tool_calls=[call("finance.read", {"query": query}, call_id="call-%s" % query)])
    return response(summary=THREE_SUMMARY)


def _result_view(view):
    return {key: view[key] for key in ("summary_pt_br", "facts", "sources", "proposal_ids", "operation_ids", "warnings")}


def _dump(pool, tenant_id, tables=("ai_runs", "ai_run_steps", "audit_events")):
    """Tudo o que ficou persistido, como texto, para procurar vazamentos."""
    chunks = []
    with scoped_tx(pool, tenant_id) as cursor:
        for table in tables:
            cursor.execute("SELECT * FROM %s" % table)
            chunks.append(json.dumps([dict(row) for row in cursor.fetchall()], default=str, ensure_ascii=False))
    return "\n".join(chunks)


# --------------------------------------------------------------- caminho feliz

def test_finance_question_answers_with_backend_facts_in_spec_format(pool, world, settings):
    ctx = world.context(pool)
    for title, amount in (("Aluguel sintético", "750.00"), ("Internet sintética", "500.00")):
        seed.create_payable(pool, world.tenant_id, world.personal_space_id, title=title,
                            amount_expected=amount, competency_month=date(2026, 10, 1))
    # Conta de outro espaço: não pode entrar na soma do espaço pessoal.
    seed.create_payable(pool, world.tenant_id, world.business_space_id, title="Anúncios sintéticos",
                        amount_expected="9000.00", competency_month=date(2026, 10, 1))
    grant_id = kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read()
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "pagar"})]),
        response(summary="Falta pagar R$ 1.250,00 em outubro/2026."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"] == {"run_id": run_id, "status": "completed"}
    view = runs.get_run_view(pool, ctx, run_id)
    assert set(view) == VIEW_KEYS
    assert view["status"] == "completed" and view["error"] is None
    assert view["finished_at"] is not None and view["cancel_requested"] is False
    assert view["summary_pt_br"] == "Falta pagar R$ 1.250,00 em outubro/2026."
    assert view["warnings"] == []
    assert view["proposal_ids"] == [] and view["operation_ids"] == []
    assert view["model"] == {"alias": "local-sintetico", "provider": "ollama", "fallback_used": False}

    # Fato e fonte vêm do resultado da ferramenta, calculados no banco.
    assert len(view["facts"]) == 1
    fact = view["facts"][0]
    assert set(fact) == FACT_KEYS
    assert fact["value"] == "1250.00" and fact["unit"] == "money" and fact["currency"] == "BRL"
    assert fact["scope"]["financial_space_id"] == world.personal_space_id
    assert fact["source_refs"] == ["sql:teste:pagar"]
    assert view["sources"] == [
        {"ref": "sql:teste:pagar", "kind": "sql", "label": "Consulta de teste pagar",
         "as_of": kit.FIXED_AS_OF, "extra": {}}
    ]

    assert view["progress"]["stage"] == "done"
    assert [(s["seq"], s["kind"], s["name"], s["status"]) for s in view["progress"]["steps"]] == [
        (1, "inference", "model.inference", "succeeded"),
        (2, "tool", "finance.read", "succeeded"),
        (3, "inference", "model.inference", "succeeded"),
    ]

    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["inference_calls"] == 2 and row["tool_calls"] == 1
    assert row["lease_owner"] is None and row["lease_expires_at"] is None
    assert row["model_alias"] == "local-sintetico" and row["model_id"] == "modelo-sintetico:1"

    # O modelo recebeu só a ferramenta autorizada e o resultado como DADO em JSON.
    assert gateway.calls == 2 and tools.calls == {"finance.read": 1}
    assert gateway.tool_names_offered() == [["finance.read"], ["finance.read"]]
    first, second = gateway.requests
    assert [message.role for message in first.messages] == ["system", "user"]
    assert first.response_schema == prompts.FINAL_RESPONSE_SCHEMA
    assert [message.role for message in second.messages] == ["system", "user", "assistant", "tool"]
    tool_payload = json.loads(second.messages[3].content)
    assert tool_payload["status"] == "ok" and tool_payload["untrusted_data"] is True
    assert tool_payload["result"]["facts"][0]["value"] == "1250.00"
    # O handler recebeu o contexto do servidor, com a execução vinculada.
    handler_ctx = tools.contexts[0][1]
    assert handler_ctx.run_id == run_id and handler_ctx.financial_space_id == world.personal_space_id
    assert handler_ctx.tenant_id == world.tenant_id and handler_ctx.actor_id == world.user_id

    # Auditoria final por referência.
    events = kit.audit_events(pool, world.tenant_id, "ai.run.finished")
    assert len(events) == 1 and str(events[0]["actor_user_id"]) == world.user_id
    audit = events[0]["metadata"]
    assert audit["status"] == "completed" and audit["grant_ids"] == [grant_id]
    assert audit["policy_version"] == 1 and audit["contract_version"] == view["contract_version"]
    assert audit["source_refs"] == ["sql:teste:pagar"]
    assert audit["model"]["alias"] == "local-sintetico" and audit["model"]["model_id"] == "modelo-sintetico:1"
    assert audit["inference_calls"] == 2 and audit["tool_calls"] == 1
    assert audit["tools"] == [{"name": "finance.read", "status": "ok"}]
    assert audit["result"]["facts"] == 1 and audit["result"]["error_code"] is None
    assert audit["duration_ms"] >= 0 and audit["cost_micros"] == 0 and audit["cost_currency"] == "USD"
    assert audit["prompt_version"] == prompts.PROMPT_VERSION
    assert "summary_pt_br" not in json.dumps(audit) and "Falta pagar" not in json.dumps(audit, ensure_ascii=False)


def test_no_prompt_or_raw_model_output_is_persisted(pool, world, settings, caplog):
    caplog.set_level(logging.DEBUG, logger="ai")
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"saldo": "42.00"})
    raw_marker = "RACIOCINIO-BRUTO-7f3a"
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "saldo"})]),
        response(
            summary="O valor consultado é R$ 42,00.",
            raw_content='<pensando %s> {"summary_pt_br": "O valor consultado é R$ 42,00."}' % raw_marker,
        ),
    ])
    message = "Pergunta com o marcador PEDIDO-DO-TITULAR-91c2"
    run_id = kit.enqueue(pool, ctx, settings, message=message)

    kit.execute_next(pool, settings, tools.registry, gateway)

    everything = _dump(pool, world.tenant_id)
    system_text = prompts.system_prompt("finance_question")
    assert gateway.requests[0].messages[0].content == system_text   # o gateway recebeu o prompt...
    assert system_text[:80] not in everything                       # ...mas ele não foi gravado
    assert "Regras obrigatórias" not in everything
    assert raw_marker not in everything                 # nem a resposta bruta do modelo
    # O pedido fica só em ai_runs.input; não é copiado para etapas nem auditoria.
    assert "PEDIDO-DO-TITULAR-91c2" not in _dump(pool, world.tenant_id, ("ai_run_steps", "audit_events"))
    assert kit.run_row(pool, world.tenant_id, run_id)["input"]["message"] == message

    # O checkpoint de inferência guarda a decisão estruturada e metadados.
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    first_inference, tool_step, last_inference = steps
    assert set(first_inference["output"]) == {"decision", "meta"}
    assert first_inference["output"]["decision"]["final"] is None
    assert [(c["name"], c["arguments"]) for c in first_inference["output"]["decision"]["tool_calls"]] == [
        ("finance.read", {"query": "saldo"})
    ]
    meta = first_inference["output"]["meta"]
    assert meta["alias"] == "local-sintetico" and meta["provider"] == "ollama"
    assert meta["model_id"] == "modelo-sintetico:1" and meta["inference_calls"] == 1
    assert meta["cost_micros"] == 0 and meta["duration_ms"] >= 0
    assert last_inference["output"]["decision"] == {
        "tool_calls": [], "final": {"summary_pt_br": "O valor consultado é R$ 42,00."}
    }
    assert tool_step["version"] == "1.0.0" and len(tool_step["args_hash"]) == 64
    assert tool_step["output"]["result"]["facts"][0]["value"] == "42.00"

    # Logs: só ids, códigos, contagens e durações.
    logged = caplog.text
    assert "run_finished run_id=%s status=completed" % run_id in logged
    for forbidden in (raw_marker, "PEDIDO-DO-TITULAR-91c2", "Regras obrigatórias", "42,00", "42.00"):
        assert forbidden not in logged


# ---------------------------------------------------------------- AC-15

def test_worker_restart_reuses_checkpoints_and_keeps_the_result(pool, world, settings):
    """AC-15: três etapas; o worker cai depois da segunda; outro worker assume
    quando o lease vence, reaproveita os checkpoints e chega ao mesmo resultado."""
    settings = replace(settings, lease_seconds=2)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])

    # Execução de controle, sem queda.
    control_tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)
    control_id = kit.enqueue(pool, ctx, settings)
    kit.execute_next(pool, settings, control_tools.registry, ScriptedGateway(three_step_plan))
    control = runs.get_run_view(pool, ctx, control_id)
    assert control["status"] == "completed" and len(control["facts"]) == 3
    assert control_tools.calls == {"finance.read": 3}

    # Execução que sofre a queda: o processo morre durante a 3ª inferência,
    # depois de duas ferramentas concluídas.
    tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)
    run_id = kit.enqueue(pool, ctx, settings, key="reenvio-ac15-0001")

    def dying(request, ctx_, budget):
        if len(kit.tool_messages(request)) == 2:
            raise WorkerKilled()
        return three_step_plan(request, ctx_, budget)

    first_gateway = ScriptedGateway(dying)
    claimed = kit.claim(pool, settings, "worker-a")
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, tools.registry, first_gateway).execute(run_id, claimed["tenant_id"], "worker-a")

    assert tools.calls == {"finance.read": 2} and first_gateway.calls == 3
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["status"] == "running" and row["lease_owner"] == "worker-a" and row["result"] is None
    assert [(s["kind"], s["status"]) for s in kit.step_rows(pool, world.tenant_id, run_id)] == [
        ("inference", "succeeded"), ("tool", "succeeded"),
        ("inference", "succeeded"), ("tool", "succeeded"),
        ("inference", "started"),
    ]

    # Enquanto o lease vale, ninguém assume; depois que vence, outro worker assume.
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    time.sleep(2.3)
    second_gateway = ScriptedGateway(three_step_plan)
    reclaimed = runs.claim_next(pool, "worker-b", settings.lease_seconds)
    assert reclaimed["run_id"] == run_id and reclaimed["attempts"] == 2
    outcome = Orchestrator(pool, settings, tools.registry, second_gateway).execute(
        run_id, reclaimed["tenant_id"], "worker-b"
    )

    assert outcome["status"] == "completed"
    # As duas primeiras ferramentas NÃO foram chamadas de novo; só a terceira rodou.
    assert tools.calls == {"finance.read": 3}
    assert [args["query"] for _, args in tools.received_args] == ["a", "b", "c"]
    # As duas primeiras inferências também vieram do checkpoint: o segundo
    # gateway só fez a 3ª e a 4ª, já recebendo os dois resultados anteriores.
    assert second_gateway.calls == 2
    assert len(kit.tool_messages(second_gateway.requests[0])) == 2

    resumed = runs.get_run_view(pool, ctx, run_id)
    assert resumed["status"] == "completed"
    assert _result_view(resumed) == _result_view(control)
    assert resumed["summary_pt_br"] == THREE_SUMMARY
    assert [f["value"] for f in resumed["facts"]] == ["10.00", "20.00", "30.00"]
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert len(steps) == 7 and all(step["status"] == "succeeded" for step in steps)
    assert [step["attempts"] for step in steps] == [1, 1, 1, 1, 2, 1, 1]  # só a etapa interrompida repetiu
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["attempts"] == 2 and row["tool_calls"] == 3 and row["inference_calls"] == 4

    # Reenvio do mesmo POST: mesma execução, nenhum trabalho novo.
    again = runs.create_run(
        pool, world.context(pool), task="finance_question", message="Quanto falta pagar em outubro?",
        idempotency_key="reenvio-ac15-0001", settings=settings,
    )
    assert again == {"run_id": run_id, "status": "completed", "trace_id": resumed["trace_id"], "created": False}
    assert seed.count_rows(pool, world.tenant_id, "ai_runs") == 2
    assert runs.claim_next(pool, "worker-c", settings.lease_seconds) is None
    assert tools.calls == {"finance.read": 3}


def test_read_tool_interrupted_midway_is_repeated_but_finished_tools_are_not(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)
    killed = []

    def kill_on_c(ctx_, args):
        if args.query == "c" and not killed:
            killed.append(True)
            raise WorkerKilled()

    tools.before["finance.read"] = kill_on_c
    run_id = kit.enqueue(pool, ctx, settings)
    claimed = kit.claim(pool, settings, "worker-a")
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, tools.registry, ScriptedGateway(three_step_plan)).execute(
            run_id, claimed["tenant_id"], "worker-a"
        )
    assert kit.step_rows(pool, world.tenant_id, run_id)[-1]["status"] == "started"

    kit.expire_lease(pool, world.tenant_id, run_id)
    done = kit.execute_next(pool, settings, tools.registry, ScriptedGateway(three_step_plan), owner="worker-b")

    assert done["outcome"]["status"] == "completed"
    # Leitura interrompida não tem efeito externo: é repetida. "a" e "b" não.
    assert [args["query"] for _, args in tools.received_args] == ["a", "b", "c", "c"]
    view = runs.get_run_view(pool, ctx, run_id)
    assert [f["value"] for f in view["facts"]] == ["10.00", "20.00", "30.00"]


def test_failed_tool_checkpoint_is_reused_on_resume_without_calling_the_tool_again(pool, world, settings):
    """Falha de ferramenta também é checkpoint. O modelo já decidiu o passo
    seguinte com base naquele erro; na retomada ele recebe o MESMO erro, e a
    ferramenta (que pode ter custo ou efeito em um conector) não roda de novo."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})

    def connector_down(ctx_, args):
        raise AiError("connector_unavailable")

    tools.before["finance.read"] = connector_down
    first = ScriptedGateway([response(tool_calls=[call("finance.read", {"query": "a"})]), WorkerKilled()])
    run_id = kit.enqueue(pool, ctx, settings)
    claimed = kit.claim(pool, settings, "worker-a")
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, tools.registry, first).execute(run_id, claimed["tenant_id"], "worker-a")
    assert tools.calls == {"finance.read": 1}
    failed_step = kit.step_rows(pool, world.tenant_id, run_id)[1]
    assert (failed_step["status"], failed_step["error_code"]) == ("failed", "connector_unavailable")

    kit.expire_lease(pool, world.tenant_id, run_id)
    second = ScriptedGateway([response(summary="Não consegui consultar os dados agora.")])
    done = kit.execute_next(pool, settings, tools.registry, second, owner="worker-b")

    assert done["outcome"]["status"] == "completed"
    assert tools.calls == {"finance.read": 1}                   # o handler não rodou de novo
    returned = json.loads(kit.tool_messages(second.requests[0])[0].content)
    assert returned["status"] == "error" and returned["error"]["code"] == "connector_unavailable"
    step = kit.step_rows(pool, world.tenant_id, run_id)[1]
    assert (step["status"], step["attempts"]) == ("failed", 1)   # a etapa não foi reaberta
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["tools"] == [{"name": "finance.read", "status": "connector_unavailable"}]


def test_run_keeps_the_policy_version_it_was_created_with(pool, world, settings):
    """Contrato, seção 15: a execução fixa a versão de política. Uma mudança de
    política publicada depois não altera uma execução em andamento."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="O valor consultado é R$ 10,00."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)
    # A execução nasceu sob a política 3; o contexto resolvido hoje diria 1.
    assert world.context(pool).policy_version == 1
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("UPDATE ai_runs SET policy_version = 3 WHERE id = %s", (run_id,))

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    assert tools.contexts[0][1].policy_version == 3                 # o que a ferramenta recebeu
    assert [item.policy_version for item in gateway.contexts] == [3, 3]   # e o gateway
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["policy_version"] == 3


# -------------------------------------------------------------- failover

def test_gateway_failure_after_a_tool_fails_the_run_without_repeating_the_tool(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        AiError("model_unavailable"),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed" and view["finished_at"] is not None
    assert view["error"] == {
        "code": "model_unavailable", "retryable": True,
        "safe_message": "Nenhum modelo autorizado está disponível agora.", "trace_id": view["trace_id"],
    }
    assert view["summary_pt_br"] == ""
    # O que a ferramenta já apurou continua disponível como verdade do backend.
    assert [f["value"] for f in view["facts"]] == ["10.00"]
    assert tools.calls == {"finance.read": 1} and gateway.calls == 2
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert [(s["kind"], s["status"], s["error_code"]) for s in steps] == [
        ("inference", "succeeded", None), ("tool", "succeeded", None), ("inference", "failed", "model_unavailable"),
    ]
    # Execução encerrada não volta para a fila: a ferramenta não será repetida.
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["status"] == "failed" and audit["result"]["error_code"] == "model_unavailable"


def test_resume_on_another_route_reuses_tool_result_and_reports_fallback(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    run_id = kit.enqueue(pool, ctx, settings)
    claimed = kit.claim(pool, settings, "worker-a")
    primary = ScriptedGateway([response(tool_calls=[call("finance.read", {"query": "a"})]), WorkerKilled()])
    with pytest.raises(WorkerKilled):
        Orchestrator(pool, settings, tools.registry, primary).execute(run_id, claimed["tenant_id"], "worker-a")

    kit.expire_lease(pool, world.tenant_id, run_id)
    secondary = ScriptedGateway([
        response(summary="O valor consultado é R$ 10,00.", alias="rota-secundaria-sintetica",
                 provider="openai_compatible", model_id="modelo-b:2", fallback_used=True),
    ])
    done = kit.execute_next(pool, settings, tools.registry, secondary, owner="worker-b")

    assert done["outcome"]["status"] == "completed"
    assert tools.calls == {"finance.read": 1}        # troca de rota não repete a ferramenta
    assert secondary.calls == 1
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["model"] == {"alias": "rota-secundaria-sintetica", "provider": "openai_compatible",
                             "fallback_used": True}
    assert orchestrator_module.WARN_FALLBACK in view["warnings"]
    assert orchestrator_module.WARN_ROUTE_CHANGED in view["warnings"]
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["fallback_used"] is True and row["model_id"] == "modelo-b:2"


def test_unexpected_gateway_exception_becomes_safe_error(pool, world, settings, caplog):
    caplog.set_level(logging.DEBUG, logger="ai")
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([RuntimeError("corpo bruto do provedor SEGREDO-PROVEDOR-55aa")])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["error"]["code"] == "internal_error"
    assert set(view["error"]) == {"code", "retryable", "safe_message", "trace_id"}
    assert "SEGREDO-PROVEDOR-55aa" not in _dump(pool, world.tenant_id)
    assert "Traceback" not in _dump(pool, world.tenant_id)
    # O log registra o TIPO da exceção, nunca a mensagem dela.
    assert "error_type=RuntimeError" in caplog.text
    assert "SEGREDO-PROVEDOR-55aa" not in caplog.text and "Traceback" not in caplog.text


def test_gateway_failure_keeps_the_route_trail_in_the_audit_and_a_contract_shaped_error(pool, world, settings):
    """Quando TODAS as rotas caem, o gateway anexa a trilha ao erro. É o caso em
    que ela mais importa: a auditoria precisa dizer o que foi tentado, e o erro
    mostrado ao titular continua com as quatro chaves do contrato."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    failure = AiError("model_unavailable", details={"reason": "all_routes_failed", "retry_after_s": 7})
    # Mesmos atributos que o gateway real anexa em ``_fail``.
    failure.attempts = [
        AttemptRecord(alias="local-sintetico", provider="ollama", outcome="timeout", latency_ms=60000),
        AttemptRecord(alias="rota-externa-sintetica", provider="openai_compatible", outcome="server_error",
                      latency_ms=812, status=503),
    ]
    failure.cost_micros = 1500
    failure.inference_calls = 2
    gateway = ScriptedGateway([failure])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["error"] == {
        "code": "model_unavailable", "retryable": True,
        "safe_message": "Nenhum modelo autorizado está disponível agora.", "trace_id": view["trace_id"],
    }
    trail = [
        {"alias": "local-sintetico", "provider": "ollama", "outcome": "timeout", "latency_ms": 60000, "status": None},
        {"alias": "rota-externa-sintetica", "provider": "openai_compatible", "outcome": "server_error",
         "latency_ms": 812, "status": 503},
    ]
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["route_attempts"] == trail
    assert audit["inference_calls"] == 2 and audit["cost_micros"] == 1500
    assert audit["result"]["error_code"] == "model_unavailable"
    assert audit["result"]["error_details"] == {"reason": "all_routes_failed", "retry_after_s": "7"}
    # Nenhuma rota respondeu: não há modelo efetivo a registrar.
    assert audit["model"]["alias"] is None and view["model"]["alias"] is None
    step = kit.step_rows(pool, world.tenant_id, run_id)[0]
    assert (step["status"], step["error_code"], step["cost_micros"]) == ("failed", "model_unavailable", 1500)
    assert step["output"]["meta"]["attempts"] == trail
    assert step["output"]["meta"]["details"] == {"reason": "all_routes_failed", "retry_after_s": "7"}
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["inference_calls"] == 2 and row["cost_micros"] == 1500


# ------------------------------------- conteúdo que o banco não aceita (NUL)

def test_nul_in_tool_result_is_sanitized_and_does_not_break_the_run(pool, world, settings):
    """Um e-mail ou PDF malicioso traz NUL no corpo. O jsonb recusa NUL: sem o
    saneamento a etapa ficaria "started" e a execução inteira cairia."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    poisoned = "linha do extrato\u0000com nul e \ud800 substituto"
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"}, extra_data={"observacao": poisoned})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="O valor consultado é R$ 10,00."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    clean = "linha do extrato�com nul e � substituto"
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert [(s["kind"], s["status"]) for s in steps] == [
        ("inference", "succeeded"), ("tool", "succeeded"), ("inference", "succeeded"),
    ]
    assert steps[1]["output"]["result"]["data"]["observacao"] == clean
    # O modelo recebeu exatamente o que ficou no checkpoint (igual em uma retomada).
    delivered = json.loads(kit.tool_messages(gateway.requests[1])[0].content)
    assert delivered["result"]["data"]["observacao"] == clean
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["error"] is None and [f["value"] for f in view["facts"]] == ["10.00"]
    assert view["summary_pt_br"] == "O valor consultado é R$ 10,00."


def test_nul_in_model_arguments_is_refused_as_a_tool_error(pool, world, settings):
    """O modelo ecoa um NUL em um argumento. A ferramenta não roda com texto
    "consertado": a chamada é recusada, o erro volta ao modelo e a execução segue."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[
            call("finance.read", {"query": "a\u0000"}, call_id="id\u0000com-nul"),
            call("finance.read", {"que\ud800ry": "a"}),
            call("finance.read\u0000", {"query": "a"}),
            call("finance\ud800.read", {"query": "a"}),      # nome que nem tem codificação UTF-8
        ]),
        response(summary="Não consegui consultar os dados."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    assert tools.total_calls() == 0
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    decision = steps[0]["output"]["decision"]["tool_calls"]
    assert [(c["id"], c["name"], c["arguments"], c.get("invalid")) for c in decision[:2]] == [
        ("id�com-nul", "finance.read", {}, "bad_chars"),
        (decision[1]["id"], "finance.read", {}, "bad_chars"),
    ]
    # Nome com NUL ou substituto isolado não casa com ferramenta nenhuma: a
    # chamada é negada como desconhecida, sem derrubar a execução.
    assert [c["name"] for c in decision[2:]] == ["finance.read�", "finance�.read"]
    assert [(s["name"], s["status"], s["error_code"]) for s in steps[1:5]] == [
        ("finance.read", "failed", "invalid_request"),
        ("finance.read", "failed", "invalid_request"),
        ("tool.unknown", "failed", "capability_denied"),
        ("tool.unknown", "failed", "capability_denied"),
    ]
    returned = json.loads(kit.tool_messages(gateway.requests[1])[0].content)
    assert returned["status"] == "error"
    assert returned["error"]["safe_message"] == orchestrator_module.MSG_BAD_ARG_CHARS
    assert runs.get_run_view(pool, ctx, run_id)["error"] is None


def test_unstorable_text_from_the_provider_does_not_break_the_run(pool, world, settings):
    """Nome de modelo e resumo vêm do provedor e passam pela mesma higiene."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([
        response(summary="Sem\u0000 dados \ud800agora.", model_id="modelo\u0000-b", alias="rota\ud800-a"),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["model_id"] == "modelo�-b" and row["model_alias"] == "rota�-a"
    assert row["result"]["summary_pt_br"] == "Sem dados agora."        # controles saem do resumo


def test_read_checkpoint_refused_by_the_database_becomes_a_tool_error(pool, world, settings, monkeypatch, caplog):
    """Segunda linha de defesa: se o banco recusar o resultado de uma LEITURA
    (um dado que o saneamento não previu), o modelo recebe um erro de ferramenta
    e a execução continua, em vez de cair com erro interno. Para provocar a
    recusa de verdade, o saneamento é desligado e o PostgreSQL recebe o NUL."""
    caplog.set_level(logging.DEBUG, logger="ai")
    monkeypatch.setattr(runs, "storable", lambda value: value)
    # A camada de banco (db.jsonb) tem o mesmo saneamento; desliga os dois.
    monkeypatch.setattr(ai_db, "storable", lambda value: value)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"}, extra_data={"observacao": "com\u0000nul"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="Não consegui consultar os dados agora."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert (steps[1]["status"], steps[1]["error_code"]) == ("failed", "internal_error")
    returned = json.loads(kit.tool_messages(gateway.requests[1])[0].content)
    assert returned["status"] == "error" and returned["error"]["code"] == "internal_error"
    # Sem checkpoint, o resultado não entra nos fatos entregues ao titular.
    assert runs.get_run_view(pool, ctx, run_id)["facts"] == []
    assert "tool_checkpoint_rejected run_id=%s tool=finance.read" % run_id in caplog.text


# ------------------------------------------------------- AC-09: orçamento

def _endless_tools(request, ctx, budget):
    return response(tool_calls=[call("finance.read", {"query": "q%d" % len(kit.tool_messages(request))})])


def test_tool_budget_is_global_and_overflow_fails_safely(pool, world, settings):
    settings = replace(settings, max_tool_calls_per_run=3, max_inference_calls_per_step=2)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"q0": "1.00", "q1": "2.00", "q2": "3.00", "q3": "4.00"})
    gateway = ScriptedGateway(_endless_tools)
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    assert tools.calls == {"finance.read": 3}                    # nunca passa do teto
    # Cada etapa de inferência recebe um orçamento novo, sempre do tamanho configurado.
    assert gateway.budget_limits == [2, 2, 2, 2]
    # Com o teto de ferramentas atingido, a 4ª inferência não recebe ferramenta alguma.
    assert gateway.tool_names_offered() == [["finance.read"]] * 3 + [[]]
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["error"]["code"] == "budget_exceeded" and view["error"]["retryable"] is False
    assert view["error"]["safe_message"] == orchestrator_module.MSG_TOOL_BUDGET
    row = kit.run_row(pool, world.tenant_id, run_id)
    assert row["tool_calls"] == 3 and row["inference_calls"] == 4
    assert seed.count_rows(pool, world.tenant_id, "ai_run_steps", "run_id = %s AND kind = 'tool'", (run_id,)) == 3


def test_many_tool_calls_in_one_response_stop_at_the_limit(pool, world, settings):
    settings = replace(settings, max_tool_calls_per_run=3)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    values = {"q%d" % index: "%d.00" % (index + 1) for index in range(6)}
    tools = ToolKit(pool, settings).with_finance_read(values)
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "q%d" % index}) for index in range(6)]),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert tools.calls == {"finance.read": 3}
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed" and view["error"]["code"] == "budget_exceeded"
    assert len(view["facts"]) == 3


def test_run_completes_when_model_concludes_at_the_tool_limit(pool, world, settings):
    settings = replace(settings, max_tool_calls_per_run=3)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)
    gateway = ScriptedGateway(three_step_plan)
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    assert tools.calls == {"finance.read": 3}
    assert gateway.tool_names_offered()[-1] == []
    assert runs.get_run_view(pool, ctx, run_id)["summary_pt_br"] == THREE_SUMMARY


def test_tool_errors_count_towards_the_limit_and_do_not_abort_on_first_occurrence(pool, world, settings):
    settings = replace(settings, max_tool_calls_per_run=3)
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})

    def stubborn(request, ctx_, budget):
        # O modelo insiste em argumentos fora do schema.
        return response(tool_calls=[call("finance.read", {"consulta": "errada"})])

    gateway = ScriptedGateway(stubborn)
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert tools.total_calls() == 0                 # schema inválido nunca chega ao handler
    assert gateway.calls == 4                       # a 1ª falha não derrubou a execução
    # O erro voltou ao modelo como resultado, com código seguro.
    returned = json.loads(kit.tool_messages(gateway.requests[1])[0].content)
    assert returned["status"] == "error" and returned["error"]["code"] == "invalid_request"
    assert returned["error"]["details"]["fields"] == ["consulta", "query"]
    steps = [s for s in kit.step_rows(pool, world.tenant_id, run_id) if s["kind"] == "tool"]
    assert [(s["status"], s["error_code"]) for s in steps] == [("failed", "invalid_request")] * 3
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed" and view["error"]["code"] == "budget_exceeded"


def test_deadline_passed_in_queue_fails_before_any_model_or_tool_call(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway(three_step_plan)
    run_id = kit.enqueue(pool, ctx, settings)
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("UPDATE ai_runs SET deadline_at = now() - interval '1 second' WHERE id = %s", (run_id,))

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    assert gateway.calls == 0 and tools.total_calls() == 0
    error = runs.get_run_view(pool, ctx, run_id)["error"]
    assert error["code"] == "budget_exceeded" and error["safe_message"] == orchestrator_module.MSG_DEADLINE


def test_deadline_passing_mid_run_stops_before_the_next_action(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)

    def expire(ctx_, args):
        with scoped_tx(pool, ctx_.tenant_id) as cursor:
            cursor.execute("UPDATE ai_runs SET deadline_at = now() - interval '1 second' WHERE id = %s", (ctx_.run_id,))

    tools.before["finance.read"] = expire
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"}), call("finance.read", {"query": "b"})]),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert tools.calls == {"finance.read": 1} and gateway.calls == 1
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "failed" and view["error"]["code"] == "budget_exceeded"


def test_run_claimed_too_many_times_is_failed_without_working(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read(THREE_VALUES)
    gateway = ScriptedGateway(three_step_plan)
    run_id = kit.enqueue(pool, ctx, settings)
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("UPDATE ai_runs SET attempts = %s WHERE id = %s", (runs.MAX_RUN_ATTEMPTS, run_id))

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "failed"
    assert gateway.calls == 0 and tools.total_calls() == 0
    error = runs.get_run_view(pool, ctx, run_id)["error"]
    assert error["code"] == "internal_error" and error["retryable"] is False


# ------------------------------------------------ guarda numérica do resumo

def test_unbacked_value_in_model_summary_is_replaced_and_warned(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"pagar": "1250.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "pagar"})]),
        response(summary="Falta pagar R$ 1.250,00, e você economizou R$ 9.999,99 neste mês."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "completed"
    assert "9.999,99" not in view["summary_pt_br"] and "economizou" not in view["summary_pt_br"]
    assert view["summary_pt_br"] == "Valor de pagar (outubro/2026): R$ 1.250,00."
    assert view["warnings"] == [summary.WARNING_UNBACKED]
    audit = kit.audit_events(pool, world.tenant_id, "ai.run.finished")[0]["metadata"]
    assert audit["result"]["summary_replaced"] is True


def test_model_cannot_state_numbers_without_any_successful_tool(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"pagar": "1250.00"})
    gateway = ScriptedGateway([response(summary="Você tem 3 contas vencidas, somando R$ 480,00.")])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "completed" and view["facts"] == []
    assert view["summary_pt_br"] == summary.NO_DATA_TEXT
    assert view["warnings"] == [summary.WARNING_NO_DATA]
    assert tools.total_calls() == 0


def test_invalid_final_output_falls_back_to_backend_summary(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"pagar": "1250.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "pagar"})]),
        response(raw_content="texto solto sem JSON"),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "completed"
    assert view["summary_pt_br"] == "Valor de pagar (outubro/2026): R$ 1.250,00."
    assert view["warnings"] == [summary.WARNING_EMPTY]


# -------------------------------------------------------- waiting_review

def test_prepared_proposal_leaves_run_waiting_review(pool, world, settings):
    ctx = world.context(pool)
    payable_id = seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Energia sintética",
                                     amount_expected="300.00", competency_month=date(2026, 10, 1))
    kit.grant(pool, world, ["finance.prepare_change", "finance.apply_change", "email.search_financial"],
              mode="assisted")
    tools = ToolKit(pool, settings).with_finance_write().with_email()
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.prepare_change", {"payable_id": payable_id, "amount": "300.00"})]),
        response(summary="Preparei uma proposta de pagamento para a sua revisão."),
    ])
    run_id = kit.enqueue(pool, ctx, settings, task="statement_import", message="Importe o extrato de outubro")

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "waiting_review"
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "waiting_review" and view["progress"]["stage"] == "waiting_review"
    assert view["finished_at"] is None and len(view["proposal_ids"]) == 1 and view["operation_ids"] == []
    assert view["summary_pt_br"] == "Preparei uma proposta de pagamento para a sua revisão."
    # Sem grant delegado, o modelo nem enxerga finance.apply_change nesta tarefa.
    assert gateway.tool_names_offered()[0] == ["email.search_financial", "finance.prepare_change"]
    assert gateway.requests[0].purpose == "read"
    assert tools.calls["finance.apply_change"] == 0
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 0
    assert runs.claim_next(pool, "worker-b", settings.lease_seconds) is None


def test_tool_signalling_review_without_a_proposal_leaves_the_run_waiting(pool, world, settings):
    """``data.status == "waiting_review"`` basta: uma ferramenta pode pedir
    revisão sem (ainda) existir proposta que o banco possa confirmar."""
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"}, extra_data={"status": "waiting_review"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="O valor consultado é R$ 10,00 e depende da sua revisão."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "waiting_review"
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "waiting_review" and view["finished_at"] is None
    assert view["proposal_ids"] == [] and view["progress"]["stage"] == "waiting_review"


def test_review_finished_between_conclusion_and_final_write_does_not_strand_the_run(pool, world, settings):
    """A corrida inteira, com as peças reais: o worker A conclui "aguardando
    revisão"; ANTES de ele gravar o estado, o titular aprova e o worker B aplica
    a proposta (e tenta fechar a execução de origem, que ainda está "running").
    A execução de origem não pode ficar em waiting_review para sempre."""
    ctx = world.context(pool)
    payable_id = seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Gás sintético",
                                     amount_expected="120.00", competency_month=date(2026, 10, 1))
    kit.grant(pool, world, ["finance.prepare_change", "finance.apply_change", "finance.operation_status"],
              mode="assisted")
    tools = ToolKit(pool, settings).with_finance_write()
    raced = []

    class RacingOrchestrator(Orchestrator):
        """Orquestrador real; só encaixa a ação concorrente no ponto exato da janela."""

        def _conclude(self, run, state):
            status = super()._conclude(run, state)
            if run["task"] == "statement_import" and not raced:
                assert status == "waiting_review"
                proposal_id = state.proposal_ids[0]
                with scoped_tx(pool, world.tenant_id) as cursor:
                    cursor.execute(
                        "UPDATE ai_proposals SET status = 'approved', approval_kind = 'specific', "
                        "approved_by_user_id = %s, approved_hash = payload_hash, approved_at = now() WHERE id = %s",
                        (world.user_id, proposal_id),
                    )
                created = runs.create_system_run(
                    pool, ctx, task="apply_proposal",
                    input={"proposal_id": proposal_id, "expected_version": 1}, settings=settings,
                )
                applied = kit.execute_next(pool, settings, tools.registry, None, owner="worker-b")
                assert applied["run_id"] == created["run_id"]
                raced.append(applied["outcome"]["status"])
            return status

    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.prepare_change", {"payable_id": payable_id, "amount": "120.00"})]),
        response(summary="Preparei uma proposta de pagamento para a sua revisão."),
    ])
    run_id = kit.enqueue(pool, ctx, settings, task="statement_import", message="Importe o extrato de outubro")
    claimed = kit.claim(pool, settings, "worker-a")

    outcome = RacingOrchestrator(pool, settings, tools.registry, gateway).execute(
        run_id, claimed["tenant_id"], "worker-a"
    )

    assert raced == ["completed"]                              # a proposta foi aplicada no meio da janela
    assert seed.count_rows(pool, world.tenant_id, "payable_payments") == 1
    assert outcome == {"run_id": run_id, "status": "completed"}
    view = runs.get_run_view(pool, ctx, run_id)
    assert view["status"] == "completed" and view["finished_at"] is not None
    assert seed.count_rows(pool, world.tenant_id, "ai_runs", "status = 'waiting_review'") == 0
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT status FROM ai_proposals WHERE id = %s", (view["proposal_ids"][0],))
        assert cursor.fetchone()["status"] == "applied"


def test_statement_import_offers_exactly_its_tool_subset_even_with_every_grant(pool, world, settings):
    """O ator tem TODAS as capacidades, em modo delegado, e todas as ferramentas
    do contrato estão registradas e ligadas. Mesmo assim a tarefa de importação
    só enxerga (e só executa) o próprio subconjunto: reversão, consulta de
    operação, leitura financeira, RAG e WhatsApp ficam de fora."""
    settings = replace(settings, whatsapp_enabled=True)
    ctx = world.context(pool)
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="delegated", amount_unlimited=True)
    tools = (
        ToolKit(pool, settings)
        .with_finance_read({"a": "10.00"})
        .with_finance_write()
        .with_reverse(world, "direct")
        .with_email()
        .with_import_tools()
        .with_extras()
    )
    assert tools.registry.names() == sorted(policy.CAPABILITIES)     # nada ficou de fora do registro
    outside = [
        call("finance.reverse_change", {"operation_id": seed.new_id(), "reason": "desfazer tudo"}),
        call("finance.operation_status", {"operation_id": seed.new_id()}),
        call("finance.read", {"query": "a"}),
        call("rag.search_personal", {"query": "senha"}),
        call("whatsapp.respond", {"query": "enviar"}),
    ]
    gateway = ScriptedGateway([response(tool_calls=outside), response(summary="Nada a importar.")])
    run_id = kit.enqueue(pool, ctx, settings, task="statement_import", message="Importe o extrato de outubro")

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    expected = [
        "email.download_attachment", "email.get_message", "email.search_financial",
        "finance.apply_change", "finance.prepare_change", "imports.preview",
    ]
    assert gateway.tool_names_offered() == [expected, expected]
    assert sorted(orchestrator_module.TASK_TOOLS["statement_import"]) == expected
    # Pedidas pelo modelo mesmo assim: negadas antes de qualquer handler.
    assert tools.total_calls() == 0
    steps = [s for s in kit.step_rows(pool, world.tenant_id, run_id) if s["kind"] == "tool"]
    assert [(s["name"], s["status"], s["error_code"]) for s in steps] == [
        (item.name, "failed", "capability_denied") for item in outside
    ]
    assert seed.count_rows(pool, world.tenant_id, "ai_operations") == 0


def test_finance_question_offers_exactly_its_tool_subset_even_with_every_grant(pool, world, settings):
    settings = replace(settings, whatsapp_enabled=True)
    ctx = world.context(pool)
    kit.grant(pool, world, list(policy.CAPABILITIES), mode="delegated", amount_unlimited=True)
    tools = (
        ToolKit(pool, settings).with_finance_read({"a": "10.00"}).with_finance_write()
        .with_reverse(world, "direct").with_email().with_import_tools().with_extras()
    )
    gateway = ScriptedGateway([response(summary="Nada a consultar.")])
    kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert gateway.tool_names_offered() == [["finance.read", "rag.search_personal"]]
    assert gateway.requests[0].purpose == "read"


def test_delegated_grant_exposes_apply_change_and_marks_inference_as_write(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.prepare_change", "finance.apply_change"], mode="delegated",
              amount_unlimited=True)
    tools = ToolKit(pool, settings).with_finance_write()
    gateway = ScriptedGateway([response(summary="Nada a importar.")])
    kit.enqueue(pool, ctx, settings, task="statement_import", message="Importe o extrato de outubro")

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert gateway.tool_names_offered()[0] == ["finance.apply_change", "finance.prepare_change"]
    # Inferência que pode disparar escrita não pode cair em rota só de leitura.
    assert gateway.requests[0].purpose == "write"


def test_read_tool_exception_is_returned_as_safe_error_and_not_leaked(pool, world, settings, caplog):
    caplog.set_level(logging.DEBUG, logger="ai")
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})

    def explode(ctx_, args):
        raise RuntimeError("stack interno SEGREDO-FERRAMENTA-33bb")

    tools.before["finance.read"] = explode
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="Não consegui consultar os dados agora."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    assert done["outcome"]["status"] == "completed"
    returned = json.loads(kit.tool_messages(gateway.requests[1])[0].content)
    assert returned == {
        "kind": "tool_result", "tool": "finance.read", "status": "error",
        "error": {"code": "internal_error", "retryable": True, "safe_message": "Não foi possível concluir o pedido."},
    }
    assert "SEGREDO-FERRAMENTA-33bb" not in _dump(pool, world.tenant_id)
    assert "tool_internal_error tool=finance.read error_type=RuntimeError" in caplog.text
    assert "SEGREDO-FERRAMENTA-33bb" not in caplog.text
    assert runs.get_run_view(pool, ctx, run_id)["facts"] == []


# ------------------------------------------- argumentos e resultados grandes

def test_float_arguments_from_the_model_are_normalized_before_checkpoint(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a", "peso": 1.5, "lista": [0.1, {"x": 2.25}]})]),
        response(summary="Não consegui consultar."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    done = kit.execute_next(pool, settings, tools.registry, gateway)

    # Float não derruba a execução nem entra no checkpoint: vira decimal em string.
    assert done["outcome"]["status"] == "completed"
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    assert steps[0]["output"]["decision"]["tool_calls"][0]["arguments"] == {
        "query": "a", "peso": "1.5", "lista": ["0.1", {"x": "2.25"}],
    }
    assert (steps[1]["status"], steps[1]["error_code"]) == ("failed", "invalid_request")   # propriedades extras
    assert tools.total_calls() == 0


def test_oversized_tool_arguments_are_rejected_and_not_persisted(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["email.search_financial"])
    tools = ToolKit(pool, settings).with_email()
    blob = "MARCADOR-ARGUMENTO-GRANDE " * 800
    gateway = ScriptedGateway([
        response(tool_calls=[call("email.search_financial", {"query": blob})]),
        response(summary="Nada encontrado."),
    ])
    run_id = kit.enqueue(pool, ctx, settings, task="statement_import", message="Importe o extrato")

    kit.execute_next(pool, settings, tools.registry, gateway)

    assert tools.total_calls() == 0
    steps = kit.step_rows(pool, world.tenant_id, run_id)
    decision = steps[0]["output"]["decision"]["tool_calls"][0]
    assert decision["invalid"] == "too_large" and decision["arguments"] == {}
    assert steps[1]["error_code"] == "invalid_request"
    assert "MARCADOR-ARGUMENTO-GRANDE" not in _dump(pool, world.tenant_id)


def test_large_tool_result_is_truncated_for_the_model_but_kept_in_checkpoint(pool, world, settings):
    ctx = world.context(pool)
    kit.grant(pool, world, ["finance.read"])
    blob = "linha de extrato sintética; " * 2000
    tools = ToolKit(pool, settings).with_finance_read({"a": "10.00"}, extra_data={"extrato": blob})
    gateway = ScriptedGateway([
        response(tool_calls=[call("finance.read", {"query": "a"})]),
        response(summary="O valor consultado é R$ 10,00."),
    ])
    run_id = kit.enqueue(pool, ctx, settings)

    kit.execute_next(pool, settings, tools.registry, gateway)

    message = kit.tool_messages(gateway.requests[1])[0]
    assert len(message.content) <= orchestrator_module.MAX_TOOL_MESSAGE_CHARS
    delivered = json.loads(message.content)
    assert delivered["result"]["data"] == {"truncated": True}
    assert delivered["result"]["facts"][0]["value"] == "10.00"       # a parte estruturada segue inteira
    step = kit.step_rows(pool, world.tenant_id, run_id)[1]
    assert step["output"]["result"]["data"]["extrato"] == blob        # o checkpoint guarda o dado completo
    assert runs.get_run_view(pool, ctx, run_id)["summary_pt_br"] == "O valor consultado é R$ 10,00."
