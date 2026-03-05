#!/bin/bash
###############################################################################
# Deploy Production - Alça Finanças
# Script completo para deploy em produção com testes e rollback
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Deploy para Produção - Alça Finanças${NC}"
echo ""

# Load environment variables
if [ -f ".env.deploy" ]; then
    export $(cat .env.deploy | grep -v '^#' | xargs)
else
    echo -e "${RED}❌ Arquivo .env.deploy não encontrado${NC}"
    echo "Crie .env.deploy com:"
    echo "  DEPLOY_HOST=76.13.239.220"
    echo "  DEPLOY_USER=root"
    echo "  DEPLOY_PATH=/var/www/alca-financas"
    echo "  DOMAIN=alcahub.cloud"
    exit 1
fi

# Validar variáveis obrigatórias
: "${DEPLOY_HOST:?DEPLOY_HOST não definido em .env.deploy}"
: "${DEPLOY_USER:?DEPLOY_USER não definido em .env.deploy}"
: "${DEPLOY_PATH:?DEPLOY_PATH não definido em .env.deploy}"
: "${DOMAIN:?DOMAIN não definido em .env.deploy}"

# Confirmation
echo -e "${YELLOW}⚠️  Você está prestes a fazer deploy em PRODUÇÃO${NC}"
echo -e "Host: ${DEPLOY_HOST}"
echo -e "User: ${DEPLOY_USER}"
echo -e "Path: ${DEPLOY_PATH}"
echo -e "Domain: ${DOMAIN}"
echo ""
read -p "Continuar? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deploy cancelado"
    exit 0
fi

# Verificar branch
echo -e "${BLUE}🔍 Verificando branch e status do git...${NC}"
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
    echo -e "${YELLOW}⚠️  Você não está na branch main/master (atual: $CURRENT_BRANCH)${NC}"
    read -p "Continuar mesmo assim? (yes/no): " force_deploy
    if [ "$force_deploy" != "yes" ]; then
        echo "Deploy cancelado"
        exit 0
    fi
fi

# Verificar se há mudanças não commitadas
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ Há mudanças não commitadas:${NC}"
    git status --short
    echo ""
    read -p "Continuar mesmo assim? (yes/no): " force_uncommitted
    if [ "$force_uncommitted" != "yes" ]; then
        echo "Deploy cancelado"
        exit 0
    fi
fi

echo -e "${GREEN}✅ Verificações de git passaram${NC}\n"

# Run tests first (se existir script de teste)
if [ -f "./scripts/run-tests.sh" ]; then
    echo -e "${BLUE}🧪 Executando testes locais...${NC}"
    ./scripts/run-tests.sh all local || {
        echo -e "${RED}❌ Testes falharam. Deploy cancelado.${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ Todos os testes passaram${NC}\n"
fi

# Função de rollback
rollback() {
    echo ""
    echo -e "${YELLOW}🔄 Erro detectado! Iniciando rollback...${NC}"
    ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && git reset --hard HEAD@{1} && docker-compose -f docker-compose.prod.yml restart" || {
        echo -e "${RED}❌ Erro ao executar rollback${NC}"
    }
    echo -e "${RED}❌ Deploy falhou. Rollback concluído.${NC}"
    exit 1
}

# Configurar trap para rollback em caso de erro
trap rollback ERR

# Push para repositório
echo -e "${BLUE}📤 Fazendo push para o repositório...${NC}"
git push origin $(git branch --show-current)
echo -e "${GREEN}✅ Push concluído${NC}\n"

# Deploy to server
echo -e "${BLUE}📦 Fazendo deploy no servidor...${NC}"

# Backup current version
echo "💾 Criando backup..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && git rev-parse HEAD > .backup-commit"

# Pull e rebuild
echo "📥 Atualizando código no servidor..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && git pull origin main"

# Build frontend
echo "🎨 Buildando frontend..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && \
    mkdir -p build/frontend && \
    docker run --rm \
        -v \$(pwd)/frontend:/app \
        -v \$(pwd)/build/frontend:/app/dist \
        -w /app \
        --env-file .env \
        node:20-alpine \
        sh -c 'npm ci && npm run build && cp -r dist/* /app/dist/'"

# Rebuild e restart containers
echo "🔄 Reconstruindo e reiniciando containers..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && \
    docker-compose -f docker-compose.prod.yml build && \
    docker-compose -f docker-compose.prod.yml up -d"

# Health check
echo -e "${BLUE}🏥 Executando health checks...${NC}"
sleep 5

# Check API
API_URL="https://${DOMAIN}/api/health"
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$API_URL" || echo "000")
if [ "$API_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ API está saudável (HTTP $API_STATUS)${NC}"
else
    echo -e "${RED}❌ API health check falhou (Status: $API_STATUS)${NC}"
    rollback
fi

# Check Frontend
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}" || echo "000")
if [ "$WEB_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Frontend está saudável (HTTP $WEB_STATUS)${NC}"
else
    echo -e "${RED}❌ Frontend health check falhou (Status: $WEB_STATUS)${NC}"
    rollback
fi

# Clean up
echo "🧹 Limpando recursos não utilizados..."
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "docker system prune -f"

# Desabilitar trap de erro (deploy foi bem sucedido)
trap - ERR

echo ""
echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
echo ""
echo "🌐 URLs:"
echo "   Frontend: https://${DOMAIN}"
echo "   API: https://${DOMAIN}/api/health"
echo ""
echo "📊 Monitore os logs:"
echo "   ssh ${DEPLOY_USER}@${DEPLOY_HOST} 'cd ${DEPLOY_PATH} && docker-compose -f docker-compose.prod.yml logs -f'"
echo ""

# Notificação opcional (Slack/Discord/Email)
if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    echo "📢 Enviando notificação..."
    COMMIT_MSG=$(git log -1 --pretty=%B)
    COMMIT_HASH=$(git rev-parse --short HEAD)
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"✅ Deploy para produção concluído!\n\nCommit: \`$COMMIT_HASH\`\nMensagem: $COMMIT_MSG\n\nFrontend: https://${DOMAIN}\nAPI: https://${DOMAIN}/api/health\"}" \
        "$SLACK_WEBHOOK_URL" 2>/dev/null || true
fi
