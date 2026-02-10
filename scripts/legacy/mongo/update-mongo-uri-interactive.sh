#!/bin/bash

###############################################################################
# Script interativo para atualizar MONGO_URI no servidor remoto
# Uso: ./scripts/update-mongo-uri-interactive.sh
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configurações do servidor
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
SERVER_PASS="4203434@Mudar"
PROJECT_DIR="/var/www/alca-financas"

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Atualização de MONGO_URI - MongoDB Atlas                ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Valores padrão
DEFAULT_USER="lezinrew"
DEFAULT_PASSWORD="2GPSrU2fXcQAhEBJ"
DEFAULT_DB="alca_financas"

echo -e "${BLUE}📋 Informações necessárias:${NC}"
echo ""
echo -e "${YELLOW}Você pode:${NC}"
echo "  1. Fornecer a connection string completa"
echo "  2. Fornecer apenas o nome do cluster (vou montar a string)"
echo ""

read -p "$(echo -e ${CYAN}Escolha uma opção [1/2]: ${NC})" option

if [ "$option" = "1" ]; then
    echo ""
    echo -e "${BLUE}Cole a connection string completa do MongoDB Atlas:${NC}"
    echo -e "${YELLOW}(Formato: mongodb+srv://usuario:senha@cluster.mongodb.net/database?retryWrites=true&w=majority)${NC}"
    read -p "$(echo -e ${CYAN}Connection String: ${NC})" MONGO_URI
    
    if [ -z "$MONGO_URI" ]; then
        echo -e "${RED}❌ Connection string não fornecida!${NC}"
        exit 1
    fi
    
elif [ "$option" = "2" ]; then
    echo ""
    echo -e "${BLUE}Forneça o nome do cluster:${NC}"
    echo -e "${YELLOW}(Exemplo: cluster0.xxxxx.mongodb.net)${NC}"
    read -p "$(echo -e ${CYAN}Nome do cluster: ${NC})" CLUSTER_NAME
    
    if [ -z "$CLUSTER_NAME" ]; then
        echo -e "${RED}❌ Nome do cluster não fornecido!${NC}"
        exit 1
    fi
    
    # Remover http:// ou https:// se o usuário colou
    CLUSTER_NAME=$(echo "$CLUSTER_NAME" | sed 's|^https\?://||' | sed 's|/$||')
    
    echo ""
    read -p "$(echo -e ${CYAN}Usuário do MongoDB [${DEFAULT_USER}]: ${NC})" MONGO_USER
    MONGO_USER=${MONGO_USER:-$DEFAULT_USER}
    
    read -p "$(echo -e ${CYAN}Senha do MongoDB [${DEFAULT_PASSWORD}]: ${NC})" MONGO_PASSWORD
    MONGO_PASSWORD=${MONGO_PASSWORD:-$DEFAULT_PASSWORD}
    
    read -p "$(echo -e ${CYAN}Nome do banco de dados [${DEFAULT_DB}]: ${NC})" MONGO_DB
    MONGO_DB=${MONGO_DB:-$DEFAULT_DB}
    
    # Montar a connection string
    MONGO_URI="mongodb+srv://${MONGO_USER}:${MONGO_PASSWORD}@${CLUSTER_NAME}/${MONGO_DB}?retryWrites=true&w=majority"
    
    echo ""
    echo -e "${GREEN}✅ Connection string montada:${NC}"
    echo -e "${CYAN}${MONGO_URI}${NC}"
    echo ""
    
else
    echo -e "${RED}❌ Opção inválida!${NC}"
    exit 1
fi

# Confirmar antes de atualizar
echo ""
read -p "$(echo -e ${YELLOW}Deseja atualizar o servidor com esta connection string? [s/N]: ${NC})" confirm

if [[ ! "$confirm" =~ ^[Ss]$ ]]; then
    echo -e "${YELLOW}Operação cancelada.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}🔧 Atualizando MONGO_URI no servidor...${NC}"
echo -e "${BLUE}Servidor: ${SERVER_USER}@${SERVER_HOST}${NC}"
echo ""

# Instalar sshpass se não estiver instalado
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass não encontrado. Instalando...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass 2>/dev/null || {
            echo -e "${RED}❌ Instale sshpass manualmente: brew install hudochenkov/sshpass/sshpass${NC}"
            exit 1
        }
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
# Escapar & para o sed (mesmo método do script original)
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
MONGO_URI_CHECK=$(execute_remote "grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1 | cut -d'=' -f2-")
if [ -n "$MONGO_URI_CHECK" ]; then
    echo -e "${GREEN}✅ MONGO_URI encontrado no arquivo${NC}"
    echo -e "${CYAN}   ${MONGO_URI_CHECK:0:60}...${NC}"
else
    echo -e "${RED}❌ MONGO_URI não encontrado no arquivo!${NC}"
fi
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
    echo ""
    echo -e "${GREEN}🎉 Atualização concluída com sucesso!${NC}"
    echo ""
    echo -e "${BLUE}📝 Para verificar os logs:${NC}"
    echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -f'"
else
    echo -e "${RED}❌ Serviço não está rodando.${NC}"
    echo ""
    echo -e "${YELLOW}📋 Últimas linhas dos logs:${NC}"
    execute_remote "journalctl -u alca-financas -n 20 --no-pager | tail -10"
    echo ""
    echo -e "${BLUE}Para ver todos os logs:${NC}"
    echo "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -n 50'"
fi

echo ""

