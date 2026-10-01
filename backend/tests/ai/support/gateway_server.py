"""Servidor HTTP local e programável que faz o papel de um provedor de modelos.

É um servidor de verdade (``http.server`` em uma thread, em 127.0.0.1): os
adaptadores falam com ele por HTTP real, com timeout real. Cada teste programa,
por rota (``"POST /api/chat"``), a fila de respostas: status, cabeçalhos, atraso
e corpo. O servidor CONTA e guarda cada requisição recebida, e é sobre essa
contagem que os testes afirmam coisas como "nenhuma requisição chegou ao
provedor externo".

Emula as rotas usadas pelos adaptadores:

* Ollama:            ``POST /api/chat`` e ``GET /api/tags``
* OpenAI-compatível: ``POST /chat/completions`` e ``GET /models``
* Anthropic:         ``POST /v1/messages`` e ``GET /v1/models``

Tudo aqui é sintético.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional


class Reply:
    """Uma resposta programada.

    Além de status, cabeçalhos, atraso e corpo, a resposta pode se comportar
    mal de propósito, para os testes de transporte:

    * ``drop=True``: lê o pedido e fecha a conexão sem responder nada;
    * ``truncate_at=N``: anuncia o corpo inteiro em ``Content-Length``, envia
      só os primeiros ``N`` bytes e fecha (conexão perdida no meio do corpo);
    * ``drip_s=X``: envia o corpo aos poucos, ``drip_bytes`` bytes a cada ``X``
      segundos (cada leitura do cliente recebe algo, mas o corpo nunca acaba
      dentro do prazo).
    """

    def __init__(
        self,
        status: int = 200,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        delay_s: float = 0.0,
        hold: Optional[threading.Event] = None,
        drop: bool = False,
        truncate_at: Optional[int] = None,
        drip_s: float = 0.0,
        drip_bytes: int = 1,
    ) -> None:
        self.status = status
        self.body = body
        self.headers = dict(headers or {})
        self.delay_s = delay_s
        # Quando presente, a resposta só é enviada depois que o teste sinalizar.
        self.hold = hold
        self.drop = drop
        self.truncate_at = truncate_at
        self.drip_s = drip_s
        self.drip_bytes = max(1, int(drip_bytes))

    def payload(self) -> bytes:
        if self.body is None:
            return b""
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")


class Recorded:
    """Uma requisição recebida."""

    def __init__(self, method: str, path: str, headers: Dict[str, str], raw: bytes) -> None:
        self.method = method
        self.path = path
        self.headers = headers  # nomes em minúsculas
        self.raw = raw

    @property
    def key(self) -> str:
        return "%s %s" % (self.method, self.path)

    @property
    def json(self) -> Any:
        return json.loads(self.raw.decode("utf-8")) if self.raw else None


class FakeProvider:
    """Provedor de mentira com respostas programáveis e contagem por rota."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: Dict[str, List[Reply]] = {}
        self._defaults: Dict[str, Reply] = {}
        self._recorded: List[Recorded] = []
        self._stop = threading.Event()
        provider = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_args: Any) -> None:  # silencia o log padrão
                return None

            def _serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                path = self.path.split("?", 1)[0]
                recorded = Recorded(
                    self.command,
                    path,
                    {str(name).lower(): str(value) for name, value in self.headers.items()},
                    raw,
                )
                reply = provider._next(recorded)
                if reply.delay_s:
                    # Espera interrompível: fechar o servidor libera o handler.
                    provider._stop.wait(reply.delay_s)
                if reply.hold is not None:
                    while not reply.hold.is_set() and not provider._stop.is_set():
                        reply.hold.wait(0.05)
                if reply.drop:
                    # Fecha sem responder: o handler retorna e o servidor
                    # encerra a conexão (o protocolo aqui é HTTP/1.0).
                    return None
                payload = reply.payload()
                try:
                    self.send_response(reply.status)
                    headers = {"Content-Type": "application/json"}
                    headers.update(reply.headers)
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    if reply.truncate_at is not None:
                        payload = payload[: reply.truncate_at]
                    if reply.drip_s > 0:
                        for start in range(0, len(payload), reply.drip_bytes):
                            self.wfile.write(payload[start:start + reply.drip_bytes])
                            self.wfile.flush()
                            # Espera interrompível, como a de ``delay_s``.
                            if provider._stop.wait(reply.drip_s):
                                return None
                    else:
                        self.wfile.write(payload)
                except OSError:
                    # O cliente desistiu (timeout): esperado nos testes de atraso.
                    return None

            do_GET = _serve
            do_POST = _serve

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()

    # -- programação -------------------------------------------------------

    @property
    def base_url(self) -> str:
        return "http://127.0.0.1:%d" % self._server.server_address[1]

    def enqueue(self, key: str, *replies: Reply) -> "FakeProvider":
        """Respostas consumidas uma por requisição, na ordem."""
        with self._lock:
            self._queues.setdefault(key, []).extend(replies)
        return self

    def always(self, key: str, reply: Reply) -> "FakeProvider":
        """Resposta usada quando a fila da rota está vazia."""
        with self._lock:
            self._defaults[key] = reply
        return self

    def _next(self, recorded: Recorded) -> Reply:
        with self._lock:
            self._recorded.append(recorded)
            queue = self._queues.get(recorded.key)
            if queue:
                return queue.pop(0)
            default = self._defaults.get(recorded.key)
        if default is not None:
            return default
        # Rota não programada: o teste esqueceu algo. 501 torna isso visível.
        return Reply(501, {"error": "rota nao programada no servidor de teste"})

    # -- observação --------------------------------------------------------

    def requests(self, key: Optional[str] = None) -> List[Recorded]:
        with self._lock:
            return [item for item in self._recorded if key is None or item.key == key]

    def count(self, key: Optional[str] = None) -> int:
        return len(self.requests(key))

    def settled_count(
        self,
        key: Optional[str] = None,
        at_least: int = 1,
        timeout_s: float = 10.0,
        settle_s: float = 0.3,
    ) -> int:
        """Contagem depois de ESTABILIZAR. Use após um timeout do cliente.

        ``count()`` logo depois de o cliente desistir é uma corrida: com a
        máquina carregada, a thread do servidor pode ainda não ter registrado a
        requisição (a contagem lida seria 0) quando o cliente já estourou o
        prazo. Aqui espera-se a contagem chegar a ``at_least`` (com prazo) e
        depois mais um instante: se houvesse um retry escondido, a segunda
        requisição apareceria nesse intervalo e a contagem voltaria maior.
        """
        deadline = time.monotonic() + timeout_s
        while self.count(key) < at_least and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(settle_s)
        return self.count(key)

    def close(self) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def refused_base_url() -> str:
    """URL de uma porta local em que ninguém escuta (conexão recusada)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return "http://127.0.0.1:%d" % port


# ---------------------------------------------------------------------------
# Corpos de resposta no formato de cada provedor (valores sintéticos)
# ---------------------------------------------------------------------------

def ollama_chat(
    content: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    model: str = "modelo-teste:1b",
    done_reason: str = "stop",
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "model": model,
        "created_at": "2026-10-01T12:00:00Z",
        "message": message,
        "done": True,
        "done_reason": done_reason,
        "total_duration": 1500000000,
        "load_duration": 200000000,
        "prompt_eval_count": 42,
        "prompt_eval_duration": 300000000,
        "eval_count": 17,
        "eval_duration": 900000000,
    }


def ollama_tags(*models: Dict[str, Any]) -> Dict[str, Any]:
    return {"models": list(models)}


def ollama_model(name: str, digest: str, **extra: Any) -> Dict[str, Any]:
    entry = {"name": name, "model": name, "digest": digest, "size": 1000, "details": {"family": "teste"}}
    entry.update(extra)
    return entry


def openai_chat(
    content: Optional[str] = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: str = "stop",
    model: str = "modelo-externo-teste",
    usage: Optional[Dict[str, Any]] = None,
    refusal: Optional[str] = None,
    **top_level: Any,
) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    if refusal is not None:
        message["refusal"] = refusal
    body: Dict[str, Any] = {
        "id": "chatcmpl-teste",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": usage if usage is not None else {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }
    body.update(top_level)
    return body


def anthropic_message(
    text: Optional[str] = "",
    tool_uses: Optional[List[Dict[str, Any]]] = None,
    stop_reason: str = "end_turn",
    model: str = "modelo-anthropic-teste",
    usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for item in tool_uses or []:
        content.append({"type": "tool_use", **item})
    return {
        "id": "msg_teste",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "usage": usage if usage is not None else {"input_tokens": 1000, "output_tokens": 200},
    }
