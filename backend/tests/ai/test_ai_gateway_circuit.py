"""Disjuntor por rota: abre com N falhas na janela, sonda decide o fechamento."""

from __future__ import annotations

import threading

import pytest

from services.ai.gateway.circuit import CLOSED, HALF_OPEN, OPEN, CircuitBreaker

from .support.gateway_harness import FakeClock, gateway_settings


pytestmark = pytest.mark.unit


def breaker(**overrides):
    clock = FakeClock()
    settings = gateway_settings(circuit_failures=3, circuit_window_s=60, circuit_open_s=60, **overrides)
    return CircuitBreaker(settings, clock=clock), clock


def test_opens_only_after_n_failures_inside_the_window():
    circuit, clock = breaker()
    assert circuit.record_failure("rota") is False
    assert circuit.record_failure("rota") is False
    assert circuit.state("rota") == CLOSED and circuit.acquire("rota") is True
    assert circuit.record_failure("rota") is True
    assert circuit.state("rota") == OPEN
    assert circuit.acquire("rota", lambda: pytest.fail("não deve sondar com o circuito recém-aberto")) is False
    # Outra rota não é afetada.
    assert circuit.state("outra") == CLOSED and circuit.acquire("outra") is True


def test_failures_outside_the_window_do_not_count():
    circuit, clock = breaker()
    circuit.record_failure("rota")
    circuit.record_failure("rota")
    clock.advance(61)
    assert circuit.record_failure("rota") is False
    assert circuit.state("rota") == CLOSED
    # Duas falhas recentes + a de agora: agora sim abre.
    clock.advance(1)
    circuit.record_failure("rota")
    assert circuit.record_failure("rota") is True


def test_success_does_not_erase_the_failure_window():
    circuit, _ = breaker()
    circuit.record_failure("rota")
    circuit.record_failure("rota")
    circuit.record_success("rota")
    assert circuit.record_failure("rota") is True


def test_open_circuit_blocks_until_timeout_then_probe_decides():
    circuit, clock = breaker()
    for _ in range(3):
        circuit.record_failure("rota")
    probes = []

    def failing_probe():
        probes.append("falhou")
        return False

    clock.advance(59)
    assert circuit.acquire("rota", failing_probe) is False and probes == []

    clock.advance(1)
    assert circuit.state("rota") == HALF_OPEN
    assert circuit.acquire("rota", failing_probe) is False
    assert probes == ["falhou"]
    # Sonda falhou: reabre por mais um período inteiro.
    assert circuit.state("rota") == OPEN
    clock.advance(59)
    assert circuit.acquire("rota", failing_probe) is False and probes == ["falhou"]

    clock.advance(1)
    assert circuit.acquire("rota", lambda: True) is True
    assert circuit.state("rota") == CLOSED
    # Fechado de novo, a contagem recomeça do zero.
    assert circuit.record_failure("rota") is False


def test_probe_exception_keeps_circuit_open_and_missing_probe_allows_trial():
    circuit, clock = breaker()
    for _ in range(3):
        circuit.record_failure("rota")
    clock.advance(60)

    def broken_probe():
        raise RuntimeError("sonda com defeito")

    assert circuit.acquire("rota", broken_probe) is False
    assert circuit.state("rota") == OPEN

    clock.advance(60)

    def no_probe():
        raise NotImplementedError

    assert circuit.acquire("rota", no_probe) is True


def test_only_one_thread_probes_in_half_open():
    circuit, clock = breaker()
    for _ in range(3):
        circuit.record_failure("rota")
    clock.advance(60)

    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_probe():
        calls.append(1)
        started.set()
        release.wait(5)
        return True

    results = []
    first = threading.Thread(target=lambda: results.append(circuit.acquire("rota", slow_probe)))
    first.start()
    assert started.wait(5)
    # Enquanto a primeira sonda está em andamento, ninguém mais passa nem sonda.
    assert circuit.acquire("rota", slow_probe) is False
    release.set()
    first.join(5)
    assert results == [True] and len(calls) == 1
    assert circuit.state("rota") == CLOSED


def test_concurrent_failures_are_counted_without_loss():
    settings = gateway_settings(circuit_failures=50, circuit_window_s=60, circuit_open_s=60)
    circuit = CircuitBreaker(settings, clock=FakeClock())
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait(5)
        for _ in range(5):
            circuit.record_failure("rota")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    # 10 threads x 5 falhas = exatamente o limiar de 50.
    assert circuit.state("rota") == OPEN
    assert circuit.snapshot() == {"rota": OPEN}
    circuit.reset("rota")
    assert circuit.state("rota") == CLOSED
