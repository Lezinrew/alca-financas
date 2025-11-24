#!/bin/bash

###############################################################################
# Script para atualizar credenciais do Google OAuth no servidor remoto
# Uso: ./scripts/update-google-oauth-remote.sh <CLIENT_ID> <CLIENT_SECRET>
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

# Verificar se as credenciais foram fornecidas
if [ -z "$1" ] || [ -z "$2" ]; then
    echo -e "${RED}❌ Erro: Credenciais do Google OAuth não fornecidas${NC}"
    echo ""
    echo "Uso: $0 <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>"
    echo ""
    echo "Exemplo:"
    echo "  $0 \"seu-client-id.apps.googleusercontent.com\" \"seu-client-secret\""
    exit 1
fi

GOOGLE_CLIENT_ID="$1"
GOOGLE_CLIENT_SECRET="$2"

echo -e "${BLUE}🔧 Atualizando credenciais do Google OAuth no servidor...${NC}"
echo -e "${BLUE}Servidor: ${SERVER_USER}@${SERVER_HOST}${NC}"
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

# Ler o arquivo .env atual
echo -e "${BLUE}📖 Lendo arquivo .env atual...${NC}"
CURRENT_ENV=$(execute_remote "cat ${PROJECT_DIR}/backend/.env 2>/dev/null || echo ''")

if [ -z "$CURRENT_ENV" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado. Execute primeiro o script update-mongo-uri-remote.sh${NC}"
    exit 1
fi

# Atualizar GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET, mantendo outras variáveis
echo -e "${BLUE}✏️  Atualizando credenciais do Google OAuth...${NC}"

# Remover linhas antigas se existirem
UPDATED_ENV=$(echo "$CURRENT_ENV" | sed '/^GOOGLE_CLIENT_ID=/d' | sed '/^GOOGLE_CLIENT_SECRET=/d')

# Adicionar as novas credenciais no final do arquivo (ou após a seção OAuth se existir)
if echo "$UPDATED_ENV" | grep -q "^# OAuth"; then
    # Se já existe seção OAuth, adicionar após ela
    UPDATED_ENV=$(echo "$UPDATED_ENV" | sed "/^# OAuth/a\\
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}\\
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}")
else
    # Se não existe, adicionar no final
    UPDATED_ENV="${UPDATED_ENV}

# OAuth Google
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}"
fi

# Salvar o arquivo atualizado
execute_remote "cat > ${PROJECT_DIR}/backend/.env << 'ENVEOF'
${UPDATED_ENV}
ENVEOF
"

echo -e "${GREEN}✅ Credenciais do Google OAuth atualizadas com sucesso!${NC}"
echo ""

# Verificar se o arquivo foi atualizado corretamente
echo -e "${BLUE}🔍 Verificando arquivo .env...${NC}"
execute_remote "grep '^GOOGLE_CLIENT_ID=' ${PROJECT_DIR}/backend/.env | head -1"
execute_remote "grep '^GOOGLE_CLIENT_SECRET=' ${PROJECT_DIR}/backend/.env | head -1 | sed 's/\(.\{30\}\).*/\1.../'"
echo ""

# Reiniciar o serviço
echo -e "${BLUE}🔄 Reiniciando serviço alca-financas...${NC}"
execute_remote "systemctl restart alca-financas"
sleep 3

# Verificar status
echo -e "${BLUE}📊 Verificando status do serviço...${NC}"
STATUS=$(execute_remote "systemctl is-active alca-financas 2>/dev/null || echo 'inactive'")
if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Serviço está rodando!${NC}"
else
    echo -e "${YELLOW}⚠️  Serviço não está rodando. Verifique os logs:${NC}"
    echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -n 50'"
fi

echo ""
echo -e "${GREEN}✅ Atualização concluída!${NC}"
echo ""
echo -e "${BLUE}📝 Para verificar os logs:${NC}"
echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -f'"

