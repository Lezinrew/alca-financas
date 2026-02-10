#!/bin/bash

###############################################################################
# Script para atualizar MONGO_URI no servidor remoto
# Uso: ./scripts/update-mongo-uri-remote.sh "mongodb+srv://usuario:senha@cluster.mongodb.net/database"
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

# Verificar se a connection string foi fornecida
if [ -z "$1" ]; then
    echo -e "${RED}❌ Erro: Connection string do MongoDB não fornecida${NC}"
    echo ""
    echo "Uso: $0 \"mongodb+srv://usuario:senha@cluster.mongodb.net/database\""
    echo ""
    echo "Exemplo:"
    echo "  $0 \"mongodb+srv://admin:senha123@cluster0.xxxxx.mongodb.net/alca_financas?retryWrites=true&w=majority\""
    exit 1
fi

MONGO_URI="$1"

echo -e "${BLUE}🔧 Atualizando MONGO_URI no servidor...${NC}"
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
    echo -e "${YELLOW}⚠️  Arquivo .env não encontrado. Criando novo arquivo...${NC}"
    CURRENT_ENV="# Ambiente
FLASK_ENV=production
NODE_ENV=production

# MongoDB
MONGO_URI=
MONGO_DB=alca_financas

# JWT
SECRET_KEY=
JWT_EXPIRES_HOURS=24

# CORS
CORS_ORIGINS=https://alcahub.com.br,https://www.alcahub.com.br,https://app.alcahub.com.br

# OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET="
fi

# Atualizar apenas o MONGO_URI, mantendo outras variáveis
echo -e "${BLUE}✏️  Atualizando MONGO_URI...${NC}"
# Escapar & para o sed
ESCAPED_URI=$(echo "$MONGO_URI" | sed 's/&/\\&/g')
UPDATED_ENV=$(echo "$CURRENT_ENV" | sed "s|^MONGO_URI=.*|MONGO_URI=${ESCAPED_URI}|")

# Salvar o arquivo atualizado
execute_remote "cat > ${PROJECT_DIR}/backend/.env << 'ENVEOF'
${UPDATED_ENV}
ENVEOF
"

echo -e "${GREEN}✅ MONGO_URI atualizado com sucesso!${NC}"
echo ""

# Verificar se o arquivo foi atualizado corretamente
echo -e "${BLUE}🔍 Verificando arquivo .env...${NC}"
execute_remote "grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1"
echo ""

# Reiniciar o serviço
echo -e "${BLUE}🔄 Reiniciando serviço alca-financas...${NC}"
execute_remote "systemctl restart alca-financas"
sleep 2

# Verificar status
echo -e "${BLUE}📊 Verificando status do serviço...${NC}"
STATUS=$(execute_remote "systemctl is-active alca-financas 2>/dev/null || echo 'inactive'")
if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Serviço está rodando!${NC}"
else
    echo -e "${RED}❌ Serviço não está rodando. Verifique os logs:${NC}"
    echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -n 50'"
fi

echo ""
echo -e "${GREEN}✅ Atualização concluída!${NC}"
echo ""
echo -e "${BLUE}📝 Para verificar os logs:${NC}"
echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -f'"

