#!/usr/bin/env bash
###############################################################################
# Test SSH Connection
# Script rápido para testar conexão SSH antes do deploy
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PASSWORD="${SERVER_PASSWORD:-}"

echo -e "${BLUE}🔍 Teste de Conexão SSH${NC}"
echo ""

if [ -z "$SERVER_HOST" ]; then
    read -p "Digite o hostname/IP: " SERVER_HOST
fi

if [ -z "$SERVER_PASSWORD" ]; then
    read -sp "Digite a senha SSH: " SERVER_PASSWORD
    echo ""
fi

echo ""
echo -e "${BLUE}Testando conexão com ${SERVER_USER}@${SERVER_HOST}...${NC}"

SSH_CMD="sshpass -p '$SERVER_PASSWORD' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o LogLevel=ERROR ${SERVER_USER}@${SERVER_HOST}"

echo ""
echo "1. Teste básico..."
if eval "$SSH_CMD 'echo OK'" | grep -q "OK"; then
    echo -e "   ${GREEN}✓ Conexão funcionando${NC}"
else
    echo -e "   ${RED}✗ Falha na conexão${NC}"
    exit 1
fi

echo "2. Verificando Docker..."
if eval "$SSH_CMD 'command -v docker'" > /dev/null 2>&1; then
    DOCKER_VERSION=$(eval "$SSH_CMD 'docker --version'")
    echo -e "   ${GREEN}✓ Docker instalado: $DOCKER_VERSION${NC}"
else
    echo -e "   ${YELLOW}⚠ Docker não instalado (será instalado)${NC}"
fi

echo "3. Verificando Docker Compose..."
if eval "$SSH_CMD 'command -v docker-compose'" > /dev/null 2>&1; then
    COMPOSE_VERSION=$(eval "$SSH_CMD 'docker-compose --version'")
    echo -e "   ${GREEN}✓ Docker Compose instalado: $COMPOSE_VERSION${NC}"
else
    echo -e "   ${YELLOW}⚠ Docker Compose não instalado (será instalado)${NC}"
fi

echo "4. Verificando diretório..."
if eval "$SSH_CMD 'test -d /var/www/alca-financas && echo exists'" | grep -q "exists"; then
    echo -e "   ${GREEN}✓ Diretório /var/www/alca-financas existe${NC}"
else
    echo -e "   ${YELLOW}⚠ Diretório não existe (será criado)${NC}"
fi

echo "5. Verificando Git..."
if eval "$SSH_CMD 'command -v git'" > /dev/null 2>&1; then
    GIT_VERSION=$(eval "$SSH_CMD 'git --version'")
    echo -e "   ${GREEN}✓ Git instalado: $GIT_VERSION${NC}"
else
    echo -e "   ${RED}✗ Git não instalado${NC}"
    echo -e "   ${YELLOW}   Instale: apt-get install -y git${NC}"
fi

echo ""
echo -e "${GREEN}✅ Teste de conexão concluído!${NC}"
echo ""
echo -e "${BLUE}Pronto para fazer deploy:${NC}"
echo "  export SERVER_PASSWORD='***'"
echo "  ./scripts/deploy-docker-remote.sh"
echo ""
