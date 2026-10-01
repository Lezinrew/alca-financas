"""Failover, orçamento de tentativas, correção de JSON e disjuntor (AC-09, AC-10).

Gateway, registro, disjuntor e adaptadores reais; os "provedores" são servidores
HTTP locais que contam as requisições recebidas. Só rotas locais aqui (sem
custo); as rotas externas e o orçamento de custo estão em
``test_ai_gateway_external.py``.
"""

from __future__ import annotations

import json
import logging
import time

import pytest

from services.ai.errors import AiError
from services.ai.gateway.base import (
    PURPOSE_WRITE,
    AdapterResult,
    AttemptBudget,
    ModelGateway,
    ProviderAdapter,
)
from services.ai.gateway.gateway import DefaultModelGateway, build_gateway
from services.ai.gateway.models import ModelRegistry
from services.ai.gateway.circuit import CircuitBreaker
from services.ai.types import Privacy

from .support.gateway_harness import (
    ANSWER_SCHEMA,
    CREDENTIAL_ENV,
    DIGEST_B,
    READ_TOOL,
    VALID_ANSWER,
    FakeClock,
    assemble,
    external_route,
    gateway_settings,
    local_route,
    make_ctx,
    outcomes,
    serve_tags,
    user_request,
)
from .support.gateway_harness import providers  # noqa: F401 - fixture do pytest
from .support.gateway_server import Reply, ollama_chat, openai_chat, refused_base_url


pytestmark = pytest.mark.unit

CHAT = "POST /api/chat"
TAGS = "GET /api/tags"
FAKE_SECRET = "credencial-ficticia-apenas-para-teste"


def local_server(providers):
    server = providers()
    serve_tags(server)
    return server


def fail_with(code, **details):
    """Contexto: espera um AiError com o código dado."""
    return pytest.raises(AiError, match="^%s:" % code)


def local_openai_route(alias, server, priority, **overrides):
    """Servidor local no formato OpenAI (ex.: vLLM), sem custo."""
    return local_route(alias, server.base_url, priority, provider="openai_compatible", digest=None, **overrides)


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------

def test_first_route_answers_and_response_is_normalized(providers):
    a, b = local_server(providers), local_server(providers)
    a.enqueue(CHAT, Reply(200, ollama_chat("Olá, titular.", model="modelo-efetivo:1b")))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(limit=3)

    response = built.gateway.complete(user_request(), make_ctx(), budget)

    assert isinstance(built.gateway, ModelGateway)
    assert response.content == "Olá, titular." and response.parsed is None and response.tool_calls == []
    assert (response.alias, response.provider) == ("primaria", "ollama")
    # Modelo efetivo devolvido pelo provedor, não o que foi pedido.
    assert response.model_id == "modelo-efetivo:1b"
    assert response.fallback_used is False and response.inference_calls == 1 and response.cost_micros == 0
    assert (response.usage.input_tokens, response.usage.output_tokens) == (42, 17)
    assert outcomes(response.attempts) == ["primaria:ok"]
    assert budget.used == 1
    assert (a.count(CHAT), b.count(CHAT), b.count()) == (1, 0, 0)


def test_structured_answer_is_parsed_and_validated(providers):
    a = local_server(providers)
    a.enqueue(CHAT, Reply(200, ollama_chat("```json\n%s\n```" % VALID_ANSWER)))
    built = assemble([local_route("primaria", a.base_url, 1)])
    response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), make_ctx(), AttemptBudget(3))
    assert response.parsed == {"categoria": "moradia", "confianca": 90}
    assert a.count(CHAT) == 1


# ---------------------------------------------------------------------------
# AC-09: falhas transitórias seguem a ordem de prioridade
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "failure, outcome",
    [
        (Reply(500, {"error": "falha"}), "server_error"),
        (Reply(503, {"error": "ocupado"}), "unavailable"),
        (Reply(404, {"error": "modelo ausente"}), "unavailable"),
        (Reply(429, {"error": "limite"}, headers={"Retry-After": "30"}), "rate_limited"),
        (Reply(200, ollama_chat("tarde demais"), delay_s=8), "timeout"),
    ],
)
def test_transient_failure_moves_to_next_route_in_priority_order(providers, failure, outcome):
    a, b, c = local_server(providers), local_server(providers), local_server(providers)
    a.always(CHAT, failure)
    b.always(CHAT, Reply(200, ollama_chat("resposta da secundária")))
    c.always(CHAT, Reply(200, ollama_chat("resposta da terciária")))
    routes = [
        local_route("terciaria", c.base_url, 30),
        # Prazo curto só no caso de timeout; nos demais, o prazo normal evita
        # que uma máquina lenta transforme um 500 em timeout. O atraso do
        # servidor (8 s) fica bem acima do prazo (1 s) para não haver corrida.
        local_route("primaria", a.base_url, 10, extra={"timeout_s": 1.0} if outcome == "timeout" else {}),
        local_route("secundaria", b.base_url, 20),
    ]
    built = assemble(routes)
    budget = AttemptBudget(limit=3)

    response = built.gateway.complete(user_request(), make_ctx(), budget)

    assert response.content == "resposta da secundária"
    assert response.alias == "secundaria" and response.fallback_used is True
    assert outcomes(response.attempts) == ["primaria:%s" % outcome, "secundaria:ok"]
    assert response.inference_calls == 2 and budget.used == 2
    # Uma requisição por tentativa, na ordem, e a terceira rota nem foi tocada.
    # No caso de timeout a contagem da primária é lida depois de estabilizar: o
    # cliente desiste antes de o servidor, sob carga, ter registrado o pedido.
    primary_count = a.settled_count(CHAT) if outcome == "timeout" else a.count(CHAT)
    assert (primary_count, b.count(CHAT), c.count(CHAT)) == (1, 1, 0)
    assert built.clock.sleeps == []


def test_refused_connection_moves_to_next_route(providers):
    b = local_server(providers)
    b.always(CHAT, Reply(200, ollama_chat("ok")))
    built = assemble(
        [local_route("primaria", refused_base_url(), 1), local_route("secundaria", b.base_url, 2)],
        verify_local_routes=False,
    )
    response = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(response.attempts) == ["primaria:network", "secundaria:ok"]


def test_attempt_budget_is_never_exceeded(providers):
    a, b, c = local_server(providers), local_server(providers), local_server(providers)
    for server in (a, b, c):
        server.always(CHAT, Reply(500, {"error": "falha"}))
    built = assemble(
        [local_route("r1", a.base_url, 1), local_route("r2", b.base_url, 2), local_route("r3", c.base_url, 3)]
    )
    budget = AttemptBudget(limit=2)

    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), budget)

    assert excinfo.value.retryable is True
    assert excinfo.value.details == {"reason": "attempt_budget_exhausted"}
    # O limite é de 2: a terceira rota existe, está saudável para tentar, e NÃO é chamada.
    assert a.count(CHAT) + b.count(CHAT) + c.count(CHAT) == 2
    assert c.count(CHAT) == 0 and budget.used == 2
    assert outcomes(excinfo.value.attempts) == ["r1:server_error", "r2:server_error"]


def test_exhausted_budget_makes_no_request(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("ok")))
    built = assemble([local_route("primaria", a.base_url, 1)])
    budget = AttemptBudget(limit=3, used=3)
    with fail_with("model_unavailable"):
        built.gateway.complete(user_request(), make_ctx(), budget)
    assert a.count() == 0 and budget.used == 3


def test_all_routes_failed_reports_model_unavailable(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(500, {"error": "falha"}))
    built = assemble([local_route("unica", a.base_url, 1)])
    budget = AttemptBudget(limit=3)
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), budget)
    # Sem Retry-After a mesma rota não é repetida: sobra orçamento, mas não há outra rota.
    assert excinfo.value.details == {"reason": "all_routes_failed"}
    assert a.count(CHAT) == 1 and budget.used == 1


# ---------------------------------------------------------------------------
# AC-09: Retry-After
# ---------------------------------------------------------------------------

def test_short_retry_after_without_other_route_waits_and_repeats_within_budget(providers):
    a = local_server(providers)
    a.enqueue(CHAT, Reply(429, {"error": "limite"}, headers={"Retry-After": "2"}), Reply(200, ollama_chat("agora sim")))
    built = assemble([local_route("unica", a.base_url, 1)])
    budget = AttemptBudget(limit=3)

    response = built.gateway.complete(user_request(), make_ctx(), budget)

    assert response.content == "agora sim" and response.fallback_used is False
    assert outcomes(response.attempts) == ["unica:rate_limited", "unica:ok"]
    # Esperou exatamente o que o provedor pediu, uma vez.
    assert built.clock.sleeps == [2.0]
    assert a.count(CHAT) == 2 and budget.used == 2 and response.inference_calls == 2


def test_retry_after_loop_stops_at_the_attempt_budget(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(429, {"error": "limite"}, headers={"Retry-After": "1"}))
    built = assemble([local_route("unica", a.base_url, 1)], gateway_settings(circuit_failures=50))
    budget = AttemptBudget(limit=3)

    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), budget)

    assert a.count(CHAT) == 3 and budget.used == 3
    assert built.clock.sleeps == [1.0, 1.0]
    assert excinfo.value.details == {"reason": "all_routes_failed", "retry_after_s": 2}


def test_long_retry_after_is_not_waited(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(429, {"error": "limite"}, headers={"Retry-After": "120"}))
    built = assemble([local_route("unica", a.base_url, 1)])
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert built.clock.sleeps == [] and a.count(CHAT) == 1
    assert excinfo.value.details["retry_after_s"] == 121

    # Enquanto o prazo pedido pelo provedor não passa, a rota não é chamada de novo.
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert a.count(CHAT) == 1
    assert outcomes(excinfo.value.attempts) == ["unica:skipped:retry_after"]


def test_retry_after_is_respected_across_calls_when_another_route_exists(providers):
    a, b = local_server(providers), local_server(providers)
    a.enqueue(CHAT, Reply(429, {"error": "limite"}, headers={"Retry-After": "5"}))
    a.always(CHAT, Reply(200, ollama_chat("primária de volta")))
    b.always(CHAT, Reply(200, ollama_chat("secundária")))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])

    first = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(first.attempts) == ["primaria:rate_limited", "secundaria:ok"]
    # Havia outra rota: não se espera, troca-se.
    assert built.clock.sleeps == []

    second = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(second.attempts) == ["primaria:skipped:retry_after", "secundaria:ok"]
    assert a.count(CHAT) == 1

    built.clock.advance(5)
    third = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert third.content == "primária de volta" and a.count(CHAT) == 2


# ---------------------------------------------------------------------------
# AC-09: JSON inválido -> exatamente uma correção, depois troca de rota
# ---------------------------------------------------------------------------

def test_invalid_json_gets_exactly_one_correction_then_switches_route(providers):
    a, b = local_server(providers), local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("Claro! A categoria é moradia.")))
    b.always(CHAT, Reply(200, ollama_chat(VALID_ANSWER)))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(limit=3)
    request = user_request(response_schema=ANSWER_SCHEMA)

    response = built.gateway.complete(request, make_ctx(), budget)

    assert response.parsed == {"categoria": "moradia", "confianca": 90}
    assert response.alias == "secundaria" and response.fallback_used is True
    assert outcomes(response.attempts) == ["primaria:invalid_output", "primaria:invalid_output", "secundaria:ok"]
    # Exatamente 2 na primária (original + UMA correção) e 1 na secundária.
    assert (a.count(CHAT), b.count(CHAT)) == (2, 1)
    assert budget.used == 3 and response.inference_calls == 3

    original, correction = (item.json["messages"] for item in a.requests(CHAT))
    assert len(original) == 1
    assert [message["role"] for message in correction] == ["user", "assistant", "user"]
    assert "objeto JSON" in correction[2]["content"]
    # A rota seguinte recebe o pedido ORIGINAL, sem o diálogo de correção da outra.
    assert b.requests(CHAT)[0].json["messages"] == original
    # O pedido do orquestrador não é alterado.
    assert len(request.messages) == 1


def test_correction_that_succeeds_stays_on_the_same_route(providers):
    a, b = local_server(providers), local_server(providers)
    wrong_type = '{"categoria": "moradia", "confianca": "alta", "extra": 1}'
    a.enqueue(CHAT, Reply(200, ollama_chat(wrong_type)), Reply(200, ollama_chat(VALID_ANSWER)))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])

    response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), make_ctx(), AttemptBudget(3))

    assert response.alias == "primaria" and response.fallback_used is False
    assert response.parsed == {"categoria": "moradia", "confianca": 90}
    assert outcomes(response.attempts) == ["primaria:invalid_output", "primaria:ok"]
    assert (a.count(CHAT), b.count(CHAT)) == (2, 0)
    correction = a.requests(CHAT)[1].json["messages"][-1]["content"]
    # O modelo recebe o caminho e a regra violada.
    assert "$.confianca: tipo esperado integer" in correction and "$.extra: propriedade não permitida" in correction


def test_invalid_output_everywhere_ends_as_invalid_output_within_budget(providers):
    a, b = local_server(providers), local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("texto solto")))
    b.always(CHAT, Reply(200, ollama_chat('{"categoria": ""}')))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(limit=3)

    with fail_with("invalid_output") as excinfo:
        built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), make_ctx(), budget)

    # 2 na primária + 1 na secundária = 3; a correção da secundária não cabe no orçamento.
    assert (a.count(CHAT), b.count(CHAT)) == (2, 1) and budget.used == 3
    assert outcomes(excinfo.value.attempts) == [
        "primaria:invalid_output", "primaria:invalid_output", "secundaria:invalid_output",
    ]


def test_truncated_structured_answer_is_not_accepted(providers):
    a = local_server(providers)
    # JSON que "fecha", mas veio marcado como cortado pelo limite de tokens.
    a.enqueue(CHAT, Reply(200, ollama_chat(VALID_ANSWER, done_reason="length")), Reply(200, ollama_chat(VALID_ANSWER)))
    built = assemble([local_route("unica", a.base_url, 1)])
    response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), make_ctx(), AttemptBudget(3))
    assert outcomes(response.attempts) == ["unica:invalid_output", "unica:ok"] and a.count(CHAT) == 2


def test_malformed_tool_call_is_corrected_once(providers):
    a = local_server(providers)
    broken = [{"function": {"name": "finance.read", "arguments": "{query: payables"}}]
    good = [{"function": {"name": "finance.read", "arguments": {"query": "payables"}}}]
    a.enqueue(CHAT, Reply(200, ollama_chat(tool_calls=broken)), Reply(200, ollama_chat(tool_calls=good)))
    built = assemble([local_route("unica", a.base_url, 1)])
    response = built.gateway.complete(
        user_request(tools=[READ_TOOL], response_schema=ANSWER_SCHEMA), make_ctx(), AttemptBudget(3)
    )
    # Com chamada de ferramenta, a resposta segue para o orquestrador sem validação de JSON final.
    assert response.finish_reason == "tool_calls" and response.parsed is None
    assert response.tool_calls[0].name == "finance.read" and response.tool_calls[0].arguments == {"query": "payables"}
    assert outcomes(response.attempts) == ["unica:invalid_output", "unica:ok"]


def test_unsupported_schema_fails_before_any_request(providers):
    a = local_server(providers)
    built = assemble([local_route("unica", a.base_url, 1)])
    budget = AttemptBudget(3)
    schema = {"type": "object", "properties": {"cpf": {"type": "string", "pattern": "^[0-9]{11}$"}}}
    with fail_with("internal_error"):
        built.gateway.complete(user_request(response_schema=schema), make_ctx(), budget)
    assert a.count() == 0 and budget.used == 0


# ---------------------------------------------------------------------------
# AC-09: disjuntor
# ---------------------------------------------------------------------------

def test_circuit_opens_after_n_failures_and_probe_decides_closing(providers):
    a, b = local_server(providers), local_server(providers)
    a.always(CHAT, Reply(500, {"error": "falha"}))
    b.always(CHAT, Reply(200, ollama_chat("secundária")))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    ctx = make_ctx()

    for _ in range(3):
        response = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
        assert outcomes(response.attempts) == ["primaria:server_error", "secundaria:ok"]
    assert a.count(CHAT) == 3 and built.circuit.state("primaria") == "open"

    # Circuito aberto: a rota não recebe requisição e não gasta orçamento.
    budget = AttemptBudget(3)
    response = built.gateway.complete(user_request(), ctx, budget)
    assert outcomes(response.attempts) == ["primaria:skipped:circuit_open", "secundaria:ok"]
    assert a.count(CHAT) == 3 and budget.used == 1
    tags_before = a.count(TAGS)

    # Passado o prazo, a SONDA decide. Sonda falhando: continua aberto, sem inferência.
    built.clock.advance(60)
    a.always(TAGS, Reply(500, {"error": "fora"}))
    response = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert outcomes(response.attempts) == ["primaria:skipped:circuit_open", "secundaria:ok"]
    assert a.count(TAGS) == tags_before + 1 and a.count(CHAT) == 3

    # Reaberto por mais um período: nem sonda antes da hora.
    built.clock.advance(30)
    built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert a.count(TAGS) == tags_before + 1 and a.count(CHAT) == 3

    # Sonda passando: fecha e a rota volta a receber pedidos.
    built.clock.advance(30)
    serve_tags(a)
    a.always(CHAT, Reply(200, ollama_chat("primária recuperada")))
    budget = AttemptBudget(3)
    response = built.gateway.complete(user_request(), ctx, budget)
    assert response.content == "primária recuperada" and response.fallback_used is False
    assert a.count(TAGS) == tags_before + 2 and a.count(CHAT) == 4
    # A sonda não consome o orçamento de inferência.
    assert budget.used == 1 and built.circuit.state("primaria") == "closed"


def test_open_circuit_with_no_other_route_is_model_unavailable(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(500, {"error": "falha"}))
    built = assemble([local_route("unica", a.base_url, 1)])
    for _ in range(3):
        with fail_with("model_unavailable"):
            built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert a.count(CHAT) == 3
    assert outcomes(excinfo.value.attempts) == ["unica:skipped:circuit_open"]


# ---------------------------------------------------------------------------
# AC-09: recusa e pedido inválido NÃO trocam de rota
# ---------------------------------------------------------------------------

def test_refusal_does_not_switch_route(providers):
    a, b = providers(), local_server(providers)
    a.always("GET /models", Reply(200, {"data": []}))
    a.always("POST /chat/completions", Reply(200, openai_chat(None, refusal="Não posso ajudar com isso.")))
    b.always(CHAT, Reply(200, ollama_chat("a secundária responderia")))
    built = assemble([local_openai_route("primaria", a, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(3)

    with fail_with("model_refused") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), budget)

    assert excinfo.value.retryable is False
    assert a.count("POST /chat/completions") == 1 and b.count(CHAT) == 0
    assert budget.used == 1 and outcomes(excinfo.value.attempts) == ["primaria:refusal"]
    # Recusa não é falha de saúde da rota: o circuito não conta.
    assert built.circuit.state("primaria") == "closed"


def test_bad_request_does_not_switch_route(providers):
    a, b = local_server(providers), local_server(providers)
    a.always(CHAT, Reply(400, {"error": '"modelo-teste:1b" does not support tools'}))
    b.always(CHAT, Reply(200, ollama_chat("a secundária responderia")))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    with fail_with("internal_error") as excinfo:
        built.gateway.complete(user_request(tools=[READ_TOOL]), make_ctx(), AttemptBudget(3))
    assert excinfo.value.details == {"reason": "bad_request", "detail_code": "tools_not_supported"}
    assert a.count(CHAT) == 1 and b.count(CHAT) == 0


# ---------------------------------------------------------------------------
# AC-09: 401 suspende a credencial
# ---------------------------------------------------------------------------

def test_401_suspends_credential_and_following_calls_do_not_use_it(providers, monkeypatch, caplog):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    a, same_key, b = providers(), providers(), local_server(providers)
    for server in (a, same_key):
        server.always("GET /models", Reply(200, {"data": []}))
    a.always("POST /chat/completions", Reply(401, {"error": {"message": "chave inválida"}}))
    same_key.always("POST /chat/completions", Reply(200, openai_chat("outra rota, mesma chave")))
    b.always(CHAT, Reply(200, ollama_chat("secundária")))
    routes = [
        local_openai_route("primaria", a, 1, credential_env=CREDENTIAL_ENV),
        local_openai_route("mesma-chave", same_key, 2, credential_env=CREDENTIAL_ENV),
        local_route("secundaria", b.base_url, 3),
    ]
    built = assemble(routes)
    caplog.set_level(logging.DEBUG)

    first = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    # A credencial foi rejeitada: a outra rota com a MESMA credencial também sai.
    assert outcomes(first.attempts) == ["primaria:auth", "mesma-chave:skipped:credential_suspended", "secundaria:ok"]
    assert built.gateway.suspended_credentials() == [CREDENTIAL_ENV]
    assert built.circuit.state("primaria") == "closed"

    budget = AttemptBudget(3)
    second = built.gateway.complete(user_request(), make_ctx(), budget)
    assert outcomes(second.attempts) == [
        "primaria:skipped:credential_suspended", "mesma-chave:skipped:credential_suspended", "secundaria:ok",
    ]
    assert a.count("POST /chat/completions") == 1 and same_key.count() == 0
    assert budget.used == 1

    # O operador é avisado com o NOME da variável, nunca com o valor.
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and record.getMessage().startswith("credential_suspended ")
    ]
    assert len(warnings) == 1 and "credential=%s" % CREDENTIAL_ENV in warnings[0] and "status=401" in warnings[0]
    assert FAKE_SECRET not in caplog.text

    assert built.gateway.reinstate_credential(CREDENTIAL_ENV) is True
    a.always("POST /chat/completions", Reply(200, openai_chat("credencial corrigida")))
    third = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert third.content == "credencial corrigida"


def test_missing_credential_does_not_consume_attempt_budget(providers, monkeypatch):
    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)
    a, b = providers(), local_server(providers)
    a.always("GET /models", Reply(200, {"data": []}))
    b.always(CHAT, Reply(200, ollama_chat("ok")))
    built = assemble(
        [local_openai_route("primaria", a, 1, credential_env=CREDENTIAL_ENV), local_route("secundaria", b.base_url, 2)],
        verify_local_routes=False,
    )
    budget = AttemptBudget(3)
    response = built.gateway.complete(user_request(), make_ctx(), budget)
    assert outcomes(response.attempts) == ["primaria:auth", "secundaria:ok"]
    # Nenhuma requisição saiu para a primária, então ela não conta no orçamento.
    assert a.count() == 0 and budget.used == 1


# ---------------------------------------------------------------------------
# AC-10 no gateway: capacidade, estado e propósito
# ---------------------------------------------------------------------------

def test_ac10_incapable_route_is_not_used_even_when_the_capable_one_fails(providers):
    plain, full = local_server(providers), local_server(providers)
    plain.always(CHAT, Reply(200, ollama_chat("eu responderia, mas não sei usar ferramentas")))
    full.always(CHAT, Reply(500, {"error": "falha"}))
    routes = [
        local_route(
            "sem-capacidades", plain.base_url, 1, supports_tools=False, supports_json=False, supports_vision=False
        ),
        local_route("completa", full.base_url, 2),
    ]
    requests_needing = [
        user_request(tools=[READ_TOOL]),
        user_request(response_schema=ANSWER_SCHEMA),
        user_request(images=[b"\x89PNG\r\n\x1a\nimagem-sintetica"]),
        user_request(task_class="vision"),
    ]
    for request in requests_needing:
        built = assemble(routes)
        with fail_with("model_unavailable") as excinfo:
            built.gateway.complete(request, make_ctx(), AttemptBudget(3))
        assert outcomes(excinfo.value.attempts) == ["completa:server_error"]
    # A rota sem a capacidade nunca recebeu nada, nem sonda.
    assert plain.count() == 0 and full.count(CHAT) == len(requests_needing)

    # Sem exigência, ela é a preferida (prova de que o que a excluiu foi a capacidade).
    built = assemble(routes)
    assert built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3)).alias == "sem-capacidades"


def test_ac10_candidate_route_is_not_used_without_the_flag(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("candidata respondeu")))
    routes = [local_route("candidata", a.base_url, 1, state="candidate")]

    built = assemble(routes)
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert excinfo.value.details == {"reason": "no_eligible_route"} and a.count() == 0

    built = assemble(routes, gateway_settings(allow_candidate_models=True))
    assert built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3)).content == "candidata respondeu"


def test_ac10_write_purpose_never_falls_back_to_read_only_route(providers):
    reader, writer = local_server(providers), local_server(providers)
    reader.always(CHAT, Reply(200, ollama_chat("rota de leitura")))
    writer.always(CHAT, Reply(500, {"error": "falha"}))
    routes = [
        local_route("so-leitura", reader.base_url, 1, approved_purposes=("read",)),
        local_route("escrita", writer.base_url, 2),
    ]
    built = assemble(routes)
    with fail_with("model_unavailable"):
        built.gateway.complete(user_request(purpose=PURPOSE_WRITE), make_ctx(), AttemptBudget(3))
    assert reader.count() == 0 and writer.count(CHAT) == 1
    # A mesma rota de leitura atende leitura normalmente.
    assert built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3)).alias == "so-leitura"


# ---------------------------------------------------------------------------
# Conferência do modelo local antes do uso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tags_kwargs",
    [
        {"digest": DIGEST_B},
        {"remote_host": "https://ollama.com", "remote_model": "modelo-remoto"},
        {"model": "outro:1b"},
    ],
)
def test_local_model_that_is_not_the_homologated_one_receives_no_inference(providers, tags_kwargs):
    a, b = providers(), local_server(providers)
    serve_tags(a, **tags_kwargs)
    a.always(CHAT, Reply(200, ollama_chat("modelo trocado respondeu")))
    b.always(CHAT, Reply(200, ollama_chat("secundária")))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(3)
    response = built.gateway.complete(user_request(), make_ctx(), budget)
    assert outcomes(response.attempts) == ["primaria:skipped:probe_failed", "secundaria:ok"]
    assert a.count(CHAT) == 0 and budget.used == 1


def test_local_verification_is_cached_for_a_while(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("ok")))
    built = assemble([local_route("unica", a.base_url, 1)], local_verify_ttl_s=300)
    for _ in range(3):
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert (a.count(TAGS), a.count(CHAT)) == (1, 3)
    built.clock.advance(301)
    built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert a.count(TAGS) == 2


# ---------------------------------------------------------------------------
# Robustez
# ---------------------------------------------------------------------------

def test_route_without_adapter_is_skipped_and_adapter_defect_is_contained(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(200, ollama_chat("ok")))
    settings = gateway_settings()
    routes = [local_route("unica", a.base_url, 1)]

    class BrokenAdapter(ProviderAdapter):
        provider = "ollama"

        def complete(self, route, request, timeout_s) -> AdapterResult:
            raise RuntimeError("defeito sintético com detalhe-interno-que-nao-deve-vazar")

    def gateway_with(adapters):
        clock = FakeClock()
        return DefaultModelGateway(
            ModelRegistry(routes, settings), adapters, CircuitBreaker(settings, clock=clock), None, settings,
            clock=clock, sleep=clock.sleep,
        )

    with fail_with("model_unavailable") as excinfo:
        gateway_with({}).complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(excinfo.value.attempts) == ["unica:skipped:no_adapter"]

    budget = AttemptBudget(3)
    with fail_with("internal_error") as excinfo:
        gateway_with({"ollama": BrokenAdapter()}).complete(user_request(), make_ctx(), budget)
    assert "detalhe-interno" not in str(excinfo.value) + repr(excinfo.value.to_dict())
    # A exceção do adaptador não viaja nem encadeada (ela pode guardar o pedido).
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None
    assert budget.used == 1 and excinfo.value.inference_calls == 1
    assert a.count(CHAT) == 0

    class NoneAdapter(BrokenAdapter):
        def complete(self, route, request, timeout_s):
            return None  # defeito: não devolveu AdapterResult

    budget = AttemptBudget(3)
    with fail_with("internal_error") as excinfo:
        gateway_with({"ollama": NoneAdapter()}).complete(user_request(), make_ctx(), budget)
    assert excinfo.value.details == {"reason": "adapter_error"} and budget.used == 1


def test_gateway_logs_carry_no_prompt_or_answer(providers, caplog):
    a = local_server(providers)
    prompt = "extrato-sintetico-conta-0001-saldo-123456"
    answer = "resposta-sintetica-do-modelo-987654"
    a.enqueue(CHAT, Reply(200, ollama_chat("prosa " + answer)), Reply(200, ollama_chat(VALID_ANSWER)))
    built = assemble([local_route("unica", a.base_url, 1)])
    caplog.set_level(logging.DEBUG)
    built.gateway.complete(user_request(prompt, response_schema=ANSWER_SCHEMA), make_ctx(), AttemptBudget(3))
    assert caplog.text and "attempt alias=unica" in caplog.text
    assert prompt not in caplog.text and answer not in caplog.text


# ---------------------------------------------------------------------------
# Rota paga sem livro de orçamento nunca roda
# ---------------------------------------------------------------------------

def test_external_route_never_runs_without_a_budget_ledger(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    external, local = providers(), local_server(providers)
    external.always("POST /chat/completions", Reply(200, openai_chat("resposta paga")))
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    paid = external_route("externa", external.base_url, 1)
    settings = gateway_settings(cloud_enabled=True)
    ctx = make_ctx(Privacy.CLOUD_ALLOWED)

    # Sem pool não há livro: não existe reserva nem teto para a rota paga.
    built = assemble([paid, local_route("local", local.base_url, 2)], settings, pool=None)
    assert built.ledger is None
    budget = AttemptBudget(3)
    response = built.gateway.complete(user_request(), ctx, budget)
    assert outcomes(response.attempts) == ["externa:skipped:no_budget_ledger", "local:ok"]
    assert external.count() == 0 and budget.used == 1 and response.cost_micros == 0

    budget = AttemptBudget(3)
    with fail_with("model_unavailable") as excinfo:
        assemble([paid], settings, pool=None).gateway.complete(user_request(), ctx, budget)
    assert outcomes(excinfo.value.attempts) == ["externa:skipped:no_budget_ledger"]
    assert external.count() == 0 and budget.used == 0


def test_build_gateway_without_pool_keeps_paid_routes_out(providers, monkeypatch, tmp_path):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    external, local = providers(), local_server(providers)
    external.always("POST /chat/completions", Reply(200, openai_chat("resposta paga")))
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    common = {
        "task_classes": ["simple_extraction"], "supports_tools": True, "supports_json": True,
        "supports_vision": False, "context_window": 8192, "state": "approved",
        "approved_purposes": ["read"], "evidence": "homologacao-sintetica-de-teste",
    }
    document = {
        "routes": [
            dict(
                common, alias="externa", provider="openai_compatible", model_id="modelo-externo-teste",
                locality="external", priority=1, privacy=["cloud_allowed"], base_url=external.base_url,
                credential_env=CREDENTIAL_ENV, max_cost_micros_per_call=1000,
            ),
            dict(
                common, alias="local", provider="ollama", model_id="modelo-teste:1b", locality="local",
                priority=2, digest="a" * 64,
            ),
        ]
    }
    registry_file = tmp_path / "models.json"
    registry_file.write_text(json.dumps(document), encoding="utf-8")
    settings = gateway_settings(
        cloud_enabled=True, model_registry_path=str(registry_file), ollama_base_url=local.base_url
    )

    # Caminho público de montagem (o que services.ai.platform usa), sem pool.
    gateway = build_gateway(None, settings)
    response = gateway.complete(user_request(), make_ctx(Privacy.CLOUD_ALLOWED), AttemptBudget(3))

    assert outcomes(response.attempts) == ["externa:skipped:no_budget_ledger", "local:ok"]
    assert response.content == "resposta local" and external.count() == 0


# ---------------------------------------------------------------------------
# Prazo por inferência: a rota só pode REDUZIR o teto global
# ---------------------------------------------------------------------------

def test_route_timeout_override_can_only_lower_the_global_ceiling(providers):
    slow, quick = local_server(providers), local_server(providers)
    slow.always(CHAT, Reply(200, ollama_chat("tarde demais"), delay_s=8))
    quick.always(CHAT, Reply(200, ollama_chat("secundária")))
    routes = [
        # A rota pede 30 s; o teto global é 1 s. Vale o teto.
        local_route("lenta", slow.base_url, 1, extra={"timeout_s": 30}),
        local_route("rapida", quick.base_url, 2),
    ]
    built = assemble(routes, gateway_settings(inference_timeout_s=1))

    started = time.monotonic()
    response = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    elapsed = time.monotonic() - started

    # Se a rota pudesse aumentar o prazo, a resposta lenta (8 s) seria aceita.
    assert outcomes(response.attempts) == ["lenta:timeout", "rapida:ok"]
    assert response.content == "secundária" and elapsed < 6


# ---------------------------------------------------------------------------
# Schema com valor de palavra-chave malformado: falha ANTES da chamada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {"a": {"type": "string", "minLength": "1"}}},
        {"type": "object", "required": 5},
        {"type": "object", "properties": {"a": {"enum": 7}}},
        {"type": "object", "additionalProperties": "false"},
        {"type": "object", "properties": {"n": {"type": "number", "minimum": "0"}}},
        {"type": "object", "properties": {"itens": {"type": "array", "maxItems": True}}},
    ],
)
def test_schema_with_malformed_keyword_value_fails_before_any_request(providers, schema):
    a = local_server(providers)
    # Resposta que EXERCITARIA cada palavra-chave se a chamada fosse feita.
    a.always(CHAT, Reply(200, ollama_chat('{"a": "x", "n": 1, "itens": [1]}')))
    built = assemble([local_route("unica", a.base_url, 1)])
    budget = AttemptBudget(3)
    with fail_with("internal_error") as excinfo:
        built.gateway.complete(user_request(response_schema=schema), make_ctx(), budget)
    assert excinfo.value.details == {"reason": "schema_unsupported"}
    # Nenhuma requisição (nem sonda) e nenhuma tentativa gasta.
    assert a.count() == 0 and budget.used == 0


# ---------------------------------------------------------------------------
# Retry-After e disjuntor
# ---------------------------------------------------------------------------

def test_retry_after_is_not_waited_when_the_circuit_is_open(providers):
    a = local_server(providers)
    a.always(CHAT, Reply(429, {"error": "limite"}, headers={"Retry-After": "9"}))
    # Uma falha já abre o circuito: a espera de 9 s (curta, sem outra rota)
    # seria seguida de "circuito aberto", ou seja, tempo perdido.
    built = assemble([local_route("unica", a.base_url, 1)], gateway_settings(circuit_failures=1))

    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(excinfo.value.attempts) == ["unica:rate_limited"]
    assert built.clock.sleeps == [] and a.count(CHAT) == 1

    # Na chamada seguinte o circuito está aberto E a espera pedida ainda não
    # passou: o disjuntor é consultado antes, e ninguém dorme.
    with fail_with("model_unavailable") as excinfo:
        built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(excinfo.value.attempts) == ["unica:skipped:circuit_open"]
    assert built.clock.sleeps == [] and a.count(CHAT) == 1


# ---------------------------------------------------------------------------
# Chamada de ferramenta cortada pelo limite de tokens
# ---------------------------------------------------------------------------

def test_truncated_tool_call_gets_one_correction_then_switches_route(providers):
    a, b = local_server(providers), local_server(providers)
    cut = [{"function": {"name": "finance.read", "arguments": {}}}]
    good = [{"function": {"name": "finance.read", "arguments": {"query": "payables"}}}]
    a.always(CHAT, Reply(200, ollama_chat(tool_calls=cut, done_reason="length")))
    b.always(CHAT, Reply(200, ollama_chat(tool_calls=good)))
    built = assemble([local_route("primaria", a.base_url, 1), local_route("secundaria", b.base_url, 2)])
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(tools=[READ_TOOL]), make_ctx(), budget)

    # A chamada cortada NÃO chega ao orquestrador: uma correção, depois outra rota.
    assert outcomes(response.attempts) == ["primaria:invalid_output", "primaria:invalid_output", "secundaria:ok"]
    assert (a.count(CHAT), b.count(CHAT)) == (2, 1) and budget.used == 3
    assert response.alias == "secundaria" and response.tool_calls[0].arguments == {"query": "payables"}
    assert "cortada" in a.requests(CHAT)[1].json["messages"][-1]["content"]

    # Sem outra rota e sem orçamento para mais, termina como saída inválida.
    alone = assemble([local_route("primaria", a.base_url, 1)])
    with fail_with("invalid_output") as excinfo:
        alone.gateway.complete(user_request(tools=[READ_TOOL]), make_ctx(), AttemptBudget(3))
    assert outcomes(excinfo.value.attempts) == ["primaria:invalid_output", "primaria:invalid_output"]
    assert excinfo.value.inference_calls == 2 and excinfo.value.cost_micros == 0


# ---------------------------------------------------------------------------
# Credencial malformada
# ---------------------------------------------------------------------------

def chained_text(error):
    """Tudo o que está pendurado em uma exceção (causa e contexto), em texto."""
    parts, current, guard = [], error, 0
    while current is not None and guard < 10:
        parts.append("%s %r %r" % (current, getattr(current, "args", ()), vars(current)))
        current, guard = current.__cause__ or current.__context__, guard + 1
    return " ".join(parts)


def test_malformed_credential_is_suspended_and_never_sent(providers, monkeypatch, caplog):
    # Colagem com reticências tipográficas: não cabe em cabeçalho HTTP.
    secret = "credencial-ficticia-colada-com-reticencias…"
    monkeypatch.setenv(CREDENTIAL_ENV, secret)
    a, b = providers(), local_server(providers)
    a.always("POST /chat/completions", Reply(200, openai_chat("a primária responderia")))
    b.always(CHAT, Reply(200, ollama_chat("secundária")))
    primary = local_openai_route("primaria", a, 1, credential_env=CREDENTIAL_ENV)
    built = assemble([primary, local_route("secundaria", b.base_url, 2)], verify_local_routes=False)
    caplog.set_level(logging.DEBUG)
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(), make_ctx(), budget)

    # Tratada como credencial com problema (failover e suspensão), não como
    # defeito do adaptador; nada saiu, então não gasta tentativa.
    assert outcomes(response.attempts) == ["primaria:auth", "secundaria:ok"]
    assert a.count() == 0 and budget.used == 1
    assert built.gateway.suspended_credentials() == [CREDENTIAL_ENV]
    assert "detail=credential_malformed" in caplog.text and secret not in caplog.text

    alone = assemble([primary], verify_local_routes=False)
    with fail_with("model_unavailable") as excinfo:
        alone.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert outcomes(excinfo.value.attempts) == ["primaria:auth"]
    # Nem no erro, nem em nada encadeado nele.
    assert secret not in chained_text(excinfo.value) and a.count() == 0


# ---------------------------------------------------------------------------
# Rótulos do provedor no resultado
# ---------------------------------------------------------------------------

def test_gateway_filters_labels_coming_from_any_adapter(providers, caplog):
    a = local_server(providers)
    dirty_model = "linha1\nlinha-forjada " + "x" * 5000
    a.enqueue(CHAT, Reply(200, ollama_chat("ok", model=dirty_model)))
    built = assemble([local_route("unica", a.base_url, 1)])
    response = built.gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    # O texto do provedor não vira "modelo efetivo": fica o do registro.
    assert response.model_id == "modelo-teste:1b" and response.effective_provider is None

    class ThirdPartyAdapter(ProviderAdapter):
        """Adaptador de fora deste pacote, que repassa o texto do provedor como veio."""

        provider = "ollama"

        def complete(self, route, request, timeout_s) -> AdapterResult:
            return AdapterResult(content="ok", model_id=dirty_model, effective_provider="fornecedor\nforjado")

    settings = gateway_settings()
    clock = FakeClock()
    gateway = DefaultModelGateway(
        ModelRegistry([local_route("unica", a.base_url, 1)], settings), {"ollama": ThirdPartyAdapter()},
        CircuitBreaker(settings, clock=clock), None, settings, clock=clock, sleep=clock.sleep,
    )
    caplog.set_level(logging.DEBUG)
    response = gateway.complete(user_request(), make_ctx(), AttemptBudget(3))
    assert response.model_id == "modelo-teste:1b" and response.effective_provider is None
    assert "provider_label_rejected alias=unica field=model" in caplog.text
    assert "linha-forjada" not in caplog.text and "forjado" not in caplog.text
