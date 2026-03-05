#!/usr/bin/env bash
###############################################################################
# Setup Supabase Credentials
# Script interativo para configurar credenciais Supabase no .env
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║     CONFIGURAÇÃO CREDENCIAIS SUPABASE        ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado!${NC}"
    echo "Crie um arquivo .env primeiro ou copie de .env.example"
    exit 1
fi

echo -e "${YELLOW}📋 Você vai precisar das seguintes informações do Supabase:${NC}"
echo ""
echo "1. URL do Projeto (https://xxx.supabase.co)"
echo "2. Service Role Key (anon/public key - começa com eyJ...)"
echo "3. Anon Key (opcional - para frontend)"
echo ""
echo -e "${BLUE}💡 Onde encontrar:${NC}"
echo "   1. Acesse: https://app.supabase.com"
echo "   2. Selecione seu projeto"
echo "   3. Vá em: Settings → API"
echo "   4. Copie: Project URL e anon/service_role keys"
echo ""
read -p "Pressione ENTER para continuar..."
echo ""

# Pedir SUPABASE_URL
echo -e "${BLUE}🔗 Supabase Project URL${NC}"
echo -e "${YELLOW}Exemplo: https://xxxxxxxxxxx.supabase.co${NC}"
read -p "Cole aqui: " SUPABASE_URL

if [ -z "$SUPABASE_URL" ]; then
    echo -e "${RED}❌ URL não pode ser vazia${NC}"
    exit 1
fi

# Validar URL
if [[ ! "$SUPABASE_URL" =~ ^https://.*\.supabase\.co$ ]]; then
    echo -e "${YELLOW}⚠️  URL não parece válida (deve ser https://xxx.supabase.co)${NC}"
    read -p "Continuar mesmo assim? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        exit 1
    fi
fi

# Pedir SERVICE_ROLE_KEY
echo ""
echo -e "${BLUE}🔑 Supabase Service Role Key${NC}"
echo -e "${YELLOW}Exemplo: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...${NC}"
echo -e "${RED}⚠️  ATENÇÃO: Esta é a chave SECRETA (service_role), não compartilhe!${NC}"
read -sp "Cole aqui (invisível): " SUPABASE_SERVICE_ROLE_KEY
echo ""

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo -e "${RED}❌ Service Role Key não pode ser vazia${NC}"
    exit 1
fi

# Validar JWT format
if [[ ! "$SUPABASE_SERVICE_ROLE_KEY" =~ ^eyJ ]]; then
    echo -e "${YELLOW}⚠️  Key não parece ser um JWT válido (deve começar com eyJ)${NC}"
    read -p "Continuar mesmo assim? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        exit 1
    fi
fi

# Pedir ANON_KEY (opcional)
echo ""
echo -e "${BLUE}🔓 Supabase Anon Key (opcional - para frontend)${NC}"
echo -e "${YELLOW}Exemplo: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...${NC}"
echo -e "${YELLOW}Pressione ENTER para pular${NC}"
read -sp "Cole aqui (invisível): " SUPABASE_ANON_KEY
echo ""

# Criar backup do .env
echo ""
echo -e "${BLUE}💾 Criando backup do .env...${NC}"
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✓ Backup criado: .env.backup.$(date +%Y%m%d_%H%M%S)${NC}"

# Atualizar .env
echo ""
echo -e "${BLUE}📝 Atualizando .env...${NC}"

# Remover linhas comentadas antigas de Supabase
sed -i.tmp '/^# SUPABASE_URL=/d' .env
sed -i.tmp '/^# SUPABASE_SERVICE_ROLE_KEY=/d' .env
sed -i.tmp '/^# SUPABASE_ANON_KEY=/d' .env
rm -f .env.tmp

# Adicionar novas credenciais (substituir se já existirem)
if grep -q "^SUPABASE_URL=" .env; then
    # Substituir existente
    sed -i.tmp "s|^SUPABASE_URL=.*|SUPABASE_URL=$SUPABASE_URL|" .env
else
    # Adicionar nova linha após comentário Supabase
    sed -i.tmp "/^# Supabase Configuration/a\\
SUPABASE_URL=$SUPABASE_URL" .env
fi

if grep -q "^SUPABASE_SERVICE_ROLE_KEY=" .env; then
    sed -i.tmp "s|^SUPABASE_SERVICE_ROLE_KEY=.*|SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY|" .env
else
    sed -i.tmp "/^SUPABASE_URL=/a\\
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" .env
fi

if [ -n "$SUPABASE_ANON_KEY" ]; then
    if grep -q "^SUPABASE_ANON_KEY=" .env; then
        sed -i.tmp "s|^SUPABASE_ANON_KEY=.*|SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY|" .env
    else
        sed -i.tmp "/^SUPABASE_SERVICE_ROLE_KEY=/a\\
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" .env
    fi

    # Também adicionar VITE_* para frontend
    if grep -q "^VITE_SUPABASE_URL=" .env; then
        sed -i.tmp "s|^VITE_SUPABASE_URL=.*|VITE_SUPABASE_URL=$SUPABASE_URL|" .env
    else
        sed -i.tmp "/^SUPABASE_ANON_KEY=/a\\
VITE_SUPABASE_URL=$SUPABASE_URL" .env
    fi

    if grep -q "^VITE_SUPABASE_ANON_KEY=" .env; then
        sed -i.tmp "s|^VITE_SUPABASE_ANON_KEY=.*|VITE_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY|" .env
    else
        sed -i.tmp "/^VITE_SUPABASE_URL=/a\\
VITE_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" .env
    fi
fi

rm -f .env.tmp

echo -e "${GREEN}✓ Credenciais adicionadas ao .env${NC}"
echo ""

# Verificar
echo -e "${BLUE}🔍 Verificando configuração...${NC}"
source scripts/load-env.sh
echo ""

echo -e "${GREEN}✅ SUCESSO!${NC}"
echo ""
echo -e "${BLUE}📋 Próximos passos:${NC}"
echo "1. Verificar: cat .env | grep SUPABASE"
echo "2. Testar deploy: ./scripts/deploy-docker-remote.sh"
echo ""
echo -e "${YELLOW}💡 Dica:${NC} Nunca commite o arquivo .env ao Git!"
echo ""
