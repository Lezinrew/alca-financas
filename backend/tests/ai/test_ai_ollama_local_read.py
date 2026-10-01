"""Homologação opt-in de leitura: Ollama real, login real e banco descartável.

Não carrega app.py/dotenv. Sem AI_REAL_OLLAMA_URL, não chama nenhum modelo.
Oito perguntas financeiras não substituem o benchmark geral de 30 casos.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from argon2 import PasswordHasher

from services.ai.db import plain_tx, scoped_tx
from services.ai.gateway.adapters.ollama import OllamaAdapter
from services.ai.platform import build_platform
from services.ai.settings import AiSettings
from services.auth_v2_service import AuthV2Service
from .support import seed
from .test_ai_api_vertical import app_for, post_run


QUESTIONS = [
    "Quanto foi realizado em outubro de 2026? Consulte entradas, saídas e saldo.",
    "Qual o total de receitas e despesas realizadas em outubro de 2026?",
    "Consulte o realizado de outubro/2026 e informe o saldo líquido.",
    "Quanto entrou e quanto saiu em outubro de 2026 pelo extrato OFX pago?",
    "Quero os totais realizados de receitas, despesas e resultado de outubro de 2026, com fontes.",
    "Mostre o resumo do realizado mensal de outubro de 2026 deste espaço financeiro.",
    "Apure entradas, saídas e resultado realizado do mês 10 do ano 2026.",
    "Verifique no banco o realizado de outubro de 2026, sem incluir pendências ou lançamentos manuais.",
]
pytestmark = pytest.mark.skipif(not os.getenv("AI_REAL_OLLAMA_URL"), reason="Ollama real: execução opt-in")


class MeasuredOllama(OllamaAdapter):
    """Métricas reais; não armazena prompts nem respostas brutas."""
    def __init__(self, base_url):
        super().__init__(base_url)
        self.measurements = []

    def complete(self, route, request, timeout_s):
        result = super().complete(route, request, timeout_s)
        diagnostic = {"finish_reason": result.finish_reason,
                      "tool_names": [call.name for call in result.tool_calls]}
        try:
            decoded = json.loads(result.content)
            if isinstance(decoded, dict):
                diagnostic["content_json_keys"] = sorted(decoded)
        except ValueError:
            diagnostic["content_is_json"] = False
        self.measurements.append(dict(result.metrics, latency_ms=result.latency_ms, **diagnostic))
        return result

    def build_payload(self, route, request):
        payload = super().build_payload(route, request)
        # Perfil exclusivo deste laboratório com GPU de 8 GiB.
        payload["options"].update(num_gpu=32, num_batch=64, use_mmap=True)
        return payload


@pytest.fixture()
def real_api(pool, world, other_world, tmp_path, monkeypatch):
    url = os.environ["AI_REAL_OLLAMA_URL"]
    assert urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}
    model = os.environ["AI_REAL_OLLAMA_MODEL"]
    digest = os.environ["AI_REAL_OLLAMA_DIGEST"]
    assert ":latest" not in model and len(digest) == 64
    monkeypatch.setenv("AUTH_V2_COOKIE_SECURE", "false")
    registry = tmp_path / "models.json"
    registry.write_text(json.dumps({"routes": [{
        "alias": "local-homologacao-leitura", "provider": "ollama", "model_id": model,
        "digest": digest, "locality": "local", "priority": 1, "state": "candidate",
        "task_classes": ["complex_tools"], "supports_tools": True, "supports_json": True,
        "supports_vision": False, "context_window": 32768,
        "extra": {"num_ctx": 4096, "seed": 7, "keep_alive": "5m"},
    }]}), encoding="utf-8")
    settings = AiSettings(enabled=True, allow_candidate_models=True,
        model_registry_path=str(registry), ollama_base_url=url,
        quarantine_dir=str(tmp_path / "quarantine"), inference_timeout_s=240,
        run_timeout_s=600, lease_seconds=660)
    adapter = MeasuredOllama(url)
    platform = build_platform(pool, settings, adapters={"ollama": adapter})
    auth = AuthV2Service(pool)
    password = "senha-sintetica-ollama"
    with plain_tx(pool) as cursor:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                       (PasswordHasher().hash(password), world.user_id))
    seed.create_grant(pool, world.tenant_id, world.personal_space_id, world.user_id,
                      capabilities=["finance.read"])
    for amount, kind in [("1000.01", "income"), ("0.29", "income"),
                         ("100.10", "expense"), ("0.20", "expense")]:
        seed.create_transaction(pool, world.tenant_id, world.personal_account_id,
            world.income_category_id if kind == "income" else world.expense_category_id,
            description="Lançamento fictício", amount=amount, tx_type=kind, occurred_on=date(2026, 10, 1))
    for overrides in [{"source_file": "manual.csv", "entry_source": "csv"},
                      {"source_file": "legacy:antigo", "entry_source": "manual"},
                      {"status": "pending"}, {"occurred_on": date(2026, 9, 30)},
                      {"account_id": world.business_account_id}]:
        fields = dict(account_id=world.personal_account_id, occurred_on=date(2026, 10, 1))
        fields.update(overrides)
        seed.create_transaction(pool, world.tenant_id, category_id=world.expense_category_id,
                                description="Fora do escopo", amount="99999.99", **fields)
    seed.create_transaction(pool, other_world.tenant_id, other_world.personal_account_id,
        other_world.expense_category_id, description="Outro tenant fictício", amount="777777.77",
        occurred_on=date(2026, 10, 1))
    client = app_for(platform, auth).test_client()
    login = client.post("/api/v2/auth/login", json={"email": "titular-alfa@example.test", "password": password})
    assert login.status_code == 200
    return SimpleNamespace(pool=pool, world=world, client=client, platform=platform,
                           adapter=adapter, headers={"X-CSRF-Token": login.json["csrf_token"]})


@pytest.mark.parametrize("case,message", list(enumerate(QUESTIONS, 1)))
def test_real_ollama_read(real_api, case, message):
    api = real_api
    start = time.monotonic()
    accepted = post_run(api, body={"task": "finance_question", "message": message,
        "financial_space_id": api.world.personal_space_id, "privacy": "local_only", "input_refs": []},
        **{"Idempotency-Key": "ollama-read-%02d" % case})
    assert accepted.status_code == 202
    run_id = accepted.json["run_id"]
    assert api.platform.worker.run_once() == run_id
    response = api.client.get("/api/ai/v1/runs/" + run_id)
    assert response.status_code == 200
    result = response.json
    record = {"case": case, "validation": "not_passed", "status": result["status"], "error": result["error"],
              "elapsed_s": round(time.monotonic() - start, 3), "model": result["model"],
              "metrics": api.adapter.measurements, "warnings": result.get("warnings", []),
              "facts": result["facts"], "sources": result["sources"],
              "steps": result["progress"]["steps"]}
    report_dir = Path(os.environ["AI_REAL_OLLAMA_REPORT_DIR"])
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / ("case-%02d.json" % case)).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("case=%02d status=%s elapsed=%.3fs" % (case, result["status"], record["elapsed_s"]), flush=True)
    with scoped_tx(api.pool, api.world.tenant_id) as cursor:
        cursor.execute("""SELECT SUM(amount) FILTER (WHERE type='income') AS income,
            SUM(amount) FILTER (WHERE type='expense') AS expense FROM transactions
            WHERE tenant_id=%s AND account_id=%s AND status='paid' AND right(source_file,4)='.ofx'
            AND occurred_on BETWEEN DATE '2026-10-01' AND DATE '2026-10-31'""",
            (api.world.tenant_id, api.world.personal_account_id))
        expected = cursor.fetchone()
        cursor.execute("SELECT event_type,metadata FROM audit_events WHERE tenant_id=%s AND entity_id=%s",
                       (api.world.tenant_id, run_id))
        events = cursor.fetchall()
        cursor.execute("SELECT count(*) AS n FROM transactions WHERE tenant_id=%s", (api.world.tenant_id,))
        transaction_count = cursor.fetchone()["n"]
    record["audit_event_types"] = sorted(event["event_type"] for event in events)
    record["transaction_count"] = transaction_count
    record["audit_contains_request"] = message in json.dumps(events, default=str)
    record["native_tool_calls"] = sum(len(item["tool_names"]) for item in api.adapter.measurements)
    (report_dir / ("case-%02d.json" % case)).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    assert transaction_count == 9
    assert {event["event_type"] for event in events} >= {"ai.run.created", "ai.run.finished"}
    assert not record["audit_contains_request"]
    assert result["status"] == "completed", result["error"]
    assert any(step["name"] == "finance.read" and step["status"] == "succeeded"
               for step in result["progress"]["steps"])
    facts = {fact["key"]: fact for fact in result["facts"]}
    for key, value in [("income", expected["income"]), ("expense", expected["expense"]),
                       ("net", expected["income"] - expected["expense"])]:
        assert facts["realized." + key]["value"] == format(value, ".2f")
    refs = {source["ref"] for source in result["sources"]}
    assert refs
    for fact in facts.values():
        assert fact["source_refs"] and set(fact["source_refs"]) <= refs
    assert {event["event_type"] for event in events} >= {"ai.run.created", "ai.run.finished"}
    assert message not in json.dumps(events, default=str)
    assert not result.get("warnings"), result.get("warnings")
    calls = len(api.adapter.measurements)
    assert api.platform.worker.run_once() is None
    assert len(api.adapter.measurements) == calls
    record["validation"] = "passed"
    (report_dir / ("case-%02d.json" % case)).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
