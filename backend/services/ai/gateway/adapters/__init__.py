"""Adaptadores de provedor e o que eles têm em comum: uma tentativa HTTP.

Cada adaptador traduz ``ModelRequest`` para o formato do provedor, faz UMA
requisição e traduz a resposta de volta. Regras que valem para todos e que
ficam concentradas aqui:

* **Sem retry embutido.** ``HTTPAdapter(max_retries=0)``: quem decide tentar de
  novo, esperar ou trocar de rota é só o gateway, dono do orçamento global de
  tentativas (contrato, seção 8). Retry escondido na camada HTTP furaria o teto.
* **Sem variáveis de ambiente de proxy** (``trust_env = False``). Um
  ``HTTP_PROXY`` esquecido faria o pedido a um modelo LOCAL sair por um proxy
  externo, quebrando ``local_only`` sem ninguém perceber. Também impede o
  ``requests`` de anexar credenciais de ``.netrc``.
* **Sem seguir redirecionamento.** Um 3xx poderia levar o pedido (e o conteúdo)
  para outro host.
* **Nada do provedor vaza.** Falha vira ``ProviderError`` com tipo, status e um
  código curto. O corpo da resposta de erro, a URL e os cabeçalhos nunca entram
  em exceção, log ou trilha. Por isso o erro é levantado FORA do bloco
  ``except``: dentro dele, a exceção original do ``requests`` (que guarda o
  pedido com o cabeçalho de autorização) viajaria pendurada em ``__context__``.
* **Prazo total, não só por leitura.** Além do timeout de conexão e de leitura
  de socket, o corpo tem prazo total (``timeout_s`` desde o início) e teto de
  tamanho. Pior caso de uma chamada: conexão + espera do primeiro byte + uma
  última leitura em curso quando o prazo vence, cada uma limitada a
  ``timeout_s``.
* **O erro diz até onde o pedido foi** (``detail_code``): nada saiu da máquina,
  saiu e a resposta não veio, ou a resposta veio estragada. O gateway usa isso
  para devolver ou manter a reserva de custo.
* **Rótulos do provedor são filtrados.** ``model`` e ``provider`` da resposta
  passam por ``safe_label`` antes de virarem "modelo efetivo" na auditoria.
* **Sem float.** O corpo é lido com ``loads_no_float``: argumentos de
  ferramenta e saída estruturada chegam com ``Decimal``.
"""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

import requests
from requests.adapters import HTTPAdapter
# O urllib3 é a camada HTTP do próprio ``requests`` (dependência obrigatória
# dele, não uma dependência nova): as exceções dele são necessárias para saber
# em que fase a falha ocorreu e para ler o corpo com ``raw.read1``.
from urllib3 import exceptions as urllib3_errors

from ..base import ProviderAdapter, ProviderError, ToolSpec
from ..validation import loads_no_float


# Teto do corpo de resposta. Uma resposta de chat cabe com folga; acima disso é
# defeito ou abuso, e ler tudo para a memória derrubaria o worker.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_CHUNK_BYTES = 64 * 1024
# Retry-After absurdo (horas) não deve virar espera nem conta de cabeça.
MAX_RETRY_AFTER_S = 3600.0

# Códigos curtos (``ProviderError.detail_code``) que dizem em que FASE a
# tentativa parou. O gateway decide com eles o que fazer com os dois orçamentos.
DETAIL_CREDENTIAL_MISSING = "credential_missing"
DETAIL_CREDENTIAL_MALFORMED = "credential_malformed"
DETAIL_CONNECT_FAILED = "connect_failed"
DETAIL_CONNECT_TIMEOUT = "connect_timeout"
DETAIL_REQUEST_INVALID = "request_invalid"
DETAIL_READ_TIMEOUT = "read_timeout"
DETAIL_CONNECTION_LOST = "connection_lost"
DETAIL_UPSTREAM_MISMATCH = "upstream_mismatch"

# Nem tentativa de conexão houve: não consome o orçamento de tentativas.
NOT_ATTEMPTED_DETAILS = frozenset({DETAIL_CREDENTIAL_MISSING, DETAIL_CREDENTIAL_MALFORMED})
# Nenhum byte do pedido saiu da máquina: o provedor não pode ter cobrado.
NOT_SENT_DETAILS = NOT_ATTEMPTED_DETAILS | frozenset(
    {DETAIL_CONNECT_FAILED, DETAIL_CONNECT_TIMEOUT, DETAIL_REQUEST_INVALID}
)

# Valor aceitável em cabeçalho HTTP: ASCII imprimível, sem espaço.
_HEADER_SAFE = re.compile(r"\A[\x21-\x7e]+\Z")
_INVALID_REQUEST_ERRORS = (
    requests.exceptions.InvalidURL,
    requests.exceptions.InvalidHeader,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
)


class HttpReply:
    """Resposta HTTP já lida. ``json()`` devolve ``None`` se o corpo não for JSON."""

    __slots__ = ("status", "headers", "body", "latency_ms")

    def __init__(self, status: int, headers: Mapping[str, str], body: bytes, latency_ms: int) -> None:
        self.status = status
        self.headers = headers
        self.body = body
        self.latency_ms = latency_ms

    def json(self) -> Any:
        try:
            return loads_no_float(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            return None


def _wire_default(value: Any) -> Any:
    """Serializa o que o ``json`` não conhece ao ENVIAR para o provedor.

    ``Decimal`` aparece em argumentos de ferramenta de turnos anteriores (lidos
    sem float). Na ida para o modelo vira número JSON; o cálculo financeiro
    continua sendo do backend, nunca do que o modelo recebe ou devolve.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    return str(value)


def encode_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, default=_wire_default).encode("utf-8")


def _error_chain(error: BaseException, limit: int = 16) -> List[BaseException]:
    """Exceções encadeadas dentro de ``error`` (causa, contexto, ``reason``, args).

    O ``requests`` embrulha as exceções do ``urllib3``, que embrulham as do
    sistema. Para saber SE o pedido chegou a sair é preciso olhar lá dentro.
    """
    seen: List[BaseException] = []
    queue: List[Any] = [error]
    while queue and len(seen) < limit:
        current = queue.pop(0)
        if not isinstance(current, BaseException) or any(current is item for item in seen):
            continue
        seen.append(current)
        queue.extend([getattr(current, "reason", None), current.__cause__, current.__context__])
        queue.extend(getattr(current, "args", ()) or ())
    return seen


def _never_connected(error: BaseException) -> bool:
    """A falha aconteceu ANTES de qualquer byte do pedido sair da máquina?

    Conexão recusada, DNS sem resposta, timeout de conexão e certificado TLS
    inválido acontecem antes do envio: o provedor não viu o pedido e não pode
    ter cobrado. Qualquer outra falha de rede é tratada como "depois do envio".
    """
    never_sent = (
        urllib3_errors.NewConnectionError,
        urllib3_errors.ConnectTimeoutError,
        socket.gaierror,
        ssl.SSLCertVerificationError,
    )
    return any(isinstance(item, never_sent) for item in _error_chain(error))


def _is_read_timeout(error: BaseException) -> bool:
    return any(
        isinstance(item, (urllib3_errors.ReadTimeoutError, socket.timeout)) for item in _error_chain(error)
    )


def _is_decode_error(error: BaseException) -> bool:
    decode_errors = (urllib3_errors.DecodeError, requests.exceptions.ContentDecodingError)
    return any(isinstance(item, decode_errors) for item in _error_chain(error))


def _body_chunks(response: Any) -> Iterator[bytes]:
    """Pedaços do corpo, um por leitura de socket.

    ``raw.read1`` devolve o que UMA leitura de socket trouxe, e assim o prazo
    total pode ser conferido a cada pedaço. ``iter_content(n)`` não serve para
    isso: ele só devolve depois de juntar ``n`` bytes (ou no fim do corpo), e
    um servidor que goteja um byte de cada vez seguraria a chamada por horas,
    porque cada leitura isolada cumpre o timeout de leitura. ``read1`` existe
    no urllib3 a partir da versão 2.2; em versão mais antiga cai-se em
    ``iter_content`` e o prazo total só é conferido a cada ``_CHUNK_BYTES``.
    """
    read1 = getattr(response.raw, "read1", None)
    if not callable(read1):
        for chunk in response.iter_content(_CHUNK_BYTES):
            yield chunk
        return
    while True:
        chunk = read1(_CHUNK_BYTES, decode_content=True)
        if not chunk:
            return
        yield chunk


def http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    payload: Any = None,
    timeout_s: float,
) -> HttpReply:
    """Uma requisição, uma tentativa. Falha de transporte vira ``ProviderError``.

    Uma sessão por chamada (fechada ao final): reutilizar conexão ociosa pode
    falhar com "connection reset" em um POST, e sem retry isso viraria falha
    transitória falsa contando no disjuntor. A inferência demora ordens de
    grandeza mais que abrir uma conexão.

    O erro diz ao gateway ATÉ ONDE o pedido foi, porque disso depende se a
    reserva de custo é devolvida ou mantida:

    * ``connect_failed`` / ``connect_timeout`` / ``request_invalid``: nada saiu
      da máquina (não pode ter havido cobrança);
    * ``read_timeout`` / ``connection_lost`` sem ``status``: o pedido foi
      enviado e a resposta não chegou (o provedor pode ter processado);
    * erro COM ``status``: a resposta começou a chegar com esse status e o
      corpo se perdeu, passou do tamanho ou do prazo.

    Os erros são levantados FORA dos blocos ``except``. Dentro deles, a exceção
    original ficaria pendurada em ``__context__`` (``from None`` esconde do
    traceback, mas não solta a referência), e ela guarda o pedido preparado
    com o cabeçalho de autorização.
    """
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = encode_json(payload)
        request_headers.setdefault("Content-Type", "application/json")
    request_headers.setdefault("Accept", "application/json")

    session = requests.Session()
    session.trust_env = False
    no_retry = HTTPAdapter(max_retries=0)
    session.mount("http://", no_retry)
    session.mount("https://", no_retry)

    started = time.perf_counter()
    deadline = started + float(timeout_s)
    failure: Optional[ProviderError] = None
    response: Any = None
    status = 0
    reply_headers: Dict[str, str] = {}
    chunks: List[bytes] = []
    try:
        try:
            response = session.request(
                method,
                url,
                headers=request_headers,
                data=data,
                timeout=(timeout_s, timeout_s),
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.Timeout as error:
            connecting = isinstance(error, requests.exceptions.ConnectTimeout)
            failure = ProviderError(
                "timeout", detail_code=DETAIL_CONNECT_TIMEOUT if connecting else DETAIL_READ_TIMEOUT
            )
        except _INVALID_REQUEST_ERRORS:
            # URL ou cabeçalho que o ``requests`` se recusa a montar: defeito de
            # configuração, não queda do provedor (não deve contar no disjuntor).
            failure = ProviderError("bad_request", detail_code=DETAIL_REQUEST_INVALID)
        except requests.exceptions.RequestException as error:
            failure = ProviderError(
                "network",
                detail_code=DETAIL_CONNECT_FAILED if _never_connected(error) else DETAIL_CONNECTION_LOST,
            )
        except (UnicodeError, ValueError):
            # ``http.client`` recusa cabeçalho com caractere fora de latin-1 ou
            # de controle com UnicodeEncodeError/ValueError, que NÃO são
            # exceções do ``requests``. O pedido nem chegou a ser escrito.
            failure = ProviderError("bad_request", detail_code=DETAIL_REQUEST_INVALID)

        if failure is None:
            status = int(response.status_code)
            reply_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            total = 0
            try:
                for chunk in _body_chunks(response):
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        failure = ProviderError("server_error", status=status, detail_code="response_too_large")
                        break
                    # O timeout de leitura vale por leitura de socket; um
                    # servidor que goteja bytes nunca o dispararia. Este prazo
                    # total, conferido a cada pedaço recebido, sim.
                    if time.perf_counter() > deadline:
                        failure = ProviderError("timeout", status=status, detail_code="deadline_exceeded")
                        break
                    chunks.append(chunk)
            except (requests.exceptions.RequestException, urllib3_errors.HTTPError, OSError) as error:
                # Conexão cortada ou parada no meio do corpo. O status já
                # chegou, então o provedor recebeu (e pode ter cobrado) o pedido.
                if _is_read_timeout(error):
                    failure = ProviderError("timeout", status=status, detail_code=DETAIL_READ_TIMEOUT)
                elif _is_decode_error(error):
                    # Corpo que diz ser gzip/deflate e não é: resposta estragada,
                    # não queda de conexão.
                    failure = ProviderError("server_error", status=status, detail_code="malformed_response")
                else:
                    failure = ProviderError("network", status=status, detail_code=DETAIL_CONNECTION_LOST)
    finally:
        if response is not None:
            response.close()
        session.close()

    if failure is not None:
        raise failure
    latency_ms = int((time.perf_counter() - started) * 1000)
    return HttpReply(status, reply_headers, b"".join(chunks), latency_ms)


def credential_from_env(variable: Optional[str]) -> str:
    """Lê a credencial do ambiente NO MOMENTO da chamada e confere o formato.

    Levanta ``ProviderError("auth")`` sem ``status`` (nenhuma requisição saiu):

    * ``credential_missing``: variável não configurada ou vazia;
    * ``credential_malformed``: o valor tem caractere que não pode ir em um
      cabeçalho HTTP (espaço, quebra de linha, acento, reticências tipográficas
      de uma colagem...). Sem esta conferência, o erro só apareceria dentro do
      ``http.client`` como ``UnicodeEncodeError``, com o valor da chave dentro
      da exceção, e seria confundido com defeito do adaptador.

    A mensagem nunca cita o valor; quem chama loga só o NOME da variável.
    """
    secret = (os.environ.get(variable) or "").strip() if variable else ""
    if not secret:
        raise ProviderError("auth", detail_code=DETAIL_CREDENTIAL_MISSING)
    if not _HEADER_SAFE.match(secret):
        raise ProviderError("auth", detail_code=DETAIL_CREDENTIAL_MALFORMED)
    return secret


def parse_retry_after(headers: Mapping[str, str], now: Optional[datetime] = None) -> Optional[float]:
    """``Retry-After`` em segundos (aceita segundos ou data HTTP), ou ``None``."""
    raw_ms = (headers.get("retry-after-ms") or "").strip()
    if raw_ms:
        try:
            return _clamp_wait(float(raw_ms) / 1000.0)
        except ValueError:
            pass
    raw = (headers.get("retry-after") or "").strip()
    if not raw:
        return None
    try:
        return _clamp_wait(float(raw))
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    return _clamp_wait((moment - reference).total_seconds())


def _clamp_wait(seconds: float) -> Optional[float]:
    if seconds != seconds:  # NaN
        return None
    return max(0.0, min(MAX_RETRY_AFTER_S, seconds))


def dig(value: Any, *path: Any) -> Any:
    """Navega em dict/list aninhados sem levantar exceção. ``None`` se faltar."""
    current = value
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and -len(current) <= key < len(current):
            current = current[key]
        else:
            return None
    return current


def as_int(value: Any) -> Optional[int]:
    """Inteiro não negativo vindo de JSON do provedor, ou ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, Decimal) and value == value.to_integral_value() and value >= 0:
        return int(value)
    return None


def detect_image_mime(data: bytes) -> str:
    """Tipo da imagem pelo conteúdo (nunca pelo nome ou por declaração de terceiros)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


_WIRE_NAME_INVALID = re.compile(r"[^A-Za-z0-9_-]")


class ToolNameCodec:
    """Converte nomes de ferramenta para o formato aceito pelo provedor e de volta.

    As ferramentas da plataforma têm ponto no nome (``finance.read``). OpenAI e
    Anthropic só aceitam ``[A-Za-z0-9_-]{1,64}``. O ponto vira ``__`` na ida; na
    volta o nome original é recuperado por tabela (não por substituição
    inversa), então um nome devolvido pelo modelo que não esteja na tabela
    passa como veio e é rejeitado pelo registro de ferramentas do backend.
    """

    def __init__(self, tools: Sequence[ToolSpec]) -> None:
        self._to_wire: Dict[str, str] = {}
        self._from_wire: Dict[str, str] = {}
        for tool in tools:
            wire = self.wire_name(tool.name)
            if wire in self._from_wire and self._from_wire[wire] != tool.name:
                # Dois nomes diferentes colidindo no provedor: erro de montagem
                # do pedido, não do modelo.
                raise ProviderError("bad_request", detail_code="tool_name_collision")
            self._to_wire[tool.name] = wire
            self._from_wire[wire] = tool.name

    @staticmethod
    def wire_name(name: str) -> str:
        return _WIRE_NAME_INVALID.sub("_", str(name).replace(".", "__"))[:64]

    def encode(self, name: str) -> str:
        return self._to_wire.get(name) or self.wire_name(name)

    def decode(self, wire: str) -> str:
        return self._from_wire.get(wire, wire)


def status_error(status: int, headers: Mapping[str, str]) -> ProviderError:
    """Mapeamento padrão de status HTTP para ``ProviderError``.

    Cada adaptador trata antes os casos próprios do seu provedor e cai aqui
    para o restante.
    """
    retry_after = parse_retry_after(headers)
    if status in (401, 402, 403):
        return ProviderError("auth", status=status)
    if status in (408, 504):
        return ProviderError("timeout", status=status)
    if status == 429:
        return ProviderError("rate_limited", status=status, retry_after_s=retry_after)
    if status == 404:
        return ProviderError("unavailable", status=status, detail_code="model_not_found")
    if status >= 500:
        return ProviderError("server_error", status=status, retry_after_s=retry_after)
    if 300 <= status < 400:
        return ProviderError("unavailable", status=status, detail_code="unexpected_redirect")
    return ProviderError("bad_request", status=status)


def build_default_adapters(settings: Any) -> Dict[str, ProviderAdapter]:
    """Um adaptador por provedor suportado. Nada é conectado aqui."""
    # Import tardio: os módulos dos adaptadores importam os helpers acima.
    from .anthropic import AnthropicAdapter
    from .ollama import OllamaAdapter
    from .openai_compatible import OpenAICompatibleAdapter

    return {
        "ollama": OllamaAdapter(default_base_url=getattr(settings, "ollama_base_url", None)),
        "openai_compatible": OpenAICompatibleAdapter(),
        "anthropic": AnthropicAdapter(),
    }
