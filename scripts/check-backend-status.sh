#!/bin/bash

###############################################################################
# Verificar Status do Backend no Servidor Remoto
# Script para diagnosticar problemas do backend
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

echo -e "${BLUE}🔍 Verificando status do backend no servidor remoto...${NC}"
echo ""

# Instalar sshpass se não estiver instalado
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass não encontrado. Instalando...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass 2>/dev/null || echo -e "${RED}❌ Instale sshpass manualmente: brew install hudochenkov/sshpass/sshpass${NC}"
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

# 1. Verificar status do serviço
echo -e "${BLUE}📊 Status do serviço alca-financas:${NC}"
execute_remote "systemctl status alca-financas --no-pager -l || echo 'Serviço não encontrado'"
echo ""

# 2. Verificar se o serviço está ativo
echo -e "${BLUE}🔍 Verificando se o serviço está ativo:${NC}"
SERVICE_STATUS=$(execute_remote "systemctl is-active alca-financas 2>/dev/null || echo 'inactive'")
if [ "$SERVICE_STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Serviço está ativo${NC}"
else
    echo -e "${RED}❌ Serviço está inativo${NC}"
fi
echo ""

# 3. Verificar logs recentes do serviço
echo -e "${BLUE}📋 Últimas 30 linhas dos logs do serviço:${NC}"
execute_remote "journalctl -u alca-financas -n 30 --no-pager || echo 'Logs não disponíveis'"
echo ""

# 4. Verificar logs do Gunicorn
echo -e "${BLUE}📋 Últimas 20 linhas dos logs do Gunicorn (erro):${NC}"
execute_remote "tail -n 20 /var/log/gunicorn/alca-financas-error.log 2>/dev/null || echo 'Arquivo de log não encontrado'"
echo ""

# 5. Verificar se a porta 8001 está em uso
echo -e "${BLUE}🔍 Verificando porta 8001:${NC}"
execute_remote "netstat -tlnp | grep :8001 || ss -tlnp | grep :8001 || echo 'Porta 8001 não está em uso'"
echo ""

# 6. Verificar arquivo .env
echo -e "${BLUE}🔍 Verificando configuração do .env:${NC}"
execute_remote "if [ -f ${PROJECT_DIR}/backend/.env ]; then
    echo 'Arquivo .env existe'
    echo 'MONGO_URI: ' \$(grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1 | cut -d'=' -f2- | cut -c1-50)...
    echo 'GOOGLE_CLIENT_ID: ' \$(grep '^GOOGLE_CLIENT_ID=' ${PROJECT_DIR}/backend/.env | head -1 | cut -d'=' -f2- | cut -c1-30)...
else
    echo 'Arquivo .env não encontrado'
fi"
echo ""

# 7. Tentar reiniciar o serviço
echo -e "${YELLOW}⚠️  Deseja tentar reiniciar o serviço? (s/n)${NC}"
read -r response
if [[ "$response" =~ ^[Ss]$ ]]; then
    echo -e "${BLUE}🔄 Reiniciando serviço...${NC}"
    execute_remote "
        systemctl restart alca-financas
        sleep 3
        systemctl status alca-financas --no-pager -l | head -20
    "
    echo ""
    echo -e "${GREEN}✅ Serviço reiniciado${NC}"
fi

echo ""
echo -e "${BLUE}✅ Verificação concluída${NC}"

