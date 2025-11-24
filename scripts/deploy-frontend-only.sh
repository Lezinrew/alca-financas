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

# Configurações do servidor
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
SERVER_PASS="4203434@Mudar"
PROJECT_DIR="/var/www/alca-financas"

echo -e "${BLUE}🚀 Fazendo deploy do frontend...${NC}"
echo ""

# Instalar sshpass se não estiver instalado
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass não encontrado. Instalando...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass 2>/dev/null || echo -e "${RED}❌ Instale sshpass manualmente${NC}"
    else
        sudo apt-get update && sudo apt-get install -y sshpass
    fi
fi

# Função para executar comandos remotos
execute_remote() {
    sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no \
        -o IdentitiesOnly=yes -o NumberOfPasswordPrompts=1 \
        "${SERVER_USER}@${SERVER_HOST}" "$1"
}

# Função para copiar arquivos
copy_file() {
    sshpass -p "$SERVER_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no \
        -o IdentitiesOnly=yes "$1" "${SERVER_USER}@${SERVER_HOST}:$2"
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

