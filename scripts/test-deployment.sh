#!/bin/bash

###############################################################################
# Script de Testes de Deploy - Alça Finanças
# Verifica se todos os serviços estão funcionando corretamente
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
SERVER_PASS="4203434@Mudar"

# Contadores
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Função para executar SSH
execute_ssh() {
    sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SERVER_USER}@${SERVER_HOST}" "$1" 2>/dev/null
}

# Função para testar
test_check() {
    local test_name="$1"
    local command="$2"
    local expected="$3"
    
    echo -e "${BLUE}🧪 Testando: ${test_name}...${NC}"
    
    if result=$(execute_ssh "$command" 2>&1); then
        if [ -z "$expected" ] || echo "$result" | grep -q "$expected"; then
            echo -e "${GREEN}✅ PASSOU: ${test_name}${NC}"
            ((TESTS_PASSED++))
            return 0
        else
            echo -e "${RED}❌ FALHOU: ${test_name}${NC}"
            echo -e "${YELLOW}   Esperado: ${expected}${NC}"
            echo -e "${YELLOW}   Recebido: ${result}${NC}"
            ((TESTS_FAILED++))
            FAILED_TESTS+=("$test_name")
            return 1
        fi
    else
        echo -e "${RED}❌ FALHOU: ${test_name} (erro ao executar)${NC}"
        ((TESTS_FAILED++))
        FAILED_TESTS+=("$test_name")
        return 1
    fi
}

# Função para testar HTTP
test_http() {
    local test_name="$1"
    local url="$2"
    local expected_status="$3"
    
    echo -e "${BLUE}🧪 Testando: ${test_name}...${NC}"
    
    if response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null); then
        if [ "$response" = "$expected_status" ]; then
            echo -e "${GREEN}✅ PASSOU: ${test_name} (HTTP ${response})${NC}"
            ((TESTS_PASSED++))
            return 0
        else
            echo -e "${RED}❌ FALHOU: ${test_name}${NC}"
            echo -e "${YELLOW}   Esperado: HTTP ${expected_status}${NC}"
            echo -e "${YELLOW}   Recebido: HTTP ${response}${NC}"
            ((TESTS_FAILED++))
            FAILED_TESTS+=("$test_name")
            return 1
        fi
    else
        echo -e "${RED}❌ FALHOU: ${test_name} (erro ao conectar)${NC}"
        ((TESTS_FAILED++))
        FAILED_TESTS+=("$test_name")
        return 1
    fi
}

echo -e "${BLUE}🚀 Iniciando testes de deploy...${NC}\n"

# 1. Testar conexão SSH
test_check "Conexão SSH" "echo 'OK'" "OK"

# 2. Testar serviços systemd
echo -e "\n${BLUE}📊 Testando serviços systemd...${NC}"
test_check "Backend (alca-financas) ativo" "systemctl is-active alca-financas" "active"
test_check "Chatbot (alca-chatbot) ativo" "systemctl is-active alca-chatbot" "active"
test_check "Nginx ativo" "systemctl is-active nginx" "active"
test_check "MongoDB ativo" "systemctl is-active mongod" "active"

# 3. Testar health checks
echo -e "\n${BLUE}🏥 Testando health checks...${NC}"
test_http "API Health Check" "https://api.alcahub.com.br/api/health" "200"
test_http "Chatbot Health Check" "https://chat.alcahub.com.br/api/health" "200"

# 4. Testar endpoints HTTP/HTTPS
echo -e "\n${BLUE}🌐 Testando endpoints...${NC}"
# Frontend pode retornar 301 (redirecionamento) ou 200, ambos são válidos
frontend_status=$(curl -sL -o /dev/null -w "%{http_code}" "https://app.alcahub.com.br" 2>/dev/null)
if [ "$frontend_status" = "200" ] || [ "$frontend_status" = "301" ]; then
    echo -e "${GREEN}✅ PASSOU: Frontend (app.alcahub.com.br) (HTTP ${frontend_status})${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FALHOU: Frontend (app.alcahub.com.br)${NC}"
    echo -e "${YELLOW}   Recebido: HTTP ${frontend_status}${NC}"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("Frontend (app.alcahub.com.br)")
fi
test_http "API (api.alcahub.com.br)" "https://api.alcahub.com.br/api/health" "200"
test_http "Chatbot (chat.alcahub.com.br)" "https://chat.alcahub.com.br/api/health" "200"
test_http "Redirecionamento HTTP → HTTPS" "http://alcahub.com.br" "301"

# 5. Testar SSL
echo -e "\n${BLUE}🔒 Testando certificados SSL...${NC}"
test_check "SSL app.alcahub.com.br" "echo | openssl s_client -connect app.alcahub.com.br:443 -servername app.alcahub.com.br 2>/dev/null | grep -q 'Verify return code: 0'" "" || echo -e "${YELLOW}⚠️  Verificação SSL manual necessária${NC}"
test_check "SSL api.alcahub.com.br" "echo | openssl s_client -connect api.alcahub.com.br:443 -servername api.alcahub.com.br 2>/dev/null | grep -q 'Verify return code: 0'" "" || echo -e "${YELLOW}⚠️  Verificação SSL manual necessária${NC}"

# 6. Testar processos
echo -e "\n${BLUE}⚙️  Testando processos...${NC}"
test_check "Gunicorn rodando" "pgrep -f gunicorn || ps aux | grep -v grep | grep gunicorn" ""
test_check "Uvicorn (chatbot) rodando" "pgrep -f uvicorn || ps aux | grep -v grep | grep uvicorn" ""
test_check "Nginx rodando" "pgrep nginx || ps aux | grep -v grep | grep nginx" ""

# 7. Testar portas
echo -e "\n${BLUE}🔌 Testando portas...${NC}"
test_check "Porta 80 (HTTP) aberta" "netstat -tlnp | grep ':80 ' || ss -tlnp | grep ':80 '" ""
test_check "Porta 443 (HTTPS) aberta" "netstat -tlnp | grep ':443 ' || ss -tlnp | grep ':443 '" ""
test_check "Porta 8001 (Backend) local" "netstat -tlnp | grep ':8001 ' || ss -tlnp | grep ':8001 '" ""

# 8. Testar logs de erros recentes
echo -e "\n${BLUE}📋 Verificando logs de erros...${NC}"
errors=$(execute_ssh "journalctl -u alca-financas --since '5 minutes ago' --no-pager | grep -i 'error\|fatal\|exception' | tail -5" 2>/dev/null || echo "")
if [ -z "$errors" ]; then
    echo -e "${GREEN}✅ PASSOU: Nenhum erro recente no backend${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  AVISO: Erros encontrados nos logs do backend:${NC}"
    echo "$errors" | while read line; do
        echo -e "${YELLOW}   $line${NC}"
    done
fi

# 9. Testar uso de recursos
echo -e "\n${BLUE}💾 Verificando recursos do sistema...${NC}"
memory=$(execute_ssh "free -h | grep Mem | awk '{print \$3}'" 2>/dev/null || echo "N/A")
disk=$(execute_ssh "df -h / | tail -1 | awk '{print \$5}' | sed 's/%//'" 2>/dev/null || echo "N/A")
echo -e "${BLUE}   Memória usada: ${memory}${NC}"
echo -e "${BLUE}   Disco usado: ${disk}%${NC}"

if [ "$disk" != "N/A" ] && [ "$disk" -gt 90 ]; then
    echo -e "${RED}❌ FALHOU: Disco acima de 90%${NC}"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("Disco acima de 90%")
else
    echo -e "${GREEN}✅ PASSOU: Recursos do sistema OK${NC}"
    ((TESTS_PASSED++))
fi

# 10. Testar build do frontend
echo -e "\n${BLUE}📦 Verificando build do frontend...${NC}"
test_check "Diretório dist existe" "test -d /var/www/alca-financas/frontend/dist && echo 'OK'" "OK"
test_check "index.html existe" "test -f /var/www/alca-financas/frontend/dist/index.html && echo 'OK'" "OK"

# Resumo final
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 RESUMO DOS TESTES${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Testes passados: ${TESTS_PASSED}${NC}"
echo -e "${RED}❌ Testes falhados: ${TESTS_FAILED}${NC}"

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "\n${GREEN}🎉 TODOS OS TESTES PASSARAM!${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  ALGUNS TESTES FALHARAM:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "${RED}   - ${test}${NC}"
    done
    echo -e "\n${YELLOW}💡 Execute os comandos manualmente para investigar:${NC}"
    echo -e "   ssh ${SERVER_USER}@${SERVER_HOST} 'systemctl status alca-financas'"
    echo -e "   ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -n 50'"
    echo -e "   ssh ${SERVER_USER}@${SERVER_HOST} 'systemctl status nginx'"
    exit 1
fi

