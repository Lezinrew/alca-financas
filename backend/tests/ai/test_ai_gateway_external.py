"""Rotas externas: privacidade (AC-07), custo e segredos (AC-13).

Tudo real dentro do componente: gateway, registro, disjuntor, livro de orçamento
(PostgreSQL) e adaptadores. O "provedor externo" é um servidor HTTP local que
conta as requisições recebidas; nenhuma API paga é chamada.
"""

from __future__ import annotations

import json
import logging
import threading
import time

import pytest
from psycopg2 import pool as pg_pool

from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.gateway.adapters import MAX_RESPONSE_BYTES, build_default_adapters
from services.ai.gateway.base import AttemptBudget
from services.ai.gateway.gateway import DefaultModelGateway
from services.ai.gateway.models import Eligibility
from services.ai.types import Privacy

from .support import seed
from .support.gateway_harness import (
    ANSWER_SCHEMA,
    CREDENTIAL_ENV,
    VALID_ANSWER,
    assemble,
    external_route,
    gateway_settings,
    local_route,
    outcomes,
    serve_tags,
    slow_clock,
    user_request,
)
from .support.gateway_harness import providers  # noqa: F401 - fixture do pytest
from .support.gateway_harness import warm_pool  # noqa: F401 - fixture do pytest
from .support.gateway_server import Reply, anthropic_message, ollama_chat, openai_chat, refused_base_url


pytestmark = pytest.mark.integration

CHAT = "POST /api/chat"
COMPLETIONS = "POST /chat/completions"
MESSAGES = "POST /v1/messages"
# Valor fictício usado como credencial. Não é chave de nenhum serviço.
FAKE_SECRET = "credencial-ficticia-apenas-para-teste-externo"
GENEROUS = 10_000_000


@pytest.fixture()
def credential(monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_SECRET)
    return FAKE_SECRET


def ctx_for(world, pool, privacy=Privacy.CLOUD_ALLOWED):
    return world.context(pool, privacy=privacy).with_run(seed.new_id())


def cloud_settings(**overrides):
    values = dict(cloud_enabled=True)
    values.update(overrides)
    return gateway_settings(**values)


def budget_rows(pool, tenant_id):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT route_alias, reserved_micros, actual_micros, status FROM ai_budget_entries "
            "WHERE tenant_id = %s ORDER BY created_at, id",
            (tenant_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def local_and_external(providers, local_reply):
    local, external = providers(), providers()
    serve_tags(local)
    local.always(CHAT, local_reply)
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta do provedor externo")))
    routes = [
        # Prazo curto só quando a resposta programada é lenta de propósito (o
        # atraso do servidor fica bem acima do prazo, para não haver corrida).
        local_route("local", local.base_url, 1, extra={"timeout_s": 1.0} if local_reply.delay_s else {}),
        external_route("externa", external.base_url, 2),
    ]
    return local, external, routes


# ---------------------------------------------------------------------------
# AC-07: local_only nunca gera tráfego externo, nem com o local falhando
# ---------------------------------------------------------------------------

LOCAL_FAILURES = [
    ("500", lambda: Reply(500, {"error": "falha interna"})),
    ("timeout", lambda: Reply(200, ollama_chat("tarde demais"), delay_s=8)),
    ("503", lambda: Reply(503, {"error": "fila cheia"})),
]


@pytest.mark.parametrize("label, failure", LOCAL_FAILURES, ids=[item[0] for item in LOCAL_FAILURES])
def test_ac07_local_only_makes_no_external_request_when_local_fails(pool, world, providers, credential, label, failure):
    local, external, routes = local_and_external(providers, failure())
    built = assemble(routes, cloud_settings(), pool)
    owner = ctx_for(world, pool)
    built.ledger.set_limits(owner, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx_for(world, pool, Privacy.LOCAL_ONLY), AttemptBudget(3))

    assert excinfo.value.code == "model_unavailable"
    # Contagem lida depois de estabilizar (no caso de timeout o cliente desiste
    # antes de o servidor, sob carga, ter registrado o pedido).
    assert local.settled_count(CHAT) == 1
    # Nem inferência, nem sonda, nem lista de modelos: ZERO requisições externas.
    assert external.count() == 0
    assert [item.alias for item in excinfo.value.attempts] == ["local"]
    assert budget_rows(pool, world.tenant_id) == []

    # Controle: com a MESMA montagem, só mudando a política, a rota externa atende.
    # É a política de privacidade (e nada mais) que impediu o tráfego acima.
    built = assemble(routes, cloud_settings(), pool)
    response = built.gateway.complete(user_request(), ctx_for(world, pool, Privacy.CLOUD_ALLOWED), AttemptBudget(3))
    assert response.alias == "externa" and response.fallback_used is True
    assert external.count(COMPLETIONS) == 1


def test_ac07_local_only_with_refused_local_connection(pool, world, providers, credential):
    external = providers()
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta do provedor externo")))
    routes = [local_route("local", refused_base_url(), 1), external_route("externa", external.base_url, 2)]
    built = assemble(routes, cloud_settings(), pool, verify_local_routes=False)
    built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx_for(world, pool, Privacy.LOCAL_ONLY), AttemptBudget(3))

    assert excinfo.value.code == "model_unavailable"
    assert outcomes(excinfo.value.attempts) == ["local:network"]
    assert external.count() == 0


def test_ac07_local_only_with_open_circuit_and_redaction_flag_still_stays_local(pool, world, providers, credential):
    local, external, routes = local_and_external(providers, Reply(500, {"error": "falha"}))
    built = assemble(routes, cloud_settings(), pool)
    built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)
    ctx = ctx_for(world, pool, Privacy.LOCAL_ONLY)
    # redaction_verified não amplia local_only; quatro falhas abrem o circuito local.
    for _ in range(4):
        with pytest.raises(AiError) as excinfo:
            built.gateway.complete(user_request(redaction_verified=True), ctx, AttemptBudget(3))
        assert excinfo.value.code == "model_unavailable"
    assert built.circuit.state("local") == "open" and local.count(CHAT) == 3
    assert external.count() == 0


def test_ac07_cloud_redacted_without_verified_redaction_stays_local(pool, world, providers, credential):
    local, external, routes = local_and_external(providers, Reply(500, {"error": "falha"}))
    built = assemble(routes, cloud_settings(), pool)
    built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)
    ctx = ctx_for(world, pool, Privacy.CLOUD_REDACTED)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(redaction_verified=False), ctx, AttemptBudget(3))
    assert excinfo.value.code == "model_unavailable" and external.count() == 0

    # Com a redução verificada, a mesma política admite a rota externa.
    response = built.gateway.complete(user_request(redaction_verified=True), ctx, AttemptBudget(3))
    assert response.alias == "externa" and external.count(COMPLETIONS) == 1


def test_ac07_cloud_allowed_with_cloud_flag_off_does_not_use_external(pool, world, providers, credential):
    local, external, routes = local_and_external(providers, Reply(500, {"error": "falha"}))
    built = assemble(routes, cloud_settings(cloud_enabled=False), pool)
    built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        ctx = ctx_for(world, pool, Privacy.CLOUD_ALLOWED)
        built.gateway.complete(user_request(redaction_verified=True), ctx, AttemptBudget(3))

    assert excinfo.value.code == "model_unavailable"
    assert local.count(CHAT) == 1 and external.count() == 0


# ---------------------------------------------------------------------------
# AC-13: custo
# ---------------------------------------------------------------------------

def test_zero_or_missing_ceiling_blocks_the_external_route(pool, world, providers, credential):
    external = providers()
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta paga")))
    built = assemble([external_route("externa", external.base_url, 1)], cloud_settings(), pool)
    ctx = ctx_for(world, pool)

    # Sem linha de limite.
    budget = AttemptBudget(3)
    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, budget)
    assert excinfo.value.code == "budget_exceeded" and excinfo.value.http_status == 429
    assert outcomes(excinfo.value.attempts) == ["externa:skipped:budget_exceeded"]
    assert external.count() == 0 and budget.used == 0

    # Com teto zero.
    built.ledger.set_limits(ctx, 0, 0, 0)
    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert excinfo.value.code == "budget_exceeded" and external.count() == 0

    # Teto definido pelo titular: a mesma rota passa a atender.
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    assert built.gateway.complete(user_request(), ctx, AttemptBudget(3)).content == "resposta paga"


def test_unknown_cost_skips_the_paid_route(pool, world, providers, credential):
    local, external = providers(), providers()
    serve_tags(local)
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta paga")))
    routes = [
        # Rota paga sem estimativa de custo (só pode existir como candidata).
        external_route("sem-custo", external.base_url, 1, state="candidate", max_cost_micros_per_call=None),
        local_route("local", local.base_url, 2),
    ]
    built = assemble(routes, cloud_settings(allow_candidate_models=True), pool)
    built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(), ctx_for(world, pool), budget)

    assert outcomes(response.attempts) == ["sem-custo:skipped:cost_unknown", "local:ok"]
    assert external.count() == 0 and budget.used == 1
    assert budget_rows(pool, world.tenant_id) == []


def test_cost_is_reserved_then_reconciled_with_real_usage(pool, world, providers, credential):
    external = providers()
    external.always(COMPLETIONS, Reply(200, openai_chat("ok", usage={"prompt_tokens": 100, "completion_tokens": 20})))
    built = assemble([external_route("externa", external.base_url, 1)], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    response = built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    # 100 tokens x 2 por token + 20 tokens x 10 por token (tarifas da rota em micros/Mtok).
    assert response.cost_micros == 400 and isinstance(response.cost_micros, int)
    assert response.model_id == "modelo-externo-teste"
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "externa", "reserved_micros": 1000, "actual_micros": 400, "status": "reconciled"}
    ]
    assert built.ledger.usage(ctx)["run_micros"] == 400


def test_failure_without_charge_releases_and_possibly_billed_failure_keeps_the_reservation(
    pool, world, providers, credential
):
    failing, slow = providers(), providers()
    failing.always(COMPLETIONS, Reply(500, {"error": {"message": "falha"}}))
    slow.always(COMPLETIONS, Reply(200, openai_chat("tarde demais"), delay_s=8))
    routes = [
        external_route("falha", failing.base_url, 1),
        external_route("lenta", slow.base_url, 2, extra={"timeout_s": 1.0}),
    ]
    built = assemble(routes, cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    assert excinfo.value.code == "model_unavailable"
    assert outcomes(excinfo.value.attempts) == ["falha:server_error", "lenta:timeout"]
    assert budget_rows(pool, world.tenant_id) == [
        # 500: o provedor não processou; a reserva volta.
        {"route_alias": "falha", "reserved_micros": 1000, "actual_micros": None, "status": "released"},
        # Timeout: o provedor pode ter processado e cobrado; conta pelo máximo.
        {"route_alias": "lenta", "reserved_micros": 1000, "actual_micros": 1000, "status": "reconciled"},
    ]


def test_ac13_parallel_calls_never_spend_beyond_the_ceiling(pool, warm_pool, world, providers, credential):
    external = providers()
    # O provedor segura as respostas até o teste liberar: todas as reservas
    # acontecem enquanto as chamadas aceitas ainda estão em voo (sem reconciliação).
    release = threading.Event()
    external.always(COMPLETIONS, Reply(200, openai_chat("ok"), hold=release))
    built = assemble(
        [external_route("externa", external.base_url, 1)],
        cloud_settings(inference_timeout_s=60),
        warm_pool,
        ledger_clock=slow_clock(),
    )
    owner = ctx_for(world, pool)
    # Cada chamada reserva 1000 micros; o teto do dia comporta 3.
    built.ledger.set_limits(owner, GENEROUS, 3000, GENEROUS)

    barrier = threading.Barrier(8)
    results, lock = [], threading.Lock()

    def worker():
        ctx = ctx_for(world, pool)
        barrier.wait(10)
        try:
            outcome = built.gateway.complete(user_request(), ctx, AttemptBudget(3)).alias
        except AiError as error:
            outcome = error.code
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    # Espera cada thread ou ser barrada pelo teto ou chegar ao provedor.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with lock:
            barred = len(results)
        if barred + external.count(COMPLETIONS) >= 8:
            break
        time.sleep(0.02)
    in_flight = external.count(COMPLETIONS)
    with lock:
        barred_now = sorted(results)
    release.set()
    for thread in threads:
        thread.join(30)

    # Com as três chamadas aceitas ainda sem resposta, as outras cinco já foram barradas.
    assert (in_flight, barred_now) == (3, ["budget_exceeded"] * 5)
    assert sorted(results) == ["budget_exceeded"] * 5 + ["externa"] * 3
    # Só as chamadas que couberam no teto chegaram ao provedor.
    assert external.count(COMPLETIONS) == 3
    rows = budget_rows(pool, world.tenant_id)
    assert len(rows) == 3 and sum(row["reserved_micros"] for row in rows) == 3000


def test_openrouter_internal_attempts_count_in_the_attempt_budget(pool, world, providers, credential):
    external = providers()
    metadata = {
        "attempt": 2,
        "attempts": [
            {"provider": "fornecedor-teste", "status": 503},
            {"provider": "fornecedor-teste", "status": 200},
        ],
    }
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.000250}
    external.always(COMPLETIONS, Reply(200, openai_chat("ok", usage=usage, openrouter_metadata=metadata)))
    route = external_route(
        "via-openrouter", external.base_url, 1, upstream_provider="fornecedor-teste", extra={"aggregator": "openrouter"}
    )
    built = assemble([route], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(), ctx, budget)

    # Uma requisição nossa, duas tentativas dentro do agregador: contam as duas.
    assert external.count(COMPLETIONS) == 1 and budget.used == 2 and response.inference_calls == 2
    assert response.effective_provider == "fornecedor-teste"
    # Custo informado pelo provedor (créditos em USD = moeda do orçamento).
    assert response.cost_micros == 250
    assert budget_rows(pool, world.tenant_id)[0]["actual_micros"] == 250

    # Com orçamento em outra moeda, o custo em USD do provedor não é usado: vale a tarifa da rota.
    brl = assemble([route], cloud_settings(budget_currency="BRL"), pool)
    brl.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS, "BRL")
    assert brl.gateway.complete(user_request(), ctx, AttemptBudget(3)).cost_micros == 70  # 10x2 + 5x10


def test_external_401_suspends_credential_and_releases_reservation(pool, world, providers, credential):
    external, local = providers(), providers()
    serve_tags(local)
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    external.always(COMPLETIONS, Reply(401, {"error": {"message": "chave inválida"}}))
    routes = [external_route("externa", external.base_url, 1), local_route("local", local.base_url, 2)]
    built = assemble(routes, cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    first = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert outcomes(first.attempts) == ["externa:auth", "local:ok"] and first.cost_micros == 0
    second = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert outcomes(second.attempts) == ["externa:skipped:credential_suspended", "local:ok"]
    # A credencial suspensa não é usada de novo, e nenhuma reserva nova é feita por ela.
    assert external.count(COMPLETIONS) == 1
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "externa", "reserved_micros": 1000, "actual_micros": None, "status": "released"}
    ]


# ---------------------------------------------------------------------------
# Anthropic pelo gateway
# ---------------------------------------------------------------------------

def test_anthropic_route_through_the_gateway(pool, world, providers, credential):
    external = providers()
    external.enqueue(
        MESSAGES,
        Reply(200, anthropic_message("texto fora do formato")),
        Reply(
            200,
            anthropic_message(
                VALID_ANSWER, model="modelo-anthropic-efetivo", usage={"input_tokens": 300, "output_tokens": 50}
            ),
        ),
    )
    route = external_route(
        "anthropic-direta", external.base_url, 1, provider="anthropic", max_cost_micros_per_call=5000
    )
    built = assemble([route], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), ctx, budget)

    assert response.parsed == {"categoria": "moradia", "confianca": 90}
    assert (response.provider, response.model_id) == ("anthropic", "modelo-anthropic-efetivo")
    assert outcomes(response.attempts) == ["anthropic-direta:invalid_output", "anthropic-direta:ok"]
    assert external.count(MESSAGES) == 2 and budget.used == 2
    # 1ª chamada: 1000x2 + 200x10 = 4000; 2ª: 300x2 + 50x10 = 1100. As duas foram cobradas.
    assert response.cost_micros == 5100
    assert [row["actual_micros"] for row in budget_rows(pool, world.tenant_id)] == [4000, 1100]


def test_anthropic_refusal_does_not_switch_route(pool, world, providers, credential):
    refusing, other = providers(), providers()
    refusing.always(MESSAGES, Reply(200, anthropic_message("", stop_reason="refusal")))
    other.always(COMPLETIONS, Reply(200, openai_chat("a outra rota responderia")))
    routes = [
        external_route("anthropic-direta", refusing.base_url, 1, provider="anthropic"),
        external_route("externa", other.base_url, 2),
    ]
    built = assemble(routes, cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    assert excinfo.value.code == "model_refused"
    assert refusing.count(MESSAGES) == 1 and other.count() == 0
    # A recusa chega com HTTP 200 e pode ser cobrada: a reserva fica pelo máximo.
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "anthropic-direta", "reserved_micros": 1000, "actual_micros": 1000, "status": "reconciled"}
    ]


# ---------------------------------------------------------------------------
# AC-13: o segredo não aparece em lugar nenhum
# ---------------------------------------------------------------------------

def test_ac13_credential_never_reaches_logs_errors_trail_or_database(
    pool, world, providers, credential, caplog, monkeypatch
):
    openai_like, anthropic_like = providers(), providers()
    # Pior caso: o provedor devolve a própria credencial no corpo do erro.
    echo = {"error": {"message": "chave recebida: %s" % FAKE_SECRET, "code": "x"}}
    openai_like.enqueue(
        COMPLETIONS,
        Reply(500, echo),
        Reply(429, echo, headers={"Retry-After": "1"}),
        Reply(200, openai_chat("prosa em vez de JSON")),
        Reply(200, openai_chat("ainda prosa")),
        Reply(200, openai_chat("devagar"), delay_s=8),
        Reply(400, echo),
        Reply(401, echo),
    )
    anthropic_like.enqueue(
        MESSAGES,
        Reply(529, {"type": "error", "error": {"type": "overloaded_error", "message": FAKE_SECRET}}),
        Reply(200, anthropic_message(VALID_ANSWER)),
        Reply(403, {"type": "error", "error": {"type": "permission_error", "message": FAKE_SECRET}}),
    )
    openai_route = external_route("externa", openai_like.base_url, 1, extra={"timeout_s": 1.5})
    anthropic_route = external_route(
        "anthropic-direta", anthropic_like.base_url, 2, provider="anthropic", credential_env=CREDENTIAL_ENV + "_B",
        max_cost_micros_per_call=5000,
    )
    built = assemble([openai_route, anthropic_route], cloud_settings(circuit_failures=50), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    caplog.set_level(logging.DEBUG)

    monkeypatch.setenv(CREDENTIAL_ENV + "_B", FAKE_SECRET)
    captured = []
    for _ in range(8):
        try:
            response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), ctx, AttemptBudget(3))
            captured.append("%r %r" % (response, response.attempts))
        except AiError as error:
            chained = (error.__cause__, error.__context__)
            captured.append(
                "%s %r %r %r %r %r"
                % (error, error, error.to_dict("trace"), error.details, error.attempts, chained)
            )
        built.clock.advance(5)

    # O segredo foi de fato usado nas duas rotas (senão o teste não provaria nada).
    assert openai_like.settled_count(COMPLETIONS, at_least=7) == 7 and anthropic_like.count(MESSAGES) == 3
    assert all(item.headers["authorization"] == "Bearer " + FAKE_SECRET for item in openai_like.requests(COMPLETIONS))
    assert all(item.headers["x-api-key"] == FAKE_SECRET for item in anthropic_like.requests(MESSAGES))
    assert sorted(built.gateway.suspended_credentials()) == [CREDENTIAL_ENV, CREDENTIAL_ENV + "_B"]

    # Logs de todos os loggers (inclusive urllib3 em DEBUG).
    assert caplog.records and "attempt alias=externa" in caplog.text
    assert FAKE_SECRET not in caplog.text
    for record in caplog.records:
        assert FAKE_SECRET not in "%r %r" % (record.args, record.__dict__.get("msg"))
    # Erros levantados, respostas e trilha de tentativas.
    assert captured and all(FAKE_SECRET not in item for item in captured)
    # Banco: auditoria e livro de orçamento.
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT metadata::text AS text FROM audit_events WHERE tenant_id = %s", (world.tenant_id,))
        stored = [row["text"] for row in cursor.fetchall()]
        cursor.execute("SELECT route_alias FROM ai_budget_entries WHERE tenant_id = %s", (world.tenant_id,))
        stored += [row["route_alias"] for row in cursor.fetchall()]
    assert stored and all(FAKE_SECRET not in item for item in stored)
    # O gateway e os adaptadores não guardam o valor em memória.
    assert FAKE_SECRET not in repr(vars(built.gateway))


def test_ac13_credential_echoed_in_success_fields_never_reaches_the_result(
    pool, world, providers, credential, caplog
):
    openai_like, anthropic_like = providers(), providers()
    # Pior caso em resposta 200: o provedor ecoa a credencial nos campos que
    # viram "modelo efetivo" e "fornecedor efetivo" na auditoria.
    openai_like.always(
        COMPLETIONS, Reply(200, openai_chat(VALID_ANSWER, model=FAKE_SECRET, provider="Eco " + FAKE_SECRET))
    )
    anthropic_like.always(MESSAGES, Reply(200, anthropic_message(VALID_ANSWER, model="modelo/" + FAKE_SECRET)))
    routes = [
        external_route("externa", openai_like.base_url, 1),
        external_route("anthropic-direta", anthropic_like.base_url, 1, provider="anthropic"),
    ]
    ctx = ctx_for(world, pool)
    caplog.set_level(logging.DEBUG)
    captured = []
    for route in routes:
        built = assemble([route], cloud_settings(), pool)
        built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
        response = built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), ctx, AttemptBudget(3))
        # O rótulo do provedor é descartado; fica o model_id do registro.
        assert response.model_id == "modelo-externo-teste" and response.effective_provider is None
        captured.append("%r %r" % (response, response.attempts))

    assert openai_like.count(COMPLETIONS) == 1 and anthropic_like.count(MESSAGES) == 1
    assert all(FAKE_SECRET not in item for item in captured)
    assert FAKE_SECRET not in caplog.text


# ---------------------------------------------------------------------------
# Livro de orçamento fora do ar: só a rota paga sai de jogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("how", ["closed", "exhausted"])
def test_ledger_failure_takes_out_only_the_paid_route(ai_database, pool, world, providers, credential, caplog, how):
    external, local = providers(), providers()
    serve_tags(local)
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta paga")))
    paid = external_route("externa", external.base_url, 1)
    ctx = ctx_for(world, pool)

    # Pool REAL do livro em estado de falha: fechado (banco fora) ou com a
    # única conexão ocupada (pool esgotado sob concorrência). Nos dois casos
    # o psycopg2 levanta PoolError em getconn, que não é AiError.
    ledger_pool = pg_pool.ThreadedConnectionPool(1, 1, dsn=ai_database.app_dsn)
    held = ledger_pool.getconn() if how == "exhausted" else None
    if how == "closed":
        ledger_pool.closeall()
    caplog.set_level(logging.INFO)
    try:
        built = assemble([paid, local_route("local", local.base_url, 2)], cloud_settings(), ledger_pool)
        budget = AttemptBudget(3)
        response = built.gateway.complete(user_request(), ctx, budget)

        # A falha do livro não derruba o caminho que não custa nada.
        assert outcomes(response.attempts) == ["externa:skipped:budget_unavailable", "local:ok"]
        assert response.content == "resposta local" and budget.used == 1
        # E a rota paga NUNCA é chamada sem reserva.
        assert external.count() == 0
        assert "budget_reserve_failed alias=externa error=PoolError" in caplog.text

        with pytest.raises(AiError) as excinfo:
            assemble([paid], cloud_settings(), ledger_pool).gateway.complete(user_request(), ctx, AttemptBudget(3))
        # Sai como AiError com trilha; indisponibilidade (retentável), não "teto atingido".
        assert excinfo.value.code == "model_unavailable" and excinfo.value.retryable is True
        assert excinfo.value.details == {"reason": "budget_unavailable"}
        assert outcomes(excinfo.value.attempts) == ["externa:skipped:budget_unavailable"]
        assert external.count() == 0
    finally:
        if held is not None:
            ledger_pool.putconn(held)
        if not ledger_pool.closed:
            ledger_pool.closeall()
    assert budget_rows(pool, world.tenant_id) == []


# ---------------------------------------------------------------------------
# OpenRouter: fornecedor efetivo fora do fixado suspende a rota
# ---------------------------------------------------------------------------

def openrouter_route(server, priority=1):
    return external_route(
        "or", server.base_url, priority, upstream_provider="fornecedor-teste", extra={"aggregator": "openrouter"}
    )


def test_openrouter_upstream_mismatch_suspends_the_route(pool, world, providers, credential, caplog):
    aggregator, local = providers(), providers()
    serve_tags(local)
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    wrong = openai_chat(
        "resposta de fornecedor não autorizado", provider="Fornecedor-Nao-Autorizado",
        model="outro/modelo-nao-homologado",
    )
    aggregator.always(COMPLETIONS, Reply(200, wrong))
    built = assemble([openrouter_route(aggregator), local_route("local", local.base_url, 2)], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    caplog.set_level(logging.WARNING)

    first = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    # A resposta do fornecedor não autorizado é descartada, não devolvida.
    assert outcomes(first.attempts) == ["or:unavailable", "local:ok"]
    assert first.content == "resposta local" and first.alias == "local"
    assert built.gateway.suspended_routes() == {"or": "upstream_mismatch"}
    # Violação de política não é falha de saúde: o disjuntor não conta.
    assert built.circuit.state("or") == "closed"

    second = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert outcomes(second.attempts) == ["or:skipped:route_suspended", "local:ok"]
    # A segunda chamada NÃO envia nada ao agregador.
    assert aggregator.count(COMPLETIONS) == 1

    # O agregador processou a primeira chamada: a reserva fica pelo máximo.
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "or", "reserved_micros": 1000, "actual_micros": 1000, "status": "reconciled"}
    ]
    assert first.cost_micros == 1000 and second.cost_micros == 0
    warnings = [r.getMessage() for r in caplog.records if r.getMessage().startswith("route_suspended ")]
    assert len(warnings) == 1 and "alias=or" in warnings[0] and "reason=upstream_mismatch" in warnings[0]
    # O aviso do adaptador diz o que divergiu, com nomes reduzidos a [a-z0-9];
    # o conteúdo da resposta descartada não aparece em log.
    assert "openrouter_upstream_mismatch alias=or what=provider pinned=fornecedorteste" in caplog.text
    assert "effective=fornecedornaoautorizado" in caplog.text
    assert "resposta de fornecedor" not in caplog.text

    # O operador confere o registro e reativa; com o fornecedor certo a rota volta.
    assert built.gateway.reinstate_route("or") is True and built.gateway.reinstate_route("or") is False
    aggregator.always(COMPLETIONS, Reply(200, openai_chat("do fornecedor certo", provider="fornecedor-teste")))
    third = built.gateway.complete(user_request(), ctx, AttemptBudget(3))
    assert (third.alias, third.effective_provider, third.content) == ("or", "fornecedor-teste", "do fornecedor certo")


def test_openrouter_internal_attempts_count_even_when_the_aggregator_fails(pool, world, providers, credential):
    aggregator, other = providers(), providers()
    body = {
        "error": {"code": 503, "message": "indisponível"},
        "openrouter_metadata": {"attempts": [{"provider": "fornecedor-teste", "status": 503}] * 3},
    }
    aggregator.always(COMPLETIONS, Reply(503, body))
    other.always(COMPLETIONS, Reply(200, openai_chat("a outra rota responderia")))
    routes = [openrouter_route(aggregator), external_route("externa", other.base_url, 2)]
    built = assemble(routes, cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    budget = AttemptBudget(3)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, budget)

    # Uma requisição nossa, três tentativas dentro do agregador: o orçamento de
    # 3 acabou ali, e a rota seguinte (saudável) não pode ser chamada.
    assert excinfo.value.details == {"reason": "attempt_budget_exhausted"}
    assert budget.used == 3 and excinfo.value.inference_calls == 3
    assert aggregator.count(COMPLETIONS) == 1 and other.count() == 0
    assert outcomes(excinfo.value.attempts) == ["or:server_error"]


# ---------------------------------------------------------------------------
# Custo: o que se sabe da requisição decide entre devolver e manter a reserva
# ---------------------------------------------------------------------------

def _oversized():
    return Reply(200, json.dumps(openai_chat("x" * (MAX_RESPONSE_BYTES + 1024))))


UNUSABLE_BUT_SENT = [
    ("not-json", lambda: Reply(200, "isto nao e json"), "server_error"),
    ("finish-error", lambda: Reply(200, openai_chat("", finish_reason="error")), "server_error"),
    ("too-large", _oversized, "server_error"),
    ("cut-mid-body", lambda: Reply(200, openai_chat("x" * 500), truncate_at=40), "network"),
    ("closed-without-answer", lambda: Reply(drop=True), "network"),
]


@pytest.mark.parametrize("label, reply, outcome", UNUSABLE_BUT_SENT, ids=[item[0] for item in UNUSABLE_BUT_SENT])
def test_unusable_answer_from_a_paid_route_keeps_the_reservation(
    pool, world, providers, credential, label, reply, outcome
):
    external = providers()
    external.always(COMPLETIONS, reply())
    built = assemble([external_route("externa", external.base_url, 1)], cloud_settings(inference_timeout_s=30), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    assert excinfo.value.code == "model_unavailable"
    assert outcomes(excinfo.value.attempts) == ["externa:%s" % outcome]
    assert external.count(COMPLETIONS) == 1
    # O pedido chegou ao provedor (que pode ter processado e cobrado): a
    # reserva fica pelo máximo e continua contando nos tetos.
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "externa", "reserved_micros": 1000, "actual_micros": 1000, "status": "reconciled"}
    ]
    assert excinfo.value.cost_micros == 1000 and built.ledger.usage(ctx)["day_micros"] == 1000


def test_request_that_never_left_the_machine_releases_the_reservation(pool, world, providers, credential):
    built = assemble([external_route("externa", refused_base_url(), 1)], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    assert outcomes(excinfo.value.attempts) == ["externa:network"]
    # Conexão recusada: o provedor nem viu o pedido, não há o que cobrar.
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "externa", "reserved_micros": 1000, "actual_micros": None, "status": "released"}
    ]
    assert excinfo.value.cost_micros == 0 and built.ledger.usage(ctx)["day_micros"] == 0


@pytest.mark.parametrize(
    "tokens, rates, expected",
    [
        # 1 x 0,3 + 1 x 0,4 = 0,7 micro: cobra 1 (para baixo daria zero).
        ((1, 1), (300_000, 400_000), 1),
        # 3 x 0,5 = 1,5 micro: cobra 2.
        ((3, 0), (500_000, 500_000), 2),
        # Divisão exata continua exata.
        ((100, 20), (2_000_000, 10_000_000), 400),
    ],
)
def test_token_cost_is_rounded_up_to_the_next_micro(pool, world, providers, credential, tokens, rates, expected):
    external = providers()
    usage = {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]}
    external.always(COMPLETIONS, Reply(200, openai_chat("ok", usage=usage)))
    route = external_route(
        "externa", external.base_url, 1, input_cost_micros_per_mtok=rates[0], output_cost_micros_per_mtok=rates[1]
    )
    built = assemble([route], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    response = built.gateway.complete(user_request(), ctx, AttemptBudget(3))

    assert response.cost_micros == expected
    assert budget_rows(pool, world.tenant_id)[0]["actual_micros"] == expected


def test_cost_already_charged_is_reported_when_the_call_ends_in_error(pool, world, providers, credential):
    external = providers()
    usage = {"prompt_tokens": 100, "completion_tokens": 20}
    external.always(COMPLETIONS, Reply(200, openai_chat("prosa em vez de JSON", usage=usage)))
    built = assemble([external_route("externa", external.base_url, 1)], cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)

    with pytest.raises(AiError) as excinfo:
        built.gateway.complete(user_request(response_schema=ANSWER_SCHEMA), ctx, AttemptBudget(3))

    error = excinfo.value
    assert error.code == "invalid_output" and external.count(COMPLETIONS) == 2
    # Duas chamadas cobradas (400 micros cada) antes de a chamada terminar em
    # erro: o custo acompanha o erro para a auditoria bater com o livro.
    assert error.cost_micros == 800 and error.inference_calls == 2
    assert sum(row["actual_micros"] for row in budget_rows(pool, world.tenant_id)) == 800
    # Mas não vai para a resposta HTTP.
    assert error.to_dict("trace").get("details") == {"reason": "invalid_output"}


def test_malformed_credential_releases_the_reservation_and_is_suspended(pool, world, providers, monkeypatch):
    monkeypatch.setenv(CREDENTIAL_ENV, "credencial-ficticia-colada-com-reticencias…")
    external, local = providers(), providers()
    serve_tags(local)
    local.always(CHAT, Reply(200, ollama_chat("resposta local")))
    external.always(COMPLETIONS, Reply(200, openai_chat("resposta paga")))
    routes = [external_route("externa", external.base_url, 1), local_route("local", local.base_url, 2)]
    built = assemble(routes, cloud_settings(), pool)
    ctx = ctx_for(world, pool)
    built.ledger.set_limits(ctx, GENEROUS, GENEROUS, GENEROUS)
    budget = AttemptBudget(3)

    response = built.gateway.complete(user_request(), ctx, budget)

    # Antes: UnicodeEncodeError dentro do http.client virava "defeito do
    # adaptador", sem failover e com a reserva cobrada pelo máximo.
    assert outcomes(response.attempts) == ["externa:auth", "local:ok"]
    assert external.count() == 0 and budget.used == 1 and response.cost_micros == 0
    assert built.gateway.suspended_credentials() == [CREDENTIAL_ENV]
    assert budget_rows(pool, world.tenant_id) == [
        {"route_alias": "externa", "reserved_micros": 1000, "actual_micros": None, "status": "released"}
    ]


# ---------------------------------------------------------------------------
# AC-07: a trava de privacidade do gateway não depende do registro
# ---------------------------------------------------------------------------

class LeakyRegistry:
    """Registro com defeito (dublê): devolve TODAS as rotas, sem olhar a política.

    O registro real nunca devolveria uma rota externa sob ``local_only``. O
    dublê existe para provar que, se um dia ele devolver, a segunda trava (no
    gateway, colada na chamada) segura o tráfego.
    """

    def __init__(self, routes):
        self._routes = list(routes)

    def eligible(self, request, ctx):
        return Eligibility(list(self._routes), [])


def test_ac07_gateway_privacy_lock_holds_even_with_a_defective_registry(pool, world, providers, credential):
    local, external, routes = local_and_external(providers, Reply(500, {"error": "falha"}))

    def leaky_gateway(settings):
        built = assemble(routes, settings, pool)
        built.ledger.set_limits(ctx_for(world, pool), GENEROUS, GENEROUS, GENEROUS)
        return DefaultModelGateway(
            LeakyRegistry(built.registry.routes), build_default_adapters(settings), built.circuit, built.ledger,
            settings, clock=built.clock, sleep=built.clock.sleep,
        )

    blocked = [
        (cloud_settings(circuit_failures=50), Privacy.LOCAL_ONLY, True),
        (cloud_settings(circuit_failures=50), Privacy.CLOUD_REDACTED, False),
        (cloud_settings(circuit_failures=50, cloud_enabled=False), Privacy.CLOUD_ALLOWED, True),
    ]
    for settings, privacy, redaction in blocked:
        with pytest.raises(AiError) as excinfo:
            leaky_gateway(settings).complete(
                user_request(redaction_verified=redaction), ctx_for(world, pool, privacy), AttemptBudget(3)
            )
        assert excinfo.value.code == "model_unavailable"
        assert outcomes(excinfo.value.attempts) == ["local:server_error", "externa:skipped:privacy"]
    assert external.count() == 0 and budget_rows(pool, world.tenant_id) == []

    # Controle: com a política permitindo, o mesmo gateway usa a rota externa.
    response = leaky_gateway(cloud_settings(circuit_failures=50)).complete(
        user_request(), ctx_for(world, pool, Privacy.CLOUD_ALLOWED), AttemptBudget(3)
    )
    assert response.alias == "externa" and external.count(COMPLETIONS) == 1
