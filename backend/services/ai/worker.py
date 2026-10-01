"""Worker da fila de execuções e entrega do outbox.

Uso em produção::

    cd backend && python -m services.ai.worker

O worker assume uma execução por vez (``runs.claim_next``), mantém o lease vivo
enquanto o orquestrador trabalha e nunca deixa uma exceção de negócio escapar:
falha vira estado ``failed`` com erro seguro. Se o processo morrer, nada é
finalizado; o lease vence e outro worker retoma a execução dos checkpoints.

Entrega do outbox (contrato, seção 9): pode se repetir (pelo menos uma vez) e o
consumidor deduplica por ``dedup_key``. Reentregar uma notificação NUNCA
reexecuta o efeito financeiro — este módulo só chama o ``handler`` de entrega,
jamais uma ferramenta.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
import uuid
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from . import runs
from .db import queue_tx, scoped_tx
from .settings import AiSettings


logger = logging.getLogger("ai.worker")

OutboxHandler = Callable[[Dict[str, Any]], None]

# Enquanto uma entrega está em andamento, a mensagem fica invisível para os
# outros workers por este tempo. Se o worker morrer, ela reaparece sozinha.
OUTBOX_VISIBILITY_S = 120
OUTBOX_MAX_ATTEMPTS = 8
OUTBOX_BACKOFF_BASE_S = 30
OUTBOX_BACKOFF_MAX_S = 3600


def default_owner() -> str:
    """Identidade única deste processo: host, pid e sufixo aleatório."""
    return "worker-%s-%d-%s" % (socket.gethostname()[:40], os.getpid(), uuid.uuid4().hex[:8])


class _LeaseKeeper(threading.Thread):
    """Renova o lease em segundo plano enquanto a execução está em andamento.

    Uma inferência pode levar mais que o lease (até 3 tentativas de 60 s contra
    um lease de 90 s). Sem a renovação, outro worker assumiria uma execução
    que não caiu. Se o processo morrer, esta thread morre junto e o lease
    vence — que é exatamente o sinal de "worker caiu".

    A renovação tem limite. Prazo e cancelamento são aplicados pelo
    orquestrador entre uma ação e outra; se uma ferramenta ou o modelo nunca
    retornam, essa checagem não acontece e uma renovação incondicional
    seguraria a execução em ``running`` para sempre. Por isso, passado um lease
    inteiro desde o vencimento do prazo (ou desde o pedido de cancelamento),
    esta thread para de renovar: o lease vence, outro worker assume e encerra a
    execução; o worker travado descobre pela cerca de lease, na próxima
    gravação, que perdeu a posse.
    """

    def __init__(self, pool, run_id: str, tenant_id: str, owner: str, lease_seconds: int) -> None:
        super().__init__(name="ai-lease-%s" % str(run_id)[:8], daemon=True)
        self._pool = pool
        self._run_id = run_id
        self._tenant_id = tenant_id
        self._owner = owner
        self._lease_seconds = lease_seconds
        self._interval = max(0.05, lease_seconds / 3.0)
        self._stop_event = threading.Event()
        self.renewals = 0
        # None: ainda renovando | "lost": posse perdida | "overdue": parou de
        # renovar porque o prazo ou o cancelamento passaram da tolerância.
        self.stopped_reason: Optional[str] = None

    def run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                # Tolerância de um lease: tempo para o orquestrador encerrar a
                # execução por conta própria depois do prazo ou do cancelamento.
                state = runs.heartbeat(
                    self._pool, self._run_id, self._tenant_id, self._owner, self._lease_seconds,
                    grace_seconds=self._lease_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - banco indisponível: tenta de novo
                logger.warning("lease_renew_error run_id=%s error_type=%s", self._run_id, type(exc).__name__)
                continue
            if state is None:
                # A execução terminou ou outro worker assumiu. O orquestrador
                # descobre na próxima escrita (cerca por lease) e para.
                self.stopped_reason = "lost"
                return
            if state["overdue"]:
                self.stopped_reason = "overdue"
                logger.warning(
                    "lease_renew_stopped run_id=%s deadline_passed=%s cancel_requested=%s",
                    self._run_id, state["deadline_passed"], state["cancel_requested"],
                )
                return
            self.renewals += 1

    def stop(self) -> None:
        self._stop_event.set()
        if self.is_alive():
            self.join(timeout=5)


class Worker:
    def __init__(
        self,
        pool,
        settings: AiSettings,
        orchestrator,
        owner: Optional[str] = None,
        outbox_handler: Optional[OutboxHandler] = None,
    ) -> None:
        self._pool = pool
        self._settings = settings
        self._orchestrator = orchestrator
        self.owner = owner or settings.worker_id or default_owner()
        self._outbox_handler = outbox_handler

    def run_once(self) -> Optional[str]:
        """Assume e executa uma execução. Devolve o ``run_id`` ou ``None`` se a fila está vazia."""
        claimed = runs.claim_next(self._pool, self.owner, self._settings.lease_seconds)
        if claimed is None:
            return None
        run_id, tenant_id = claimed["run_id"], claimed["tenant_id"]
        keeper = _LeaseKeeper(self._pool, run_id, tenant_id, self.owner, self._settings.lease_seconds)
        keeper.start()
        try:
            self._orchestrator.execute(run_id, tenant_id, self.owner)
        except Exception as exc:  # noqa: BLE001
            # O orquestrador já transforma falha em estado. Chegar aqui significa
            # que nem o estado final pôde ser gravado (ex.: banco fora): a
            # execução continua "running" e será retomada quando o lease vencer.
            logger.error("run_execute_error run_id=%s error_type=%s", run_id, type(exc).__name__)
        finally:
            keeper.stop()
        return run_id

    def run_forever(self, stop_event: threading.Event, idle_sleep: float = 1.0) -> None:
        """Laço principal. Para quando ``stop_event`` é sinalizado."""
        logger.info("worker_started owner=%s", self.owner)
        while not stop_event.is_set():
            worked = False
            try:
                worked = self.run_once() is not None
                if self._outbox_handler is not None:
                    worked = deliver_outbox_once(self._pool, self._outbox_handler) is not None or worked
            except Exception as exc:  # noqa: BLE001 - o laço não pode morrer por uma falha pontual
                logger.error("worker_loop_error owner=%s error_type=%s", self.owner, type(exc).__name__)
            if not worked:
                stop_event.wait(idle_sleep)
        logger.info("worker_stopped owner=%s", self.owner)


def _backoff_seconds(attempts: int) -> int:
    return min(OUTBOX_BACKOFF_MAX_S, OUTBOX_BACKOFF_BASE_S * (2 ** max(0, attempts - 1)))


def deliver_outbox_once(
    pool,
    handler: OutboxHandler,
    *,
    visibility_s: int = OUTBOX_VISIBILITY_S,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
) -> Optional[str]:
    """Entrega uma mensagem pendente do outbox. Devolve o id tratado ou ``None``.

    Três passos, cada um em sua transação:

    1. reserva (``queue_tx`` + ``FOR UPDATE SKIP LOCKED``): escolhe uma mensagem
       pendente e a torna invisível por ``visibility_s``. A linha continua
       ``pending``: se o worker morrer agora, ela volta sozinha;
    2. entrega: ``handler(mensagem)`` fora de qualquer transação (pode ser uma
       chamada HTTP demorada);
    3. confirmação no escopo do tenant: ``delivered``, ou reagendamento com
       backoff exponencial; depois de ``max_attempts`` vira ``failed``.

    Se o worker cair entre 2 e 3, a mensagem é entregue de novo: por isso o
    ``handler`` recebe ``dedup_key`` e deve ignorar o que já recebeu.
    """
    with queue_tx(pool) as cursor:
        cursor.execute(
            """
            WITH candidate AS (
                SELECT id FROM ai_outbox
                WHERE status = 'pending' AND available_at <= now()
                ORDER BY available_at, created_at, id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE ai_outbox AS o
            SET attempts = o.attempts + 1,
                available_at = now() + make_interval(secs => %s)
            FROM candidate
            WHERE o.id = candidate.id
            RETURNING o.id, o.tenant_id, o.topic, o.payload, o.dedup_key, o.operation_id, o.run_id, o.attempts
            """,
            (int(visibility_s),),
        )
        row = cursor.fetchone()
    if row is None:
        return None

    outbox_id, tenant_id, attempts = str(row["id"]), str(row["tenant_id"]), int(row["attempts"])
    message = {
        "id": outbox_id,
        "tenant_id": tenant_id,
        "topic": row["topic"],
        "payload": row["payload"],
        "dedup_key": row["dedup_key"],
        "operation_id": str(row["operation_id"]) if row["operation_id"] else None,
        "run_id": str(row["run_id"]) if row["run_id"] else None,
        "attempts": attempts,
    }
    try:
        handler(message)
    except Exception as exc:  # noqa: BLE001 - falha de entrega nunca derruba o worker
        # Só o tipo da exceção vai para o banco e para o log: a mensagem dela
        # pode conter corpo de resposta de um serviço externo.
        code = type(exc).__name__[:60]
        exhausted = attempts >= max_attempts
        with scoped_tx(pool, tenant_id) as cursor:
            cursor.execute(
                """
                UPDATE ai_outbox
                SET status = %s, last_error_code = %s,
                    available_at = now() + make_interval(secs => %s)
                WHERE id = %s AND tenant_id = %s AND status = 'pending'
                """,
                ("failed" if exhausted else "pending", code, _backoff_seconds(attempts), outbox_id, tenant_id),
            )
        logger.warning(
            "outbox_delivery_failed outbox_id=%s topic=%s attempts=%d exhausted=%s error_type=%s",
            outbox_id, message["topic"], attempts, exhausted, code,
        )
        return outbox_id

    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            UPDATE ai_outbox
            SET status = 'delivered', delivered_at = now(), last_error_code = NULL
            WHERE id = %s AND tenant_id = %s AND status = 'pending'
            """,
            (outbox_id, tenant_id),
        )
    logger.info("outbox_delivered outbox_id=%s topic=%s attempts=%d", outbox_id, message["topic"], attempts)
    return outbox_id


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    """Ponto de entrada de ``python -m services.ai.worker``."""
    parser = argparse.ArgumentParser(prog="services.ai.worker", description="Worker da plataforma de IA")
    parser.add_argument("--once", action="store_true", help="processa no máximo uma execução e sai")
    parser.add_argument("--idle-sleep", type=float, default=1.0, help="espera (s) com a fila vazia")
    options = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = AiSettings.from_env(env)
    if not settings.enabled:
        # Pausar a IA não é erro: o app financeiro segue funcionando sem worker.
        logger.info("worker_not_started reason=ai_disabled")
        return 0

    # Importação tardia: montar a plataforma abre pool e lê configuração. Isso só
    # deve acontecer quando o worker realmente vai rodar, nunca no import.
    try:
        from services.ai.platform import build_platform
    except ImportError:
        logger.error("worker_not_started reason=platform_unavailable")
        return 2

    try:
        from database.v2_connection import init_v2_pool

        platform = build_platform(init_v2_pool(), settings)
    except Exception as exc:
        logger.error("worker_not_started reason=platform_initialization_failed error_type=%s", type(exc).__name__)
        return 2
    worker = getattr(platform, "worker", None)
    if worker is None:
        worker = Worker(platform.pool, platform.settings, platform.orchestrator)

    if options.once:
        worker.run_once()
        return 0

    stop_event = threading.Event()

    def request_stop(signum, frame) -> None:  # noqa: ARG001
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), request_stop)
            except ValueError:
                pass  # fora da thread principal (ex.: testes)
    worker.run_forever(stop_event, idle_sleep=max(0.05, options.idle_sleep))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
