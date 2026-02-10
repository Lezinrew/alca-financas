#!/bin/bash

###############################################################################
# Start MongoDB - Alça Finanças
# Script para iniciar MongoDB localmente (com ou sem Docker)
###############################################################################

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🗄️  Iniciando MongoDB para Alça Finanças${NC}\n"

# Option 1: Try Docker first
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker está disponível${NC}"
    echo "🐳 Iniciando MongoDB via Docker..."

    # Check if port 27017 is already in use
    if lsof -Pi :27017 -sTCP:LISTEN -t >/dev/null 2>&1 || nc -z localhost 27017 >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Porta 27017 já está em uso${NC}"
        echo "🔍 Verificando se é MongoDB..."

        # Test if it's actually MongoDB
        if docker exec alca-mongo mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1 || \
           mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1 || \
           mongo --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ MongoDB já está rodando e acessível!${NC}"
            echo "📍 Conexão: mongodb://localhost:27017/alca_financas"
            exit 0
        else
            echo -e "${RED}❌ Porta 27017 está ocupada mas não é MongoDB${NC}"
            echo "Por favor, libere a porta 27017 ou use outra porta"
            exit 1
        fi
    fi

    # Check if mongo container exists
    if docker ps -a | grep -q alca-mongo; then
        echo "♻️  Container MongoDB já existe, reiniciando..."
        docker start alca-mongo
    else
        echo "📦 Criando container MongoDB..."
        docker run -d \
            --name alca-mongo \
            -p 27017:27017 \
            -v alca-mongo-data:/data/db \
            -e MONGO_INITDB_DATABASE=alca_financas \
            mongo:6.0
    fi

    echo "⏳ Aguardando MongoDB inicializar..."
    sleep 5

    # Test connection
    if docker exec alca-mongo mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MongoDB está rodando!${NC}"
        echo "📍 Conexão: mongodb://localhost:27017/alca_financas"
        exit 0
    else
        echo -e "${YELLOW}⚠️  MongoDB container iniciado mas não respondendo${NC}"
    fi

# Option 2: Check if MongoDB is already running locally
elif command -v mongosh &> /dev/null || command -v mongo &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker não disponível${NC}"
    echo "🔍 Verificando MongoDB local..."

    if mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1 || mongo --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MongoDB já está rodando localmente!${NC}"
        echo "📍 Conexão: mongodb://localhost:27017/alca_financas"
        exit 0
    else
        echo -e "${RED}❌ MongoDB não está rodando${NC}"
        echo ""
        echo "Por favor, inicie MongoDB manualmente:"
        echo ""
        echo "macOS (Homebrew):"
        echo "  brew services start mongodb-community"
        echo ""
        echo "Linux:"
        echo "  sudo systemctl start mongod"
        echo ""
        echo "Windows:"
        echo "  net start MongoDB"
        echo ""
        exit 1
    fi

# Option 3: No MongoDB found
else
    echo -e "${RED}❌ MongoDB não encontrado${NC}"
    echo ""
    echo "Instale MongoDB usando uma das opções:"
    echo ""
    echo "1. Com Docker (recomendado):"
    echo "   - Instale Docker Desktop: https://www.docker.com/products/docker-desktop"
    echo "   - Execute: docker run -d -p 27017:27017 --name alca-mongo mongo:6.0"
    echo ""
    echo "2. Instalação local:"
    echo "   macOS: brew install mongodb-community"
    echo "   Ubuntu: https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/"
    echo "   Windows: https://docs.mongodb.com/manual/tutorial/install-mongodb-on-windows/"
    echo ""
    exit 1
fi
