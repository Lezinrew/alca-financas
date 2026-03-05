#!/bin/bash
###############################################################################
# Deploy Local - Alça Finanças
# Script para iniciar ambiente de desenvolvimento local com Docker
###############################################################################

set -e

echo "🚀 Iniciando ambiente local do Alça Finanças..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado.${NC}"
    echo -e "${YELLOW}   Crie um .env com suas credenciais Supabase:${NC}"
    echo ""
    echo "SUPABASE_URL=https://seu-projeto.supabase.co"
    echo "SUPABASE_SERVICE_ROLE_KEY=eyJ..."
    echo "SECRET_KEY=\$(openssl rand -hex 32)"
    echo "JWT_SECRET=\$(openssl rand -hex 32)"
    echo ""
    exit 1
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
    echo -e "${RED}❌ Docker daemon não está rodando${NC}"
    echo -e "${YELLOW}   Inicie o Docker Desktop ou docker service${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker daemon está rodando${NC}"

# Stop existing containers
echo -e "${BLUE}🛑 Parando containers existentes...${NC}"
docker-compose down || true

# Start services
echo -e "${BLUE}🚀 Iniciando serviços com Docker Compose...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${BLUE}⏳ Aguardando serviços iniciarem...${NC}"
sleep 5

# Check backend health
echo -e "${BLUE}🔍 Verificando saúde do backend...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend está saudável${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${YELLOW}⚠️  Backend ainda não está respondendo. Verifique os logs.${NC}"
    fi
    sleep 2
done

# Check frontend
echo -e "${BLUE}🔍 Verificando frontend...${NC}"
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend está acessível${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend ainda não está acessível. Aguarde alguns segundos.${NC}"
fi

echo ""
echo -e "${GREEN}✅ Ambiente local iniciado com sucesso!${NC}"
echo ""
echo -e "${BLUE}📍 Serviços disponíveis:${NC}"
echo "   🌐 Frontend:    http://localhost:3000"
echo "   🔧 Backend API: http://localhost:8001"
echo "   📊 Health:      http://localhost:8001/api/health"
echo ""
echo -e "${BLUE}📝 Comandos úteis:${NC}"
echo "   Ver logs:       docker-compose logs -f"
echo "   Logs backend:   docker-compose logs -f backend"
echo "   Logs frontend:  docker-compose logs -f frontend"
echo "   Parar tudo:     docker-compose down"
echo "   Restart:        docker-compose restart"
echo ""
echo -e "${BLUE}🗄️  Banco de dados:${NC}"
echo "   Usando Supabase (configurado em .env)"
echo "   Dashboard: https://app.supabase.com"
echo ""
