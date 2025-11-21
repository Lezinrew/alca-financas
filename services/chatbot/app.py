from __future__ import annotations

import os
import uuid
import jwt
import requests
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

SERVICE_NAME = "Alça Finanças Chatbot"
DEFAULT_GREETING = (
    "Olá! Eu sou o assistente virtual da Alça Finanças. "
    "Como posso ajudá-lo hoje? Posso responder sobre suas transações, contas, categorias e muito mais!"
)

# Configuração
JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "dev-secret-key"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001")

security = HTTPBearer()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    suggestions: Optional[list[str]] = None


app = FastAPI(
    title=SERVICE_NAME,
    version="0.1.0",
    description="Serviço independente responsável pelo chatbot da plataforma.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.alcahub.com.br",
        "https://alcahub.com.br",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verifica o token JWT e retorna o user_id."""
    try:
        token = credentials.credentials
        # Armazena token para uso nas requisições
        verify_token._current_token = token
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def get_user_data(user_id: str, endpoint: str, token: Optional[str] = None) -> Optional[dict]:
    """Busca dados do usuário na API."""
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def build_reply(message: str, user_id: Optional[str] = None, token: Optional[str] = None) -> tuple[str, list[str]]:
    """Gera uma resposta inteligente baseada na mensagem e dados do usuário."""
    lower_msg = message.lower()
    suggestions = []
    
    # Saldo e contas
    if any(word in lower_msg for word in ["saldo", "conta", "contas", "quanto tenho"]):
        if user_id and token:
            accounts = get_user_data(user_id, "/api/accounts", token)
            if accounts and len(accounts) > 0:
                total = sum(acc.get("balance", 0) for acc in accounts)
                accounts_list = "\n".join([
                    f"• {acc.get('name', 'Conta')}: R$ {acc.get('balance', 0):,.2f}"
                    for acc in accounts[:5]
                ])
                reply = f"📊 Seu saldo total é **R$ {total:,.2f}**\n\nContas:\n{accounts_list}"
                suggestions = ["Ver transações", "Adicionar transação", "Ver relatórios"]
                return reply, suggestions
        return "Para ver seu saldo, acesse a seção de Contas no menu principal.", ["Ver contas", "Adicionar conta"]
    
    # Transações recentes
    if any(word in lower_msg for word in ["transação", "transações", "gastos", "receitas", "últimas"]):
        if user_id and token:
            transactions = get_user_data(user_id, "/api/transactions?limit=5", token)
            if transactions and transactions.get("data"):
                trans_list = "\n".join([
                    f"• {t.get('description', 'Sem descrição')}: R$ {t.get('amount', 0):,.2f} ({t.get('type', 'despesa')})"
                    for t in transactions["data"][:5]
                ])
                reply = f"📝 Suas últimas transações:\n\n{trans_list}"
                suggestions = ["Ver todas", "Adicionar transação", "Filtrar por categoria"]
                return reply, suggestions
        return "Para ver suas transações, acesse a seção de Transações no menu.", ["Ver transações", "Adicionar transação"]
    
    # Categorias
    if any(word in lower_msg for word in ["categoria", "categorias", "gastos por"]):
        if user_id and token:
            categories = get_user_data(user_id, "/api/categories", token)
            if categories and len(categories) > 0:
                cats_list = "\n".join([
                    f"• {cat.get('name', 'Categoria')}"
                    for cat in categories[:10]
                ])
                reply = f"🏷️ Suas categorias:\n\n{cats_list}"
                suggestions = ["Criar categoria", "Ver relatórios por categoria"]
                return reply, suggestions
        return "Para gerenciar categorias, acesse a seção de Categorias no menu.", ["Ver categorias", "Criar categoria"]
    
    # Dashboard e resumo
    if any(word in lower_msg for word in ["resumo", "dashboard", "visão geral", "estatísticas"]):
        if user_id and token:
            dashboard = get_user_data(user_id, "/api/dashboard", token)
            if dashboard:
                reply = f"📊 **Resumo Financeiro:**\n\n"
                reply += f"• Saldo Atual: R$ {dashboard.get('current_balance', 0):,.2f}\n"
                reply += f"• Receitas (mês): R$ {dashboard.get('monthly_income', 0):,.2f}\n"
                reply += f"• Despesas (mês): R$ {dashboard.get('monthly_expenses', 0):,.2f}\n"
                suggestions = ["Ver relatórios", "Ver transações", "Ver gráficos"]
                return reply, suggestions
        return "Para ver o resumo, acesse o Dashboard no menu principal.", ["Ver dashboard", "Ver relatórios"]
    
    # Cartões de crédito
    if any(word in lower_msg for word in ["cartão", "cartões", "limite", "fatura"]):
        return (
            "💳 Para gerenciar seus cartões de crédito:\n\n"
            "1. Acesse 'Cartões de Crédito' no menu\n"
            "2. Clique em um cartão para ver detalhes\n"
            "3. Você pode editar limite, ver faturas e despesas\n\n"
            "Quer que eu mostre como adicionar um novo cartão?"
        ), ["Ver cartões", "Adicionar cartão", "Ver faturas"]
    
    # Planejamento
    if any(word in lower_msg for word in ["planejamento", "orçamento", "meta", "metas"]):
        return (
            "📅 **Planejamento Financeiro:**\n\n"
            "O módulo de Planejamento ajuda você a:\n"
            "• Definir metas mensais por categoria\n"
            "• Acompanhar gastos vs. planejado\n"
            "• Visualizar progresso em gráficos\n\n"
            "Acesse 'Planejamento' no menu para começar!"
        ), ["Ver planejamento", "Criar planejamento", "Ver metas"]
    
    # Relatórios
    if any(word in lower_msg for word in ["relatório", "relatórios", "gráfico", "análise"]):
        return (
            "📈 **Relatórios e Análises:**\n\n"
            "Acesse a seção 'Relatórios' para:\n"
            "• Ver evolução de receitas e despesas\n"
            "• Análise por categoria\n"
            "• Comparativos mensais\n"
            "• Exportar dados\n\n"
            "Quer que eu mostre algum relatório específico?"
        ), ["Ver relatórios", "Ver gráficos", "Exportar dados"]
    
    # Ajuda geral
    if any(word in lower_msg for word in ["ajuda", "help", "como usar", "funcionalidades"]):
        return (
            "🤖 **Como posso ajudar:**\n\n"
            "Posso responder sobre:\n"
            "• Saldo e contas\n"
            "• Transações recentes\n"
            "• Categorias\n"
            "• Resumo financeiro\n"
            "• Cartões de crédito\n"
            "• Planejamento\n"
            "• Relatórios\n\n"
            "Basta me perguntar! 😊"
        ), ["Ver saldo", "Ver transações", "Ver dashboard"]
    
    # App mobile
    if any(word in lower_msg for word in ["app", "mobile", "celular", "android", "ios"]):
        return (
            "📱 **App Mobile:**\n\n"
            "O app mobile utiliza a mesma API em https://api.alcahub.com.br.\n"
            "Basta fazer login com o mesmo usuário da versão web.\n\n"
            "Funcionalidades disponíveis:\n"
            "• Todas as funcionalidades da versão web\n"
            "• Sincronização em tempo real\n"
            "• Notificações de transações\n\n"
            "Em breve nas lojas! 🚀"
        ), ["Ver mais", "Suporte"]
    
    # Resposta padrão
    return (
        f"{DEFAULT_GREETING}\n\n"
        "Tente perguntar sobre:\n"
        "• Seu saldo atual\n"
        "• Transações recentes\n"
        "• Categorias\n"
        "• Resumo financeiro\n"
        "• Ou qualquer outra dúvida!"
    ), ["Ver saldo", "Ver transações", "Ver dashboard", "Ajuda"]


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> ChatResponse:
    """Endpoint de chat com autenticação."""
    # Verifica token e obtém user_id
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    reply, suggestions = build_reply(request.message, user_id, token)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        suggestions=suggestions
    )


@app.post("/api/chat/public", response_model=ChatResponse)
def chat_public(request: ChatRequest) -> ChatResponse:
    """Endpoint de chat público (sem autenticação) para perguntas gerais."""
    reply, suggestions = build_reply(request.message)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        suggestions=suggestions
    )


CHATBOT_PORT = int(os.getenv("CHATBOT_PORT", "8100"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.chatbot.app:app",
        host="127.0.0.1",
        port=CHATBOT_PORT,
        reload=True,
    )

