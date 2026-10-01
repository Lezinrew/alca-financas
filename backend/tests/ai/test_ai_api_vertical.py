"""Fronteiras reais: sessão V2 → HTTP → gateway Ollama → ferramenta → banco."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest
from argon2 import PasswordHasher
from flask import Flask

from extensions import limiter
from routes.ai import bp as ai_bp
from routes.auth_v2 import bp as auth_bp
from services.ai import CONTRACT_VERSION, runs
from services.ai.db import plain_tx, scoped_tx
from services.ai.gateway.adapters.ollama import OllamaAdapter
from services.ai.platform import build_platform
from services.ai.policy import CAPABILITIES
from services.ai.settings import AiSettings
from services.auth_v2_service import AuthV2Service

from .support import seed
from .support.gateway_server import FakeProvider, Reply, ollama_chat, ollama_model, ollama_tags, refused_base_url


PREFIX = "/api/ai/v1"
PASSWORD = "senha-sintetica-de-teste"
MODEL = "modelo-teste:1b"
DIGEST = "a" * 64
ERROR_KEYS = {"code", "retryable", "safe_message", "trace_id"}


@pytest.fixture(scope="session")
def password_hash():
    return PasswordHasher().hash(PASSWORD)


def app_for(platform=None, auth_service=None):
    """Aplicativo próprio; nunca importa app.py ou carrega dotenv."""
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    limiter.init_app(app)
    if platform is not None:
        app.config["AI_PLATFORM"] = platform
    if auth_service is not None:
        app.config["AUTH_V2_SERVICE"] = auth_service
    app.register_blueprint(auth_bp, url_prefix="/api/v2")
    app.register_blueprint(ai_bp, url_prefix=PREFIX)
    return app


@pytest.fixture()
def api(pool, world, tmp_path, password_hash, monkeypatch):
    monkeypatch.setenv("AUTH_V2_COOKIE_SECURE", "false")
    provider = FakeProvider()
    provider.always("GET /api/tags", Reply(body=ollama_tags(ollama_model(MODEL, DIGEST))))
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps({"routes": [{
        "alias": "local-teste", "provider": "ollama", "model_id": MODEL,
        "locality": "local", "priority": 1, "task_classes": ["complex_tools"],
        "supports_tools": True, "supports_json": True, "supports_vision": False,
        "context_window": 8192, "state": "approved", "approved_purposes": ["read"],
        "evidence": "somente-teste-sintetico", "digest": DIGEST,
    }]}), encoding="utf-8")
    settings = AiSettings(
        enabled=True, model_registry_path=str(registry_path), ollama_base_url=provider.base_url,
        quarantine_dir=str(tmp_path / "quarentena"), inference_timeout_s=1,
    )
    auth = AuthV2Service(pool)
    with plain_tx(pool) as cursor:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, world.user_id))
    seed.create_grant(pool, world.tenant_id, world.personal_space_id, world.user_id,
                      capabilities=["finance.read"])
    platform = build_platform(pool, settings)
    app = app_for(platform, auth)
    client = app.test_client()
    login = client.post("/api/v2/auth/login", json={
        "email": "titular-alfa@example.test", "password": PASSWORD,
    })
    assert login.status_code == 200
    headers = {"X-CSRF-Token": login.json["csrf_token"]}
    try:
        yield SimpleNamespace(
            pool=pool, world=world, settings=settings, provider=provider, platform=platform,
            app=app, client=client, auth=auth, headers=headers,
        )
    finally:
        provider.close()


def payload(api, **overrides):
    return dict({
        "task": "finance_question", "message": "Quanto foi realizado em outubro de 2026?",
        "financial_space_id": api.world.personal_space_id, "privacy": "local_only", "input_refs": [],
    }, **overrides)


def post_run(api, body=None, **headers):
    return api.client.post(PREFIX + "/runs", json=body if body is not None else payload(api),
                           headers=dict(api.headers, **headers))


def assert_headers(response):
    assert response.headers["Cache-Control"] == "no-store"
    UUID(response.headers["X-Trace-Id"])


def assert_error(response, status, code):
    assert response.status_code == status
    assert_headers(response)
    assert set(response.json) == {"error"}
    assert set(response.json["error"]) == ERROR_KEYS
    assert response.json["error"]["code"] == code
    assert response.json["error"]["trace_id"] == response.headers["X-Trace-Id"]


def test_login_http_worker_finance_sources_and_audit(api, other_world):
    world = api.world
    for amount, tx_type in [("1000.01", "income"), ("0.29", "income"),
                            ("100.10", "expense"), ("0.20", "expense")]:
        seed.create_transaction(
            api.pool, world.tenant_id, world.personal_account_id,
            world.income_category_id if tx_type == "income" else world.expense_category_id,
            description="Lançamento sintético", amount=amount, tx_type=tx_type,
            occurred_on=date(2026, 10, 1),
        )
    # Valores deliberadamente grandes que NUNCA podem entrar na soma pessoal.
    for kwargs in [
        {"source_file": "manual.csv", "entry_source": "csv"},
        {"source_file": "legacy:antigo", "entry_source": "manual"},
        {"status": "pending"}, {"occurred_on": date(2026, 9, 30)},
        {"account_id": world.business_account_id},
    ]:
        data = dict(account_id=world.personal_account_id, occurred_on=date(2026, 10, 1))
        data.update(kwargs)
        seed.create_transaction(api.pool, world.tenant_id, category_id=world.expense_category_id,
                                description="Fora do realizado pessoal", amount="99999.99", **data)
    seed.create_transaction(
        api.pool, other_world.tenant_id, other_world.personal_account_id, other_world.expense_category_id,
        description="Outro tenant", amount="777777.77", occurred_on=date(2026, 10, 1),
    )
    api.provider.enqueue("POST /api/chat",
        Reply(body=ollama_chat(tool_calls=[{"function": {
            "name": "finance.read", "arguments": {"query": "realized_totals", "month": 10, "year": 2026},
        }}])),
        Reply(body=ollama_chat(content=json.dumps({"summary_pt_br": "Consulte os fatos e suas fontes."}))),
    )
    accepted = post_run(api, **{"Idempotency-Key": "vertical-001"})
    assert accepted.status_code == 202
    assert_headers(accepted)
    assert set(accepted.json) == {"run_id", "status", "trace_id"}
    run_id = accepted.json["run_id"]
    assert accepted.json["trace_id"] == accepted.headers["X-Trace-Id"]
    assert api.platform.worker.run_once() == run_id
    response = api.client.get(PREFIX + "/runs/" + run_id)
    assert response.status_code == 200
    assert_headers(response)
    result = response.json
    assert result["status"] == "completed", result["error"]
    assert result["error"] is None
    assert result["contract_version"] == CONTRACT_VERSION
    assert result["trace_id"] == accepted.json["trace_id"]
    assert result["scope"]["financial_space"]["id"] == world.personal_space_id
    assert result["model"]["provider"] == "ollama"
    assert any(step["name"] == "finance.read" and step["status"] == "succeeded"
               for step in result["progress"]["steps"])
    # Agregação NUMERIC independente: não usa o repositório financeiro ou money_str.
    with scoped_tx(api.pool, world.tenant_id) as cursor:
        cursor.execute("""
            SELECT SUM(amount) FILTER (WHERE type = 'income') AS income,
                   SUM(amount) FILTER (WHERE type = 'expense') AS expense
            FROM transactions
            WHERE tenant_id = %s AND account_id = %s AND status = 'paid'
              AND right(source_file, 4) = '.ofx'
              AND occurred_on BETWEEN DATE '2026-10-01' AND DATE '2026-10-31'
        """, (world.tenant_id, world.personal_account_id))
        expected = cursor.fetchone()
        cursor.execute("""SELECT event_type, metadata FROM audit_events
            WHERE tenant_id = %s AND entity_id = %s ORDER BY created_at, id""", (world.tenant_id, run_id))
        audit = cursor.fetchall()
    facts = {fact["key"]: fact for fact in result["facts"]}
    assert facts["realized.income"]["value"] == format(expected["income"], ".2f") == "1000.30"
    assert facts["realized.expense"]["value"] == format(expected["expense"], ".2f") == "100.30"
    assert facts["realized.net"]["value"] == format(expected["income"] - expected["expense"], ".2f") == "900.00"
    refs = {source["ref"] for source in result["sources"]}
    assert refs
    for fact in result["facts"]:
        assert fact["source_refs"] and set(fact["source_refs"]) <= refs
        assert fact["as_of"]
        assert fact["scope"]["financial_space_id"] == world.personal_space_id
        assert fact["value"] is None or isinstance(fact["value"], str)
    assert [row["event_type"] for row in audit] == ["ai.run.created", "ai.run.finished"]
    assert payload(api)["message"] not in json.dumps(audit, default=str)
    assert api.provider.count("GET /api/tags") == 1
    assert api.provider.count("POST /api/chat") == 2
    # Repetir o trabalho não executa novamente o gateway.
    assert api.platform.worker.run_once() is None
    assert api.provider.count("POST /api/chat") == 2


def test_platform_registers_every_real_tool_and_accepts_adapters(api):
    assert api.platform.registry.names() == sorted(CAPABILITIES)
    adapter = OllamaAdapter(api.provider.base_url)
    platform = build_platform(api.pool, api.settings, adapters={"ollama": adapter})
    assert platform.gateway._adapters["ollama"] is adapter
    assert platform.worker._orchestrator is platform.orchestrator
    assert api.provider.count() == 0  # Montar não consulta provedor.


def test_enabled_status_scopes_capabilities_and_flags(api):
    response = api.client.get(PREFIX + "/status")
    assert response.status_code == 200
    assert_headers(response)
    assert response.json["enabled"] is True
    assert response.json["flags"] == {"cloud": False, "email": False, "write": False}
    assert response.json["capabilities"] == ["finance.read"]
    assert {space["id"] for space in response.json["spaces"]} == {
        api.world.personal_space_id, api.world.business_space_id,
    }


@pytest.mark.parametrize("method,path", [
    ("GET", "/status"), ("GET", "/runs"), ("POST", "/runs"),
    ("GET", "/runs/invalid"), ("POST", "/runs/invalid/cancel"),
])
def test_requires_real_session(api, method, path):
    response = api.app.test_client().open(PREFIX + path, method=method, json={})
    assert_error(response, 401, "unauthorized")


@pytest.mark.parametrize("path", ["/runs", "/runs/invalid/cancel"])
@pytest.mark.parametrize("token", [None, "csrf-incorreto"])
def test_post_requires_csrf(api, path, token):
    response = api.client.post(PREFIX + path, json=payload(api),
                               headers={"X-CSRF-Token": token} if token else {})
    assert_error(response, 403, "invalid_csrf")


@pytest.mark.parametrize("field", ["tenant_id", "actor_id", "extra"])
def test_extra_body_properties_are_forbidden(api, field):
    assert_error(post_run(api, payload(api, **{field: "valor-injetado"})), 400, "invalid_request")


@pytest.mark.parametrize("body", [[], None, {"task": "apply_proposal", "message": "Aplique"},
    {"task": "finance_question", "message": 123}, {"task": "finance_question", "message": " "},
    {"task": "finance_question", "message": "texto\u0000"},
])
def test_invalid_requests(api, body):
    response = api.client.post(PREFIX + "/runs", data=json.dumps(body), content_type="application/json",
                               headers=api.headers)
    assert_error(response, 400, "invalid_request")


@pytest.mark.parametrize("data,content_type", [("{", "application/json"), ("{}", "text/plain")])
def test_invalid_json_or_content_type(api, data, content_type):
    assert_error(api.client.post(PREFIX + "/runs", data=data, content_type=content_type,
                                headers=api.headers), 400, "invalid_request")


@pytest.mark.parametrize("path", ["/runs", "/runs/invalid/cancel"])
def test_request_body_limit(api, path):
    assert_error(api.client.post(PREFIX + path, data=b" " * (65536 + 1),
                                content_type="application/json", headers=api.headers), 413, "payload_too_large")


def test_idempotency_replays_without_duplicate_audit_and_conflicts(api):
    first = post_run(api, **{"Idempotency-Key": "reenvio-0001"})
    second = post_run(api, **{"Idempotency-Key": "reenvio-0001"})
    assert first.status_code == second.status_code == 202
    assert first.json == second.json
    assert_error(post_run(api, payload(api, message="Outro pedido"),
                          **{"Idempotency-Key": "reenvio-0001"}), 409, "conflict")
    with scoped_tx(api.pool, api.world.tenant_id) as cursor:
        cursor.execute("SELECT count(*) AS total FROM ai_runs WHERE tenant_id = %s", (api.world.tenant_id,))
        assert cursor.fetchone()["total"] == 1
        cursor.execute("SELECT count(*) AS total FROM audit_events WHERE tenant_id = %s AND event_type = 'ai.run.created'",
                       (api.world.tenant_id,))
        assert cursor.fetchone()["total"] == 1


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("outside", ["tenant", "space", "actor"])
def test_foreign_run_is_not_found(api, other_world, outside, method):
    world = api.world
    if outside == "tenant":
        ctx = other_world.context(api.pool)
    elif outside == "space":
        ctx = world.context(api.pool, "business")
    else:
        user = seed.create_user(api.pool, "outro-ator@example.test")
        seed.add_tenant_member(api.pool, world.tenant_id, user, "member")
        seed.add_space_member(api.pool, world.tenant_id, world.personal_space_id, user, "member")
        ctx = replace(world.context(api.pool), actor_id=user)
    foreign = runs.create_run(api.pool, ctx, task="finance_question", message="Pedido privado",
                               settings=api.settings)["run_id"]
    if outside == "space":
        # Perdeu vínculo: o id real existe, mas o ator já não pode consultar o espaço.
        with scoped_tx(api.pool, world.tenant_id) as cursor:
            cursor.execute("DELETE FROM financial_space_members WHERE tenant_id = %s AND financial_space_id = %s AND user_id = %s",
                           (world.tenant_id, world.business_space_id, world.user_id))
    path = PREFIX + "/runs/" + foreign + ("/cancel" if method == "POST" else "")
    response = api.client.open(path, method=method, json={} if method == "POST" else None, headers=api.headers)
    assert_error(response, 404, "not_found")
    listing = api.client.get(PREFIX + "/runs", query_string={"financial_space_id": world.personal_space_id})
    assert listing.json["runs"] == []


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_explicit_other_space_cannot_read_or_cancel(api, method):
    run_id = post_run(api).json["run_id"]
    path = PREFIX + "/runs/" + run_id + ("/cancel" if method == "POST" else "")
    response = api.client.open(path, method=method, json={} if method == "POST" else None,
                               query_string={"financial_space_id": api.world.business_space_id}, headers=api.headers)
    assert_error(response, 404, "not_found")


@pytest.mark.parametrize("space_source", ["body", "query"])
def test_foreign_space_selection_is_not_found(api, other_world, space_source):
    if space_source == "body":
        response = post_run(api, payload(api, financial_space_id=other_world.personal_space_id))
    else:
        response = api.client.get(PREFIX + "/runs", query_string={"financial_space_id": other_world.personal_space_id})
    assert_error(response, 404, "not_found")


def test_foreign_tenant_header_is_not_found(api, other_world):
    assert_error(post_run(api, **{"X-Tenant-Id": other_world.tenant_id}), 404, "not_found")


def test_history_pagination_and_cancel(api):
    ids = [post_run(api, payload(api, message="Pedido %d" % i)).json["run_id"] for i in range(3)]
    query = {"financial_space_id": api.world.personal_space_id, "limit": 2}
    page = api.client.get(PREFIX + "/runs", query_string=query)
    assert page.status_code == 200
    assert_headers(page)
    assert [row["run_id"] for row in page.json["runs"]] == ids[::-1][:2]
    tail = api.client.get(PREFIX + "/runs", query_string=dict(query, cursor=page.json["next_cursor"]))
    assert [row["run_id"] for row in tail.json["runs"]] == ids[:1]
    assert tail.json["next_cursor"] is None
    for _ in range(2):
        cancelled = api.client.post(PREFIX + "/runs/" + ids[0] + "/cancel", json={}, headers=api.headers)
        assert cancelled.status_code == 200
        assert_headers(cancelled)
        assert cancelled.json["status"] == "cancelled"
        assert cancelled.json["cancel_requested"] is True


@pytest.mark.parametrize("query", [{"limit": "no"}, {"limit": "0"}, {"limit": "51"},
                                    {"cursor": "inválido"}, {"actor_id": "injeção"}])
def test_invalid_history_query(api, query):
    assert_error(api.client.get(PREFIX + "/runs", query_string=dict(
        {"financial_space_id": api.world.personal_space_id}, **query)), 400, "invalid_request")


@pytest.mark.parametrize("configured", [False, True])
def test_disabled_status_and_all_other_routes_without_database(configured):
    # Objeto sem getconn: qualquer tentativa de banco falharia no teste.
    platform = SimpleNamespace(settings=AiSettings(enabled=False), pool=object()) if configured else None
    client = app_for(platform).test_client()
    status = client.get(PREFIX + "/status")
    assert status.status_code == 200 and status.json == {"enabled": False}
    assert_headers(status)
    for method, path in [("GET", "/runs"), ("POST", "/runs"),
                         ("GET", "/runs/invalid"), ("POST", "/runs/invalid/cancel")]:
        assert_error(client.open(PREFIX + path, method=method, json={}), 503, "ai_disabled")


def test_model_server_offline_fails_run_safely(api):
    offline = replace(api.settings, ollama_base_url=refused_base_url())
    platform = build_platform(api.pool, offline)
    api.app.config["AI_PLATFORM"] = platform
    run_id = post_run(api).json["run_id"]
    assert platform.worker.run_once() == run_id
    response = api.client.get(PREFIX + "/runs/" + run_id)
    assert response.status_code == 200
    assert response.json["status"] == "failed"
    assert set(response.json["error"]) == ERROR_KEYS
    assert response.json["error"]["code"] == "model_unavailable"
    assert response.json["facts"] == []


def test_unexpected_database_error_has_safe_envelope(api, caplog):
    # Pool real fechado provoca falha de infraestrutura, sem substituir lógica.
    from psycopg2.pool import ThreadedConnectionPool
    connection = api.pool.getconn()
    try:
        broken_pool = ThreadedConnectionPool(1, 1, dsn=connection.dsn)
    finally:
        api.pool.putconn(connection)
    broken_pool.closeall()
    api.app.config["AI_PLATFORM"] = replace(api.platform, pool=broken_pool)
    response = post_run(api)
    assert_error(response, 500, "internal_error")
    assert payload(api)["message"] not in caplog.text


def test_cors_preflight_does_not_require_session(api):
    response = api.app.test_client().options(PREFIX + "/runs")
    assert response.status_code == 200
    assert_headers(response)


@pytest.mark.parametrize("method,path,status,code", [
    ("GET", "/rota-inexistente", 404, "not_found"),
    ("PUT", "/runs", 405, "invalid_request"),
])
def test_routing_errors_also_use_the_contract(api, method, path, status, code):
    assert_error(api.client.open(PREFIX + path, method=method), status, code)


def test_ai_routing_guard_preserves_unrelated_flask_routes(api):
    response = api.client.get("/rota-fora-da-ia")
    assert response.status_code == 404
    assert response.is_json is False
    assert "X-Trace-Id" not in response.headers


@pytest.mark.parametrize("size,expected_status", [(65536, 202), (65537, 413)])
@pytest.mark.parametrize("known_length", [True, False])
def test_exact_body_boundary_even_without_content_length(api, size, expected_status, known_length):
    data = json.dumps(payload(api)).encode("utf-8")
    data += b" " * (size - len(data))
    overrides = {} if known_length else {"CONTENT_LENGTH": "", "wsgi.input_terminated": True}
    response = api.client.post(PREFIX + "/runs", data=data, content_type="application/json",
                               headers=api.headers, environ_overrides=overrides)
    assert response.status_code == expected_status
    if expected_status == 413:
        assert_error(response, 413, "payload_too_large")


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_invalid_run_id_is_not_found(api, method):
    path = PREFIX + "/runs/invalid" + ("/cancel" if method == "POST" else "")
    assert_error(api.client.open(path, method=method, json={} if method == "POST" else None,
                                headers=api.headers), 404, "not_found")


def test_cancel_rejects_extra_body_before_effect(api):
    run_id = post_run(api).json["run_id"]
    assert_error(api.client.post(PREFIX + "/runs/" + run_id + "/cancel", json={"actor_id": "forged"},
                                headers=api.headers), 400, "invalid_request")
    assert api.client.get(PREFIX + "/runs/" + run_id).json["status"] == "queued"


def test_expired_session_is_unauthorized(api):
    with plain_tx(api.pool) as cursor:
        cursor.execute("UPDATE auth_sessions SET created_at = now() - interval '1 day', "
                       "expires_at = now() - interval '1 second' WHERE user_id = %s",
                       (api.world.user_id,))
    assert_error(post_run(api), 401, "unauthorized")


def test_worker_command_line_uses_real_platform_and_test_database(api, ai_database, tmp_path):
    api.provider.enqueue("POST /api/chat",
        Reply(body=ollama_chat(tool_calls=[{"function": {
            "name": "finance.read", "arguments": {"query": "accounts"},
        }}])),
        Reply(body=ollama_chat(content=json.dumps({"summary_pt_br": "Contas consultadas."}))),
    )
    run_id = post_run(api).json["run_id"]
    # Ambiente próprio, sem dotenv nem credenciais externas. A URL é do banco descartável.
    env = {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join(sys.path), "PYTHONIOENCODING": "utf-8",
        "TEMP": str(tmp_path), "TMP": str(tmp_path), "AI_ENABLED": "true",
        "DATABASE_V2_URL": ai_database.app_dsn,
        "AI_MODEL_REGISTRY_PATH": api.settings.model_registry_path,
        "AI_OLLAMA_BASE_URL": api.provider.base_url,
    }
    process = subprocess.run([sys.executable, "-m", "services.ai.worker", "--once"],
                             env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stderr
    result = api.client.get(PREFIX + "/runs/" + run_id)
    assert result.json["status"] == "completed", result.json["error"]
    assert result.json["sources"]
    assert api.provider.count("POST /api/chat") == 2


def _limited_app(api):
    """Mesmo aplicativo, com o limitador ligado e contadores zerados."""
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=True)
    limiter.init_app(app)
    limiter.reset()
    app.config["AI_PLATFORM"] = api.platform
    app.config["AUTH_V2_SERVICE"] = api.auth
    app.register_blueprint(auth_bp, url_prefix="/api/v2")
    app.register_blueprint(ai_bp, url_prefix=PREFIX)
    client = app.test_client()
    login = client.post("/api/v2/auth/login", json={"email": "titular-alfa@example.test", "password": PASSWORD})
    assert login.status_code == 200
    return client, {"X-CSRF-Token": login.json["csrf_token"]}


@pytest.mark.integration
def test_polling_a_run_is_not_cut_by_the_global_default_limit(api):
    """O padrão global do app (50 por hora) não pode valer para o acompanhamento."""
    client, headers = _limited_app(api)
    try:
        created = client.post(PREFIX + "/runs", json=payload(api), headers=headers)
        assert created.status_code == 202
        path = PREFIX + "/runs/" + created.json["run_id"]
        statuses = {client.get(path).status_code for _ in range(60)}
        assert statuses == {200}
    finally:
        limiter.reset()


@pytest.mark.integration
def test_rate_limit_answers_in_contract_format_and_is_per_session(api):
    client, headers = _limited_app(api)
    try:
        responses = [client.post(PREFIX + "/runs", json=payload(api), headers=headers) for _ in range(31)]
        assert [item.status_code for item in responses[:30]] == [202] * 30
        limited = responses[30]
        assert limited.status_code == 429
        assert set(limited.json["error"]) == ERROR_KEYS
        assert limited.json["error"]["code"] == "rate_limited" and limited.json["error"]["retryable"] is True
        assert limited.headers["X-Trace-Id"] == limited.json["error"]["trace_id"]
        # Outra sessão do mesmo IP tem cota própria: a chave é a sessão.
        other = api.app.test_client()
        other_login = other.post("/api/v2/auth/login", json={"email": "titular-alfa@example.test", "password": PASSWORD})
        other_client, other_headers = client.application.test_client(), {"X-CSRF-Token": other_login.json["csrf_token"]}
        other_client.set_cookie("alcahub_session", other.get_cookie("alcahub_session").value)
        assert other_client.post(PREFIX + "/runs", json=payload(api), headers=other_headers).status_code == 202
    finally:
        limiter.reset()
