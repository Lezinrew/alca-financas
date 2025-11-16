#!/bin/bash

###############################################################################
# Setup GitHub Secrets - Alça Finanças
# Script interativo para configurar secrets do GitHub
###############################################################################

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔐 Configuração de GitHub Secrets - Alça Finanças${NC}\n"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) não encontrado${NC}"
    echo ""
    echo "Instale o GitHub CLI:"
    echo "  macOS:   brew install gh"
    echo "  Ubuntu:  https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    echo "  Windows: https://github.com/cli/cli/releases"
    echo ""
    echo "Depois execute: gh auth login"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Não autenticado no GitHub${NC}"
    echo "Execute: gh auth login"
    exit 1
fi

echo -e "${GREEN}✅ GitHub CLI autenticado${NC}\n"

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
if [ -z "$REPO" ]; then
    echo -e "${RED}❌ Não foi possível detectar o repositório${NC}"
    echo "Execute este script na raiz do repositório Git"
    exit 1
fi

echo -e "📦 Repositório: ${BLUE}$REPO${NC}\n"

# Function to set secret
set_secret() {
    local name=$1
    local value=$2
    local description=$3

    echo -e "${YELLOW}Configurando: $name${NC}"
    echo "$value" | gh secret set "$name" --body-file -

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $name configurado${NC}\n"
    else
        echo -e "${RED}❌ Erro ao configurar $name${NC}\n"
    fi
}

# Interactive configuration
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Docker Registry Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

read -p "Docker Registry (registry.hub.docker.com): " DOCKER_REGISTRY
DOCKER_REGISTRY=${DOCKER_REGISTRY:-registry.hub.docker.com}

read -p "Docker Username: " DOCKER_USERNAME

read -sp "Docker Password/Token: " DOCKER_PASSWORD
echo ""

if [ -n "$DOCKER_USERNAME" ] && [ -n "$DOCKER_PASSWORD" ]; then
    set_secret "DOCKER_REGISTRY" "$DOCKER_REGISTRY"
    set_secret "DOCKER_USERNAME" "$DOCKER_USERNAME"
    set_secret "DOCKER_PASSWORD" "$DOCKER_PASSWORD"
else
    echo -e "${YELLOW}⚠️  Pulando configuração Docker${NC}\n"
fi

# Production Server
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Production Server Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

read -p "Production Host (alcahub.com.br): " PROD_HOST
PROD_HOST=${PROD_HOST:-alcahub.com.br}

read -p "Production User (deploy): " PROD_USER
PROD_USER=${PROD_USER:-deploy}

echo ""
echo "SSH Private Key:"
echo "Cole a chave privada (termine com linha em branco):"
echo ""

SSH_KEY=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    SSH_KEY+="$line"$'\n'
done

if [ -n "$PROD_HOST" ] && [ -n "$PROD_USER" ] && [ -n "$SSH_KEY" ]; then
    set_secret "PROD_HOST" "$PROD_HOST"
    set_secret "PROD_USER" "$PROD_USER"
    set_secret "PROD_SSH_KEY" "$SSH_KEY"
else
    echo -e "${YELLOW}⚠️  Pulando configuração do servidor${NC}\n"
fi

# Telegram (Optional)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Telegram Notifications (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

read -p "Configurar Telegram? (y/N): " SETUP_TELEGRAM

if [[ "$SETUP_TELEGRAM" =~ ^[Yy]$ ]]; then
    read -p "Telegram Chat ID: " TELEGRAM_CHAT_ID
    read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN

    if [ -n "$TELEGRAM_CHAT_ID" ] && [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        set_secret "TELEGRAM_CHAT_ID" "$TELEGRAM_CHAT_ID"
        set_secret "TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_TOKEN"
    fi
fi

# Summary
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Configuração Concluída!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "📋 Secrets configurados:"
gh secret list

echo ""
echo -e "${BLUE}📍 Próximos Passos:${NC}"
echo ""
echo "1. Verifique os secrets:"
echo "   ${YELLOW}gh secret list${NC}"
echo ""
echo "2. Teste o pipeline:"
echo "   ${YELLOW}git commit --allow-empty -m 'test: verificar secrets'${NC}"
echo "   ${YELLOW}git push origin main${NC}"
echo ""
echo "3. Acompanhe em:"
echo "   ${YELLOW}https://github.com/$REPO/actions${NC}"
echo ""
