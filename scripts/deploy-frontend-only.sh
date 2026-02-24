#!/bin/bash

###############################################################################
# Script para fazer deploy apenas do frontend (rápido)
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações do servidor (use variáveis de ambiente: PROD_HOST, PROD_USER, PROD_SSH_KEY)
SERVER_HOST="${PROD_HOST:-alcahub.com.br}"
SERVER_USER="${PROD_USER:-root}"
PROJECT_DIR="${PROJECT_DIR:-/var/www/alca-financas}"

echo -e "${BLUE}🚀 Fazendo deploy do frontend...${NC}"
echo ""

# Requer chave SSH (PROD_SSH_KEY) ou ssh-agent com chave carregada
# NUNCA use senha hardcoded. Configure: export PROD_SSH_KEY="$(cat ~/.ssh/id_rsa)"
if [ -z "$PROD_SSH_KEY" ]; then
    echo -e "${YELLOW}Usando ssh-agent (certifique-se de que a chave está carregada)${NC}"
    SSH_CMD="ssh -o StrictHostKeyChecking=no"
    SCP_CMD="scp -o StrictHostKeyChecking=no"
else
    SSH_KEY_FILE=$(mktemp)
    echo "$PROD_SSH_KEY" > "$SSH_KEY_FILE"
    chmod 600 "$SSH_KEY_FILE"
    trap "rm -f $SSH_KEY_FILE" EXIT
    SSH_CMD="ssh -i $SSH_KEY_FILE -o StrictHostKeyChecking=no"
    SCP_CMD="scp -i $SSH_KEY_FILE -o StrictHostKeyChecking=no"
fi

execute_remote() {
    $SSH_CMD "${SERVER_USER}@${SERVER_HOST}" "$1"
}

copy_file() {
    $SCP_CMD "$1" "${SERVER_USER}@${SERVER_HOST}:$2"
}

# 1. Fazer pull do repositório
echo -e "${BLUE}📥 Atualizando código do repositório...${NC}"
execute_remote "
    cd ${PROJECT_DIR}
    git reset --hard origin/main
    git pull origin main
"
echo ""

# 2. Copiar arquivo vite.svg se necessário
if [ -f "frontend/public/vite.svg" ]; then
    echo -e "${BLUE}📋 Copiando vite.svg...${NC}"
    execute_remote "mkdir -p ${PROJECT_DIR}/frontend/public"
    copy_file "frontend/public/vite.svg" "${PROJECT_DIR}/frontend/public/vite.svg"
    echo ""
fi

# 3. Build do frontend
echo -e "${BLUE}🏗️  Buildando frontend...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/frontend
    npm install --silent
    npm run build
"
echo ""

# 4. Recarregar Nginx
echo -e "${BLUE}🔄 Recarregando Nginx...${NC}"
execute_remote "systemctl reload nginx"
echo ""

echo -e "${GREEN}✅ Deploy do frontend concluído!${NC}"
echo ""
echo -e "${BLUE}📝 Teste em: https://alcahub.com.br${NC}"

