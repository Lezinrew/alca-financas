from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

SERVICE_NAME = "Alça Finanças Chatbot"
DEFAULT_GREETING = (
    "Olá! Eu sou o assistente virtual da Alça Finanças. "
    "Ainda estou aprendendo, mas já consigo responder dúvidas básicas."
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


app = FastAPI(
    title=SERVICE_NAME,
    version="0.1.0",
    description="Serviço independente responsável pelo chatbot da plataforma.",
)


def build_reply(message: str) -> str:
    """Gera uma resposta simples enquanto a IA real não é integrada."""
    lower_msg = message.lower()

    if "limite" in lower_msg or "cartão" in lower_msg:
        return (
            "Você pode consultar e ajustar o limite dos seus cartões em "
            "Cartões › Selecionar cartão › Ações › Editar limite."
        )

    if "planejamento" in lower_msg or "orçamento" in lower_msg:
        return (
            "O módulo de Planejamento ajuda a definir metas mensais por categoria. "
            "Acesse Planejamento › Novo planejamento e defina suas metas."
        )

    if "app" in lower_msg or "mobile" in lower_msg:
        return (
            "O app mobile utiliza a mesma API em https://api.alcahub.com.br. "
            "Basta fazer login com o mesmo usuário da versão web."
        )

    return DEFAULT_GREETING


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    reply = build_reply(request.message)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    return ChatResponse(reply=reply, conversation_id=conversation_id)


CHATBOT_PORT = int(os.getenv("CHATBOT_PORT", "8100"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.chatbot.app:app",
        host="127.0.0.1",
        port=CHATBOT_PORT,
        reload=True,
    )

