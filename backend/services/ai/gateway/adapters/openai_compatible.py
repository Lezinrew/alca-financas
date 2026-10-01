"""Adaptador para APIs no formato OpenAI Chat Completions (direta ou OpenRouter).

ATENÇÃO: validado apenas contra servidor local de teste; não validado contra o
provedor real. Os formatos seguem a documentação oficial consultada em
01/10/2026, mas nenhuma chamada paga foi feita. Antes de aprovar uma rota,
rode a homologação contra o provedor e confira os pontos marcados "a
confirmar" abaixo.

O mesmo formato serve a três situações, distinguidas pelo registro de modelos:

* API direta de um fornecedor (``locality: external``);
* servidor local compatível, como vLLM ou llama.cpp (``locality: local``,
  ``credential_env`` opcional);
* OpenRouter, um agregador (``extra.aggregator == "openrouter"``).

Sobre o OpenRouter: ele sabe trocar de fornecedor e de modelo sozinho. Aqui
isso é DESLIGADO de propósito, porque (a) o gateway é o único dono do orçamento
de tentativas e (b) cada fornecedor efetivo precisa estar na lista autorizada
pelo titular (contrato, seção 11). Por isso o pedido leva
``provider.order=[upstream]`` com ``allow_fallbacks=false``, nunca leva
``models`` e pede os metadados de roteamento para conferir quem atendeu e
quantas tentativas o agregador fez por conta própria.

Pedir não basta: a resposta é CONFERIDA. Se o fornecedor efetivo ou o modelo
devolvido não forem os fixados na rota, a resposta é descartada e o adaptador
levanta ``ProviderError("unavailable", detail_code="upstream_mismatch")``; o
gateway suspende a rota até o operador reativá-la. Um aviso em log não
impediria as chamadas seguintes de continuarem indo para o fornecedor errado.

A credencial é lida do ambiente NO MOMENTO da chamada e vive só em uma variável
local de ``complete``. Não fica em atributo do adaptador, em exceção nem em
log; se o provedor a ecoar em ``model``/``provider``, o rótulo é descartado.

A confirmar na homologação: aninhamento de ``response_format.json_schema``;
nome do parâmetro de limite de saída (``max_tokens`` ou
``max_completion_tokens``, configurável em ``extra.max_tokens_param``); formato
de ``openrouter_metadata``; se o 403 do OpenRouter por moderação deve ser
tratado como recusa em vez de falha de credencial.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

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
from ..validation import loads_no_float, safe_label
from . import (
    DETAIL_CREDENTIAL_MISSING,
    DETAIL_UPSTREAM_MISMATCH,
    HttpReply,
    ToolNameCodec,
    as_int,
    b64,
    credential_from_env,
    detect_image_mime,
    dig,
    encode_json,
    http_request,
    parse_retry_after,
    status_error,
)


logger = logging.getLogger("ai.gateway.openai_compatible")

OPENROUTER = "openrouter"
MICROS = 1_000_000
# Marca "não consegui ler os argumentos" sem usar exceção para o controle de fluxo.
_UNPARSEABLE = object()

# 429 que NÃO é limite de taxa: a conta ficou sem crédito ou bateu o teto de
# gasto. Esperar e repetir não resolve; é tratado como falha de credencial.
_QUOTA_CODES = frozenset(
    {
        "insufficient_quota",
        "credit_balance_exhausted",
        "billing_hard_limit_reached",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }
)
_SLUG = re.compile(r"[^a-z0-9]")


def _slug(value: Any) -> str:
    """Normaliza nome de fornecedor para comparação ("DeepInfra/turbo" -> "deepinfra")."""
    return _SLUG.sub("", str(value or "").split("/")[0].strip().lower())


def _strict_compatible(schema: Any) -> bool:
    """O schema atende às exigências do modo estrito da OpenAI?

    Modo estrito exige, em todo objeto, ``additionalProperties: false`` e todas
    as propriedades em ``required``. Enviar ``strict: true`` com um schema fora
    disso devolve 400; nesse caso o pedido vai sem modo estrito e a validação
    do gateway continua valendo.
    """
    if not isinstance(schema, dict):
        return True
    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is not False:
            return False
        if set(schema.get("required") or []) != set(properties):
            return False
        if not all(_strict_compatible(child) for child in properties.values()):
            return False
    items = schema.get("items")
    if isinstance(items, dict) and not _strict_compatible(items):
        return False
    return True


class OpenAICompatibleAdapter(ProviderAdapter):
    """Uma tentativa em ``POST {base_url}/chat/completions``.

    Validado apenas contra servidor local de teste; não validado contra o
    provedor real.
    """

    provider = "openai_compatible"

    # -- credencial ----------------------------------------------------------

    @staticmethod
    def _secret(route: ModelRoute) -> Optional[str]:
        """Credencial da rota, lida agora. ``None`` só em rota local sem chave."""
        if route.credential_env:
            return credential_from_env(route.credential_env)
        if not route.is_local:
            # Rota externa sem credencial configurada não é tentada "sem chave".
            raise ProviderError("auth", detail_code=DETAIL_CREDENTIAL_MISSING)
        return None

    @staticmethod
    def _headers(route: ModelRoute, secret: Optional[str]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if secret:
            headers["Authorization"] = "Bearer " + secret
        if route.extra.get("aggregator") == OPENROUTER:
            headers["X-OpenRouter-Metadata"] = "enabled"
        return headers

    @staticmethod
    def _base_url(route: ModelRoute) -> str:
        base = (route.base_url or "").rstrip("/")
        if not base:
            raise ProviderError("bad_request", detail_code="base_url_missing")
        return base

    # -- montagem do pedido --------------------------------------------------

    @staticmethod
    def _message(message: ChatMessage, codec: ToolNameCodec) -> Dict[str, Any]:
        if message.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id or "",
                "content": message.content or "",
            }
        if message.role == "assistant" and message.tool_calls:
            return {
                "role": "assistant",
                "content": message.content or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": codec.encode(call.name),
                            # Na OpenAI os argumentos viajam como TEXTO JSON.
                            "arguments": _dump_arguments(call.arguments),
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        return {"role": message.role, "content": message.content or ""}

    def build_payload(self, route: ModelRoute, request: ModelRequest) -> Dict[str, Any]:
        """Corpo de ``POST /chat/completions``. Público para a homologação inspecionar."""
        codec = ToolNameCodec(request.tools)
        messages = [self._message(message, codec) for message in request.messages]
        if request.images:
            for item in reversed(messages):
                if item["role"] == "user":
                    parts: List[Dict[str, Any]] = [{"type": "text", "text": item["content"]}]
                    for image in request.images:
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:%s;base64,%s" % (detect_image_mime(image), b64(image))},
                            }
                        )
                    item["content"] = parts
                    break
            else:
                raise ProviderError("bad_request", detail_code="image_without_user_message")

        payload: Dict[str, Any] = {"model": route.model_id, "messages": messages, "stream": False}
        limit_param = route.extra.get("max_tokens_param")
        if limit_param not in ("max_tokens", "max_completion_tokens"):
            limit_param = "max_tokens"
        payload[limit_param] = int(request.max_output_tokens)
        if route.extra.get("send_temperature", True) is not False:
            payload["temperature"] = request.temperature
        seed = route.extra.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            payload["seed"] = seed

        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": codec.encode(tool.name),
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        if request.response_schema is not None:
            strict = route.extra.get("json_schema_strict")
            if not isinstance(strict, bool):
                strict = _strict_compatible(request.response_schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "resposta", "strict": strict, "schema": request.response_schema},
            }

        if route.extra.get("aggregator") == OPENROUTER:
            if not route.upstream_provider:
                # Sem fornecedor fixado o agregador escolheria um qualquer, fora
                # da lista autorizada. Nenhuma requisição é feita.
                raise ProviderError("bad_request", detail_code="upstream_not_pinned")
            provider: Dict[str, Any] = {
                "order": [route.upstream_provider],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
            }
            if route.extra.get("zdr") is True:
                provider["zdr"] = True
            payload["provider"] = provider
            # "models" (fallback entre modelos) nunca é enviado.
        return payload

    # -- chamada -------------------------------------------------------------

    def complete(self, route: ModelRoute, request: ModelRequest, timeout_s: float) -> AdapterResult:
        # ``secret`` vive só nesta chamada: monta o cabeçalho e serve de filtro
        # para os rótulos devolvidos pelo provedor (ver ``safe_label``).
        secret = self._secret(route)
        payload = self.build_payload(route, request)
        reply = http_request(
            "POST",
            self._base_url(route) + "/chat/completions",
            headers=self._headers(route, secret),
            payload=payload,
            timeout_s=timeout_s,
        )
        body = reply.json()
        is_openrouter = route.extra.get("aggregator") == OPENROUTER
        effective_provider, upstream_attempts = (
            self._routing_metadata(body) if is_openrouter else (None, 1)
        )
        if reply.status != 200:
            raise _with_attempts(self._error(reply, body), upstream_attempts)

        choice = dig(body, "choices", 0)
        message = dig(choice, "message")
        if not isinstance(body, dict) or not isinstance(message, dict):
            raise _with_attempts(
                ProviderError("server_error", status=200, detail_code="malformed_response"), upstream_attempts
            )
        if is_openrouter:
            violation = self._pin_violation(route, effective_provider, body.get("model"))
            if violation is not None:
                # Quem atendeu não é quem o titular autorizou (contrato, seção
                # 11). A resposta é DESCARTADA, mesmo que pareça boa: aceitá-la
                # seria deixar o agregador escolher o fornecedor. O gateway
                # suspende a rota e avisa o operador. ``status=200`` mantém a
                # reserva de custo: o agregador processou e vai cobrar.
                logger.warning(
                    "openrouter_upstream_mismatch alias=%s what=%s pinned=%s effective=%s",
                    route.alias, violation, _slug(route.upstream_provider)[:40], _slug(effective_provider)[:40],
                )
                raise _with_attempts(
                    ProviderError("unavailable", status=200, detail_code=DETAIL_UPSTREAM_MISMATCH), upstream_attempts
                )
        finish = choice.get("finish_reason")
        if message.get("refusal") or finish == "content_filter":
            # Recusa de conteúdo: o gateway NÃO troca de rota para contornar.
            raise _with_attempts(ProviderError("refusal", status=200), upstream_attempts)
        if finish == "error":
            raise _with_attempts(
                ProviderError("server_error", status=200, detail_code="upstream_error"), upstream_attempts
            )

        codec = ToolNameCodec(request.tools)
        try:
            tool_calls = self._tool_calls(message.get("tool_calls"), codec)
        except ProviderError as error:
            raise _with_attempts(error, upstream_attempts)
        content = message.get("content")
        if finish == "length":
            # "length" tem precedência sobre "tool_calls": uma chamada de
            # ferramenta cortada pelo limite de tokens tem argumentos pela
            # metade. O gateway precisa SABER do corte para não entregá-la ao
            # orquestrador como se fosse válida.
            finish_reason = "length"
        elif tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"

        forbidden = (secret,) if secret else ()
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        metrics: Dict[str, Any] = {}
        if is_openrouter:
            metrics["upstream_attempts"] = upstream_attempts
            # Falso quando o agregador não disse quem atendeu: o fornecedor
            # registrado abaixo é então o que foi PEDIDO, não o conferido.
            metrics["upstream_confirmed"] = bool(effective_provider)
        return AdapterResult(
            content=content if isinstance(content, str) else "",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model_id=safe_label(body.get("model"), route.model_id, forbidden=forbidden),
            effective_provider=safe_label(effective_provider, allow_spaces=True, forbidden=forbidden)
            or (route.upstream_provider if is_openrouter else None),
            usage=Usage(
                input_tokens=as_int(usage.get("prompt_tokens")),
                output_tokens=as_int(usage.get("completion_tokens")),
            ),
            cost_micros=self._cost_micros(usage),
            latency_ms=reply.latency_ms,
            upstream_attempts=upstream_attempts,
            metrics=metrics,
        )

    @staticmethod
    def _cost_micros(usage: Dict[str, Any]) -> Optional[int]:
        """``usage.cost`` (OpenRouter, em créditos = USD) convertido para micros."""
        cost = usage.get("cost")
        if isinstance(cost, bool) or not isinstance(cost, (int, Decimal)):
            return None
        if cost < 0:
            return None
        # Arredonda para cima: no orçamento, errar para mais é o lado seguro.
        micros = Decimal(cost) * MICROS
        whole = int(micros)
        return whole if micros == whole else whole + 1

    @staticmethod
    def _pin_violation(route: ModelRoute, effective_provider: Optional[str], returned_model: Any) -> Optional[str]:
        """``"provider"``/``"model"`` se a resposta veio de fora do que foi fixado.

        O pedido já proíbe a troca (``allow_fallbacks: false``, sem ``models``).
        Esta é a conferência do que o agregador de fato FEZ:

        * fornecedor: o nome devolvido precisa bater com ``upstream_provider``;
        * modelo: precisa ser o ``model_id`` da rota ou um dos nomes listados
          em ``extra.accepted_model_ids`` (para o caso de o agregador devolver
          um nome canônico diferente do pedido; preenche-se na homologação).

        Campo ausente não é violação: sem a informação não há o que comparar, e
        o que vale é a restrição enviada no pedido (``metrics`` registra que o
        fornecedor não foi confirmado).
        """
        if effective_provider and _slug(effective_provider) != _slug(route.upstream_provider):
            return "provider"
        if isinstance(returned_model, str) and returned_model.strip():
            accepted = [route.model_id] + [
                item for item in (route.extra.get("accepted_model_ids") or []) if isinstance(item, str)
            ]
            if returned_model.strip().lower() not in {item.strip().lower() for item in accepted}:
                return "model"
        return None

    @staticmethod
    def _routing_metadata(body: Any) -> Tuple[Optional[str], int]:
        """Fornecedor efetivo e nº de tentativas internas do agregador."""
        metadata = dig(body, "openrouter_metadata")
        attempts = dig(metadata, "attempts")
        count = 1
        provider: Optional[str] = None
        if isinstance(attempts, list) and attempts:
            count = len(attempts)
            winner = as_int(dig(metadata, "attempt"))
            index = winner - 1 if winner and 1 <= winner <= len(attempts) else len(attempts) - 1
            name = dig(attempts, index, "provider")
            provider = name if isinstance(name, str) and name else None
        else:
            winner = as_int(dig(metadata, "attempt"))
            if winner and winner > 1:
                count = winner
        if provider is None:
            available = dig(metadata, "endpoints", "available")
            if isinstance(available, list):
                for endpoint in available:
                    if dig(endpoint, "selected") is True and isinstance(dig(endpoint, "provider"), str):
                        provider = endpoint["provider"]
                        break
        if provider is None and isinstance(dig(body, "provider"), str):
            provider = body["provider"]
        return provider, max(1, count)

    @staticmethod
    def _tool_calls(raw: Any, codec: ToolNameCodec) -> List[ToolCall]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
        calls: List[ToolCall] = []
        for item in raw:
            name = dig(item, "function", "name")
            arguments = dig(item, "function", "arguments")
            call_id = dig(item, "id")
            if isinstance(arguments, str):
                try:
                    arguments = loads_no_float(arguments) if arguments.strip() else {}
                except (ValueError, RecursionError):
                    # Levantado fora do ``except``: a exceção original guarda o
                    # texto recebido e ficaria pendurada em ``__context__``.
                    arguments = _UNPARSEABLE
                if arguments is _UNPARSEABLE:
                    raise ProviderError("invalid_output", status=200, detail_code="tool_arguments_invalid")
            if not isinstance(name, str) or not name or not isinstance(arguments, dict):
                raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
            if not isinstance(call_id, str) or not call_id:
                raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
            calls.append(ToolCall(id=call_id, name=codec.decode(name), arguments=arguments))
        return calls

    @staticmethod
    def _error(reply: HttpReply, body: Any) -> ProviderError:
        status = reply.status
        # Campos do envelope de erro servem só para classificar; nenhum texto
        # do provedor sai daqui.
        code = dig(body, "error", "code")
        kind = dig(body, "error", "type")
        if status == 429 and (code in _QUOTA_CODES or kind in _QUOTA_CODES):
            return ProviderError("auth", status=429, detail_code="quota_exhausted")
        if status == 402 and dig(body, "error", "metadata", "limit_source") == "openrouter_in_flight_budget":
            # Único 402 transitório do OpenRouter: há pedidos em voo reservando saldo.
            return ProviderError(
                "rate_limited",
                status=402,
                retry_after_s=parse_retry_after(reply.headers),
                detail_code="in_flight_budget",
            )
        if status == 413:
            return ProviderError("bad_request", status=413, detail_code="request_too_large")
        return status_error(status, reply.headers)

    # -- sonda ---------------------------------------------------------------

    def probe(self, route: ModelRoute, timeout_s: float) -> bool:
        """Lista de modelos: barata e sem inferência."""
        try:
            headers = self._headers(route, self._secret(route))
            reply = http_request("GET", self._base_url(route) + "/models", headers=headers, timeout_s=timeout_s)
        except ProviderError:
            return False
        return reply.status == 200


def _dump_arguments(arguments: Dict[str, Any]) -> str:
    return encode_json(arguments).decode("utf-8")


def _with_attempts(error: ProviderError, upstream_attempts: int) -> ProviderError:
    """Anexa ao erro as tentativas internas do agregador (contam no orçamento).

    ``ProviderError`` (espinha) não tem esse campo; o gateway lê com
    ``getattr(error, "upstream_attempts", 1)``.
    """
    error.upstream_attempts = max(1, int(upstream_attempts))  # type: ignore[attr-defined]
    return error
