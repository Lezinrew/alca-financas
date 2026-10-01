"""Adaptador da API de Mensagens da Anthropic (``POST /v1/messages``).

ATENÇÃO: validado apenas contra servidor local de teste; não validado contra o
provedor real. Os formatos seguem a documentação oficial consultada em
01/10/2026, mas nenhuma chamada paga foi feita.

Por que HTTP direto em vez do SDK oficial: a plataforma não pode ganhar
dependências novas, e o SDK repete sozinho (2 vezes, por padrão) em 408, 409,
429 e 5xx. Aqui é uma requisição por chamada; quem repete é o gateway.

Diferenças em relação ao formato OpenAI que este adaptador resolve:

* ``system`` é um campo do pedido, não uma mensagem;
* o resultado de ferramenta volta em uma mensagem ``user`` com blocos
  ``tool_result`` (todos os resultados do turno na MESMA mensagem);
* a ferramenta declara ``input_schema`` e a chamada chega como bloco
  ``tool_use`` com ``input`` já em objeto;
* saída estruturada usa ``output_config.format`` (``json_schema``), que não
  aceita limites numéricos nem de tamanho e exige ``additionalProperties:
  false``. O schema é adaptado só na IDA; a validação completa continua no
  gateway, com o schema original;
* nomes de ferramenta não aceitam ponto (ver ``ToolNameCodec``).

Decisões deliberadas, que divergem de exemplos da documentação:

* ``temperature`` NÃO é enviado por padrão: os modelos atuais recusam
  parâmetros de amostragem com 400. Rota de modelo que aceite liga
  ``extra.send_temperature``.
* ``fallbacks`` (troca de modelo pelo servidor em caso de recusa) NÃO é usado.
  O contrato (seção 8) proíbe trocar de rota para contornar recusa, e troca
  feita pelo provedor ficaria fora do orçamento de tentativas e do registro de
  modelos autorizados. ``stop_reason: "refusal"`` vira ``ProviderError("refusal")``.
* blocos ``thinking`` da resposta não são guardados nem reenviados:
  ``ChatMessage`` não tem onde carregá-los. Remover todos é aceito pela API;
  o custo é o modelo não reaproveitar o raciocínio entre turnos de ferramenta.
* ``max_tokens`` inclui o raciocínio do modelo. ``extra.min_max_tokens`` define
  um piso por rota para a resposta não ser cortada antes de começar.

Erros: 529 e 5xx são transitórios; 429 com ``retry-after`` é limite de taxa;
429 de teto de gasto, 401, 402 e 403 são falha de credencial/conta (não
adianta repetir).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import (
    AdapterResult,
    ModelRequest,
    ModelRoute,
    ProviderAdapter,
    ProviderError,
    ToolCall,
    Usage,
)
from ..validation import safe_label
from . import (
    HttpReply,
    ToolNameCodec,
    as_int,
    b64,
    credential_from_env,
    detect_image_mime,
    dig,
    http_request,
    parse_retry_after,
    status_error,
)


logger = logging.getLogger("ai.gateway.anthropic")

DEFAULT_API_VERSION = "2023-06-01"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Restrições que ``output_config.format`` não aceita (devolveria 400).
_UNSUPPORTED_IN_OUTPUT_SCHEMA = ("minimum", "maximum", "multipleOf", "minLength", "maxLength", "maxItems")
_SPEND_LIMIT_PREFIX = "You have reached your specified API usage limits"


def output_schema_for_wire(schema: Any) -> Any:
    """Cópia do schema só com o que ``output_config.format`` aceita.

    Nada disso afrouxa a validação: o gateway valida a resposta com o schema
    ORIGINAL. Aqui só se evita um 400 por palavra-chave não suportada.
    """
    if isinstance(schema, list):
        return [output_schema_for_wire(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result: Dict[str, Any] = {}
    for key, value in schema.items():
        if key in _UNSUPPORTED_IN_OUTPUT_SCHEMA:
            continue
        if key == "minItems" and value not in (0, 1):
            continue
        if key == "properties" and isinstance(value, dict):
            result[key] = {name: output_schema_for_wire(child) for name, child in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            result[key] = output_schema_for_wire(value)
        else:
            result[key] = value
    if result.get("type") == "object" or "properties" in result:
        result["additionalProperties"] = False
    return result


class AnthropicAdapter(ProviderAdapter):
    """Uma tentativa em ``POST {base_url}/v1/messages``.

    Validado apenas contra servidor local de teste; não validado contra o
    provedor real.
    """

    provider = "anthropic"

    # -- credencial ----------------------------------------------------------

    @staticmethod
    def _headers(route: ModelRoute, secret: str) -> Dict[str, str]:
        version = route.extra.get("anthropic_version")
        return {
            "x-api-key": secret,
            "anthropic-version": version if isinstance(version, str) and version else DEFAULT_API_VERSION,
        }

    @staticmethod
    def _base_url(route: ModelRoute) -> str:
        base = (route.base_url or "").rstrip("/")
        if not base:
            raise ProviderError("bad_request", detail_code="base_url_missing")
        return base

    # -- montagem do pedido --------------------------------------------------

    @staticmethod
    def _append(messages: List[Dict[str, Any]], role: str, blocks: List[Dict[str, Any]]) -> None:
        """Acrescenta blocos, fundindo com a mensagem anterior de mesmo papel.

        Garante a alternância user/assistant e coloca todos os ``tool_result``
        de um turno em uma única mensagem ``user``.
        """
        if not blocks:
            return
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": list(blocks)})

    def build_payload(self, route: ModelRoute, request: ModelRequest) -> Dict[str, Any]:
        """Corpo de ``POST /v1/messages``. Público para a homologação inspecionar."""
        codec = ToolNameCodec(request.tools)
        system_parts: List[str] = []
        messages: List[Dict[str, Any]] = []
        last_user_text: Optional[Dict[str, Any]] = None
        for message in request.messages:
            if message.role == "system":
                if message.content:
                    system_parts.append(message.content)
            elif message.role == "tool":
                self._append(
                    messages,
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id or "",
                            "content": message.content or "",
                        }
                    ],
                )
            elif message.role == "assistant":
                blocks: List[Dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                for call in message.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": codec.encode(call.name),
                            "input": dict(call.arguments),
                        }
                    )
                self._append(messages, "assistant", blocks)
            else:
                text_block = {"type": "text", "text": message.content or ""}
                self._append(messages, "user", [text_block])
                last_user_text = text_block

        if request.images:
            if last_user_text is None:
                raise ProviderError("bad_request", detail_code="image_without_user_message")
            images = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": detect_image_mime(image), "data": b64(image)},
                }
                for image in request.images
            ]
            # As imagens entram logo ANTES do último texto escrito pelo usuário
            # (ordem recomendada pela documentação). Não podem ir no início de
            # uma mensagem que carrega ``tool_result``: esses blocos precisam
            # vir primeiro.
            for wire_message in messages:
                content = wire_message["content"]
                position = next((i for i, block in enumerate(content) if block is last_user_text), None)
                if position is not None:
                    content[position:position] = images
                    break

        if not messages or messages[0]["role"] != "user":
            raise ProviderError("bad_request", detail_code="first_message_not_user")

        max_tokens = int(request.max_output_tokens)
        floor = route.extra.get("min_max_tokens")
        if isinstance(floor, int) and not isinstance(floor, bool):
            max_tokens = max(max_tokens, floor)

        payload: Dict[str, Any] = {"model": route.model_id, "max_tokens": max_tokens, "messages": messages}
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if route.extra.get("send_temperature") is True:
            payload["temperature"] = request.temperature
        if request.tools:
            payload["tools"] = [
                {
                    "name": codec.encode(tool.name),
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]
        output_config: Dict[str, Any] = {}
        if request.response_schema is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": output_schema_for_wire(request.response_schema),
            }
        effort = route.extra.get("effort")
        if effort in EFFORT_LEVELS:
            output_config["effort"] = effort
        if output_config:
            payload["output_config"] = output_config
        return payload

    # -- chamada -------------------------------------------------------------

    def complete(self, route: ModelRoute, request: ModelRequest, timeout_s: float) -> AdapterResult:
        # Lida do ambiente a cada chamada; vive só nesta variável local (monta o
        # cabeçalho e filtra o rótulo de modelo devolvido pelo provedor).
        secret = credential_from_env(route.credential_env)
        payload = self.build_payload(route, request)
        reply = http_request(
            "POST",
            self._base_url(route) + "/v1/messages",
            headers=self._headers(route, secret),
            payload=payload,
            timeout_s=timeout_s,
        )
        body = reply.json()
        if reply.status != 200:
            raise self._error(reply, body)
        if not isinstance(body, dict) or not isinstance(body.get("content"), list):
            raise ProviderError("server_error", status=200, detail_code="malformed_response")

        stop_reason = body.get("stop_reason")
        if stop_reason == "refusal":
            # Recusa de conteúdo: o gateway NÃO troca de rota para contornar.
            raise ProviderError("refusal", status=200)

        codec = ToolNameCodec(request.tools)
        texts: List[str] = []
        tool_calls: List[ToolCall] = []
        for block in body["content"]:
            kind = dig(block, "type")
            if kind == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif kind == "tool_use":
                name, call_id, arguments = block.get("name"), block.get("id"), block.get("input")
                if arguments is None:
                    arguments = {}
                if not isinstance(name, str) or not isinstance(call_id, str) or not isinstance(arguments, dict):
                    raise ProviderError("invalid_output", status=200, detail_code="tool_calls_malformed")
                tool_calls.append(ToolCall(id=call_id, name=codec.decode(name), arguments=arguments))
            # Blocos ``thinking`` e outros tipos são ignorados: raciocínio do
            # modelo não é resposta e não vai para logs nem auditoria.

        if stop_reason in ("max_tokens", "model_context_window_exceeded"):
            finish_reason = "length"
        elif tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"

        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        # Entrada total = não cacheada + escrita em cache + lida do cache.
        input_parts = [
            as_int(usage.get(key))
            for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        ]
        known = [value for value in input_parts if value is not None]
        return AdapterResult(
            content="".join(texts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model_id=safe_label(body.get("model"), route.model_id, forbidden=(secret,)),
            effective_provider=None,
            usage=Usage(
                input_tokens=sum(known) if known else None,
                output_tokens=as_int(usage.get("output_tokens")),
            ),
            # A API não devolve custo; o gateway calcula pelos tokens e pelas
            # tarifas registradas na rota.
            cost_micros=None,
            latency_ms=reply.latency_ms,
            upstream_attempts=1,
            metrics={},
        )

    @staticmethod
    def _error(reply: HttpReply, body: Any) -> ProviderError:
        status = reply.status
        # O envelope de erro serve só para classificar; o texto não é propagado.
        if status == 429:
            retry_after = parse_retry_after(reply.headers)
            if dig(body, "error", "details", "error_code") == "enforced_spend_limit_reached":
                return ProviderError("auth", status=429, detail_code="spend_limit")
            return ProviderError("rate_limited", status=429, retry_after_s=retry_after)
        if status == 400:
            message = dig(body, "error", "message")
            if isinstance(message, str) and message.startswith(_SPEND_LIMIT_PREFIX):
                # Teto de gasto definido pelo próprio cliente no console chega como 400.
                return ProviderError("auth", status=400, detail_code="spend_limit")
            return ProviderError("bad_request", status=400)
        if status == 413:
            return ProviderError("bad_request", status=413, detail_code="request_too_large")
        if status == 529:
            return ProviderError("server_error", status=529, retry_after_s=parse_retry_after(reply.headers),
                                 detail_code="overloaded")
        return status_error(status, reply.headers)

    # -- sonda ---------------------------------------------------------------

    def probe(self, route: ModelRoute, timeout_s: float) -> bool:
        """Lista de modelos (uma página de um item): barata e sem inferência."""
        try:
            headers = self._headers(route, credential_from_env(route.credential_env))
            reply = http_request(
                "GET", self._base_url(route) + "/v1/models?limit=1", headers=headers, timeout_s=timeout_s
            )
        except ProviderError:
            return False
        return reply.status == 200
