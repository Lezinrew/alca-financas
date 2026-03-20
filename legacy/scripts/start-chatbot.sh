#!/bin/bash

# Script to start the chatbot service for Alça Finanças
# Runs on port 8100

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🤖 Iniciando Assistente Virtual...${NC}"

# Carregar variáveis de ambiente do root .env se existir
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

cd services/chatbot

if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

# Inicia o chatbot em background
# Garante que uvicorn use 127.0.0.1 em vez de 0.0.0.0 se for local
uvicorn app:app --host 127.0.0.1 --port 8100 > ../../logs/chatbot.log 2>&1 &
CHATBOT_PID=$!

echo $CHATBOT_PID > ../../logs/chatbot.pid
echo -e "${GREEN}✅ Chatbot rodando (PID: $CHATBOT_PID)${NC}"
