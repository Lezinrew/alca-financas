"""Disjuntor (circuit breaker) por rota (contrato, seção 8).

Ideia: se uma rota falhou várias vezes seguidas por motivo transitório (queda,
timeout, 429, 5xx), insistir nela só gasta o orçamento de tentativas de cada
execução e atrasa a resposta. O disjuntor "abre" e a rota deixa de receber
pedidos por um tempo; depois uma SONDA barata decide se ela volta.

Estados, por alias:

* ``closed``   - normal. Falhas transitórias são contadas em uma janela móvel.
* ``open``     - ``circuit_failures`` falhas dentro de ``circuit_window_s``
  abrem o circuito por ``circuit_open_s``. Nenhum pedido vai para a rota.
* ``half_open``- passado o prazo, UMA sonda (``adapter.probe``) é feita. Se
  passar, o circuito fecha; se falhar, reabre por mais ``circuit_open_s``.

A sonda não é inferência: não consome o orçamento de tentativas nem gera custo
de modelo (lista de modelos do provedor).

LIMITAÇÃO IMPORTANTE: o estado vive na memória DO PROCESSO. Com vários workers
(gunicorn, mais de um container), cada um tem o próprio disjuntor: uma rota
caída pode receber até ``circuit_failures`` pedidos POR PROCESSO antes de todos
abrirem, e reiniciar o processo zera a contagem. Isso é aceitável porque o
disjuntor é uma otimização; quem garante o teto de chamadas de cada execução é
o ``AttemptBudget``, e quem garante o teto de custo é o ``BudgetLedger``
(esse sim no banco, compartilhado).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

from ..settings import AiSettings


logger = logging.getLogger("ai.gateway.circuit")

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class _RouteState:
    __slots__ = ("failures", "opened_at", "probing")

    def __init__(self) -> None:
        self.failures: Deque[float] = deque()
        self.opened_at: Optional[float] = None
        self.probing = False


class CircuitBreaker:
    """Disjuntor thread-safe com relógio injetável (monotônico, em segundos)."""

    def __init__(self, settings: AiSettings, clock: Callable[[], float] = time.monotonic) -> None:
        self._threshold = max(1, int(settings.circuit_failures))
        self._window_s = float(settings.circuit_window_s)
        self._open_s = float(settings.circuit_open_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._states: Dict[str, _RouteState] = {}

    def _state_of(self, alias: str) -> _RouteState:
        state = self._states.get(alias)
        if state is None:
            state = self._states[alias] = _RouteState()
        return state

    def _prune(self, state: _RouteState, now: float) -> None:
        while state.failures and now - state.failures[0] > self._window_s:
            state.failures.popleft()

    def state(self, alias: str) -> str:
        """Estado atual, sem efeitos colaterais (não dispara sonda)."""
        with self._lock:
            state = self._states.get(alias)
            if state is None or state.opened_at is None:
                return CLOSED
            if state.probing or self._clock() - state.opened_at >= self._open_s:
                return HALF_OPEN
            return OPEN

    def record_failure(self, alias: str) -> bool:
        """Registra uma falha TRANSITÓRIA. Devolve ``True`` se abriu agora.

        Só falhas transitórias entram aqui. Recusa de conteúdo, pedido inválido
        e credencial rejeitada não dizem nada sobre a saúde da rota.
        """
        now = self._clock()
        with self._lock:
            state = self._state_of(alias)
            if state.opened_at is not None:
                return False
            state.failures.append(now)
            self._prune(state, now)
            if len(state.failures) < self._threshold:
                return False
            state.opened_at = now
            state.failures.clear()
        logger.warning("circuit_opened alias=%s failures=%d open_s=%d", alias, self._threshold, int(self._open_s))
        return True

    def record_success(self, alias: str) -> None:
        """Sucesso em circuito fechado NÃO zera a janela.

        O contrato define a regra como "N falhas em X segundos". Uma rota que
        alterna sucesso e falha continua instável e deve poder abrir.
        """
        return None

    def acquire(self, alias: str, probe: Optional[Callable[[], Any]] = None) -> bool:
        """A rota pode receber um pedido agora?

        * fechado: sim;
        * aberto dentro do prazo: não;
        * prazo vencido: executa ``probe`` (uma thread por vez) e decide.

        ``probe`` devolve verdadeiro/falso; exceção conta como falha. Uma sonda
        que levante ``NotImplementedError`` (adaptador sem sonda) libera um
        pedido de teste em vez de manter a rota fechada para sempre.
        """
        with self._lock:
            state = self._states.get(alias)
            if state is None or state.opened_at is None:
                return True
            if self._clock() - state.opened_at < self._open_s:
                return False
            if state.probing:
                # Outra thread já está sondando: quem chega agora não espera
                # nem dispara uma segunda sonda.
                return False
            state.probing = True

        healthy = False
        try:
            # Fora do lock: a sonda faz rede e não pode travar as outras rotas.
            healthy = self._run_probe(probe)
        finally:
            with self._lock:
                state = self._state_of(alias)
                state.probing = False
                if healthy:
                    state.opened_at = None
                    state.failures.clear()
                else:
                    state.opened_at = self._clock()
        logger.info("circuit_probe alias=%s healthy=%s", alias, "yes" if healthy else "no")
        return healthy

    @staticmethod
    def _run_probe(probe: Optional[Callable[[], Any]]) -> bool:
        if probe is None:
            return True
        try:
            return bool(probe())
        except NotImplementedError:
            return True
        except Exception:  # noqa: BLE001 - qualquer falha da sonda mantém o circuito aberto
            return False

    def reset(self, alias: Optional[str] = None) -> None:
        """Fecha o circuito de uma rota (ou de todas). Uso operacional e testes."""
        with self._lock:
            if alias is None:
                self._states.clear()
            else:
                self._states.pop(alias, None)

    def snapshot(self) -> Dict[str, str]:
        """Estado de cada rota conhecida, para diagnóstico."""
        with self._lock:
            aliases = list(self._states)
        return {alias: self.state(alias) for alias in aliases}
