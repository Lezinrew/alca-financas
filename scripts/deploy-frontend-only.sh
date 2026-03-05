#!/bin/bash
###############################################################################
# Deploy Frontend Only - Quick frontend deployment
# Use quando fizer mudanças apenas no frontend (CSS, JS, componentes)
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações (use variáveis de ambiente)
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_SSH_KEY="${SERVER_SSH_KEY:-}"
PROJECT_DIR="${PROJECT_DIR:-/var/www/alca-financas}"
DOMAIN="${DOMAIN:-alcahub.cloud}"

echo -e "${BLUE}🚀 Deploy Frontend Only${NC}"
echo ""

# Validar servidor
if [ -z "$SERVER_HOST" ]; then
    read -p "Digite o hostname/IP do servidor: " SERVER_HOST
    [ -z "$SERVER_HOST" ] && { echo -e "${RED}❌ Hostname é obrigatório${NC}"; exit 1; }
fi

echo -e "${BLUE}📡 Servidor: ${SERVER_USER}@${SERVER_HOST}${NC}"
echo -e "${BLUE}📁 Diretório: ${PROJECT_DIR}${NC}"
echo -e "${BLUE}🌐 Domínio: ${DOMAIN}${NC}"
echo ""

# Construir comando SSH
SSH_CMD="ssh -o StrictHostKeyChecking=no"
if [ -n "$SERVER_SSH_KEY" ]; then
    SSH_KEY_FILE=$(mktemp)
    echo "$SERVER_SSH_KEY" > "$SSH_KEY_FILE"
    chmod 600 "$SSH_KEY_FILE"
    trap "rm -f $SSH_KEY_FILE" EXIT
    SSH_CMD="$SSH_CMD -i $SSH_KEY_FILE"
fi

# Função para executar comandos remotos
remote_exec() {
    $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" "$1"
}

# 1. Git pull
echo -e "${BLUE}📥 Atualizando código...${NC}"
remote_exec "cd ${PROJECT_DIR} && git fetch origin && git reset --hard origin/main"
echo -e "${GREEN}✅ Código atualizado${NC}"
echo ""

# 2. Build frontend remoto (usando Docker para build)
echo -e "${BLUE}🏗️  Buildando frontend no servidor...${NC}"
remote_exec "cd ${PROJECT_DIR} && \
    mkdir -p build/frontend && \
    docker run --rm \
        -v \$(pwd)/frontend:/app \
        -v \$(pwd)/build/frontend:/app/dist \
        -w /app \
        --env-file .env \
        node:20-alpine \
        sh -c 'npm ci && npm run build && cp -r dist/* /app/dist/'"
echo -e "${GREEN}✅ Frontend buildado${NC}"
echo ""

# 3. Restart container frontend
echo -e "${BLUE}🔄 Reiniciando container frontend...${NC}"
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml restart frontend"
echo -e "${GREEN}✅ Frontend reiniciado${NC}"
echo ""

# 4. Teste
echo -e "${BLUE}🧪 Testando aplicação...${NC}"
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Frontend respondendo (HTTP $HTTP_STATUS)${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend pode não estar respondendo (HTTP $HTTP_STATUS)${NC}"
    echo -e "${YELLOW}   Verifique os logs: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs frontend'${NC}"
fi
echo ""

echo -e "${GREEN}✅ Deploy do frontend concluído!${NC}"
echo ""
echo -e "${BLUE}📝 URLs:${NC}"
echo "   Frontend: https://${DOMAIN}"
echo ""
echo -e "${BLUE}🔍 Ver logs:${NC}"
echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs -f frontend'"
echo ""
