import json
import os
import subprocess
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Binário do CLI: "openclaw" (npm install -g openclaw) ou path customizado via env
OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://openclaw-gateway:18789")
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "90"))


class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None


def run_openclaw_agent(message: str) -> dict:
    """
    Ajuste o comando final conforme a saída de:
      openclaw agent --help

    A estrutura abaixo é a correta arquiteturalmente.
    O detalhe fino dos argumentos pode variar conforme a versão do OpenClaw.
    """
    if not message or not message.strip():
        return {"message": "Mensagem vazia."}

    # Split the bin in case it's a command with arguments like "node dist/index.js"
    bin_parts = OPENCLAW_BIN.split()
    
    cmd = bin_parts + [
        "agent",
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
        raise HTTPException(status_code=504, detail="OpenClaw CLI execution timed out")

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "OpenClaw agent failed"
        # We might not want to raise 500 right away, but return failure softly
        return {
            "message": f"Erro interno no bot: {error_msg}",
            "raw": result.stdout.strip()
        }

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
    try:
        r = requests.get(f"{OPENCLAW_GATEWAY_URL.rstrip('/')}/health", timeout=5)
        if r.status_code != 200:
            return {"ok": False, "gateway_status": r.status_code}

        payload = r.json()
        return {
            "ok": payload.get("ok") is True,
            "gateway": payload,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        data = run_openclaw_agent(req.message)

        return {
            "message": data.get("message") or data.get("response") or data.get("raw") or "",
            "conversation_id": req.conversation_id,
            "metadata": data,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="OpenClaw timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    return {
        "history": [],
        "conversation_id": conversation_id,
    }
