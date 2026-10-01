"""Homologação opt-in da leitura pela assinatura do Claude (Claude Code oficial).

Mesmas oito perguntas e as mesmas verificações da homologação local com Ollama,
agora pela rota ``plano-claude``. Só roda com ``AI_REAL_CLAUDE_PLAN=1`` e com o
Claude Code logado na conta do titular. Envia à Anthropic apenas dados
sintéticos deste teste. Oito perguntas não substituem o benchmark de 30 casos.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from argon2 import PasswordHasher

from services.ai.db import plain_tx, scoped_tx
from services.ai.platform import build_platform
from services.ai.settings import AiSettings
from services.auth_v2_service import AuthV2Service

from .support import seed
from .test_ai_api_vertical import app_for, post_run
from .test_ai_ollama_local_read import QUESTIONS


pytestmark = pytest.mark.skipif(
    os.getenv("AI_REAL_CLAUDE_PLAN") != "1", reason="Claude pelo plano: execução opt-in"
)
MODEL = os.getenv("AI_REAL_CLAUDE_MODEL", "claude-sonnet-5-5")


@pytest.fixture()
def plan_api(pool, world, other_world, tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_V2_COOKIE_SECURE", "false")
    registry = tmp_path / "models.json"
    registry.write_text(json.dumps({"routes": [{
        "alias": "plano-claude", "provider": "claude_code_cli", "model_id": MODEL,
        "locality": "external", "priority": 1, "state": "candidate",
        "task_classes": ["complex_tools"], "supports_tools": True, "supports_json": True,
        "supports_vision": False, "context_window": 200000, "privacy": ["cloud_allowed"],
        "extra": {"billing": "subscription"},
    }]}), encoding="utf-8")
    settings = AiSettings(
        enabled=True, cloud_enabled=True, allow_candidate_models=True,
        model_registry_path=str(registry), quarantine_dir=str(tmp_path / "quarantine"),
        inference_timeout_s=180, run_timeout_s=600, lease_seconds=660,
        plan_owner_email="titular-alfa@example.test",
    )
    platform = build_platform(pool, settings)
    auth = AuthV2Service(pool)
    password = "senha-sintetica-plano"
    with plain_tx(pool) as cursor:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                       (PasswordHasher().hash(password), world.user_id))
    seed.create_grant(pool, world.tenant_id, world.personal_space_id, world.user_id, capabilities=["finance.read"])
    for amount, kind in [("1000.01", "income"), ("0.29", "income"), ("100.10", "expense"), ("0.20", "expense")]:
        seed.create_transaction(
            pool, world.tenant_id, world.personal_account_id,
            world.income_category_id if kind == "income" else world.expense_category_id,
            description="Lançamento fictício", amount=amount, tx_type=kind, occurred_on=date(2026, 10, 1),
        )
    # Ruído que NÃO pode entrar no realizado: CSV, legado, pendente, fora do mês,
    # outro espaço e outro tenant.
    for overrides in [{"source_file": "manual.csv", "entry_source": "csv"},
                      {"source_file": "legacy:antigo", "entry_source": "manual"},
                      {"status": "pending"}, {"occurred_on": date(2026, 9, 30)},
                      {"account_id": world.business_account_id}]:
        fields = dict(account_id=world.personal_account_id, occurred_on=date(2026, 10, 1))
        fields.update(overrides)
        seed.create_transaction(pool, world.tenant_id, category_id=world.expense_category_id,
                                description="Fora do escopo", amount="99999.99", **fields)
    seed.create_transaction(pool, other_world.tenant_id, other_world.personal_account_id,
                            other_world.expense_category_id, description="Outro tenant fictício",
                            amount="777777.77", occurred_on=date(2026, 10, 1))
    client = app_for(platform, auth).test_client()
    login = client.post("/api/v2/auth/login", json={"email": "titular-alfa@example.test", "password": password})
    assert login.status_code == 200
    return SimpleNamespace(pool=pool, world=world, client=client, platform=platform,
                           headers={"X-CSRF-Token": login.json["csrf_token"]})


@pytest.mark.parametrize("case,message", list(enumerate(QUESTIONS, 1)))
def test_claude_plan_read(plan_api, case, message):
    api = plan_api
    start = time.monotonic()
    accepted = post_run(api, body={
        "task": "finance_question", "message": message, "financial_space_id": api.world.personal_space_id,
        "privacy": "cloud_allowed", "input_refs": [],
    }, **{"Idempotency-Key": "claude-plan-read-%02d" % case})
    assert accepted.status_code == 202
    run_id = accepted.json["run_id"]
    assert api.platform.worker.run_once() == run_id
    result = api.client.get("/api/ai/v1/runs/" + run_id).json
    record = {"case": case, "status": result["status"], "error": result["error"],
              "elapsed_s": round(time.monotonic() - start, 3), "model": result["model"],
              "steps": result["progress"]["steps"], "facts": result["facts"], "warnings": result.get("warnings", [])}
    report_dir = os.getenv("AI_REAL_CLAUDE_REPORT_DIR")
    if report_dir:
        Path(report_dir).mkdir(parents=True, exist_ok=True)
        (Path(report_dir) / ("case-%02d.json" % case)).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("case=%02d status=%s elapsed=%.1fs model=%s" % (
        case, result["status"], record["elapsed_s"], (result["model"] or {}).get("alias")), flush=True)

    assert result["status"] == "completed", result["error"]
    assert (result["model"] or {}).get("alias") == "plano-claude"
    assert any(step["name"] == "finance.read" and step["status"] == "succeeded" for step in result["progress"]["steps"])
    facts = {fact["key"]: fact for fact in result["facts"]}
    # Valores esperados calculados pelo próprio banco, não digitados.
    with scoped_tx(api.pool, api.world.tenant_id) as cursor:
        cursor.execute(
            """SELECT SUM(amount) FILTER (WHERE type='income') AS income,
                      SUM(amount) FILTER (WHERE type='expense') AS expense
               FROM transactions
               WHERE tenant_id=%s AND account_id=%s AND status='paid' AND right(source_file,4)='.ofx'
                 AND occurred_on BETWEEN DATE '2026-10-01' AND DATE '2026-10-31'""",
            (api.world.tenant_id, api.world.personal_account_id),
        )
        expected = cursor.fetchone()
        cursor.execute("SELECT count(*) AS n FROM transactions WHERE tenant_id=%s", (api.world.tenant_id,))
        assert cursor.fetchone()["n"] == 9                                  # nada foi gravado
    for key, value in [("income", expected["income"]), ("expense", expected["expense"]),
                       ("net", expected["income"] - expected["expense"])]:
        assert facts["realized." + key]["value"] == format(value, ".2f")
    refs = {source["ref"] for source in result["sources"]}
    assert refs and all(fact["source_refs"] and set(fact["source_refs"]) <= refs for fact in facts.values())
    assert not result.get("warnings"), result.get("warnings")              # resumo sem número sem lastro
