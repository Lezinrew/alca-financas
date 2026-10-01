"""Montagem do gateway para os testes: rotas, contexto, relógio e fixtures.

Os testes usam o gateway, o registro, o disjuntor, o livro de orçamento e os
adaptadores REAIS. O que é de mentira fica fora do componente: o provedor
(``gateway_server.FakeProvider``, um servidor HTTP local) e o relógio/espera
(para não dormir de verdade).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

import pytest
from psycopg2 import pool as pg_pool

from services.ai.gateway.adapters import build_default_adapters
from services.ai.gateway.base import (
    LOCALITY_EXTERNAL,
    LOCALITY_LOCAL,
    PURPOSE_READ,
    TASK_COMPLEX,
    TASK_SIMPLE,
    TASK_VISION,
    ChatMessage,
    ModelRequest,
    ModelRoute,
    ToolSpec,
)
from services.ai.gateway.budget import BudgetLedger
from services.ai.gateway.circuit import CircuitBreaker
from services.ai.gateway.gateway import DefaultModelGateway
from services.ai.gateway.models import ModelRegistry
from services.ai.settings import AiSettings
from services.ai.types import ExecutionContext, Privacy, utc_now

from .gateway_server import FakeProvider, Reply, ollama_model, ollama_tags


# Digests sintéticos (64 hex). Não correspondem a nenhum modelo real.
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
LOCAL_MODEL = "modelo-teste:1b"
ALL_TASKS = (TASK_SIMPLE, TASK_COMPLEX, TASK_VISION)
ALL_PRIVACY = ("local_only", "cloud_redacted", "cloud_allowed")
EXTERNAL_PRIVACY = ("cloud_redacted", "cloud_allowed")
# Nome da variável de ambiente usada como credencial nos testes (o valor é
# definido por teste, com monkeypatch, e é sempre fictício).
CREDENTIAL_ENV = "AI_TEST_FAKE_PROVIDER_CREDENTIAL"

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "minLength": 1},
        "confianca": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["categoria", "confianca"],
    "additionalProperties": False,
}
VALID_ANSWER = '{"categoria": "moradia", "confianca": 90}'

READ_TOOL = ToolSpec(
    name="finance.read",
    description="Consulta enumerada de dados financeiros.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
)


def gateway_settings(**overrides: Any) -> AiSettings:
    values: Dict[str, Any] = dict(
        enabled=True,
        cloud_enabled=False,
        allow_candidate_models=False,
        inference_timeout_s=5,
        max_inference_calls_per_step=3,
        circuit_failures=3,
        circuit_window_s=60,
        circuit_open_s=60,
        budget_currency="USD",
    )
    values.update(overrides)
    return AiSettings(**values)


def make_ctx(privacy: Privacy = Privacy.LOCAL_ONLY, run_id: Optional[str] = None) -> ExecutionContext:
    """Contexto sintético para testes sem banco."""
    return ExecutionContext(
        tenant_id=str(uuid.uuid4()),
        actor_id=str(uuid.uuid4()),
        financial_space_id=str(uuid.uuid4()),
        space_kind="personal",
        space_name="Pessoal",
        allowed_account_ids=frozenset(),
        channel="web",
        privacy=privacy,
        request_id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        run_id=run_id or str(uuid.uuid4()),
    )


def local_route(alias: str, base_url: str, priority: int = 10, **overrides: Any) -> ModelRoute:
    """Rota Ollama local já homologada (para o teste)."""
    values: Dict[str, Any] = dict(
        alias=alias,
        provider="ollama",
        model_id=LOCAL_MODEL,
        locality=LOCALITY_LOCAL,
        priority=priority,
        task_classes=ALL_TASKS,
        supports_tools=True,
        supports_json=True,
        supports_vision=True,
        context_window=8192,
        state="approved",
        approved_purposes=(PURPOSE_READ, "write"),
        privacy=ALL_PRIVACY,
        base_url=base_url,
        digest=DIGEST_A,
        evidence="homologacao-sintetica-de-teste",
        extra={},
    )
    values.update(overrides)
    return ModelRoute(**values)


def external_route(alias: str, base_url: str, priority: int = 50, provider: str = "openai_compatible",
                   **overrides: Any) -> ModelRoute:
    """Rota externa já homologada (para o teste), apontando para o servidor local."""
    values: Dict[str, Any] = dict(
        alias=alias,
        provider=provider,
        model_id="modelo-externo-teste",
        locality=LOCALITY_EXTERNAL,
        priority=priority,
        task_classes=ALL_TASKS,
        supports_tools=True,
        supports_json=True,
        supports_vision=True,
        context_window=100000,
        state="approved",
        approved_purposes=(PURPOSE_READ, "write"),
        privacy=EXTERNAL_PRIVACY,
        base_url=base_url,
        credential_env=CREDENTIAL_ENV,
        max_cost_micros_per_call=1000,
        input_cost_micros_per_mtok=2_000_000,
        output_cost_micros_per_mtok=10_000_000,
        evidence="homologacao-sintetica-de-teste",
        extra={},
    )
    values.update(overrides)
    return ModelRoute(**values)


def serve_tags(server: FakeProvider, model: str = LOCAL_MODEL, digest: str = DIGEST_A, **extra: Any) -> None:
    """Programa ``GET /api/tags`` com o modelo local presente."""
    server.always("GET /api/tags", Reply(200, ollama_tags(ollama_model(model, digest, **extra))))


def user_request(text: str = "Classifique a despesa sintética.", **overrides: Any) -> ModelRequest:
    values: Dict[str, Any] = dict(task_class=TASK_SIMPLE, messages=[ChatMessage(role="user", content=text)])
    values.update(overrides)
    return ModelRequest(**values)


class FakeClock:
    """Relógio monotônico controlado pelo teste; ``sleep`` avança o relógio."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: List[float] = []

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Assembly:
    """Gateway montado com as peças reais, expostas para inspeção."""

    def __init__(self, gateway: DefaultModelGateway, circuit: CircuitBreaker, ledger: Optional[BudgetLedger],
                 clock: FakeClock, registry: ModelRegistry) -> None:
        self.gateway = gateway
        self.circuit = circuit
        self.ledger = ledger
        self.clock = clock
        self.registry = registry


def assemble(
    routes: Sequence[ModelRoute],
    settings: Optional[AiSettings] = None,
    pool: Any = None,
    ledger_clock: Optional[Callable[[], datetime]] = None,
    **gateway_options: Any,
) -> Assembly:
    settings = settings or gateway_settings()
    clock = FakeClock()
    registry = ModelRegistry(list(routes), settings)
    circuit = CircuitBreaker(settings, clock=clock)
    ledger = BudgetLedger(pool, settings, clock=ledger_clock or utc_now) if pool is not None else None
    gateway = DefaultModelGateway(
        registry,
        build_default_adapters(settings),
        circuit,
        ledger,
        settings,
        clock=clock,
        sleep=clock.sleep,
        **gateway_options,
    )
    return Assembly(gateway, circuit, ledger, clock, registry)


def outcomes(attempts: Sequence[Any]) -> List[str]:
    """Trilha compacta: ``["alias:desfecho", ...]``."""
    return ["%s:%s" % (item.alias, item.outcome) for item in attempts]


def with_privacy(ctx: ExecutionContext, privacy: Privacy) -> ExecutionContext:
    return replace(ctx, privacy=privacy)


@pytest.fixture()
def providers():
    """Fábrica de servidores de teste; todos são fechados ao final."""
    created: List[FakeProvider] = []

    def factory() -> FakeProvider:
        server = FakeProvider()
        created.append(server)
        return server

    try:
        yield factory
    finally:
        for server in created:
            server.close()


WARM_CONNECTIONS = 10


@pytest.fixture()
def warm_pool(ai_database, pool):
    """Pool com conexões JÁ ABERTAS, para os testes de concorrência.

    O pool padrão dos testes abre uma conexão nova a cada ``getconn`` e faz
    isso dentro de um lock; as threads acabariam entrando no banco uma de cada
    vez e o teste "passaria" mesmo sem a reserva ser atômica. Com as conexões
    prontas, as transações de fato se sobrepõem. Depende de ``pool`` para o
    banco já ter sido esvaziado.
    """
    warm = pg_pool.ThreadedConnectionPool(WARM_CONNECTIONS, WARM_CONNECTIONS + 4, dsn=ai_database.app_dsn)
    try:
        yield warm
    finally:
        warm.closeall()


def slow_clock(delay_s: float = 0.05) -> Callable[[], datetime]:
    """Relógio do livro de orçamento que demora um pouco para responder.

    O livro consulta o relógio DENTRO da transação de reserva, entre ler os
    tetos e somar o que já foi gasto. A demora alarga essa janela: sem o lock
    de linha, todas as threads leriam o mesmo saldo e todas reservariam.
    """

    def clock() -> datetime:
        time.sleep(delay_s)
        return utc_now()

    return clock
