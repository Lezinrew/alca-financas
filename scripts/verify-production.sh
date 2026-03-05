#!/bin/bash
###############################################################################
# Verify Production Setup - Alça Finanças
# Script para verificar DNS, SSL e status da aplicação
# Pode ser executado localmente ou no servidor
###############################################################################

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
EXPECTED_IP="76.13.239.220"

echo -e "${BLUE}🔍 Verificação de Produção - Alça Finanças${NC}"
echo ""

# =============================================================================
# VERIFICAÇÃO 1: DNS
# =============================================================================
echo -e "${BLUE}📡 Verificando DNS...${NC}"
echo ""

check_dns() {
    local domain=$1
    echo -n "  $domain → "

    if command -v dig &> /dev/null; then
        resolved_ip=$(dig +short "$domain" A | head -n1)
    elif command -v nslookup &> /dev/null; then
        resolved_ip=$(nslookup "$domain" | grep -A1 "Name:" | tail -n1 | awk '{print $2}')
    else
        echo -e "${YELLOW}⚠️  comando dig/nslookup não encontrado${NC}"
        return 1
    fi

    if [ "$resolved_ip" = "$EXPECTED_IP" ]; then
        echo -e "${GREEN}✅ $resolved_ip${NC}"
        return 0
    else
        echo -e "${RED}❌ $resolved_ip (esperado: $EXPECTED_IP)${NC}"
        return 1
    fi
}

DNS_OK=true
check_dns "$DOMAIN" || DNS_OK=false
check_dns "$WWW_DOMAIN" || DNS_OK=false
check_dns "$API_DOMAIN" || DNS_OK=false

if [ "$DNS_OK" = true ]; then
    echo -e "${GREEN}✅ DNS OK${NC}"
else
    echo -e "${RED}❌ DNS com problemas!${NC}"
fi
echo ""

# =============================================================================
# VERIFICAÇÃO 2: HTTP/HTTPS
# =============================================================================
echo -e "${BLUE}🌐 Verificando HTTP/HTTPS...${NC}"
echo ""

check_http() {
    local url=$1
    local service=$2
    echo -n "  $service ($url)... "

    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)

    if [ "$response" = "200" ] || [ "$response" = "301" ] || [ "$response" = "302" ]; then
        echo -e "${GREEN}✅ HTTP $response${NC}"
        return 0
    else
        echo -e "${RED}❌ HTTP $response (ou timeout)${NC}"
        return 1
    fi
}

HTTP_OK=true
check_http "http://$DOMAIN" "Frontend HTTP" || HTTP_OK=false
check_http "https://$DOMAIN" "Frontend HTTPS" || HTTP_OK=false
check_http "https://$API_DOMAIN/api/health" "API Health" || HTTP_OK=false

if [ "$HTTP_OK" = true ]; then
    echo -e "${GREEN}✅ HTTP/HTTPS OK${NC}"
else
    echo -e "${YELLOW}⚠️  Alguns endpoints não estão respondendo${NC}"
fi
echo ""

# =============================================================================
# VERIFICAÇÃO 3: SSL Certificate
# =============================================================================
echo -e "${BLUE}🔒 Verificando certificado SSL...${NC}"
echo ""

check_ssl() {
    local domain=$1
    echo -n "  $domain... "

    if command -v openssl &> /dev/null; then
        cert_info=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)

        if [ $? -eq 0 ]; then
            expiry=$(echo "$cert_info" | grep "notAfter" | cut -d= -f2)
            echo -e "${GREEN}✅ Válido até: $expiry${NC}"
            return 0
        else
            echo -e "${RED}❌ Certificado inválido ou não encontrado${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  openssl não encontrado${NC}"
        return 1
    fi
}

SSL_OK=true
check_ssl "$DOMAIN" || SSL_OK=false
check_ssl "$API_DOMAIN" || SSL_OK=false

if [ "$SSL_OK" = true ]; then
    echo -e "${GREEN}✅ SSL OK${NC}"
else
    echo -e "${YELLOW}⚠️  Certificado SSL com problemas${NC}"
fi
echo ""

# =============================================================================
# VERIFICAÇÃO 4: Portas (apenas no servidor)
# =============================================================================
if command -v ss &> /dev/null; then
    echo -e "${BLUE}🔌 Verificando portas (servidor)...${NC}"
    echo ""

    check_port() {
        local port=$1
        local service=$2
        echo -n "  Porta $port ($service)... "

        if ss -lntp 2>/dev/null | grep -q ":$port "; then
            echo -e "${GREEN}✅ Escutando${NC}"
            return 0
        else
            echo -e "${RED}❌ Não está escutando${NC}"
            return 1
        fi
    }

    PORTS_OK=true
    check_port 80 "HTTP" || PORTS_OK=false
    check_port 443 "HTTPS" || PORTS_OK=false
    check_port 3000 "Frontend" || PORTS_OK=false
    check_port 8001 "Backend" || PORTS_OK=false

    if [ "$PORTS_OK" = true ]; then
        echo -e "${GREEN}✅ Portas OK${NC}"
    else
        echo -e "${YELLOW}⚠️  Algumas portas não estão escutando${NC}"
    fi
    echo ""
fi

# =============================================================================
# VERIFICAÇÃO 5: Docker (apenas no servidor)
# =============================================================================
if command -v docker &> /dev/null; then
    echo -e "${BLUE}🐳 Verificando containers Docker...${NC}"
    echo ""

    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "alca-financas|backend|frontend" &> /dev/null; then
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "alca-financas|backend|frontend|NAME"
        echo -e "${GREEN}✅ Containers rodando${NC}"
    else
        echo -e "${RED}❌ Nenhum container encontrado!${NC}"
    fi
    echo ""
fi

# =============================================================================
# RESUMO
# =============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 Resumo da Verificação${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

[ "$DNS_OK" = true ] && echo -e "${GREEN}✅ DNS${NC}" || echo -e "${RED}❌ DNS${NC}"
[ "$HTTP_OK" = true ] && echo -e "${GREEN}✅ HTTP/HTTPS${NC}" || echo -e "${YELLOW}⚠️  HTTP/HTTPS${NC}"
[ "$SSL_OK" = true ] && echo -e "${GREEN}✅ SSL${NC}" || echo -e "${YELLOW}⚠️  SSL${NC}"

echo ""
echo -e "${BLUE}🌐 URLs para testar:${NC}"
echo "  https://$DOMAIN"
echo "  https://$API_DOMAIN/api/health"
echo ""
