#!/bin/bash

###############################################################################
# Script para diagnosticar e corrigir problemas de SSL com MongoDB Atlas
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

echo -e "${BLUE}🔧 Diagnosticando problema de SSL com MongoDB...${NC}"
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

# 1. Verificar versão do Python e pymongo
echo -e "${BLUE}📊 Verificando versões...${NC}"
execute_remote "
    echo 'Python:'
    ${PROJECT_DIR}/backend/venv/bin/python3 --version
    echo ''
    echo 'pymongo:'
    ${PROJECT_DIR}/backend/venv/bin/pip show pymongo | grep Version || echo 'pymongo não encontrado'
"
echo ""

# 2. Verificar certificados SSL do sistema
echo -e "${BLUE}🔍 Verificando certificados SSL do sistema...${NC}"
execute_remote "
    if [ -f /etc/ssl/certs/ca-certificates.crt ]; then
        echo 'Certificados encontrados: /etc/ssl/certs/ca-certificates.crt'
        ls -lh /etc/ssl/certs/ca-certificates.crt
    else
        echo '⚠️  Certificados não encontrados em /etc/ssl/certs/ca-certificates.crt'
    fi
    echo ''
    echo 'Atualizando certificados...'
    apt-get update -qq && apt-get install -y ca-certificates 2>&1 | tail -5 || echo 'Erro ao atualizar certificados'
"
echo ""

# 3. Verificar MONGO_URI atual
echo -e "${BLUE}📋 Verificando MONGO_URI atual...${NC}"
MONGO_URI=$(execute_remote "grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1 | cut -d'=' -f2-")
echo "MONGO_URI atual: ${MONGO_URI:0:50}..."
echo ""

# 4. Verificar se a connection string precisa de parâmetros SSL adicionais
echo -e "${BLUE}🔧 Ajustando connection string com parâmetros SSL...${NC}"

# Adicionar parâmetros SSL/TLS à connection string se não existirem
if echo "$MONGO_URI" | grep -q "tlsAllowInvalidCertificates"; then
    echo "Connection string já tem parâmetros SSL"
else
    # Adicionar parâmetros SSL seguros
    if echo "$MONGO_URI" | grep -q "?"; then
        # Já tem parâmetros, adicionar aos existentes
        NEW_MONGO_URI="${MONGO_URI}&tlsAllowInvalidCertificates=false&tls=true"
    else
        # Não tem parâmetros, adicionar
        NEW_MONGO_URI="${MONGO_URI}?tlsAllowInvalidCertificates=false&tls=true&retryWrites=true&w=majority"
    fi
    
    # Atualizar no .env
    execute_remote "
        sed -i 's|^MONGO_URI=.*|MONGO_URI=${NEW_MONGO_URI}|' ${PROJECT_DIR}/backend/.env
        echo 'MONGO_URI atualizado'
        grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1
    "
    echo ""
fi

# 5. Testar conexão Python com MongoDB
echo -e "${BLUE}🧪 Testando conexão com MongoDB...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/backend
    source venv/bin/activate
    python3 << 'PYTHON_EOF'
import sys
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError

# Ler MONGO_URI do .env
env_file = '.env'
mongo_uri = None
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith('MONGO_URI='):
                mongo_uri = line.split('=', 1)[1].strip()
                break

if not mongo_uri:
    print('❌ MONGO_URI não encontrado no .env')
    sys.exit(1)

print(f'Conectando a: {mongo_uri[:50]}...')
try:
    # Tentar conexão com timeout curto
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    # Tentar ping
    client.admin.command('ping')
    print('✅ Conexão com MongoDB bem-sucedida!')
    client.close()
except ConnectionFailure as e:
    print(f'❌ Erro de conexão: {e}')
    sys.exit(1)
except ConfigurationError as e:
    print(f'❌ Erro de configuração: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Erro inesperado: {e}')
    sys.exit(1)
PYTHON_EOF
"
echo ""

# 6. Atualizar pymongo se necessário
echo -e "${BLUE}📦 Verificando se precisa atualizar pymongo...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/backend
    source venv/bin/activate
    pip install --upgrade pymongo[srv] 2>&1 | tail -3
"
echo ""

# 7. Reiniciar serviço
echo -e "${BLUE}🔄 Reiniciando serviço...${NC}"
execute_remote "systemctl restart alca-financas"
sleep 3

# 8. Verificar status
echo -e "${BLUE}📊 Verificando status do serviço...${NC}"
STATUS=$(execute_remote "systemctl is-active alca-financas 2>/dev/null || echo 'inactive'")
if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Serviço está rodando!${NC}"
    echo ""
    echo -e "${BLUE}📋 Últimas linhas dos logs:${NC}"
    execute_remote "journalctl -u alca-financas -n 10 --no-pager | tail -5"
else
    echo -e "${RED}❌ Serviço não está rodando${NC}"
    echo ""
    echo -e "${YELLOW}📋 Últimas 20 linhas dos logs de erro:${NC}"
    execute_remote "journalctl -u alca-financas -n 20 --no-pager | grep -i error || journalctl -u alca-financas -n 20 --no-pager"
fi

echo ""
echo -e "${GREEN}✅ Diagnóstico concluído!${NC}"
echo ""
echo -e "${YELLOW}💡 Dicas:${NC}"
echo "   1. Verifique se o IP do servidor está na whitelist do MongoDB Atlas"
echo "   2. Verifique se o usuário e senha do MongoDB estão corretos"
echo "   3. Tente adicionar '0.0.0.0/0' temporariamente na whitelist para teste"

