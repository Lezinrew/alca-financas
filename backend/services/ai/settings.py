"""Configuração da plataforma de IA lida do ambiente.

Somente nomes e valores não sensíveis. Chaves de provedores são lidas pelos
adaptadores no momento da chamada e nunca ficam neste objeto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


MIB = 1024 * 1024


def _flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class AiSettings:
    # Feature flags independentes (contrato, seção 14). Tudo desligado por padrão.
    enabled: bool = False
    cloud_enabled: bool = False
    email_enabled: bool = False
    write_enabled: bool = False
    # Resposta por WhatsApp depende de vínculo de remetente verificado
    # (etapa 5 do contrato); permanece desligada até lá.
    whatsapp_enabled: bool = False

    # Orçamento global de tentativas e tempo (contrato, seção 8).
    max_inference_calls_per_step: int = 3
    max_tool_calls_per_run: int = 8
    inference_timeout_s: int = 60
    run_timeout_s: int = 180

    # Circuito: N falhas transitórias em uma janela abrem o circuito.
    circuit_failures: int = 3
    circuit_window_s: int = 60
    circuit_open_s: int = 60

    # Retenção e limites de arquivo (contrato, seções 10 e 11).
    proposal_ttl_hours: int = 24
    artifact_ttl_days: int = 7
    artifact_max_bytes: int = 20 * MIB
    pdf_max_pages: int = 100

    # Fila.
    lease_seconds: int = 90
    inline_worker: bool = False

    # Caminhos e endpoints (não sensíveis).
    quarantine_dir: Optional[str] = None
    model_registry_path: Optional[str] = None
    allow_candidate_models: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    # Conector de e-mail: none | fixture | mcp_http.
    email_connector: str = "none"
    email_fixture_dir: Optional[str] = None
    # Arquivo JSON com URL, mapa de ferramentas e lista de permissão do
    # servidor MCP de e-mail (sem credenciais).
    email_mcp_config_path: Optional[str] = None
    # Moeda dos tetos de custo e fuso que define "dia" e "mês" do orçamento.
    budget_currency: str = "USD"
    budget_timezone: str = "America/Sao_Paulo"
    worker_id: Optional[str] = None

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "AiSettings":
        env = os.environ if env is None else env
        return cls(
            enabled=_flag(env, "AI_ENABLED"),
            cloud_enabled=_flag(env, "AI_CLOUD_ENABLED"),
            email_enabled=_flag(env, "AI_EMAIL_ENABLED"),
            write_enabled=_flag(env, "AI_WRITE_ENABLED"),
            whatsapp_enabled=_flag(env, "AI_WHATSAPP_ENABLED"),
            max_inference_calls_per_step=_int(env, "AI_MAX_INFERENCE_CALLS_PER_STEP", 3, 1, 10),
            max_tool_calls_per_run=_int(env, "AI_MAX_TOOL_CALLS_PER_RUN", 8, 1, 50),
            inference_timeout_s=_int(env, "AI_INFERENCE_TIMEOUT_S", 60, 1, 600),
            run_timeout_s=_int(env, "AI_RUN_TIMEOUT_S", 180, 5, 3600),
            circuit_failures=_int(env, "AI_CIRCUIT_FAILURES", 3, 1, 50),
            circuit_window_s=_int(env, "AI_CIRCUIT_WINDOW_S", 60, 1, 3600),
            circuit_open_s=_int(env, "AI_CIRCUIT_OPEN_S", 60, 1, 3600),
            proposal_ttl_hours=_int(env, "AI_PROPOSAL_TTL_HOURS", 24, 1, 24 * 30),
            artifact_ttl_days=_int(env, "AI_ARTIFACT_TTL_DAYS", 7, 1, 90),
            artifact_max_bytes=_int(env, "AI_ARTIFACT_MAX_BYTES", 20 * MIB, 1024, 20 * MIB),
            pdf_max_pages=_int(env, "AI_PDF_MAX_PAGES", 100, 1, 100),
            lease_seconds=_int(env, "AI_LEASE_SECONDS", 90, 5, 3600),
            inline_worker=_flag(env, "AI_INLINE_WORKER"),
            quarantine_dir=(env.get("AI_QUARANTINE_DIR") or "").strip() or None,
            model_registry_path=(env.get("AI_MODEL_REGISTRY_PATH") or "").strip() or None,
            allow_candidate_models=_flag(env, "AI_ALLOW_CANDIDATE_MODELS"),
            ollama_base_url=(env.get("AI_OLLAMA_BASE_URL") or "http://127.0.0.1:11434").strip().rstrip("/"),
            email_connector=(env.get("AI_EMAIL_CONNECTOR") or "none").strip().lower(),
            email_fixture_dir=(env.get("AI_EMAIL_FIXTURE_DIR") or "").strip() or None,
            email_mcp_config_path=(env.get("AI_EMAIL_MCP_CONFIG_PATH") or "").strip() or None,
            budget_currency=((env.get("AI_BUDGET_CURRENCY") or "USD").strip().upper() or "USD")[:3],
            budget_timezone=(env.get("AI_BUDGET_TIMEZONE") or "America/Sao_Paulo").strip(),
            worker_id=(env.get("AI_WORKER_ID") or "").strip() or None,
        )

    def resolved_quarantine_dir(self) -> Path:
        if self.quarantine_dir:
            return Path(self.quarantine_dir)
        # Fora da árvore servida pelo app e ignorado pelo git (ver .gitignore).
        return Path(__file__).resolve().parents[2] / "var" / "ai-quarantine"

    def resolved_model_registry_path(self) -> Path:
        if self.model_registry_path:
            return Path(self.model_registry_path)
        return Path(__file__).resolve().parent / "config" / "models.json"
