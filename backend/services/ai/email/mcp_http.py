"""Conector de e-mail genérico sobre um servidor MCP (JSON-RPC 2.0 por HTTP).

ESTADO: validado apenas contra servidor MCP local de teste; não validado
contra um servidor de e-mail real. Em especial, o modo "modern" foi escrito a
partir da leitura da especificação 2026-07-28 e nunca falou com um servidor
de terceiros. Antes de ativar, o conector configurado precisa PROVAR busca
paginada e download real de anexo (contrato, seção 10).

Por que não usar o SDK ``mcp``: ele exige ``pydantic>=2.12`` e o backend fixa
2.5; além disso é só assíncrono. O que precisamos do protocolo é pequeno
(``initialize``, ``tools/list``, ``tools/call``), então falamos JSON-RPC
direto com ``requests``.

O conector é dirigido por um arquivo JSON (``AI_EMAIL_MCP_CONFIG_PATH``), sem
credenciais::

    {
      "url": "https://exemplo.invalid/mcp",
      "protocol_mode": "auto",
      "allowed_tools": ["search_threads", "get_message", "get_attachment"],
      "operations": {
        "search": {
          "tool": "search_threads",
          "arguments": {"query": "query", "cursor": "pageToken"},
          "query_filters": {"after": "after:{value}", "before": "before:{value}", "sender": "from:{value}"},
          "date_format": "%Y/%m/%d",
          "static_arguments": {"pageSize": 20},
          "result": {"items": "threads", "next_cursor": "nextPageToken",
                     "item": {"message_id": "id", "sender": "from", "subject": "subject",
                              "date": "date", "snippet": "snippet"}}
        },
        "get_message": {
          "tool": "get_message",
          "arguments": {"message_id": "messageId"},
          "result": {"sender": "from", "subject": "subject", "date": "date",
                     "body_text": "plaintextBody", "attachments": "attachments",
                     "attachment": {"attachment_id": "id", "filename": "filename",
                                    "declared_mime": "mimeType", "size_hint": "size"}}
        },
        "download_attachment": {
          "tool": "get_attachment",
          "arguments": {"message_id": "messageId", "attachment_id": "attachmentId"},
          "result": {"data": "data"}
        }
      }
    }

Regras de segurança, todas cobertas por teste contra um servidor local:

* só são chamadas ferramentas mapeadas E presentes em ``allowed_tools``. O
  que o servidor anuncia em ``tools/list`` serve apenas para conferir que as
  mapeadas existem; uma ferramenta de enviar/apagar/rotular anunciada pelo
  servidor nunca é chamada;
* ``description``, ``instructions``, ``annotations`` e ``serverInfo`` do
  servidor são descartados na leitura: não são guardados, registrados nem
  repassados (são um vetor conhecido de injeção de instruções);
* erro JSON-RPC, ``isError`` e ``resultType`` diferente de ``complete`` viram
  ``connector_unavailable``; HTTP 401 vira ``ConnectorAuthError``;
* o token vai só no cabeçalho ``Authorization`` e nunca é registrado;
* o conector fala com UMA URL: a configurada. Não segue redirecionamento e
  nunca busca URL devolvida pelo servidor (nem ``resource_link``);
* toda resposta tem teto de bytes e prazo total, por operação. O prazo total
  é imposto por quem pede, não pelo servidor: a troca HTTP roda em uma thread
  auxiliar e quem pediu espera por ela no máximo ``timeout_s``. O timeout do
  ``requests`` sozinho não serve para isso, porque vale por leitura do socket:
  um servidor que goteja um byte de cada vez nunca o dispara.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple
from urllib.parse import urlsplit

import requests
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from ..errors import AiError
from ..settings import MIB
from ..types import ExecutionContext
from .base import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_BODY_CHARS,
    MAX_FILENAME_CHARS,
    MAX_ITEMS_PER_PAGE,
    MAX_SENDER_CHARS,
    MAX_SNIPPET_CHARS,
    MAX_SUBJECT_CHARS,
    AttachmentBlob,
    AttachmentInfo,
    ConnectorAuthError,
    EmailConnector,
    EmailMessage,
    EmailPage,
    EmailSummary,
    clean_body,
    clean_mime,
    clean_size,
    clean_text,
    decode_base64_payload,
    is_safe_identifier,
    max_encoded_length,
    unavailable,
)
from .credentials import Secret


logger = logging.getLogger("ai.email.mcp")

PROTOCOL_MODES = ("legacy", "modern", "auto")
# Marca especial em ``result.data``: o conteúdo vem em ``content[]`` como
# recurso embutido (``{"type": "resource", "resource": {"blob": "..."}}``).
RESOURCE_BLOB = "@resource.blob"

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.\-/]{1,128}$")
_PROTOCOL_VERSION = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SESSION_ID = re.compile(r"^[\x21-\x7e]{1,256}$")
# Erros que só um servidor da especificação 2026-07-28 devolve: HeaderMismatch,
# MissingRequiredClientCapability e UnsupportedProtocolVersion.
_MODERN_ERROR_CODES = frozenset({-32020, -32021, -32022})
# Respostas que, no modo "auto", indicam um servidor anterior a 2026-07-28.
_NOT_MODERN_STATUSES = frozenset({400, 404, 405, 406})

_SMALL_RESPONSE_BYTES = 2 * MIB       # busca, leitura, handshake
_JSON_OVERHEAD_BYTES = 1 * MIB        # envelope JSON em volta do anexo
_MAX_TOOL_LIST_PAGES = 20
_MAX_ANNOUNCED_TOOLS = 2000

_SEARCH_ARGUMENTS = frozenset({"query", "after", "before", "sender", "cursor"})
_FILTER_KEYS = frozenset({"after", "before", "sender"})
_ITEM_FIELDS = frozenset({"message_id", "sender", "subject", "date", "snippet"})
_ATTACHMENT_FIELDS = frozenset({"attachment_id", "filename", "declared_mime", "size_hint"})


# ---------------------------------------------------------------------------
# Configuração (JSON validado; propriedades desconhecidas são rejeitadas).
# ---------------------------------------------------------------------------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_tool(name: str) -> str:
    if not _TOOL_NAME.match(name or ""):
        raise ValueError("nome de ferramenta inválido")
    return name


def _check_timeout(value: float) -> float:
    if not 0 < value <= 300:
        raise ValueError("timeout fora do intervalo (0, 300] segundos")
    return value


class SearchResultMap(_Strict):
    items: str
    next_cursor: Optional[str] = None
    item: Dict[str, str]

    @model_validator(mode="after")
    def _check(self) -> "SearchResultMap":
        if "message_id" not in self.item or set(self.item) - _ITEM_FIELDS:
            raise ValueError("result.item precisa de message_id e só aceita campos conhecidos")
        return self


class SearchOperation(_Strict):
    tool: str
    arguments: Dict[str, str]
    static_arguments: Dict[str, Any] = {}
    # Filtros que o servidor só aceita DENTRO da consulta (ex.: "after:{value}").
    query_filters: Dict[str, str] = {}
    date_format: str = "%Y-%m-%d"
    result: SearchResultMap
    timeout_s: float = 20.0

    @model_validator(mode="after")
    def _check(self) -> "SearchOperation":
        _check_tool(self.tool)
        _check_timeout(self.timeout_s)
        if "query" not in self.arguments or set(self.arguments) - _SEARCH_ARGUMENTS:
            raise ValueError("arguments precisa mapear query e só aceita argumentos conhecidos")
        if set(self.query_filters) - _FILTER_KEYS or any("{value}" not in t for t in self.query_filters.values()):
            raise ValueError("query_filters inválido")
        return self


class MessageResultMap(_Strict):
    sender: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    body_text: Optional[str] = None
    attachments: Optional[str] = None
    attachment: Dict[str, str] = {}

    @model_validator(mode="after")
    def _check(self) -> "MessageResultMap":
        if set(self.attachment) - _ATTACHMENT_FIELDS:
            raise ValueError("result.attachment só aceita campos conhecidos")
        if self.attachments is not None and "attachment_id" not in self.attachment:
            raise ValueError("result.attachment precisa de attachment_id")
        return self


class GetMessageOperation(_Strict):
    tool: str
    arguments: Dict[str, str]
    static_arguments: Dict[str, Any] = {}
    result: MessageResultMap
    timeout_s: float = 20.0

    @model_validator(mode="after")
    def _check(self) -> "GetMessageOperation":
        _check_tool(self.tool)
        _check_timeout(self.timeout_s)
        if set(self.arguments) != {"message_id"}:
            raise ValueError("arguments deve mapear exatamente message_id")
        return self


class DownloadResultMap(_Strict):
    data: str
    filename: Optional[str] = None
    declared_mime: Optional[str] = None


class DownloadOperation(_Strict):
    tool: str
    arguments: Dict[str, str]
    static_arguments: Dict[str, Any] = {}
    result: DownloadResultMap
    timeout_s: float = 60.0

    @model_validator(mode="after")
    def _check(self) -> "DownloadOperation":
        _check_tool(self.tool)
        _check_timeout(self.timeout_s)
        if set(self.arguments) != {"message_id", "attachment_id"}:
            raise ValueError("arguments deve mapear exatamente message_id e attachment_id")
        return self


class Operations(_Strict):
    search: SearchOperation
    get_message: GetMessageOperation
    # Opcional de propósito: há servidores (como o Gmail MCP oficial, na
    # documentação consultada) que não oferecem download de anexo.
    download_attachment: Optional[DownloadOperation] = None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class McpEmailConfig(_Strict):
    url: str
    protocol_mode: str = "auto"
    allowed_tools: List[str]
    operations: Operations
    connect_timeout_s: float = 5.0
    handshake_timeout_s: float = 10.0
    legacy_protocol_version: str = "2025-06-18"
    modern_protocol_version: str = "2026-07-28"

    @model_validator(mode="after")
    def _check(self) -> "McpEmailConfig":
        parts = urlsplit(self.url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("https", "http") or not host:
            raise ValueError("url inválida")
        # Sem TLS o token Bearer viajaria em claro. Só loopback pode usar http.
        if parts.scheme == "http" and not _is_loopback(host):
            raise ValueError("url precisa ser https (http só em loopback)")
        if parts.username or parts.password or parts.fragment:
            raise ValueError("url não pode conter credenciais nem fragmento")
        if self.protocol_mode not in PROTOCOL_MODES:
            raise ValueError("protocol_mode inválido")
        _check_timeout(self.connect_timeout_s)
        _check_timeout(self.handshake_timeout_s)
        for version in (self.legacy_protocol_version, self.modern_protocol_version):
            if not _PROTOCOL_VERSION.match(version):
                raise ValueError("versão de protocolo inválida")
        if not self.allowed_tools or len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed_tools vazio ou com repetição")
        for name in self.allowed_tools:
            _check_tool(name)
        outside = set(self.mapped_tools()) - set(self.allowed_tools)
        if outside:
            raise ValueError("operação mapeada para ferramenta fora de allowed_tools")
        return self

    def mapped_tools(self) -> List[str]:
        tools = [self.operations.search.tool, self.operations.get_message.tool]
        if self.operations.download_attachment is not None:
            tools.append(self.operations.download_attachment.tool)
        return tools


def _invalid_config() -> AiError:
    return unavailable("A configuração do conector de e-mail está ausente ou inválida.")


def parse_mcp_config(document: Any) -> McpEmailConfig:
    try:
        return McpEmailConfig.model_validate(document)
    except ValidationError as exc:
        # Só os NOMES dos campos com problema; nunca os valores.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        logger.error("event=mcp_config_invalid fields=%s", ",".join(fields)[:300] or "-")
        raise _invalid_config() from None


def load_mcp_config(path: Any) -> McpEmailConfig:
    if not path:
        raise _invalid_config()
    try:
        raw = Path(str(path)).read_bytes()
        if len(raw) > 256 * 1024:
            raise ValueError("arquivo de configuração grande demais")
        document = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        logger.error("event=mcp_config_unreadable")
        raise _invalid_config() from None
    return parse_mcp_config(document)


# ---------------------------------------------------------------------------
# Transporte.
# ---------------------------------------------------------------------------

class _NotModern(Exception):
    """A sondagem "modern" encontrou um servidor de versão anterior."""


class _DeadlineExceeded(Exception):
    """O prazo total da operação venceu antes de a troca HTTP terminar."""


class _Exchange:
    """Estado de UMA troca HTTP, compartilhado entre quem pede e a thread auxiliar.

    Só guarda o que quem pede precisa depois: status, dois cabeçalhos e o
    corpo já limitado. A resposta em si pertence à thread auxiliar, que é
    quem a fecha.
    """

    def __init__(self) -> None:
        self.done = threading.Event()
        # Ligado por quem pede quando o prazo vence: a thread auxiliar para de
        # ler assim que perceber.
        self.abandoned = threading.Event()
        self.response: Optional[requests.Response] = None
        self.status = 0
        self.content_type = ""
        self.session_id: Optional[str] = None
        self.raw = b""
        self.error: Optional[BaseException] = None


def _reads_body(status: int) -> bool:
    """Respostas cujo corpo interessa. Nas demais o status já decide o erro,
    e ler o corpo só daria ao servidor a chance de nos ocupar."""
    return status not in (401, 403, 429) and not 300 <= status < 400 and status < 500


def _abort_connection(response: Optional[requests.Response]) -> None:
    """Derruba a conexão de uma troca abandonada, para a thread auxiliar sair logo.

    Usa ``shutdown`` e não ``close``: é o ``shutdown`` que acorda um ``recv``
    bloqueado em outra thread; fechar o descritor por fora não interrompe a
    leitura em todos os sistemas. O socket é alcançado por
    ``raw.connection.sock`` (atributos públicos do urllib3 e do
    ``http.client``). Se uma versão futura não os expuser, nada quebra: a
    garantia de prazo de quem pede não depende disto, e a thread auxiliar
    sai sozinha no próximo bloco (ela confere ``abandoned``) ou no timeout
    de leitura do socket.
    """
    try:
        connection = getattr(getattr(response, "raw", None), "connection", None)
        sock = getattr(connection, "sock", None)
        if sock is not None:
            sock.shutdown(socket.SHUT_RDWR)
    except Exception:  # conexão já fechada, socket sem shutdown etc.: só limpeza
        pass


def _dig(payload: Any, path: Optional[str]) -> Any:
    """Segue um caminho ``a.b.0.c`` em dicionários e listas. ``None`` se faltar."""
    if not path:
        return None
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _parse_sse(body: bytes, request_id: int) -> Optional[Dict[str, Any]]:
    """Extrai a resposta JSON-RPC de um corpo ``text/event-stream``.

    Outros eventos (notificações, pedidos do servidor) são ignorados: este
    cliente nunca responde a pedidos iniciados pelo servidor.
    """
    text = body.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    for event in text.split("\n\n"):
        data_lines = [line[5:].lstrip(" ") for line in event.split("\n") if line.startswith("data:")]
        if not data_lines:
            continue
        try:
            message = json.loads("\n".join(data_lines))
        except (ValueError, RecursionError):
            continue
        if isinstance(message, dict) and message.get("id") == request_id and (
            "result" in message or "error" in message
        ):
            return message
    return None


class McpHttpEmailConnector(EmailConnector):
    """Fala com UM servidor MCP, usando só as ferramentas mapeadas e permitidas."""

    def __init__(
        self,
        config: McpEmailConfig,
        token_provider: Callable[[], Secret],
        *,
        max_attachment_bytes: int = 20 * MIB,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._token_provider = token_provider
        self._max_attachment_bytes = int(max_attachment_bytes)
        self._session = session or requests.Session()
        # Sem proxies do ambiente e, principalmente, sem ``.netrc``: com
        # ``trust_env`` ligado, o requests troca o nosso cabeçalho
        # ``Authorization`` pela credencial que encontrar no netrc.
        self._session.trust_env = False
        # Interseção explícita: o que pode ser chamado é mapeado E permitido.
        self._callable: FrozenSet[str] = frozenset(config.mapped_tools()) & frozenset(config.allowed_tools)
        self._connected = False
        self._mode: Optional[str] = None
        self._session_id: Optional[str] = None
        self._negotiated_version: Optional[str] = None
        self._next_id = 0

    def close(self) -> None:
        self._session.close()

    # -- HTTP + JSON-RPC --------------------------------------------------

    def _headers(self, mode: str, method: str, tool: Optional[str]) -> Dict[str, str]:
        token = self._token_provider()
        value = token.reveal() if isinstance(token, Secret) else None
        if not value or any(ch in value for ch in "\r\n\x00") or not value.isascii():
            raise unavailable("A credencial da caixa de e-mail não está disponível. Reconecte a conta.")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "alca-financas-ai/1",
            # Único lugar em que o token aparece. Não vai para a URL, para o
            # corpo, para logs nem para mensagens de erro.
            "Authorization": "Bearer " + value,
        }
        if mode == "modern":
            headers["MCP-Protocol-Version"] = self._config.modern_protocol_version
            headers["Mcp-Method"] = method
            if tool is not None:
                headers["Mcp-Name"] = tool
        else:
            if self._negotiated_version:
                headers["MCP-Protocol-Version"] = self._negotiated_version
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _read_body(response: requests.Response, limit: int, abandoned: threading.Event, too_large: AiError) -> bytes:
        """Lê o corpo até ``limit`` bytes. Roda na thread auxiliar."""
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > limit:
            # O servidor já avisou que passa do teto: recusa sem ler nada.
            raise too_large
        chunks: List[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > limit:
                raise too_large
            if abandoned.is_set():
                # O prazo venceu e quem pediu já foi embora: não há para quem ler.
                return b""
            chunks.append(chunk)
        return b"".join(chunks)

    def _exchange(
        self,
        payload: bytes,
        headers: Dict[str, str],
        *,
        timeout_s: float,
        notification: bool,
        max_response_bytes: int,
        too_large: AiError,
    ) -> _Exchange:
        """Um POST com prazo TOTAL de ``timeout_s`` (cabeçalhos e corpo).

        Por que uma thread auxiliar: o ``timeout`` do ``requests`` vale para
        CADA leitura do socket, e ``iter_content`` só devolve quando o bloco
        inteiro chega. Um servidor que mande um byte a cada intervalo menor
        que o timeout mantém a leitura viva indefinidamente; conferir o
        relógio entre blocos não resolve, porque o bloco nunca termina. Aqui
        quem pede espera no máximo ``timeout_s`` e vai embora; a thread
        auxiliar é avisada (``abandoned``), tem a conexão derrubada e fecha
        a resposta por conta própria. Ela é ``daemon``: nunca impede o
        processo de encerrar.

        Limite conhecido: se o prazo vence ainda na fase dos cabeçalhos, não
        existe resposta (nem socket ao alcance) para derrubar; quem pediu é
        liberado no prazo do mesmo jeito, mas a thread auxiliar só sai quando
        o servidor terminar os cabeçalhos, ficar mudo por ``timeout_s`` ou
        fechar a conexão.

        A ``Session`` pode, por isso, estar em uso por uma troca abandonada
        quando a próxima chamada começa. Isso é seguro: cada troca usa a
        própria conexão, e o pool do urllib3 é feito para uso entre threads.
        """
        state = _Exchange()
        session = self._session
        url = self._config.url
        connect_timeout = self._config.connect_timeout_s

        def run() -> None:
            response = None
            try:
                response = session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=(connect_timeout, timeout_s),
                    stream=True,
                    # Um redirecionamento levaria o token para outro destino.
                    allow_redirects=False,
                )
                state.response = response
                state.status = response.status_code
                state.content_type = (response.headers.get("Content-Type") or "").lower()
                state.session_id = response.headers.get("Mcp-Session-Id")
                if not notification and _reads_body(state.status) and not state.abandoned.is_set():
                    state.raw = self._read_body(response, max_response_bytes, state.abandoned, too_large)
            except BaseException as exc:  # entregue a quem pediu; a thread nunca morre calada
                state.error = exc
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:  # fechar é só limpeza
                        pass
                state.done.set()

        threading.Thread(target=run, name="ai-mcp-http", daemon=True).start()
        if not state.done.wait(timeout_s):
            state.abandoned.set()
            _abort_connection(state.response)
            raise _DeadlineExceeded()
        if state.error is not None:
            raise state.error
        return state

    def _rpc(
        self,
        mode: str,
        method: str,
        params: Optional[Dict[str, Any]],
        *,
        timeout_s: float,
        max_response_bytes: int = _SMALL_RESPONSE_BYTES,
        tool: Optional[str] = None,
        notification: bool = False,
        probing: bool = False,
        too_large: Optional[AiError] = None,
    ) -> Dict[str, Any]:
        """Uma requisição JSON-RPC. Uma tentativa; sem repetição automática."""
        body: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        request_id = None
        if not notification:
            self._next_id += 1
            request_id = self._next_id
            body["id"] = request_id
        payload = dict(params or {})
        if mode == "modern":
            payload["_meta"] = {
                "io.modelcontextprotocol/protocolVersion": self._config.modern_protocol_version,
                # Nenhuma capacidade de cliente: sem sampling, elicitation ou roots.
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "alca-financas-ai", "version": "1"},
            }
        if payload or not notification:
            body["params"] = payload
        too_large = too_large or unavailable("O conector de e-mail devolveu uma resposta grande demais.")
        headers = self._headers(mode, method, tool)
        started = time.monotonic()
        status = 0
        size = 0
        outcome = "error"
        try:
            try:
                exchange = self._exchange(
                    json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers,
                    timeout_s=timeout_s,
                    notification=notification,
                    max_response_bytes=max_response_bytes,
                    too_large=too_large,
                )
                status = exchange.status
                if status == 401:
                    outcome = "auth"
                    raise ConnectorAuthError()
                if status == 403:
                    outcome = "forbidden"
                    raise unavailable("A caixa de e-mail não autorizou esta leitura.")
                if status == 429 or status >= 500:
                    outcome = "upstream_busy"
                    raise unavailable("O conector de e-mail está indisponível no momento.", retryable=True)
                if 300 <= status < 400:
                    outcome = "redirect"
                    raise unavailable("O conector de e-mail respondeu de forma inesperada.")
                if notification:
                    outcome = "ok" if status < 300 else "rejected"
                    if status >= 300:
                        raise unavailable("O conector de e-mail respondeu de forma inesperada.")
                    return {}
                raw = exchange.raw
                exchange.raw = b""  # uma referência só: o ``del raw`` abaixo libera o corpo
                size = len(raw)
            except (requests.exceptions.Timeout, _DeadlineExceeded):
                # Timeout de uma leitura (servidor mudo) ou prazo total
                # vencido (servidor que goteja): para quem chama é o mesmo.
                outcome = "timeout"
                raise unavailable("O conector de e-mail não respondeu a tempo.", retryable=True) from None
            except requests.exceptions.RequestException:
                # A mensagem da exceção pode conter a URL; não é registrada.
                outcome = "network"
                raise unavailable("Não foi possível falar com o conector de e-mail.", retryable=True) from None

            message: Any = None
            if "text/event-stream" in exchange.content_type:
                message = _parse_sse(raw, request_id)
            else:
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (ValueError, RecursionError):
                    # Inclui JSON aninhado demais, enviado para derrubar o cliente.
                    message = None
            del raw

            error = message.get("error") if isinstance(message, dict) else None
            error_code = error.get("code") if isinstance(error, dict) else None
            if probing and error_code not in _MODERN_ERROR_CODES and (
                status in _NOT_MODERN_STATUSES or error is not None
            ):
                outcome = "not_modern"
                raise _NotModern()
            if status >= 400:
                outcome = "http_error"
                raise unavailable("O conector de e-mail recusou o pedido.")
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or message.get("id") != request_id:
                outcome = "invalid_envelope"
                raise unavailable("O conector de e-mail devolveu uma resposta inválida.")
            if error is not None:
                # Só o código numérico é registrado; ``error.message`` é texto
                # do servidor e pode conter dados ou instruções.
                outcome = "rpc_error:%s" % (error_code if isinstance(error_code, int) else "?")
                raise unavailable("O conector de e-mail devolveu um erro.")
            result = message.get("result")
            if not isinstance(result, dict):
                outcome = "invalid_result"
                raise unavailable("O conector de e-mail devolveu uma resposta inválida.")
            if mode == "legacy" and method == "initialize":
                self._capture_session(exchange.session_id, result)
            outcome = "ok"
            return result
        finally:
            logger.info(
                "event=mcp_request method=%s tool=%s mode=%s status=%d outcome=%s bytes=%d duration_ms=%d",
                method, tool or "-", mode, status, outcome, size, int((time.monotonic() - started) * 1000),
            )

    def _capture_session(self, session_id: Optional[str], result: Dict[str, Any]) -> None:
        # O id de sessão volta em um cabeçalho NOSSO nas próximas chamadas:
        # só ASCII visível, sem espaço nem quebra de linha, senão é descartado.
        self._session_id = session_id if session_id and _SESSION_ID.match(session_id) else None
        version = result.get("protocolVersion")
        if isinstance(version, str) and _PROTOCOL_VERSION.match(version):
            self._negotiated_version = version
        else:
            self._negotiated_version = self._config.legacy_protocol_version
        # ``instructions``, ``serverInfo`` e ``capabilities`` do servidor são
        # descartados aqui, sem guardar nem registrar.

    # -- conexão ----------------------------------------------------------

    def _handshake_legacy(self) -> None:
        timeout = self._config.handshake_timeout_s
        self._rpc(
            "legacy",
            "initialize",
            {
                "protocolVersion": self._config.legacy_protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "alca-financas-ai", "version": "1"},
            },
            timeout_s=timeout,
        )
        self._rpc("legacy", "notifications/initialized", None, timeout_s=timeout, notification=True)

    def _list_tool_names(self, mode: str, probing: bool = False) -> FrozenSet[str]:
        """Nomes anunciados pelo servidor. Só os nomes: o resto é descartado."""
        names = set()
        cursor: Optional[str] = None
        seen_cursors = set()
        for _ in range(_MAX_TOOL_LIST_PAGES):
            params = {"cursor": cursor} if cursor is not None else {}
            result = self._rpc(
                mode, "tools/list", params, timeout_s=self._config.handshake_timeout_s, probing=probing
            )
            probing = False
            tools = result.get("tools")
            for tool in tools if isinstance(tools, list) else []:
                name = tool.get("name") if isinstance(tool, dict) else None
                if isinstance(name, str) and _TOOL_NAME.match(name) and len(names) < _MAX_ANNOUNCED_TOOLS:
                    names.add(name)
            cursor = result.get("nextCursor")
            # String vazia é um cursor válido no protocolo; ausência é o fim.
            if not isinstance(cursor, str) or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
        return frozenset(names)

    def connect(self) -> None:
        """Negocia o protocolo e confirma que as ferramentas mapeadas existem."""
        if self._connected:
            return
        mode = self._config.protocol_mode
        if mode == "legacy":
            self._handshake_legacy()
            announced = self._list_tool_names("legacy")
        elif mode == "modern":
            announced = self._list_tool_names("modern")
        else:
            try:
                announced = self._list_tool_names("modern", probing=True)
                mode = "modern"
            except _NotModern:
                mode = "legacy"
                self._handshake_legacy()
                announced = self._list_tool_names("legacy")
        missing = sorted(self._callable - announced)
        if missing:
            logger.error("event=mcp_tools_missing count=%d", len(missing))
            raise unavailable("O servidor de e-mail não oferece as ferramentas configuradas.")
        self._mode = mode
        self._connected = True
        logger.info("event=mcp_connected mode=%s announced=%d used=%d", mode, len(announced), len(self._callable))

    def _call_tool(
        self,
        tool: str,
        arguments: Dict[str, Any],
        *,
        timeout_s: float,
        max_response_bytes: int = _SMALL_RESPONSE_BYTES,
        too_large: Optional[AiError] = None,
    ) -> Dict[str, Any]:
        # Barreira final: mesmo que um defeito em outro ponto pedisse outra
        # ferramenta, nada fora da lista sai deste processo.
        if tool not in self._callable:
            raise unavailable("Ferramenta fora da lista de permissão do conector.")
        self.connect()
        result = self._rpc(
            self._mode or "legacy",
            "tools/call",
            {"name": tool, "arguments": arguments},
            timeout_s=timeout_s,
            max_response_bytes=max_response_bytes,
            tool=tool,
            too_large=too_large,
        )
        if result.get("isError"):
            raise unavailable("O conector de e-mail não conseguiu concluir o pedido.")
        # ``input_required`` pediria dados ao usuário/modelo em nome do
        # servidor; este cliente não atende a esse tipo de pedido.
        if result.get("resultType") not in (None, "complete"):
            raise unavailable("O conector de e-mail pediu uma interação não suportada.")
        return result

    @staticmethod
    def _structured(result: Dict[str, Any]) -> Dict[str, Any]:
        """Objeto de dados do resultado: ``structuredContent`` ou JSON em texto."""
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content")
        for item in content if isinstance(content, list) else []:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str):  # o tamanho já foi limitado no corpo HTTP
                continue
            try:
                parsed = json.loads(text)
            except (ValueError, RecursionError):
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    # -- operações --------------------------------------------------------

    def search(
        self,
        ctx: ExecutionContext,
        *,
        query: str,
        after: Optional[date] = None,
        before: Optional[date] = None,
        sender: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> EmailPage:
        operation = self._config.operations.search
        arguments: Dict[str, Any] = dict(operation.static_arguments)
        text = query
        filters: List[Tuple[str, Optional[str], str]] = [
            ("after", after.strftime(operation.date_format) if after else None, "data inicial"),
            ("before", before.strftime(operation.date_format) if before else None, "data final"),
            ("sender", sender, "remetente"),
        ]
        for key, value, label in filters:
            if value is None:
                continue
            if key in operation.arguments:
                arguments[operation.arguments[key]] = value
            elif key in operation.query_filters:
                text = "%s %s" % (text, operation.query_filters[key].replace("{value}", value))
            else:
                # Ignorar o filtro devolveria mensagens fora do que foi pedido.
                raise AiError("invalid_request", "O conector configurado não filtra por %s." % label)
        arguments[operation.arguments["query"]] = text
        if cursor is not None:
            if "cursor" not in operation.arguments:
                raise AiError("invalid_request", "O conector configurado não pagina resultados.")
            arguments[operation.arguments["cursor"]] = cursor

        payload = self._structured(self._call_tool(operation.tool, arguments, timeout_s=operation.timeout_s))
        raw_items = _dig(payload, operation.result.items)
        items: List[EmailSummary] = []
        # ``{}`` (sem a lista) significa "nenhum resultado", não erro.
        for raw in raw_items if isinstance(raw_items, list) else []:
            if len(items) >= MAX_ITEMS_PER_PAGE or not isinstance(raw, dict):
                continue
            mapping = operation.result.item
            message_id = _dig(raw, mapping["message_id"])
            if not is_safe_identifier(message_id):
                continue
            items.append(
                EmailSummary(
                    message_id=message_id,
                    sender=clean_text(_dig(raw, mapping.get("sender")), MAX_SENDER_CHARS),
                    subject=clean_text(_dig(raw, mapping.get("subject")), MAX_SUBJECT_CHARS),
                    date=clean_text(_dig(raw, mapping.get("date")), 64) or None,
                    snippet=clean_text(_dig(raw, mapping.get("snippet")), MAX_SNIPPET_CHARS),
                )
            )
        next_cursor = _dig(payload, operation.result.next_cursor)
        if not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 4096:
            next_cursor = None
        return EmailPage(items=items, next_cursor=next_cursor)

    def get_message(self, ctx: ExecutionContext, message_id: str) -> EmailMessage:
        operation = self._config.operations.get_message
        arguments: Dict[str, Any] = dict(operation.static_arguments)
        arguments[operation.arguments["message_id"]] = message_id
        payload = self._structured(self._call_tool(operation.tool, arguments, timeout_s=operation.timeout_s))
        mapping = operation.result
        body, truncated = clean_body(_dig(payload, mapping.body_text), MAX_BODY_CHARS)
        attachments: List[AttachmentInfo] = []
        raw_attachments = _dig(payload, mapping.attachments)
        for raw in raw_attachments if isinstance(raw_attachments, list) else []:
            if len(attachments) >= MAX_ATTACHMENTS_PER_MESSAGE or not isinstance(raw, dict):
                continue
            attachment_id = _dig(raw, mapping.attachment.get("attachment_id"))
            if not is_safe_identifier(attachment_id):
                continue
            filename = _dig(raw, mapping.attachment.get("filename"))
            attachments.append(
                AttachmentInfo(
                    attachment_id=attachment_id,
                    filename=filename[:MAX_FILENAME_CHARS] if isinstance(filename, str) else "",
                    declared_mime=clean_mime(_dig(raw, mapping.attachment.get("declared_mime"))),
                    size_hint=clean_size(_dig(raw, mapping.attachment.get("size_hint"))),
                )
            )
        return EmailMessage(
            message_id=message_id,
            sender=clean_text(_dig(payload, mapping.sender), MAX_SENDER_CHARS),
            subject=clean_text(_dig(payload, mapping.subject), MAX_SUBJECT_CHARS),
            date=clean_text(_dig(payload, mapping.date), 64) or None,
            body_text=body,
            body_truncated=truncated,
            attachments=attachments,
        )

    def download_attachment(self, ctx: ExecutionContext, message_id: str, attachment_id: str) -> AttachmentBlob:
        operation = self._config.operations.download_attachment
        if operation is None:
            raise unavailable("O conector configurado não oferece download de anexo.")
        arguments: Dict[str, Any] = dict(operation.static_arguments)
        arguments[operation.arguments["message_id"]] = message_id
        arguments[operation.arguments["attachment_id"]] = attachment_id
        too_large = AiError("payload_too_large", "O anexo excede o tamanho permitido.")
        result = self._call_tool(
            operation.tool,
            arguments,
            timeout_s=operation.timeout_s,
            # Primeiro teto: o corpo HTTP inteiro. Um anexo acima do limite é
            # recusado ainda durante a leitura, sem montar o JSON.
            max_response_bytes=max_encoded_length(self._max_attachment_bytes) + _JSON_OVERHEAD_BYTES,
            too_large=too_large,
        )
        payload = self._structured(result)
        if operation.result.data == RESOURCE_BLOB:
            encoded = None
            content = result.get("content")
            for item in content if isinstance(content, list) else []:
                resource = item.get("resource") if isinstance(item, dict) and item.get("type") == "resource" else None
                if isinstance(resource, dict) and isinstance(resource.get("blob"), str):
                    encoded = resource["blob"]
                    break
        else:
            encoded = _dig(payload, operation.result.data)
        if not isinstance(encoded, str):
            # Inclui o caso em que o servidor devolve uma URL ou um
            # ``resource_link`` em vez do conteúdo: não buscamos URL alguma.
            raise unavailable("O conector não devolveu o conteúdo do anexo.")
        # Segundo teto: o tamanho do texto codificado, antes de decodificar.
        content_bytes = decode_base64_payload(encoded, self._max_attachment_bytes)
        del encoded, result

        filename = _dig(payload, operation.result.filename)
        declared_mime = clean_mime(_dig(payload, operation.result.declared_mime))
        if not isinstance(filename, str) or not filename.strip():
            # Há servidores (ex.: API do Gmail) em que o download só traz os
            # bytes; nome e tipo declarado ficam nos metadados da mensagem.
            filename = "anexo"
            for attachment in self.get_message(ctx, message_id).attachments:
                if attachment.attachment_id == attachment_id:
                    filename = attachment.filename or "anexo"
                    declared_mime = declared_mime or attachment.declared_mime
                    break
        return AttachmentBlob(
            content=content_bytes,
            filename=filename[:MAX_FILENAME_CHARS],
            declared_mime=declared_mime,
        )
