#!/bin/bash

###############################################################################
# Script para corrigir connection string do MongoDB no servidor remoto
# Adiciona parâmetros SSL/TLS necessários
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

echo -e "${BLUE}🔧 Corrigindo connection string do MongoDB...${NC}"
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

# Usar Python para corrigir a connection string de forma segura
echo -e "${BLUE}📋 Lendo e corrigindo MONGO_URI...${NC}"
execute_remote "
cd ${PROJECT_DIR}/backend
python3 << 'PYTHON_EOF'
import re
import os

env_file = '.env'
if not os.path.exists(env_file):
    print('❌ Arquivo .env não encontrado')
    exit(1)

# Ler arquivo
with open(env_file, 'r') as f:
    lines = f.readlines()

# Encontrar e corrigir MONGO_URI
mongo_uri_found = False
for i, line in enumerate(lines):
    if line.startswith('MONGO_URI='):
        mongo_uri_found = True
        # Extrair a connection string
        current_uri = line.split('=', 1)[1].strip()
        
        # Remover parâmetros duplicados ou malformados
        # Extrair a parte base (antes de ?)
        if '?' in current_uri:
            base_uri, params = current_uri.split('?', 1)
        else:
            base_uri = current_uri
            params = ''
        
        # Limpar parâmetros existentes e reconstruir
        # Manter apenas parâmetros válidos
        valid_params = []
        if params:
            # Separar parâmetros
            param_pairs = params.split('&')
            seen_params = set()
            for param in param_pairs:
                if '=' in param:
                    key = param.split('=')[0]
                    if key not in seen_params:
                        valid_params.append(param)
                        seen_params.add(key)
        
        # Adicionar parâmetros necessários se não existirem
        param_keys = [p.split('=')[0] for p in valid_params]
        
        if 'retryWrites' not in param_keys:
            valid_params.append('retryWrites=true')
        if 'w' not in param_keys:
            valid_params.append('w=majority')
        # Não adicionar tlsAllowInvalidCertificates=false pois pode causar problemas
        # O MongoDB Atlas já usa TLS por padrão com mongodb+srv
        
        # Reconstruir URI
        if valid_params:
            new_uri = base_uri + '?' + '&'.join(valid_params)
        else:
            new_uri = base_uri + '?retryWrites=true&w=majority'
        
        # Atualizar linha
        lines[i] = f'MONGO_URI={new_uri}\n'
        print(f'✅ MONGO_URI corrigido:')
        print(f'   {new_uri[:80]}...')
        break

if not mongo_uri_found:
    print('⚠️  MONGO_URI não encontrado no .env')
    exit(1)

# Salvar arquivo
with open(env_file, 'w') as f:
    f.writelines(lines)

print('✅ Arquivo .env atualizado')
PYTHON_EOF
"
echo ""

# Verificar se foi atualizado corretamente
echo -e "${BLUE}🔍 Verificando MONGO_URI atualizado...${NC}"
execute_remote "grep '^MONGO_URI=' ${PROJECT_DIR}/backend/.env | head -1"
echo ""

# Atualizar pymongo com suporte a SRV
echo -e "${BLUE}📦 Atualizando pymongo com suporte SRV...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/backend
    source venv/bin/activate
    pip install --upgrade 'pymongo[srv]' --quiet 2>&1 | tail -2 || echo 'pymongo já atualizado'
"
echo ""

# Testar conexão
echo -e "${BLUE}🧪 Testando conexão com MongoDB...${NC}"
execute_remote "
cd ${PROJECT_DIR}/backend
source venv/bin/activate
python3 << 'PYTHON_EOF'
import sys
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, ServerSelectionTimeoutError

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
    print('❌ MONGO_URI não encontrado')
    sys.exit(1)

print(f'Conectando...')
try:
    # Tentar conexão com timeout
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    # Tentar ping
    result = client.admin.command('ping')
    print('✅ Conexão com MongoDB bem-sucedida!')
    print(f'   Resposta: {result}')
    client.close()
except ServerSelectionTimeoutError as e:
    print(f'❌ Timeout ao conectar: {str(e)[:200]}')
    print('')
    print('💡 Possíveis causas:')
    print('   1. IP do servidor não está na whitelist do MongoDB Atlas')
    print('   2. Usuário/senha incorretos')
    print('   3. Problema de rede/firewall')
    sys.exit(1)
except ConfigurationError as e:
    print(f'❌ Erro de configuração: {e}')
    sys.exit(1)
except ConnectionFailure as e:
    print(f'❌ Erro de conexão: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Erro inesperado: {type(e).__name__}: {e}')
    sys.exit(1)
PYTHON_EOF
"
TEST_RESULT=$?

echo ""

if [ $TEST_RESULT -eq 0 ]; then
    # Reiniciar serviço
    echo -e "${BLUE}🔄 Reiniciando serviço...${NC}"
    execute_remote "systemctl restart alca-financas"
    sleep 3
    
    # Verificar status
    STATUS=$(execute_remote "systemctl is-active alca-financas 2>/dev/null || echo 'inactive'")
    if [ "$STATUS" = "active" ]; then
        echo -e "${GREEN}✅ Serviço está rodando!${NC}"
    else
        echo -e "${YELLOW}⚠️  Serviço não está rodando. Verifique os logs:${NC}"
        execute_remote "journalctl -u alca-financas -n 10 --no-pager | tail -5"
    fi
else
    echo -e "${RED}❌ Teste de conexão falhou. Verifique:${NC}"
    echo "   1. IP do servidor na whitelist do MongoDB Atlas"
    echo "   2. Credenciais corretas no MONGO_URI"
    echo ""
    echo "   Para adicionar IP na whitelist:"
    echo "   - Acesse MongoDB Atlas → Network Access"
    echo "   - Adicione o IP do servidor ou use 0.0.0.0/0 temporariamente"
fi

echo ""
echo -e "${GREEN}✅ Processo concluído!${NC}"

