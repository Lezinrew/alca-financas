#!/usr/bin/env bash
###############################################################################
# Setup .env - Cria .env a partir de .env.example e auxilia no preenchimento
# Uso: ./scripts/setup-env.sh [--editor-only]
###############################################################################

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║        CONFIGURAÇÃO DO ARQUIVO .env          ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# 1. Criar .env a partir de .env.example se não existir
if [ ! -f ".env" ]; then
    if [ ! -f ".env.example" ]; then
        echo -e "${RED}❌ .env.example não encontrado na raiz do projeto.${NC}"
        exit 1
    fi
    cp .env.example .env
    echo -e "${GREEN}✅ Arquivo .env criado a partir de .env.example${NC}"
else
    echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
fi

# Opção: só abrir o editor
if [ "$1" = "--editor-only" ]; then
    echo -e "\n${BLUE}Abrindo .env no editor...${NC}"
    "${EDITOR:-nano}" .env
    echo -e "${GREEN}Pronto. Verifique as variáveis obrigatórias (SUPABASE_*, SECRET_KEY, JWT_SECRET).${NC}"
    exit 0
fi

# 2. Gerar SECRET_KEY e JWT_SECRET se ainda forem placeholders
need_secrets=false
if grep -q "your-secret-key-min-32-chars" .env 2>/dev/null || grep -q "your-jwt-secret-min-32-chars" .env 2>/dev/null; then
    need_secrets=true
fi

if [ "$need_secrets" = true ]; then
    echo ""
    echo -e "${YELLOW}🔐 SECRET_KEY e JWT_SECRET ainda estão com valor de exemplo.${NC}"
    read -p "Gerar valores seguros agora com openssl? (s/n): " gen
    if [ "$gen" = "s" ] || [ "$gen" = "S" ]; then
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "")
        JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "")
        if [ -n "$SECRET_KEY" ] && [ -n "$JWT_SECRET" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
                sed -i '' "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
            else
                sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
                sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
            fi
            echo -e "${GREEN}✅ SECRET_KEY e JWT_SECRET gerados e gravados no .env${NC}"
        else
            echo -e "${YELLOW}⚠️  openssl não disponível. Preencha manualmente no .env.${NC}"
        fi
    fi
fi

# 3. Oferecer script de credenciais Supabase
echo ""
echo -e "${BLUE}📋 Preenchimento das variáveis:${NC}"
echo "   1) Rodar script interativo só para Supabase (URL + keys)"
echo "   2) Abrir .env no editor para preencher tudo manualmente"
echo "   3) Sair (já preenchi ou vou preencher depois)"
echo ""
read -p "Escolha (1/2/3): " choice

case "$choice" in
    1)
        if [ -f "scripts/setup-supabase-credentials.sh" ]; then
            ./scripts/setup-supabase-credentials.sh
        else
            echo -e "${YELLOW}Script setup-supabase-credentials.sh não encontrado. Abrindo .env...${NC}"
            "${EDITOR:-nano}" .env
        fi
        ;;
    2)
        echo -e "\n${BLUE}Abrindo .env no editor (${EDITOR:-nano})...${NC}"
        "${EDITOR:-nano}" .env
        echo -e "${GREEN}Pronto.${NC}"
        ;;
    3)
        echo -e "${GREEN}Lembre de preencher pelo menos: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SECRET_KEY, JWT_SECRET, CORS_ORIGINS.${NC}"
        exit 0
        ;;
    *)
        echo -e "${YELLOW}Opção inválida. Abrindo .env no editor...${NC}"
        "${EDITOR:-nano}" .env
        ;;
esac

echo ""
echo -e "${GREEN}✅ Configuração do .env concluída.${NC}"
echo -e "${BLUE}Variáveis obrigatórias: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SECRET_KEY, JWT_SECRET.${NC}"
echo -e "${YELLOW}Nunca commite o arquivo .env no Git.${NC}"
echo ""
