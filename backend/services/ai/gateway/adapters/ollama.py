"""Adaptador do Ollama (modelos locais) pela API nativa ``/api/chat``.

Por que a API nativa e não a camada compatível com OpenAI (``/v1``): só a
nativa aceita ``format`` com JSON Schema, ``num_ctx`` por requisição e devolve
as métricas de tempo em nanossegundos (``load_duration`` mostra o custo de
carregar o modelo a frio), que a homologação precisa registrar.

Pontos que parecem detalhe e não são:

* ``stream: false`` - uma resposta, um JSON. Em streaming um erro chega como
  linha de dados com HTTP 200.
* ``tools`` e ``format`` nunca vão juntos. No Ollama o ``format`` prevalece e
  as ferramentas são ignoradas (issue 13750 do projeto). Com ferramentas no
  pedido, o schema fica só na validação do gateway.
* ``seed`` fixo e ``num_ctx`` explícito por rota. Mudar ``num_ctx`` entre
  pedidos faz o Ollama recarregar o modelo; o padrão do servidor (4k) é
  pequeno para ferramentas.
* ``arguments`` de ferramenta chega como OBJETO (na OpenAI é string).
* A sonda confere mais que "o servidor respondeu": o modelo precisa existir,
  ter o digest registrado e NÃO ser remoto. Um modelo com ``remote_host`` é
  repassado pelo Ollama para a nuvem; conversar com ``localhost`` não garante
  execução local.

O Ollama não cobra por chamada: ``cost_micros`` é sempre zero.

Validado contra servidor local de teste que emula a API; a conferência com um
Ollama real (e com cada modelo candidato) é parte da homologação.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from ..base import (
    AdapterResult,
    ChatMessage,
    ModelRequest,
    ModelRoute,
    ProviderAdapter,
    ProviderError,
    ToolCall,
    Usage,
)
from ..models import looks_like_remote_model
from ..validation import loads_no_float, safe_label
from . import as_int, b64, dig, http_request, status_error


logger = logging.getLogger("ai.gateway.ollama")

DEFAULT_SEED = 7
# Marca "não consegui ler os argumentos" sem usar exceção para o controle de fluxo.
_UNPARSEABLE = object()
_METRIC_KEYS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)

# Resultado de ``inspect``: por que a rota não está pronta.
PROBE_OK = "ok"
PROBE_UNREACHABLE = "unreachable"
PROBE_MODEL_MISSING = "model_missing"
PROBE_DIGEST_MISMATCH = "digest_mismatch"
PROBE_REMOTE_MODEL = "remote_model"


def _normalize_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text[7:] if text.startswith("sha256:") else text


class OllamaAdapter(ProviderAdapter):
    provider = "ollama"

    def __init__(self, default_base_url: Optional[str] = None) -> None:
        self._default_base_url = (default_base_url or "").rstrip("/") or None

    def _base_url(self, route: ModelRoute) -> str:
        base = (route.base_url or self._default_base_url or "").rstrip("/")
        if not base:
            raise ProviderError("bad_request", detail_code="base_url_missing")
        return base

    # -- montagem do pedido --------------------------------------------------

    @staticmethod
    def _message(message: ChatMessage) -> Dict[str, Any]:
        if message.role == "tool":
            item: Dict[str, Any] = {"role": "tool", "content": message.content or ""}
            if message.tool_name:
                item["tool_name"] = message.tool_name
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            return item
        item = {"role": message.role, "content": message.content or ""}
        if message.role == "assistant" and message.tool_calls:
            item["tool_calls"] = [
                {"type": "function", "function": {"name": call.name, "arguments": dict(call.arguments)}}
                for call in message.tool_calls
            ]
        return item

    def build_payload(self, route: ModelRoute, request: ModelRequest) -> Dict[str, Any]:
        """Corpo de ``POST /api/chat``. Público para a homologação inspecionar."""
        messages = [self._message(message) for message in request.messages]
        if request.images:
            # Imagens acompanham a última mensagem do usuário.
            for item in reversed(messages):
                if item["role"] == "user":
                    item["images"] = [b64(image) for image in request.images]
                    break
            else:
                raise ProviderError("bad_request", detail_code="image_without_user_message")

        seed = route.extra.get("seed", DEFAULT_SEED)
        options: Dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": int(request.max_output_tokens),
            "seed": seed if isinstance(seed, int) and not isinstance(seed, bool) else DEFAULT_SEED,
        }
        num_ctx = route.extra.get("num_ctx")
        if isinstance(num_ctx, int) and not isinstance(num_ctx, bool) and num_ctx > 0:
            options["num_ctx"] = num_ctx

        payload: Dict[str, Any] = {
            "model": route.model_id,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        elif request.response_schema is not None:
            payload["format"] = request.response_schema
        if route.extra.get("think") is False:
            # Modelos "thinking" gastam tokens raciocinando e pioram a saída
            # estruturada; a rota desliga explicitamente quando homologada assim.
            payload["think"] = False
        keep_alive = route.extra.get("keep_alive")
        if isinstance(keep_alive, (str, int)) and not isinstance(keep_alive, bool):
            payload["keep_alive"] = keep_alive
        return payload

    # -- chamada -------------------------------------------------------------

    def complete(self, route: ModelRoute, request: ModelRequest, timeout_s: float) -> AdapterResult:
        if looks_like_remote_model(route.model_id):
            # Segunda trava (a primeira é o registro): modelo remoto atrás de um
            # Ollama local é tráfego externo. Nenhuma requisição é feita.
            raise ProviderError("bad_request", detail_code="remote_model_blocked")
        payload = self.build_payload(route, request)
        reply = http_request("POST", self._base_url(route) + "/api/chat", payload=payload, timeout_s=timeout_s)
        if reply.status != 200:
            raise self._error(reply.status, reply)
        body = reply.json()
        if not isinstance(body, dict) or not isinstance(body.get("message"), dict):
            raise ProviderError("server_error", status=200, detail_code="malformed_response")
        if body.get("error"):
            raise ProviderError("server_error", status=200, detail_code="error_in_body")
        if body.get("done") is False:
            # Com stream=false a resposta precisa vir completa.
            raise ProviderError("invalid_output", status=200, detail_code="incomplete_response")

        message = body["message"]
        tool_calls = self._tool_calls(message.get("tool_calls"))
        content = message.get("content")
        if body.get("done_reason") == "length":
            # Precedência sobre "tool_calls": chamada de ferramenta cortada pelo
            # limite de tokens não é chamada válida, e o gateway precisa saber.
            finish_reason = "length"
        elif tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"
        metrics = {key: as_int(body.get(key)) for key in _METRIC_KEYS if as_int(body.get(key)) is not None}
        return AdapterResult(
            content=content if isinstance(content, str) else "",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model_id=safe_label(body.get("model"), route.model_id),
            effective_provider=None,
            usage=Usage(
                input_tokens=as_int(body.get("prompt_eval_count")),
                output_tokens=as_int(body.get("eval_count")),
            ),
            cost_micros=0,
            latency_ms=reply.latency_ms,
            upstream_attempts=1,
            metrics=metrics,
        )

    @staticmethod
    def _tool_calls(raw: Any) -> List[ToolCall]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
        calls: List[ToolCall] = []
        for item in raw:
            function = dig(item, "function")
            name = dig(function, "name")
            arguments = dig(function, "arguments")
            if isinstance(arguments, str):
                # Alguns modelos devolvem os argumentos como texto JSON.
                try:
                    arguments = loads_no_float(arguments)
                except (ValueError, RecursionError):
                    # Levantado fora do ``except``: a exceção original guarda o
                    # texto recebido e ficaria pendurada em ``__context__``.
                    arguments = _UNPARSEABLE
                if arguments is _UNPARSEABLE:
                    raise ProviderError("invalid_output", status=200, detail_code="tool_arguments_invalid")
            if arguments is None:
                arguments = {}
            if not isinstance(name, str) or not name or not isinstance(arguments, dict):
                raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
            call_id = dig(item, "id")
            if not isinstance(call_id, str) or not call_id:
                # O Ollama nem sempre dá id; o gateway precisa de um para casar
                # chamada e resultado se a conversa migrar para outro provedor.
                call_id = "call_" + uuid.uuid4().hex[:24]
            calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
        return calls

    @staticmethod
    def _error(status: int, reply) -> ProviderError:
        if status == 404:
            # Modelo ausente. Nunca há "pull" automático em tempo de execução.
            return ProviderError("unavailable", status=404, detail_code="model_not_found")
        if status == 503:
            return ProviderError("unavailable", status=503, detail_code="server_busy")
        if status == 400:
            body = reply.json()
            text = dig(body, "error")
            # O texto do provedor serve só para classificar; não é propagado.
            if isinstance(text, str) and "does not support tools" in text:
                return ProviderError("bad_request", status=400, detail_code="tools_not_supported")
            return ProviderError("bad_request", status=400)
        if status == 403:
            # Ollama com OLLAMA_NO_CLOUD=1 recusa modelo remoto com 403. É
            # violação de política da rota, não credencial a suspender.
            return ProviderError("bad_request", status=403, detail_code="remote_model_blocked")
        return status_error(status, reply.headers)

    # -- sonda ---------------------------------------------------------------

    def inspect(self, route: ModelRoute, timeout_s: float) -> str:
        """Confere servidor, presença do modelo, digest e execução local."""
        try:
            reply = http_request("GET", self._base_url(route) + "/api/tags", timeout_s=timeout_s)
        except ProviderError:
            return PROBE_UNREACHABLE
        body = reply.json() if reply.status == 200 else None
        models = dig(body, "models")
        if not isinstance(models, list):
            return PROBE_UNREACHABLE
        entry = None
        for item in models:
            if isinstance(item, dict) and route.model_id in (item.get("name"), item.get("model")):
                entry = item
                break
        if entry is None:
            return PROBE_MODEL_MISSING
        if entry.get("remote_host") or entry.get("remote_model"):
            return PROBE_REMOTE_MODEL
        if route.digest and _normalize_digest(entry.get("digest")) != _normalize_digest(route.digest):
            # A tag foi reapontada (ou o modelo trocado) depois da homologação.
            return PROBE_DIGEST_MISMATCH
        return PROBE_OK

    def probe(self, route: ModelRoute, timeout_s: float) -> bool:
        outcome = self.inspect(route, timeout_s)
        if outcome != PROBE_OK:
            logger.warning("ollama_probe_failed alias=%s reason=%s", route.alias, outcome)
        return outcome == PROBE_OK
