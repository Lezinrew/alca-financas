#!/bin/bash
# Script para configurar Google OAuth no servidor
# Uso: ./scripts/configurar-google-oauth.sh <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar argumentos
if [ $# -lt 2 ]; then
    echo -e "${RED}❌ Erro: Argumentos insuficientes${NC}"
    echo "Uso: $0 <GOOGLE_CLIENT_ID> <GOOGLE_CLIENT_SECRET>"
    echo ""
    echo "Exemplo:"
    echo "  $0 123456789-abc.apps.googleusercontent.com GOCSPX-abcdefghijklmnop"
    exit 1
fi

GOOGLE_CLIENT_ID="$1"
GOOGLE_CLIENT_SECRET="$2"

# Validar formato básico
if [[ ! "$GOOGLE_CLIENT_ID" =~ \.apps\.googleusercontent\.com$ ]]; then
    echo -e "${YELLOW}⚠️  Aviso: GOOGLE_CLIENT_ID não parece estar no formato correto${NC}"
    echo "   Formato esperado: xxx.apps.googleusercontent.com"
    read -p "   Continuar mesmo assim? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

if [[ ! "$GOOGLE_CLIENT_SECRET" =~ ^GOCSPX- ]]; then
    echo -e "${YELLOW}⚠️  Aviso: GOOGLE_CLIENT_SECRET não parece estar no formato correto${NC}"
    echo "   Formato esperado: GOCSPX-xxx"
    read -p "   Continuar mesmo assim? (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}🔐 Configurando Google OAuth no servidor...${NC}"
echo ""

# Configurações do servidor
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
ENV_FILE="/var/www/alca-financas/backend/.env"

# Verificar se sshpass está instalado
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}❌ sshpass não encontrado. Instale com: brew install hudochenkov/sshpass/sshpass${NC}"
    exit 1
fi

# Solicitar senha do servidor
read -sp "Digite a senha do servidor: " SERVER_PASS
echo ""

echo -e "${YELLOW}📝 Atualizando arquivo .env no servidor...${NC}"

# Ler o arquivo .env atual e atualizar as variáveis
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<EOF
    # Backup do .env
    cp $ENV_FILE ${ENV_FILE}.backup.\$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Remover linhas antigas (se existirem)
    sed -i '/^GOOGLE_CLIENT_ID=/d' $ENV_FILE 2>/dev/null || true
    sed -i '/^GOOGLE_CLIENT_SECRET=/d' $ENV_FILE 2>/dev/null || true
    
    # Adicionar novas linhas
    echo "" >> $ENV_FILE
    echo "# OAuth Google" >> $ENV_FILE
    echo "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID" >> $ENV_FILE
    echo "GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET" >> $ENV_FILE
    
    echo "✅ Arquivo .env atualizado"
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Credenciais adicionadas ao .env${NC}"
else
    echo -e "${RED}❌ Erro ao atualizar .env${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}🔄 Reiniciando serviço alca-financas...${NC}"

sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" "systemctl restart alca-financas"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Serviço reiniciado${NC}"
else
    echo -e "${RED}❌ Erro ao reiniciar serviço${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Configuração concluída!${NC}"
echo ""
echo "📋 Próximos passos:"
echo "   1. Teste o login com Google em: https://alcahub.com.br/login"
echo "   2. Verifique os logs se houver problemas:"
echo "      ssh root@alcahub.com.br 'journalctl -u alca-financas -f'"
echo ""

