#!/bin/bash
###############################################################################
# Fix 502 Error - Alça Finanças
# Script para diagnosticar e corrigir erro 502 Bad Gateway
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/var/www/alca-financas"

echo -e "${RED}🔧 Diagnóstico e Fix do Erro 502${NC}"
echo ""

# =============================================================================
# 1. Verificar se os containers estão rodando
# =============================================================================
echo -e "${BLUE}1️⃣ Verificando containers...${NC}"
cd "$PROJECT_DIR"

if ! docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    echo -e "${RED}❌ Containers não estão rodando!${NC}"
    echo ""
    echo -e "${BLUE}Iniciando containers...${NC}"
    docker-compose -f docker-compose.prod.yml up -d
    sleep 10
else
    echo -e "${GREEN}✅ Containers rodando${NC}"
fi
echo ""

# =============================================================================
# 2. Verificar portas
# =============================================================================
echo -e "${BLUE}2️⃣ Verificando portas...${NC}"

check_port() {
    local port=$1
    local service=$2
    echo -n "  Porta $port ($service): "

    if ss -lntp | grep -q ":$port "; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ Não está escutando${NC}"
        return 1
    fi
}

PORTS_OK=true
check_port 3000 "Frontend" || PORTS_OK=false
check_port 8001 "Backend" || PORTS_OK=false

if [ "$PORTS_OK" = false ]; then
    echo -e "${RED}❌ Algumas portas não estão escutando!${NC}"
    echo ""
    echo -e "${BLUE}Verificando mapeamento de portas no Docker...${NC}"
    docker-compose -f docker-compose.prod.yml ps
    echo ""

    # Verificar .env
    echo -e "${BLUE}Verificando variável BACKEND_PORT no .env...${NC}"
    if grep -q "BACKEND_PORT=8000" .env; then
        echo -e "${YELLOW}⚠️  BACKEND_PORT está configurado como 8000, mas Nginx espera 8001!${NC}"
        echo ""
        echo -e "${BLUE}Corrigindo...${NC}"

        # Fazer backup do .env
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

        # Corrigir porta
        sed -i 's/BACKEND_PORT=8000/BACKEND_PORT=8001/g' .env
        # ou PORT=8000 para PORT=8001
        sed -i 's/^PORT=8000/PORT=8001/g' .env

        echo -e "${GREEN}✅ .env corrigido${NC}"
        echo ""
        echo -e "${BLUE}Reiniciando containers...${NC}"
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up -d --build
        sleep 10
    fi
else
    echo -e "${GREEN}✅ Todas as portas estão escutando${NC}"
fi
echo ""

# =============================================================================
# 3. Verificar logs do backend
# =============================================================================
echo -e "${BLUE}3️⃣ Verificando logs do backend...${NC}"
echo ""
docker-compose -f docker-compose.prod.yml logs --tail=20 backend
echo ""

# =============================================================================
# 4. Testar conexão local
# =============================================================================
echo -e "${BLUE}4️⃣ Testando conexão local...${NC}"

echo -n "  Frontend (localhost:3000): "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Falhou${NC}"
fi

echo -n "  Backend (localhost:8001/api/health): "
if curl -s http://localhost:8001/api/health | grep -q "ok"; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Falhou${NC}"
    echo ""
    echo -e "${YELLOW}Tentando porta 8000...${NC}"
    if curl -s http://localhost:8000/api/health | grep -q "ok"; then
        echo -e "${YELLOW}⚠️  Backend está na porta 8000, não 8001!${NC}"
        echo "Configure BACKEND_PORT=8001 no .env e reinicie os containers."
    fi
fi
echo ""

# =============================================================================
# 5. Verificar configuração Nginx
# =============================================================================
echo -e "${BLUE}5️⃣ Verificando configuração Nginx...${NC}"

# Verificar upstream do backend
if grep -q "proxy_pass http://127.0.0.1:8001" /etc/nginx/sites-available/alcahub.cloud; then
    echo -e "${GREEN}✅ Nginx configurado para porta 8001${NC}"
else
    echo -e "${YELLOW}⚠️  Verificar configuração do proxy_pass${NC}"
fi

# Testar configuração
sudo nginx -t
echo ""

# =============================================================================
# 6. Verificar CORS
# =============================================================================
echo -e "${BLUE}6️⃣ Verificando configuração CORS...${NC}"
echo ""
grep "CORS_ORIGINS" .env || echo -e "${YELLOW}⚠️  CORS_ORIGINS não encontrado no .env${NC}"
echo ""

# =============================================================================
# 7. Reiniciar tudo
# =============================================================================
echo -e "${BLUE}7️⃣ Reiniciando serviços...${NC}"

echo "Reiniciando containers..."
docker-compose -f docker-compose.prod.yml restart

echo "Aguardando inicialização..."
sleep 10

echo "Recarregando Nginx..."
sudo systemctl reload nginx

echo ""

# =============================================================================
# 8. Teste final
# =============================================================================
echo -e "${BLUE}8️⃣ Teste final...${NC}"
echo ""

echo "Testando frontend:"
curl -I https://alcahub.cloud

echo ""
echo "Testando backend:"
curl https://alcahub.cloud/api/health

echo ""

# =============================================================================
# RESUMO
# =============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 Resumo${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Status dos containers:${NC}"
docker-compose -f docker-compose.prod.yml ps
echo ""
echo -e "${BLUE}Portas escutando:${NC}"
ss -lntp | grep -E ':(80|443|3000|8001)'
echo ""
echo -e "${BLUE}Próximos passos:${NC}"
echo "1. Verifique os logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "2. Teste manualmente: curl https://alcahub.cloud"
echo "3. Ver logs Nginx: sudo tail -f /var/log/nginx/error.log"
echo ""
