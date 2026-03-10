import json
import logging
import os
import subprocess
import time
import uuid
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI()

# Env explícitos: defaults alinhados ao docker-compose.prod.yml
OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
OPENCLAW_GATEWAY_URL = (os.getenv("OPENCLAW_GATEWAY_URL") or "http://openclaw-gateway:18789").rstrip("/")
_raw_timeout = os.getenv("OPENCLAW_TIMEOUT", "90")
try:
    OPENCLAW_TIMEOUT = max(30, min(300, int(_raw_timeout)))
except (TypeError, ValueError):
    OPENCLAW_TIMEOUT = 90


class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None


def run_openclaw_agent(message: str, session_id: str) -> dict:
    """
    Ajuste o comando final conforme a saída de:
      openclaw agent --help

    A estrutura abaixo é a correta arquiteturalmente.
    O detalhe fino dos argumentos pode variar conforme a versão do OpenClaw.
    """
    msg_len = len(message.strip()) if message else 0
    if not message or not message.strip():
        return {"message": "Mensagem vazia."}

    t0 = time.perf_counter()
    logger.info(
        "bridge_agent_start session_id=%s message_len=%s",
        session_id, msg_len
    )

    bin_parts = OPENCLAW_BIN.split()
    cmd = bin_parts + [
        "agent",
        "--session-id",
        session_id,
        "--message",
        message.strip(),
        "--json",
    ]

    env = os.environ.copy()
    env["OPENCLAW_GATEWAY_URL"] = OPENCLAW_GATEWAY_URL

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OPENCLAW_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "bridge_timeout session_id=%s message_len=%s elapsed_ms=%s",
            session_id, msg_len, elapsed_ms
        )
        raise HTTPException(status_code=504, detail="OpenClaw CLI execution timed out")

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "OpenClaw agent failed"
        logger.warning(
            "bridge_agent_end session_id=%s message_len=%s elapsed_ms=%s returncode=%s outcome=cli_error",
            session_id, msg_len, elapsed_ms, result.returncode
        )
        return {
            "message": f"Erro interno no bot: {error_msg}",
            "raw": result.stdout.strip()
        }

    logger.info(
        "bridge_agent_end session_id=%s message_len=%s elapsed_ms=%s returncode=0 outcome=success",
        session_id, msg_len, elapsed_ms
    )

    stdout = result.stdout.strip()
    try:
        return json.loads(stdout)
    except Exception:
        return {
            "message": stdout,
            "raw": stdout,
        }


@app.get("/health")
def health():
    """Disponibilidade do bridge + gateway. Backend usa este endpoint para /api/chatbot/health."""
    try:
        r = requests.get(f"{OPENCLAW_GATEWAY_URL}/health", timeout=5)
        if r.status_code != 200:
            logger.warning(
                "gateway_health_failure gateway_url=%s status_code=%s",
                OPENCLAW_GATEWAY_URL, r.status_code
            )
            return {"ok": False, "gateway_status": r.status_code}

        payload = r.json()
        ok = payload.get("ok") is True
        if not ok:
            logger.warning(
                "gateway_health_failure gateway_url=%s response_ok=False payload=%s",
                OPENCLAW_GATEWAY_URL, payload
            )
        return {
            "ok": ok,
            "gateway": payload,
        }
    except Exception as e:
        logger.warning(
            "gateway_health_failure gateway_url=%s error=%s",
            OPENCLAW_GATEWAY_URL, e
        )
        return {"ok": False, "error": str(e)}


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Usa conversation_id como session-id se existir; caso contrário gera um novo
    UUID e o devolve como conversation_id para o cliente reutilizar.
    """
    try:
        session_id = req.conversation_id or str(uuid.uuid4())
        data = run_openclaw_agent(req.message, session_id=session_id)

        return {
            "message": data.get("message") or data.get("response") or data.get("raw") or "",
            "conversation_id": session_id,
            "metadata": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("bridge_unexpected_error chat endpoint error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    return {
        "history": [],
        "conversation_id": conversation_id,
    }
