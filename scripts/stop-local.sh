#!/bin/bash

###############################################################################
# Stop Local - Alça Finanças
# Script para parar ambiente de desenvolvimento local
###############################################################################

set -e

echo "🛑 Parando serviços locais do Alça Finanças..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Stop Backend
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if ps -p $BACKEND_PID > /dev/null; then
        echo "🛑 Parando Backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
        rm logs/backend.pid
    fi
fi

# Stop Frontend
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null; then
        echo "🛑 Parando Frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
        rm logs/frontend.pid
    fi
fi

# Stop Docker containers (if Docker is running)
if docker info > /dev/null 2>&1; then
    echo "🛑 Parando containers Docker..."
    docker-compose down || true
else
    echo "ℹ️  Docker daemon não está rodando, pulando containers"
fi

echo -e "${GREEN}✅ Todos os serviços foram parados${NC}"
