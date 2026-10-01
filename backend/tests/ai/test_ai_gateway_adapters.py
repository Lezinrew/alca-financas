"""Adaptadores contra um servidor HTTP local: formato do pedido, da resposta e dos erros.

HTTP real (requests -> http.server). Nenhum provedor real é chamado.
"""

from __future__ import annotations

import base64
import gzip
import json
import time
from decimal import Decimal
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone

import pytest

from services.ai.gateway.adapters import MAX_RESPONSE_BYTES, ToolNameCodec, parse_retry_after
from services.ai.gateway.adapters.anthropic import AnthropicAdapter, output_schema_for_wire
from services.ai.gateway.adapters.ollama import OllamaAdapter
from services.ai.gateway.adapters.openai_compatible import OpenAICompatibleAdapter
from services.ai.gateway.base import ChatMessage, ProviderError, ToolCall, ToolSpec
from services.ai.gateway.validation import safe_label
from services.ai.types import canonical_json

from .support.gateway_harness import (
    ANSWER_SCHEMA,
    CREDENTIAL_ENV,
    DIGEST_A,
    DIGEST_B,
    LOCAL_MODEL,
    READ_TOOL,
    external_route,
    local_route,
    serve_tags,
    user_request,
)
from .support.gateway_harness import providers  # noqa: F401 - fixture do pytest
from .support.gateway_server import (
    Reply,
    anthropic_message,
    ollama_chat,
    ollama_model,
    ollama_tags,
    openai_chat,
    refused_base_url,
)


pytestmark = pytest.mark.unit

# Marcador sintético colocado nos corpos de erro do "provedor": nada dele pode
# aparecer no que o adaptador devolve ou levanta.
BODY_MARKER = "corpo-bruto-sintetico-do-provedor-4242"
# Valor fictício de credencial (não é chave de nenhum serviço).
FAKE_SECRET = "credencial-ficticia-apenas-para-teste"
PNG = b"\x89PNG\r\n\x1a\n" + b"imagem-sintetica"
NO_TOOLS_TEXT = '"modelo-teste:1b" does not support tools '
OLLAMA_TOOL_CALL = {"function": {"name": "finance.read", "arguments": {"query": "x", "v": 1.25}}}
READ_TOOL_FUNCTION = {"description": READ_TOOL.description, "parameters": READ_TOOL.parameters}

TOOL_CONVERSATION = [
    ChatMessage(role="system", content="Você é um operador financeiro."),
    ChatMessage(role="user", content="Quanto falta pagar?"),
    ChatMessage(
        role="assistant",
        content="",
        tool_calls=[
            ToolCall(id="call_1", name="finance.read", arguments={"query": "payables", "limite": Decimal("10.5")}),
            ToolCall(id="call_2", name="finance.read", arguments={"query": "balance"}),
        ],
    ),
    ChatMessage(role="tool", content='{"remaining": "300.00"}', tool_call_id="call_1", tool_name="finance.read"),
    ChatMessage(role="tool", content='{"balance": "50.00"}', tool_call_id="call_2", tool_name="finance.read"),
]


def raises(kind, call):
    with pytest.raises(ProviderError) as excinfo:
        call()
    error = excinfo.value
    assert error.kind == kind, "esperado %s, veio %s" % (kind, error.kind)
    # Nada do corpo do provedor viaja no erro.
    exposed = "%s %r %r %r" % (error, error.args, error.detail_code, error.__dict__)
    assert BODY_MARKER not in exposed
    # Nem encadeado: a exceção original (que guarda o pedido ou o corpo) não
    # viaja pendurada no erro. ``from None`` só a esconderia do traceback.
    assert error.__cause__ is None and error.__context__ is None
    return error


# ===========================================================================
# Ollama
# ===========================================================================

def test_ollama_request_format(providers):
    server = providers()
    server.enqueue("POST /api/chat", Reply(200, ollama_chat('{"categoria": "moradia", "confianca": 90}')))
    route = local_route("local", server.base_url, extra={"num_ctx": 4096, "think": False, "seed": 11})
    request = user_request("Classifique.", response_schema=ANSWER_SCHEMA, max_output_tokens=256, images=[PNG])

    result = OllamaAdapter().complete(route, request, 5)

    sent = server.requests("POST /api/chat")[0].json
    assert sent["model"] == LOCAL_MODEL and sent["stream"] is False
    assert sent["options"] == {"temperature": 0.0, "num_predict": 256, "seed": 11, "num_ctx": 4096}
    assert sent["format"] == ANSWER_SCHEMA and "tools" not in sent
    assert sent["think"] is False
    assert sent["messages"] == [
        {"role": "user", "content": "Classifique.", "images": [base64.b64encode(PNG).decode("ascii")]}
    ]
    assert result.content == '{"categoria": "moradia", "confianca": 90}'
    assert result.finish_reason == "stop" and result.cost_micros == 0 and result.upstream_attempts == 1
    assert result.model_id == LOCAL_MODEL
    assert (result.usage.input_tokens, result.usage.output_tokens) == (42, 17)
    assert result.metrics == {
        "total_duration": 1500000000,
        "load_duration": 200000000,
        "prompt_eval_count": 42,
        "prompt_eval_duration": 300000000,
        "eval_count": 17,
        "eval_duration": 900000000,
    }


def test_ollama_tools_and_format_never_go_together(providers):
    server = providers()
    server.enqueue(
        "POST /api/chat",
        Reply(200, ollama_chat(tool_calls=[OLLAMA_TOOL_CALL])),
    )
    route = local_route("local", server.base_url)
    request = user_request(messages=list(TOOL_CONVERSATION), tools=[READ_TOOL], response_schema=ANSWER_SCHEMA)

    result = OllamaAdapter().complete(route, request, 5)

    sent = server.requests("POST /api/chat")[0].json
    # Com ferramentas, o schema NÃO vai em "format" (o Ollama ignoraria as tools).
    assert "format" not in sent
    assert "think" not in sent and "num_ctx" not in sent["options"] and sent["options"]["seed"] == 7
    assert sent["tools"] == [
        {
            "type": "function",
            "function": dict(READ_TOOL_FUNCTION, name="finance.read"),
        }
    ]
    assistant = sent["messages"][2]
    # No Ollama os argumentos são OBJETO, não texto.
    assert assistant["tool_calls"][0] == {
        "type": "function",
        "function": {"name": "finance.read", "arguments": {"query": "payables", "limite": 10.5}},
    }
    assert sent["messages"][3] == {
        "role": "tool", "content": '{"remaining": "300.00"}', "tool_name": "finance.read", "tool_call_id": "call_1",
    }
    assert result.finish_reason == "tool_calls"
    call = result.tool_calls[0]
    assert call.name == "finance.read" and call.id.startswith("call_")
    # Sem float: o resultado precisa passar pelo JSON canônico da plataforma.
    assert call.arguments == {"query": "x", "v": Decimal("1.25")}
    assert canonical_json(call.arguments) == '{"query":"x","v":"1.25"}'


@pytest.mark.parametrize(
    "status, body, kind, detail",
    [
        (404, {"error": "model 'x' not found " + BODY_MARKER}, "unavailable", "model_not_found"),
        (503, {"error": "server busy " + BODY_MARKER}, "unavailable", "server_busy"),
        (500, {"error": "falha interna " + BODY_MARKER}, "server_error", None),
        (400, {"error": NO_TOOLS_TEXT + BODY_MARKER}, "bad_request", "tools_not_supported"),
        (400, {"error": "invalid request " + BODY_MARKER}, "bad_request", None),
        (403, {"error": "cloud disabled " + BODY_MARKER}, "bad_request", "remote_model_blocked"),
    ],
)
def test_ollama_error_mapping_makes_one_request_and_hides_body(providers, status, body, kind, detail):
    server = providers()
    server.always("POST /api/chat", Reply(status, body))
    route = local_route("local", server.base_url)
    error = raises(kind, lambda: OllamaAdapter().complete(route, user_request(), 5))
    assert error.status == status and error.detail_code == detail
    # Uma chamada = uma requisição. Nenhum retry escondido no adaptador.
    assert server.count("POST /api/chat") == 1


def test_ollama_timeout_and_refused_connection(providers):
    server = providers()
    server.always("POST /api/chat", Reply(200, ollama_chat("tarde demais"), delay_s=8))
    route = local_route("local", server.base_url)
    error = raises("timeout", lambda: OllamaAdapter().complete(route, user_request(), 1.0))
    # O pedido saiu e a resposta não veio a tempo.
    assert error.status is None and error.detail_code == "read_timeout"
    # Uma única requisição: espera a contagem estabilizar em vez de ler no
    # instante do timeout (a thread do servidor pode ainda não ter registrado).
    assert server.settled_count("POST /api/chat") == 1

    refused = local_route("local", refused_base_url())
    error = raises("network", lambda: OllamaAdapter().complete(refused, user_request(), 5))
    # Conexão recusada: nada saiu da máquina.
    assert error.status is None and error.detail_code == "connect_failed"


def test_ollama_malformed_success_bodies(providers):
    server = providers()
    route = local_route("local", server.base_url)
    server.enqueue("POST /api/chat", Reply(200, "<html>proxy " + BODY_MARKER + "</html>"))
    raises("server_error", lambda: OllamaAdapter().complete(route, user_request(), 5))
    server.enqueue(
        "POST /api/chat",
        Reply(
            200,
            ollama_chat(tool_calls=[{"function": {"name": "finance.read", "arguments": "{nao e json " + BODY_MARKER}}]),
        ),
    )
    raises("invalid_output", lambda: OllamaAdapter().complete(route, user_request(), 5))
    server.enqueue("POST /api/chat", Reply(200, ollama_chat("cortado", done_reason="length")))
    assert OllamaAdapter().complete(route, user_request(), 5).finish_reason == "length"


def test_ollama_probe_checks_presence_digest_and_remote(providers):
    adapter = OllamaAdapter()
    server = providers()
    route = local_route("local", server.base_url)

    serve_tags(server)
    assert adapter.inspect(route, 2) == "ok" and adapter.probe(route, 2) is True
    # Digest com prefixo "sha256:" é o mesmo digest.
    serve_tags(server, digest="sha256:" + DIGEST_A)
    assert adapter.probe(route, 2) is True

    server.always("GET /api/tags", Reply(200, ollama_tags(ollama_model("outro-modelo:1b", DIGEST_A))))
    assert adapter.inspect(route, 2) == "model_missing" and adapter.probe(route, 2) is False

    serve_tags(server, digest=DIGEST_B)
    assert adapter.inspect(route, 2) == "digest_mismatch" and adapter.probe(route, 2) is False

    # Modelo remoto atrás do Ollama local seria tráfego externo.
    serve_tags(server, remote_host="https://ollama.com", remote_model="modelo-remoto")
    assert adapter.inspect(route, 2) == "remote_model" and adapter.probe(route, 2) is False

    server.always("GET /api/tags", Reply(500, {"error": "x"}))
    assert adapter.inspect(route, 2) == "unreachable"
    assert adapter.probe(local_route("local", refused_base_url()), 2) is False
    assert server.count("POST /api/chat") == 0


def test_ollama_refuses_remote_model_names_without_any_request(providers):
    server = providers()
    # Monta a rota direto (o registro recusaria este nome) para exercitar a segunda trava.
    route = local_route("local", server.base_url, model_id="modelo:cloud")
    error = raises("bad_request", lambda: OllamaAdapter().complete(route, user_request(), 5))
    assert error.detail_code == "remote_model_blocked"
    assert server.count() == 0


def test_local_call_ignores_proxy_environment(providers, monkeypatch):
    server = providers()
    server.always("POST /api/chat", Reply(200, ollama_chat("ok")))
    # Se o adaptador respeitasse HTTP_PROXY, o pedido iria para esta porta
    # fechada (um "proxy externo") e falharia.
    dead_proxy = refused_base_url()
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, dead_proxy)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    result = OllamaAdapter().complete(local_route("local", server.base_url), user_request(), 5)
    assert result.content == "ok" and server.count("POST /api/chat") == 1


def test_redirect_is_not_followed(providers):
    server, elsewhere = providers(), providers()
    elsewhere.always("POST /api/chat", Reply(200, ollama_chat("não deveria chegar aqui")))
    redirect = Reply(307, {"x": BODY_MARKER}, headers={"Location": elsewhere.base_url + "/api/chat"})
    server.always("POST /api/chat", redirect)
    route = local_route("local", server.base_url)
    error = raises("unavailable", lambda: OllamaAdapter().complete(route, user_request(), 5))
    assert error.detail_code == "unexpected_redirect"
    assert elsewhere.count() == 0


# ===========================================================================
# OpenAI-compatível
# ===========================================================================

def test_openai_reads_credential_at_call_time(providers, monkeypatch):
    server = providers()
    server.always("POST /chat/completions", Reply(200, openai_chat("ok")))
    route = external_route("externa", server.base_url)
    adapter = OpenAICompatibleAdapter()

    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)
    error = raises("auth", lambda: adapter.complete(route, user_request(), 5))
    assert error.detail_code == "credential_missing" and error.status is None
    assert server.count() == 0  # sem credencial, nenhuma requisição sai

    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    adapter.complete(route, user_request(), 5)
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET + "-rotacionada")
    adapter.complete(route, user_request(), 5)
    sent = server.requests("POST /chat/completions")
    assert sent[0].headers["authorization"] == "Bearer " + FAKE_SECRET
    # A rotação da chave vale na chamada seguinte, sem reiniciar nada.
    assert sent[1].headers["authorization"] == "Bearer " + FAKE_SECRET + "-rotacionada"
    assert FAKE_SECRET not in repr(vars(adapter))


def test_openai_request_and_response_format(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.enqueue(
        "POST /chat/completions",
        Reply(
            200,
            openai_chat(
                content=None,
                finish_reason="tool_calls",
                model="modelo-efetivo-2026",
                tool_calls=[
                    {"id": "call_9", "type": "function",
                     "function": {"name": "finance__read", "arguments": '{"query": "payables", "valor": 12.5}'}}
                ],
            ),
        ),
    )
    route = external_route("externa", server.base_url)
    request = user_request(
        messages=list(TOOL_CONVERSATION), tools=[READ_TOOL], response_schema=ANSWER_SCHEMA, max_output_tokens=300
    )

    result = OpenAICompatibleAdapter().complete(route, request, 5)

    recorded = server.requests("POST /chat/completions")[0]
    sent = recorded.json
    assert sent["model"] == "modelo-externo-teste" and sent["stream"] is False
    assert sent["max_tokens"] == 300 and sent["temperature"] == 0.0
    # Rota direta: nada de parâmetros de agregador.
    assert "provider" not in sent and "models" not in sent
    assert "x-openrouter-metadata" not in recorded.headers
    # Nome de ferramenta sem ponto (a OpenAI recusa "finance.read").
    assert sent["tools"][0] == {
        "type": "function",
        "function": {"name": "finance__read", "description": READ_TOOL.description, "parameters": READ_TOOL.parameters},
    }
    assistant = sent["messages"][2]
    assert assistant["tool_calls"][0]["function"] == {
        "name": "finance__read", "arguments": '{"query": "payables", "limite": 10.5}',
    }
    assert sent["messages"][3] == {"role": "tool", "tool_call_id": "call_1", "content": '{"remaining": "300.00"}'}
    assert sent["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "resposta", "strict": True, "schema": ANSWER_SCHEMA},
    }

    assert result.finish_reason == "tool_calls" and result.model_id == "modelo-efetivo-2026"
    assert result.tool_calls == [
        ToolCall(id="call_9", name="finance.read", arguments={"query": "payables", "valor": Decimal("12.5")})
    ]
    assert (result.usage.input_tokens, result.usage.output_tokens) == (100, 20)
    assert result.cost_micros is None and result.effective_provider is None and result.upstream_attempts == 1


def test_openai_strict_mode_only_when_schema_allows_and_options(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.always("POST /chat/completions", Reply(200, openai_chat("{}")))
    loose_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
    }
    route = external_route(
        "externa", server.base_url, extra={"max_tokens_param": "max_completion_tokens", "send_temperature": False}
    )
    OpenAICompatibleAdapter().complete(route, user_request(response_schema=loose_schema, images=[PNG]), 5)
    sent = server.requests("POST /chat/completions")[0].json
    assert sent["response_format"]["json_schema"]["strict"] is False
    assert "max_tokens" not in sent and sent["max_completion_tokens"] == 1024
    assert "temperature" not in sent
    content = sent["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Classifique a despesa sintética."}
    assert content[1]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")


def test_openai_invalid_tool_arguments_and_refusals(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    route = external_route("externa", server.base_url)
    adapter = OpenAICompatibleAdapter()

    bad_function = {"name": "finance__read", "arguments": "{query: " + BODY_MARKER}
    bad_call = [{"id": "call_1", "type": "function", "function": bad_function}]
    server.enqueue(
        "POST /chat/completions", Reply(200, openai_chat(None, tool_calls=bad_call, finish_reason="tool_calls"))
    )
    error = raises("invalid_output", lambda: adapter.complete(route, user_request(tools=[READ_TOOL]), 5))
    assert error.detail_code == "tool_arguments_invalid"

    server.enqueue("POST /chat/completions", Reply(200, openai_chat(None, refusal="Não posso ajudar. " + BODY_MARKER)))
    assert raises("refusal", lambda: adapter.complete(route, user_request(), 5)).status == 200
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("", finish_reason="content_filter")))
    raises("refusal", lambda: adapter.complete(route, user_request(), 5))

    server.enqueue("POST /chat/completions", Reply(200, {"choices": []}))
    error = raises("server_error", lambda: adapter.complete(route, user_request(), 5))
    assert error.detail_code == "malformed_response"
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("parcial", finish_reason="length")))
    assert adapter.complete(route, user_request(), 5).finish_reason == "length"


@pytest.mark.parametrize(
    "status, headers, body, kind, retry_after",
    [
        (429, {"Retry-After": "7"}, {"error": {"message": BODY_MARKER}}, "rate_limited", 7.0),
        (429, {}, {"error": {"message": BODY_MARKER}}, "rate_limited", None),
        (429, {"Retry-After": "7"}, {"error": {"code": "insufficient_quota", "message": BODY_MARKER}}, "auth", None),
        (401, {}, {"error": {"message": "chave inválida " + BODY_MARKER}}, "auth", None),
        (402, {}, {"error": {"message": BODY_MARKER}}, "auth", None),
        (403, {}, {"error": {"message": BODY_MARKER}}, "auth", None),
        (408, {}, {"error": {"message": BODY_MARKER}}, "timeout", None),
        (504, {}, {"error": {"message": BODY_MARKER}}, "timeout", None),
        (500, {}, {"error": {"message": BODY_MARKER}}, "server_error", None),
        (502, {}, "<html>" + BODY_MARKER + "</html>", "server_error", None),
        (503, {"Retry-After": "3"}, {"error": {"message": BODY_MARKER}}, "server_error", 3.0),
        (400, {}, {"error": {"message": BODY_MARKER}}, "bad_request", None),
        (404, {}, {"error": {"message": BODY_MARKER}}, "unavailable", None),
    ],
)
def test_openai_error_mapping(providers, monkeypatch, status, headers, body, kind, retry_after):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.always("POST /chat/completions", Reply(status, body, headers=headers))
    route = external_route("externa", server.base_url)
    error = raises(kind, lambda: OpenAICompatibleAdapter().complete(route, user_request(), 5))
    assert error.status == status and error.retry_after_s == retry_after
    assert server.count("POST /chat/completions") == 1
    assert FAKE_SECRET not in "%s %r" % (error, error.__dict__)


def test_openai_timeout_makes_a_single_request(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.always("POST /chat/completions", Reply(200, openai_chat("tarde"), delay_s=8))
    route = external_route("externa", server.base_url)
    raises("timeout", lambda: OpenAICompatibleAdapter().complete(route, user_request(), 1.0))
    assert server.settled_count("POST /chat/completions") == 1


def test_openrouter_pins_upstream_disables_fallbacks_and_reads_metadata(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    metadata = {
        "attempt": 2,
        "attempts": [
            {"provider": "fornecedor-teste", "model": "m", "status": 503},
            {"provider": "fornecedor-teste", "model": "m", "status": 200},
        ],
    }
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0012345}
    server.enqueue(
        "POST /chat/completions",
        Reply(200, openai_chat("ok", usage=usage, openrouter_metadata=metadata)),
    )
    route = external_route(
        "via-openrouter",
        server.base_url,
        upstream_provider="fornecedor-teste",
        extra={"aggregator": "openrouter", "zdr": True},
    )

    result = OpenAICompatibleAdapter().complete(route, user_request(response_schema=ANSWER_SCHEMA), 5)

    recorded = server.requests("POST /chat/completions")[0]
    assert recorded.json["provider"] == {
        "order": ["fornecedor-teste"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
    # Fallback entre modelos do agregador nunca é pedido.
    assert "models" not in recorded.json and "route" not in recorded.json
    assert recorded.headers["x-openrouter-metadata"] == "enabled"
    assert result.effective_provider == "fornecedor-teste"
    # As duas tentativas internas do agregador contam no orçamento do gateway.
    assert result.upstream_attempts == 2
    # 0.0012345 crédito = 1234.5 micros, arredondado para cima.
    assert result.cost_micros == 1235 and isinstance(result.cost_micros, int)


def test_openrouter_error_carries_internal_attempts_and_requires_pinned_upstream(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    body = {
        "error": {"code": 503, "message": BODY_MARKER},
        "openrouter_metadata": {"attempts": [{"provider": "a", "status": 503}] * 3},
    }
    server.enqueue("POST /chat/completions", Reply(503, body, headers={"Retry-After": "2"}))
    route = external_route(
        "via-openrouter", server.base_url, upstream_provider="fornecedor-teste", extra={"aggregator": "openrouter"}
    )
    error = raises("server_error", lambda: OpenAICompatibleAdapter().complete(route, user_request(), 5))
    assert error.upstream_attempts == 3 and error.retry_after_s == 2.0

    # 402 "em voo" é o único 402 transitório.
    in_flight = {"error": {"code": 402, "metadata": {"limit_source": "openrouter_in_flight_budget"}}}
    server.enqueue("POST /chat/completions", Reply(402, in_flight, headers={"Retry-After": "1"}))
    error = raises("rate_limited", lambda: OpenAICompatibleAdapter().complete(route, user_request(), 5))
    assert error.retry_after_s == 1.0

    before = server.count()
    unpinned = external_route("sem-upstream", server.base_url, state="candidate", extra={"aggregator": "openrouter"})
    error = raises("bad_request", lambda: OpenAICompatibleAdapter().complete(unpinned, user_request(), 5))
    assert error.detail_code == "upstream_not_pinned" and server.count() == before


def test_openai_probe_lists_models_without_inference(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    route = external_route("externa", server.base_url)
    server.enqueue("GET /models", Reply(200, {"data": []}), Reply(500, {"error": {}}))
    adapter = OpenAICompatibleAdapter()
    assert adapter.probe(route, 2) is True and adapter.probe(route, 2) is False
    assert server.requests("GET /models")[0].headers["authorization"] == "Bearer " + FAKE_SECRET
    assert server.count("POST /chat/completions") == 0


# ===========================================================================
# Anthropic
# ===========================================================================

def anthropic_route(server, **overrides):
    return external_route("anthropic-direta", server.base_url, provider="anthropic", **overrides)


def test_anthropic_request_format(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.enqueue(
        "POST /v1/messages",
        Reply(
            200,
            anthropic_message(
                text="Vou consultar.",
                tool_uses=[{"id": "toolu_1", "name": "finance__read", "input": {"query": "payables", "v": 2.5}}],
                stop_reason="tool_use",
                model="modelo-anthropic-efetivo",
                usage={
                    "input_tokens": 100,
                    "cache_creation_input_tokens": 30,
                    "cache_read_input_tokens": 20,
                    "output_tokens": 40,
                },
            ),
        ),
    )
    route = anthropic_route(server, extra={"min_max_tokens": 4000, "effort": "low"})
    request = user_request(
        messages=list(TOOL_CONVERSATION),
        tools=[READ_TOOL],
        response_schema=ANSWER_SCHEMA,
        max_output_tokens=500,
        images=[PNG],
    )

    result = AnthropicAdapter().complete(route, request, 5)

    recorded = server.requests("POST /v1/messages")[0]
    assert recorded.headers["x-api-key"] == FAKE_SECRET
    assert recorded.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in recorded.headers
    sent = recorded.json
    assert sent["model"] == "modelo-externo-teste"
    assert sent["max_tokens"] == 4000  # piso da rota acima do pedido (500)
    assert sent["system"] == "Você é um operador financeiro."
    # Modelos atuais recusam parâmetros de amostragem; por padrão não vão.
    assert "temperature" not in sent and "thinking" not in sent and "fallbacks" not in sent
    assert sent["tools"] == [
        {"name": "finance__read", "description": READ_TOOL.description, "input_schema": READ_TOOL.parameters}
    ]
    assert [message["role"] for message in sent["messages"]] == ["user", "assistant", "user"]
    first_user = sent["messages"][0]["content"]
    assert first_user[0]["type"] == "image" and first_user[0]["source"] == {
        "type": "base64", "media_type": "image/png", "data": base64.b64encode(PNG).decode("ascii"),
    }
    assert first_user[1] == {"type": "text", "text": "Quanto falta pagar?"}
    assert sent["messages"][1]["content"] == [
        {"type": "tool_use", "id": "call_1", "name": "finance__read", "input": {"query": "payables", "limite": 10.5}},
        {"type": "tool_use", "id": "call_2", "name": "finance__read", "input": {"query": "balance"}},
    ]
    # Os dois resultados de ferramenta vão na MESMA mensagem user.
    assert sent["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": '{"remaining": "300.00"}'},
        {"type": "tool_result", "tool_use_id": "call_2", "content": '{"balance": "50.00"}'},
    ]
    wire_schema = sent["output_config"]["format"]
    assert wire_schema["type"] == "json_schema"
    assert wire_schema["schema"]["properties"]["confianca"] == {"type": "integer"}
    assert wire_schema["schema"]["properties"]["categoria"] == {"type": "string"}
    assert wire_schema["schema"]["additionalProperties"] is False
    assert sent["output_config"]["effort"] == "low"

    assert result.content == "Vou consultar." and result.finish_reason == "tool_calls"
    assert result.tool_calls == [
        ToolCall(id="toolu_1", name="finance.read", arguments={"query": "payables", "v": Decimal("2.5")})
    ]
    assert result.model_id == "modelo-anthropic-efetivo"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (150, 40)
    assert result.cost_micros is None


def test_anthropic_output_schema_is_adapted_only_on_the_wire():
    schema = {
        "type": "object",
        "properties": {
            "itens": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "object", "properties": {"n": {"type": "number", "minimum": 0}}},
            },
            "obs": {"type": "string", "maxLength": 10},
            "um": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
        "required": ["itens"],
    }
    wire = output_schema_for_wire(schema)
    assert wire["additionalProperties"] is False
    assert wire["properties"]["itens"] == {
        "type": "array",
        "items": {"type": "object", "properties": {"n": {"type": "number"}}, "additionalProperties": False},
    }
    assert wire["properties"]["obs"] == {"type": "string"}
    assert wire["properties"]["um"]["minItems"] == 1
    # O schema original não é alterado: é com ele que o gateway valida.
    assert schema["properties"]["itens"]["minItems"] == 2 and "additionalProperties" not in schema


def test_anthropic_stop_reasons_and_optional_temperature(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    adapter = AnthropicAdapter()
    route = anthropic_route(server, extra={"send_temperature": True, "anthropic_version": "2099-01-01"})

    server.enqueue("POST /v1/messages", Reply(200, anthropic_message("recusado " + BODY_MARKER, stop_reason="refusal")))
    assert raises("refusal", lambda: adapter.complete(route, user_request(), 5)).status == 200

    server.enqueue("POST /v1/messages", Reply(200, anthropic_message('{"categoria": "mor', stop_reason="max_tokens")))
    assert adapter.complete(route, user_request(), 5).finish_reason == "length"

    thinking = anthropic_message("resposta final")
    thinking["content"].insert(
        0, {"type": "thinking", "thinking": "raciocínio interno", "signature": "assinatura-sintetica"}
    )
    server.enqueue("POST /v1/messages", Reply(200, thinking))
    result = adapter.complete(route, user_request(), 5)
    # Raciocínio do modelo não vira conteúdo da resposta.
    assert result.content == "resposta final" and result.finish_reason == "stop"

    sent = server.requests("POST /v1/messages")
    assert sent[0].json["temperature"] == 0.0
    assert sent[0].headers["anthropic-version"] == "2099-01-01"
    assert "output_config" not in sent[0].json and "system" not in sent[0].json

    server.enqueue("POST /v1/messages", Reply(200, {"type": "message", "content": "texto solto"}))
    raises("server_error", lambda: adapter.complete(route, user_request(), 5))


def anthropic_error(error_type, message=BODY_MARKER, **extra):
    """Envelope de erro da Anthropic com o marcador sintético no texto."""
    return {"type": "error", "error": dict(type=error_type, message=message, **extra)}


SPEND_LIMIT_400 = "You have reached your specified API usage limits. " + BODY_MARKER
SPEND_LIMIT_429 = {"error_code": "enforced_spend_limit_reached"}


@pytest.mark.parametrize(
    "status, headers, body, kind, detail, retry_after",
    [
        (529, {}, anthropic_error("overloaded_error"), "server_error", "overloaded", None),
        (500, {}, anthropic_error("api_error"), "server_error", None, None),
        (504, {}, anthropic_error("timeout_error"), "timeout", None, None),
        (429, {"retry-after": "12"}, anthropic_error("rate_limit_error"), "rate_limited", None, 12.0),
        (429, {}, anthropic_error("rate_limit_error", details=SPEND_LIMIT_429), "auth", "spend_limit", None),
        (401, {}, anthropic_error("authentication_error"), "auth", None, None),
        (402, {}, anthropic_error("billing_error"), "auth", None, None),
        (403, {}, anthropic_error("permission_error"), "auth", None, None),
        (400, {}, anthropic_error("invalid_request_error"), "bad_request", None, None),
        (400, {}, anthropic_error("invalid_request_error", SPEND_LIMIT_400), "auth", "spend_limit", None),
        (404, {}, anthropic_error("not_found_error"), "unavailable", "model_not_found", None),
        (413, {}, anthropic_error("request_too_large"), "bad_request", "request_too_large", None),
    ],
)
def test_anthropic_error_mapping(providers, monkeypatch, status, headers, body, kind, detail, retry_after):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.always("POST /v1/messages", Reply(status, body, headers=headers))
    error = raises(kind, lambda: AnthropicAdapter().complete(anthropic_route(server), user_request(), 5))
    assert error.status == status and error.detail_code == detail and error.retry_after_s == retry_after
    assert server.count("POST /v1/messages") == 1
    assert FAKE_SECRET not in "%s %r" % (error, error.__dict__)


def test_anthropic_missing_credential_and_probe(providers, monkeypatch):
    server = providers()
    route = anthropic_route(server)
    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)
    error = raises("auth", lambda: AnthropicAdapter().complete(route, user_request(), 5))
    assert error.detail_code == "credential_missing" and server.count() == 0
    assert AnthropicAdapter().probe(route, 2) is False and server.count() == 0

    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server.enqueue("GET /v1/models", Reply(200, {"data": []}))
    assert AnthropicAdapter().probe(route, 2) is True
    assert server.requests("GET /v1/models")[0].headers["x-api-key"] == FAKE_SECRET
    assert server.count("POST /v1/messages") == 0


# ===========================================================================
# Helpers comuns
# ===========================================================================

def test_retry_after_parsing():
    assert parse_retry_after({"retry-after": "5"}) == 5.0
    assert parse_retry_after({"retry-after": "0.5"}) == 0.5
    assert parse_retry_after({"retry-after-ms": "1500"}) == 1.5
    assert parse_retry_after({}) is None and parse_retry_after({"retry-after": "em breve"}) is None
    assert parse_retry_after({"retry-after": "-3"}) == 0.0
    # Valor absurdo é limitado: ninguém espera um dia inteiro.
    assert parse_retry_after({"retry-after": "86400"}) == 3600.0
    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    header = format_datetime(now + timedelta(seconds=30), usegmt=True)
    assert parse_retry_after({"retry-after": header}, now=now) == 30.0


def test_tool_name_codec_round_trip_and_collision():
    codec = ToolNameCodec([READ_TOOL, ToolSpec("imports.preview", "x", {})])
    assert codec.encode("finance.read") == "finance__read" and codec.decode("finance__read") == "finance.read"
    # Nome que o modelo inventou volta como veio (e o registro de ferramentas o rejeita).
    assert codec.decode("shell__exec") == "shell__exec"
    with pytest.raises(ProviderError) as excinfo:
        ToolNameCodec([ToolSpec("a.b", "x", {}), ToolSpec("a__b", "y", {})])
    assert excinfo.value.detail_code == "tool_name_collision"


# ===========================================================================
# Transporte: até onde o pedido foi, prazo total e teto de tamanho
# ===========================================================================

def test_transport_failure_tells_how_far_the_request_went(providers):
    adapter = OllamaAdapter()
    server = providers()
    route = local_route("local", server.base_url)

    # O servidor lê o pedido e fecha sem responder: o pedido FOI enviado.
    server.enqueue("POST /api/chat", Reply(drop=True))
    error = raises("network", lambda: adapter.complete(route, user_request(), 5))
    assert (error.status, error.detail_code) == (None, "connection_lost")

    # A conexão cai no meio do corpo: o status 200 já tinha chegado.
    server.enqueue("POST /api/chat", Reply(200, ollama_chat("x" * 500), truncate_at=40))
    error = raises("network", lambda: adapter.complete(route, user_request(), 5))
    assert (error.status, error.detail_code) == (200, "connection_lost")
    assert server.count("POST /api/chat") == 2

    # URL que nem pode ser montada: defeito de configuração, não queda de rede
    # (não pode contar no disjuntor nem virar "tente a próxima rota").
    broken = local_route("local", "http://")
    error = raises("bad_request", lambda: adapter.complete(broken, user_request(), 5))
    assert (error.status, error.detail_code) == (None, "request_invalid")


def test_body_that_stalls_midway_is_a_timeout_with_the_status_already_known(providers):
    server = providers()
    payload = json.dumps(ollama_chat("resposta que para no meio"))
    # Envia o começo do corpo e fica 8 s sem mandar mais nada (prazo: 1 s).
    server.always("POST /api/chat", Reply(200, payload, drip_s=8, drip_bytes=20))
    route = local_route("local", server.base_url)
    error = raises("timeout", lambda: OllamaAdapter().complete(route, user_request(), 1.0))
    # Timeout (não "rede"), e com o status: a resposta já tinha começado.
    assert (error.status, error.detail_code) == (200, "read_timeout")
    assert server.settled_count("POST /api/chat") == 1


def test_header_that_cannot_be_encoded_is_a_local_defect_not_a_crash(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.always("POST /v1/messages", Reply(200, anthropic_message("ok")))
    # Versão colada de um documento, com travessões tipográficos: o http.client
    # recusa o cabeçalho com UnicodeEncodeError, que não é exceção do requests.
    route = anthropic_route(server, extra={"anthropic_version": "2023–06–01"})
    error = raises("bad_request", lambda: AnthropicAdapter().complete(route, user_request(), 5))
    assert (error.status, error.detail_code) == (None, "request_invalid")
    assert server.count() == 0


def test_body_read_has_a_total_deadline_against_a_dripping_server(providers):
    server = providers()
    payload = json.dumps(ollama_chat("resposta que nunca termina de chegar"))
    # ~40 pedaços, um a cada 0,15 s: o corpo inteiro levaria uns 6 s. Cada
    # leitura de socket recebe bytes bem antes do timeout de leitura (1 s), de
    # modo que só um prazo TOTAL consegue encerrar a chamada.
    server.always("POST /api/chat", Reply(200, payload, drip_s=0.15, drip_bytes=len(payload) // 40 + 1))
    route = local_route("local", server.base_url)

    started = time.monotonic()
    error = raises("timeout", lambda: OllamaAdapter().complete(route, user_request(), 1.0))
    elapsed = time.monotonic() - started

    assert (error.status, error.detail_code) == (200, "deadline_exceeded")
    # Encerrou perto do prazo de 1 s, não ao fim dos ~6 s de gotejamento.
    assert elapsed < 4.0, "o prazo total não interrompeu a leitura (%.1f s)" % elapsed


def test_response_larger_than_the_cap_is_refused(providers):
    server = providers()
    filler = "x" * (MAX_RESPONSE_BYTES + 1024)
    # JSON válido, só que grande demais: sem o teto ele seria lido e aceito.
    server.always("POST /api/chat", Reply(200, json.dumps(ollama_chat(filler))))
    route = local_route("local", server.base_url)
    error = raises("server_error", lambda: OllamaAdapter().complete(route, user_request(), 30))
    assert (error.status, error.detail_code) == (200, "response_too_large")
    # Controle: logo abaixo do teto a mesma resposta é aceita.
    server.always("POST /api/chat", Reply(200, json.dumps(ollama_chat("x" * (MAX_RESPONSE_BYTES - 4096)))))
    assert len(OllamaAdapter().complete(route, user_request(), 30).content) == MAX_RESPONSE_BYTES - 4096


def test_compressed_body_is_decoded_and_the_cap_counts_decoded_bytes(providers):
    server = providers()
    route = local_route("local", server.base_url)
    gzip_headers = {"Content-Encoding": "gzip"}

    # Provedores reais comprimem a resposta (o requests anuncia que aceita gzip).
    small = gzip.compress(json.dumps(ollama_chat("resposta comprimida")).encode("utf-8"))
    server.enqueue("POST /api/chat", Reply(200, small, headers=gzip_headers))
    assert OllamaAdapter().complete(route, user_request(), 5).content == "resposta comprimida"

    # Poucos KiB no fio, mais de 8 MiB depois de descomprimir: o teto vale para
    # o que vai para a memória, não para o que trafegou.
    bomb = gzip.compress(json.dumps(ollama_chat("x" * (MAX_RESPONSE_BYTES + 1024))).encode("utf-8"))
    assert len(bomb) < 64 * 1024
    server.enqueue("POST /api/chat", Reply(200, bomb, headers=gzip_headers))
    error = raises("server_error", lambda: OllamaAdapter().complete(route, user_request(), 30))
    assert (error.status, error.detail_code) == (200, "response_too_large")

    # Corpo que diz ser gzip e não é: resposta estragada depois do status 200.
    server.enqueue("POST /api/chat", Reply(200, b"isto nao e gzip", headers=gzip_headers))
    error = raises("server_error", lambda: OllamaAdapter().complete(route, user_request(), 5))
    assert (error.status, error.detail_code) == (200, "malformed_response")


MALFORMED_CREDENTIALS = [
    "credencial-ficticia-colada-com-reticencias…",
    "credencial ficticia com espaco",
    "credencial-ficticia\ncom-quebra-de-linha",
    "credencial-ficticia-com-acento-ç",
]


@pytest.mark.parametrize("value", MALFORMED_CREDENTIALS)
def test_malformed_credential_is_refused_before_any_request(providers, monkeypatch, value):
    monkeypatch.setenv(CREDENTIAL_ENV, value)
    server = providers()
    server.always("POST /chat/completions", Reply(200, openai_chat("ok")))
    server.always("POST /v1/messages", Reply(200, anthropic_message("ok")))
    cases = [
        (OpenAICompatibleAdapter(), external_route("externa", server.base_url)),
        (AnthropicAdapter(), anthropic_route(server)),
    ]
    for adapter, route in cases:
        error = raises("auth", lambda: adapter.complete(route, user_request(), 5))
        # Sem status: nenhuma requisição saiu. O gateway suspende a credencial.
        assert (error.status, error.detail_code) == (None, "credential_malformed")
        assert value not in "%s %r %r" % (error, error.args, error.__dict__)
        assert adapter.probe(route, 2) is False
    assert server.count() == 0


def test_credential_with_surrounding_whitespace_is_still_usable(providers, monkeypatch):
    # Espaço e quebra de linha nas PONTAS (comum em arquivo .env) são aparados.
    monkeypatch.setenv(CREDENTIAL_ENV, "  " + FAKE_SECRET + "\n")
    server = providers()
    server.always("POST /chat/completions", Reply(200, openai_chat("ok")))
    OpenAICompatibleAdapter().complete(external_route("externa", server.base_url), user_request(), 5)
    assert server.requests("POST /chat/completions")[0].headers["authorization"] == "Bearer " + FAKE_SECRET


# ===========================================================================
# Chamada de ferramenta cortada pelo limite de tokens
# ===========================================================================

def test_truncated_tool_call_is_reported_as_length_by_every_adapter(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    request = user_request(tools=[READ_TOOL])

    server.enqueue("POST /api/chat", Reply(200, ollama_chat(tool_calls=[OLLAMA_TOOL_CALL], done_reason="length")))
    result = OllamaAdapter().complete(local_route("local", server.base_url), request, 5)
    assert result.finish_reason == "length" and len(result.tool_calls) == 1

    cut_call = [{"id": "call_1", "type": "function", "function": {"name": "finance__read", "arguments": "{}"}}]
    server.enqueue(
        "POST /chat/completions", Reply(200, openai_chat(None, tool_calls=cut_call, finish_reason="length"))
    )
    result = OpenAICompatibleAdapter().complete(external_route("externa", server.base_url), request, 5)
    # "length" tem precedência: o corte não pode ficar escondido atrás de "tool_calls".
    assert result.finish_reason == "length" and len(result.tool_calls) == 1

    cut_use = [{"id": "toolu_1", "name": "finance__read", "input": {}}]
    server.enqueue("POST /v1/messages", Reply(200, anthropic_message(tool_uses=cut_use, stop_reason="max_tokens")))
    result = AnthropicAdapter().complete(anthropic_route(server), request, 5)
    assert result.finish_reason == "length" and len(result.tool_calls) == 1


# ===========================================================================
# OpenRouter: quem atendeu precisa ser quem foi autorizado
# ===========================================================================

def openrouter_route(server, **extra):
    return external_route(
        "via-openrouter", server.base_url, upstream_provider="fornecedor-teste",
        extra=dict({"aggregator": "openrouter"}, **extra),
    )


OUTSIDE_THE_PIN = {
    # Fornecedor efetivo nos metadados de roteamento.
    "provider-metadata": openai_chat(
        "ok", openrouter_metadata={"attempts": [{"provider": "Fornecedor-Nao-Autorizado", "status": 200}]}
    ),
    # Fornecedor efetivo no campo de topo.
    "provider-field": openai_chat("ok", provider="Outro Fornecedor"),
    # Fornecedor certo, modelo diferente do homologado.
    "model": openai_chat("ok", provider="fornecedor-teste", model="outro/modelo-nao-homologado"),
}


@pytest.mark.parametrize("case", sorted(OUTSIDE_THE_PIN))
def test_openrouter_answer_from_outside_the_pin_is_rejected(providers, monkeypatch, case):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    server.enqueue("POST /chat/completions", Reply(200, OUTSIDE_THE_PIN[case]))
    adapter = OpenAICompatibleAdapter()
    error = raises("unavailable", lambda: adapter.complete(openrouter_route(server), user_request(), 5))
    # status 200: o agregador processou (e vai cobrar); a resposta é descartada.
    assert (error.status, error.detail_code) == (200, "upstream_mismatch")
    assert error.upstream_attempts == 1


def test_openrouter_pin_check_accepts_what_was_authorized(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    adapter = OpenAICompatibleAdapter()

    # Mesma empresa, grafia diferente: não é violação.
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("ok", provider="Fornecedor Teste")))
    result = adapter.complete(openrouter_route(server), user_request(), 5)
    assert result.effective_provider == "Fornecedor Teste" and result.metrics["upstream_confirmed"] is True

    # Nome canônico devolvido pelo agregador, listado na homologação.
    canonical = openai_chat("ok", provider="fornecedor-teste", model="outro/modelo-canonico")
    server.enqueue("POST /chat/completions", Reply(200, canonical))
    listed = openrouter_route(server, accepted_model_ids=["outro/modelo-canonico"])
    assert adapter.complete(listed, user_request(), 5).model_id == "outro/modelo-canonico"

    # Sem informação de fornecedor não há o que comparar: vale o que foi PEDIDO,
    # e fica registrado que não houve confirmação.
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("ok")))
    result = adapter.complete(openrouter_route(server), user_request(), 5)
    assert result.effective_provider == "fornecedor-teste" and result.metrics["upstream_confirmed"] is False

    # Rota direta (sem agregador): o provedor É o autorizado; o nome efetivo do
    # modelo (ex.: versão datada de um alias) é só registrado.
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("ok", model="modelo-externo-teste-2026-10-01")))
    direct = adapter.complete(external_route("externa", server.base_url), user_request(), 5)
    assert direct.model_id == "modelo-externo-teste-2026-10-01" and direct.effective_provider is None


# ===========================================================================
# Rótulos devolvidos pelo provedor
# ===========================================================================

def test_provider_controlled_labels_are_filtered(providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    server = providers()
    dirty = "linha1\nlinha-forjada " + "x" * 5000

    server.enqueue("POST /api/chat", Reply(200, ollama_chat("ok", model=dirty)))
    assert OllamaAdapter().complete(local_route("local", server.base_url), user_request(), 5).model_id == LOCAL_MODEL

    route = external_route("externa", server.base_url)
    # A credencial ecoada tem cara de identificador válido: só a comparação
    # com o próprio valor consegue barrá-la.
    for echoed in (dirty, FAKE_SECRET, "prefixo/" + FAKE_SECRET + ":sufixo", 12345, None):
        server.enqueue("POST /chat/completions", Reply(200, openai_chat("ok", model=echoed)))
        assert OpenAICompatibleAdapter().complete(route, user_request(), 5).model_id == "modelo-externo-teste"
        server.enqueue("POST /v1/messages", Reply(200, anthropic_message("ok", model=echoed)))
        result = AnthropicAdapter().complete(anthropic_route(server), user_request(), 5)
        assert result.model_id == "modelo-externo-teste"

    # Fornecedor efetivo: é o fixado (passa na conferência), mas veio com quebra
    # de linha. O texto do provedor é descartado e fica o nome do REGISTRO.
    server.enqueue("POST /chat/completions", Reply(200, openai_chat("ok", provider="fornecedor\nteste")))
    result = OpenAICompatibleAdapter().complete(openrouter_route(server), user_request(), 5)
    assert result.effective_provider == "fornecedor-teste"


def test_safe_label_rules():
    assert safe_label("fornecedor/modelo-1.5:8b@v2") == "fornecedor/modelo-1.5:8b@v2"
    assert safe_label("  modelo-teste  ") == "modelo-teste"
    assert safe_label("Fornecedor Dois", allow_spaces=True) == "Fornecedor Dois"
    assert safe_label("Fornecedor Dois") is None  # espaço só onde é esperado
    for bad in ("", "a\nb", "a\tb", "a  b", "x" * 129, "modelo;drop", "modeloç", None, 7, ["m"]):
        assert safe_label(bad, allow_spaces=True) is None, bad
    assert safe_label("a\nb", "reserva") == "reserva"
    assert safe_label("chave-abc", "reserva", forbidden=("chave-abc",)) == "reserva"
    assert safe_label("x-chave-abc-y", forbidden=("", "chave-abc")) is None
