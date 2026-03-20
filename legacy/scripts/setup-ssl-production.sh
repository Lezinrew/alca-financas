#!/bin/bash
###############################################################################
# Setup SSL/HTTPS for Production - Alça Finanças
# Script para configurar SSL com Let's Encrypt no VPS
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações
DOMAIN="alcahub.cloud"
WWW_DOMAIN="www.alcahub.cloud"
API_DOMAIN="api.alcahub.cloud"
EMAIL="seu-email@exemplo.com"  # ⚠️  ALTERE ESTE EMAIL!
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN"
PROJECT_DIR="/var/www/alca-financas"

echo -e "${BLUE}🔒 Setup SSL/HTTPS - Alça Finanças${NC}"
echo ""

# Verificar se está executando como root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Este script deve ser executado como root (use sudo)${NC}"
    exit 1
fi

# Verificar se o email foi alterado
if [ "$EMAIL" = "seu-email@exemplo.com" ]; then
    echo -e "${RED}❌ Por favor, altere o EMAIL no início do script!${NC}"
    exit 1
fi

# =============================================================================
# PASSO 1: Verificar DNS
# =============================================================================
echo -e "${BLUE}📡 PASSO 1/8: Verificando DNS...${NC}"
echo ""

check_dns() {
    local domain=$1
    local expected_ip="76.13.239.220"
    echo -n "  Verificando $domain... "

    resolved_ip=$(dig +short "$domain" A | head -n1)

    if [ "$resolved_ip" = "$expected_ip" ]; then
        echo -e "${GREEN}✅ OK ($resolved_ip)${NC}"
        return 0
    else
        echo -e "${RED}❌ FALHOU (esperado: $expected_ip, obtido: $resolved_ip)${NC}"
        return 1
    fi
}

DNS_OK=true
check_dns "$DOMAIN" || DNS_OK=false
check_dns "$WWW_DOMAIN" || DNS_OK=false
check_dns "$API_DOMAIN" || DNS_OK=false

if [ "$DNS_OK" = false ]; then
    echo -e "${RED}❌ Alguns domínios não estão apontando para o IP correto!${NC}"
    echo "Aguarde a propagação DNS (pode levar até 48h) e tente novamente."
    exit 1
fi
echo -e "${GREEN}✅ DNS configurado corretamente!${NC}"
echo ""

# =============================================================================
# PASSO 2: Verificar se o Docker está rodando
# =============================================================================
echo -e "${BLUE}🐳 PASSO 2/8: Verificando Docker...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker não está rodando!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker OK${NC}"
echo ""

# =============================================================================
# PASSO 3: Verificar se a aplicação está rodando
# =============================================================================
echo -e "${BLUE}🔍 PASSO 3/8: Verificando containers da aplicação...${NC}"

check_port() {
    local port=$1
    local service=$2
    echo -n "  Verificando $service (porta $port)... "

    if ss -lntp | grep -q ":$port "; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ Não está escutando${NC}"
        return 1
    fi
}

APP_OK=true
check_port 3000 "Frontend" || APP_OK=false
check_port 8001 "Backend" || APP_OK=false

if [ "$APP_OK" = false ]; then
    echo -e "${RED}❌ Aplicação não está rodando!${NC}"
    echo "Execute o deploy primeiro: cd $PROJECT_DIR && ./scripts/deploy-hostinger.sh"
    exit 1
fi
echo -e "${GREEN}✅ Aplicação rodando${NC}"
echo ""

# =============================================================================
# PASSO 4: Instalar Certbot
# =============================================================================
echo -e "${BLUE}📦 PASSO 4/8: Instalando Certbot...${NC}"
if ! command -v certbot &> /dev/null; then
    apt update
    apt install -y certbot python3-certbot-nginx
    echo -e "${GREEN}✅ Certbot instalado${NC}"
else
    echo -e "${GREEN}✅ Certbot já instalado${NC}"
fi
echo ""

# =============================================================================
# PASSO 5: Backup da configuração Nginx atual
# =============================================================================
echo -e "${BLUE}💾 PASSO 5/8: Backup da configuração Nginx...${NC}"
if [ -f "$NGINX_CONF" ]; then
    cp "$NGINX_CONF" "$NGINX_CONF.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✅ Backup criado${NC}"
else
    echo -e "${YELLOW}⚠️  Nenhuma configuração anterior encontrada${NC}"
fi
echo ""

# =============================================================================
# PASSO 6: Copiar nova configuração Nginx
# =============================================================================
echo -e "${BLUE}📝 PASSO 6/8: Configurando Nginx...${NC}"

# Criar diretório para Let's Encrypt
mkdir -p /var/www/certbot

# Copiar configuração
if [ -f "$PROJECT_DIR/nginx-vps.conf" ]; then
    cp "$PROJECT_DIR/nginx-vps.conf" "$NGINX_CONF"
    echo -e "${GREEN}✅ Configuração copiada${NC}"
else
    echo -e "${RED}❌ Arquivo nginx-vps.conf não encontrado!${NC}"
    exit 1
fi

# Criar link simbólico se não existir
if [ ! -L "/etc/nginx/sites-enabled/$DOMAIN" ]; then
    ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/$DOMAIN"
    echo -e "${GREEN}✅ Link simbólico criado${NC}"
fi

# Remover configuração padrão se existir
if [ -L "/etc/nginx/sites-enabled/default" ]; then
    rm "/etc/nginx/sites-enabled/default"
    echo -e "${GREEN}✅ Configuração padrão removida${NC}"
fi

# Testar configuração
if nginx -t; then
    echo -e "${GREEN}✅ Configuração Nginx válida${NC}"
    systemctl reload nginx
else
    echo -e "${RED}❌ Erro na configuração Nginx!${NC}"
    exit 1
fi
echo ""

# =============================================================================
# PASSO 7: Obter certificado SSL
# =============================================================================
echo -e "${BLUE}🔒 PASSO 7/8: Obtendo certificado SSL...${NC}"
echo "Domínios: $DOMAIN, $WWW_DOMAIN, $API_DOMAIN"
echo "Email: $EMAIL"
echo ""

certbot --nginx \
    -d "$DOMAIN" \
    -d "$WWW_DOMAIN" \
    -d "$API_DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --redirect

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Certificado SSL obtido com sucesso!${NC}"
else
    echo -e "${RED}❌ Erro ao obter certificado SSL!${NC}"
    exit 1
fi
echo ""

# =============================================================================
# PASSO 8: Configurar renovação automática
# =============================================================================
echo -e "${BLUE}♻️  PASSO 8/8: Configurando renovação automática...${NC}"

# Testar renovação
certbot renew --dry-run

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Renovação automática configurada!${NC}"
    echo "O certificado será renovado automaticamente antes de expirar."
else
    echo -e "${YELLOW}⚠️  Aviso: teste de renovação falhou${NC}"
fi
echo ""

# =============================================================================
# RESUMO FINAL
# =============================================================================
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ SSL/HTTPS configurado com sucesso!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}🌐 URLs disponíveis:${NC}"
echo "  Frontend:  https://$DOMAIN"
echo "  Frontend:  https://$WWW_DOMAIN (redireciona para $DOMAIN)"
echo "  API:       https://$API_DOMAIN"
echo ""
echo -e "${BLUE}🔧 Comandos úteis:${NC}"
echo "  Ver certificados:     sudo certbot certificates"
echo "  Renovar manualmente:  sudo certbot renew"
echo "  Testar renovação:     sudo certbot renew --dry-run"
echo "  Recarregar Nginx:     sudo systemctl reload nginx"
echo "  Ver logs Nginx:       sudo tail -f /var/log/nginx/error.log"
echo ""
echo -e "${BLUE}📝 Próximos passos:${NC}"
echo "  1. Acesse https://$DOMAIN e verifique se está funcionando"
echo "  2. Acesse https://$API_DOMAIN/api/health e verifique o backend"
echo "  3. Atualize o FRONTEND_URL no .env para: https://$DOMAIN"
echo "  4. Atualize o API_BASE_URL no .env para: https://$API_DOMAIN"
echo "  5. Reinicie os containers: cd $PROJECT_DIR && docker-compose -f docker-compose.prod.yml restart"
echo ""
