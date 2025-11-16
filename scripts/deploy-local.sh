#!/bin/bash

###############################################################################
# Deploy Local - Alça Finanças
# Script para iniciar ambiente de desenvolvimento local
###############################################################################

set -e

echo "🚀 Iniciando deploy local do Alça Finanças..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado. Copiando de .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Arquivo .env criado. Configure as variáveis necessárias.${NC}"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado. Instale Docker primeiro.${NC}"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado. Instale Docker Compose primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker e Docker Compose encontrados${NC}"

# Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Docker daemon não está rodando${NC}"
    echo -e "${YELLOW}   Continuando sem Docker. Certifique-se de ter MongoDB rodando localmente.${NC}"
    USE_DOCKER=false
else
    echo -e "${GREEN}✅ Docker daemon está rodando${NC}"
    USE_DOCKER=true

    # Stop existing containers
    echo "🛑 Parando containers existentes..."
    docker-compose down || true

    # Start MongoDB
    echo "🗄️  Iniciando MongoDB via Docker..."
    docker-compose up -d mongo

    # Wait for MongoDB
    echo "⏳ Aguardando MongoDB..."
    sleep 5
fi

# Check MongoDB connection
echo "🔍 Verificando conexão com MongoDB..."
if command -v mongosh &> /dev/null; then
    if mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MongoDB está acessível${NC}"
    else
        echo -e "${YELLOW}⚠️  MongoDB não está acessível. Inicie MongoDB manualmente.${NC}"
    fi
elif command -v mongo &> /dev/null; then
    if mongo --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MongoDB está acessível${NC}"
    else
        echo -e "${YELLOW}⚠️  MongoDB não está acessível. Inicie MongoDB manualmente.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  MongoDB client não encontrado. Certifique-se de ter MongoDB rodando.${NC}"
fi

# Backend setup
echo "🔧 Configurando Backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual Python..."
    python3 -m venv venv
fi

echo "📦 Ativando ambiente virtual..."
source venv/bin/activate

echo "📦 Instalando dependências do Backend..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -r requirements-dev.txt

echo "✅ Backend configurado"
cd ..

# Frontend setup
echo "🎨 Configurando Frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências do Frontend..."
    npm install
else
    echo "✅ Dependências já instaladas"
fi

echo "✅ Frontend configurado"
cd ..

# Start services
echo "🚀 Iniciando serviços..."

# Start Backend in background
echo "🔧 Iniciando Backend API..."
cd backend
source venv/bin/activate
python app.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
cd ..

# Wait for backend
sleep 3

# Start Frontend
echo "🎨 Iniciando Frontend..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
cd ..

echo ""
echo -e "${GREEN}✅ Deploy local concluído!${NC}"
echo ""
echo "📍 Serviços disponíveis:"
echo "   🌐 Frontend: http://localhost:3000"
echo "   🔧 Backend API: http://localhost:5000"
echo "   🗄️  MongoDB: mongodb://localhost:27017"
echo ""
echo "📝 Logs disponíveis em:"
echo "   Backend: logs/backend.log"
echo "   Frontend: logs/frontend.log"
echo ""
echo "🛑 Para parar os serviços, execute:"
echo "   ./scripts/stop-local.sh"
echo ""
