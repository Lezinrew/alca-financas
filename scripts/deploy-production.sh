#!/bin/bash

###############################################################################
# Deploy Production - Alça Finanças
# Script para deploy em produção (alcahub.com.br)
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Deploy para Produção - alcahub.com.br${NC}"
echo ""

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${RED}❌ Arquivo .env não encontrado${NC}"
    exit 1
fi

# Confirmation
echo -e "${YELLOW}⚠️  Você está prestes a fazer deploy em PRODUÇÃO${NC}"
echo -e "Host: ${DEPLOY_HOST}"
echo -e "User: ${DEPLOY_USER}"
echo ""
read -p "Continuar? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deploy cancelado"
    exit 0
fi

# Run tests first
echo -e "${BLUE}🧪 Executando testes antes do deploy...${NC}"
./scripts/run-tests.sh all local

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Testes falhou. Deploy cancelado.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Todos os testes passaram${NC}\n"

# Build Backend Docker Image
echo -e "${BLUE}🔧 Building Backend Docker image...${NC}"
cd backend
docker build -t alcahub/backend:latest -t alcahub/backend:$(git rev-parse --short HEAD) .
cd ..

# Build Frontend
echo -e "${BLUE}🎨 Building Frontend...${NC}"
cd frontend
export VITE_API_URL=https://api.alcahub.com.br
export NODE_ENV=production
npm run build
cd ..

# Deploy to server
echo -e "${BLUE}📦 Deploying to production server...${NC}"

# Backup current version
echo "💾 Creating backup..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && ./scripts/backup.sh"

# Deploy Backend
echo "🔧 Deploying Backend..."
docker save alcahub/backend:latest | ssh ${DEPLOY_USER}@${DEPLOY_HOST} "docker load"
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && docker-compose pull backend && docker-compose up -d backend"

# Deploy Frontend
echo "🎨 Deploying Frontend..."
rsync -avz --delete frontend/dist/ ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/frontend/dist/

# Restart services
echo "🔄 Restarting services..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "sudo systemctl reload nginx"

# Health check
echo -e "${BLUE}🏥 Running health checks...${NC}"
sleep 5

# Check API
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://api.alcahub.com.br/api/health)
if [ "$API_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${RED}❌ API health check failed (Status: $API_STATUS)${NC}"
    exit 1
fi

# Check Frontend
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://alcahub.com.br)
if [ "$WEB_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Frontend is healthy${NC}"
else
    echo -e "${RED}❌ Frontend health check failed (Status: $WEB_STATUS)${NC}"
    exit 1
fi

# Run smoke tests
echo -e "${BLUE}🧪 Running production smoke tests...${NC}"
cd frontend
export TEST_ENV=production
npx playwright test e2e/auth.spec.ts e2e/dashboard.spec.ts --project=chromium
cd ..

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Smoke tests passed${NC}"
else
    echo -e "${YELLOW}⚠️  Some smoke tests failed. Check the results.${NC}"
fi

# Clean up
echo "🧹 Cleaning up..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "docker system prune -f"

echo ""
echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
echo ""
echo "🌐 URLs:"
echo "   Frontend: https://alcahub.com.br"
echo "   API: https://api.alcahub.com.br"
echo ""
echo "📊 Monitore os logs:"
echo "   ssh ${DEPLOY_USER}@${DEPLOY_HOST} 'docker-compose logs -f'"
echo ""
