#!/usr/bin/env bash
###############################################################################
# Quick Update - Alça Finanças
# Deploy rápido: apenas git pull + restart (sem rebuild)
# Use quando fizer mudanças simples no código Python/JS
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_SSH_KEY="${SERVER_SSH_KEY:-}"
SERVER_PASSWORD="${SERVER_PASSWORD:-}"
PROJECT_DIR="${PROJECT_DIR:-/var/www/alca-financas}"

# Funções de log
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo -e "${BLUE}⚡ QUICK UPDATE - Alça Finanças${NC}"
echo ""

# Validar servidor
if [ -z "$SERVER_HOST" ]; then
    read -p "Digite o hostname/IP do servidor: " SERVER_HOST
    [ -z "$SERVER_HOST" ] && log_error "Hostname é obrigatório"
fi

# Configurar autenticação SSH
SSH_CMD="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$SERVER_SSH_KEY" ]; then
    # Usar chave SSH se fornecida
    SSH_CMD="$SSH_CMD -i $SERVER_SSH_KEY"
else
    # Pedir senha uma única vez
    if [ -z "$SERVER_PASSWORD" ]; then
        read -sp "Digite a senha SSH para ${SERVER_USER}@${SERVER_HOST}: " SERVER_PASSWORD
        echo ""
    fi

    # Verificar se sshpass está instalado
    if ! command -v sshpass &> /dev/null; then
        log_error "sshpass não encontrado. Instale: brew install hudochenkov/sshpass/sshpass (macOS) ou sudo apt-get install sshpass (Linux)"
    fi

    SSH_CMD="sshpass -p '$SERVER_PASSWORD' $SSH_CMD"
fi

SSH_CMD="$SSH_CMD ${SERVER_USER}@${SERVER_HOST}"

# Função para executar comandos remotos
remote_exec() {
    eval "$SSH_CMD \"$1\"" 2>&1 | grep -v "Warning: Permanently added"
}

# 1. Git pull
log_info "Atualizando código..."
remote_exec "cd ${PROJECT_DIR} && git pull origin main"
log_success "Código atualizado"

# 2. Restart containers
log_info "Reiniciando containers..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml restart"
log_success "Containers reiniciados"

# 3. Verificar status
sleep 3
log_info "Verificando status..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml ps"

log_success "Update completo!"
echo ""
echo -e "${BLUE}🔍 Ver logs:${NC}"
echo "   Backend:  ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs -f backend'"
echo "   Frontend: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs -f frontend'"
echo ""
