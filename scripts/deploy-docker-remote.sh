#!/usr/bin/env bash
###############################################################################
# Deploy Remoto - Alça Finanças com Docker (Supabase)
# Script moderno para deploy via SSH usando Docker Compose
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações (definir via environment ou prompt)
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-}"
SERVER_SSH_KEY="${SERVER_SSH_KEY:-}"
PROJECT_DIR="${PROJECT_DIR:-/var/www/alca-financas}"
DOMAIN="${DOMAIN:-alcahub.cloud}"

# Funções de log
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Banner
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════╗
║     ALÇA FINANÇAS - DEPLOY DOCKER REMOTO     ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Validar configurações
if [ -z "$SERVER_HOST" ]; then
    read -p "Digite o hostname/IP do servidor: " SERVER_HOST
    [ -z "$SERVER_HOST" ] && log_error "Hostname é obrigatório"
fi

if [ -z "$SERVER_USER" ]; then
    read -p "Digite o usuário SSH (default: root): " SERVER_USER
    SERVER_USER="${SERVER_USER:-root}"
fi

log_info "Servidor: ${SERVER_USER}@${SERVER_HOST}"
log_info "Diretório: ${PROJECT_DIR}"
log_info "Domínio: ${DOMAIN}"
echo ""

# Construir comando SSH
SSH_CMD="ssh"
if [ -n "$SERVER_SSH_KEY" ]; then
    SSH_CMD="$SSH_CMD -i $SERVER_SSH_KEY"
fi
SSH_CMD="$SSH_CMD -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_HOST}"

# Função para executar comandos remotos
remote_exec() {
    $SSH_CMD "$1"
}

# Testar conexão
log_info "Testando conexão SSH..."
if ! remote_exec "echo 'OK'" > /dev/null 2>&1; then
    log_error "Não foi possível conectar ao servidor via SSH"
fi
log_success "Conexão SSH estabelecida"

# 1. Verificar/Instalar dependências
log_info "Verificando dependências no servidor..."
remote_exec "command -v docker > /dev/null 2>&1 || curl -fsSL https://get.docker.com | sh"
remote_exec "command -v docker-compose > /dev/null 2>&1 || (curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose)"
log_success "Docker e Docker Compose instalados"

# 2. Criar/atualizar diretório do projeto
log_info "Preparando diretório do projeto..."
remote_exec "mkdir -p ${PROJECT_DIR} && cd ${PROJECT_DIR} && \
    if [ -d '.git' ]; then \
        git fetch origin && git reset --hard origin/main; \
    else \
        git clone https://github.com/Lezinrew/alca-financas.git .; \
    fi"
log_success "Código atualizado"

# 3. Verificar arquivo .env
log_info "Verificando configurações..."
if ! remote_exec "test -f ${PROJECT_DIR}/.env"; then
    log_warn "Arquivo .env não encontrado!"
    log_warn "Criando .env.example..."

    remote_exec "cat > ${PROJECT_DIR}/.env << 'ENVEOF'
# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
BACKEND_PORT=8001
FLASK_ENV=production

# CORS
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

# Frontend Build
VITE_API_URL=https://${DOMAIN}
VITE_SUPABASE_URL=https://seu-projeto.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
ENVEOF
"

    log_error "Configure o arquivo ${PROJECT_DIR}/.env com suas credenciais Supabase antes de continuar!"
else
    log_success "Arquivo .env encontrado"
fi

# 4. Build do frontend com configurações de produção
log_info "Fazendo build do frontend..."
remote_exec "cd ${PROJECT_DIR} && \
    mkdir -p build/frontend && \
    docker run --rm -v \$(pwd)/frontend:/app -v \$(pwd)/build/frontend:/app/dist -w /app \
        -e VITE_API_URL=\${VITE_API_URL} \
        -e VITE_SUPABASE_URL=\${VITE_SUPABASE_URL} \
        -e VITE_SUPABASE_ANON_KEY=\${VITE_SUPABASE_ANON_KEY} \
        --env-file .env \
        node:20-alpine sh -c 'npm ci && npm run build && cp -r dist/* /app/dist/'"
log_success "Frontend buildado"

# 5. Build das imagens Docker
log_info "Construindo imagens Docker..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml build"
log_success "Imagens construídas"

# 6. Parar containers antigos
log_info "Parando containers antigos..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml down" || true

# 7. Iniciar containers
log_info "Iniciando containers..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml up -d"
log_success "Containers iniciados"

# 8. Aguardar backend inicializar
log_info "Aguardando backend inicializar..."
sleep 5

# 9. Verificar status
log_info "Verificando status dos containers..."
BACKEND_STATUS=$(remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml ps backend | grep -c 'Up' || echo '0'")
FRONTEND_STATUS=$(remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml ps frontend | grep -c 'Up' || echo '0'")

if [ "$BACKEND_STATUS" = "1" ] && [ "$FRONTEND_STATUS" = "1" ]; then
    log_success "Todos os containers estão rodando!"
else
    log_warn "Alguns containers podem não estar rodando corretamente"
    remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml ps"
fi

# 10. Teste de saúde
log_info "Testando endpoint de saúde..."
sleep 3
HEALTH_CHECK=$(remote_exec "curl -s http://localhost:8001/api/health | grep -c 'ok' || echo '0'")
if [ "$HEALTH_CHECK" = "1" ]; then
    log_success "Backend respondendo corretamente!"
else
    log_warn "Backend pode não estar respondendo. Verifique os logs."
fi

# 11. Logs finais
echo ""
log_success "═══════════════════════════════════════════════"
log_success "           DEPLOY CONCLUÍDO COM SUCESSO!"
log_success "═══════════════════════════════════════════════"
echo ""
echo -e "${BLUE}📊 URLs do Projeto:${NC}"
echo "   Frontend: https://${DOMAIN}"
echo "   Backend:  https://${DOMAIN}/api/health"
echo ""
echo -e "${BLUE}🔍 Comandos Úteis:${NC}"
echo "   Ver logs backend:  ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs -f backend'"
echo "   Ver logs frontend: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml logs -f frontend'"
echo "   Status containers: ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml ps'"
echo "   Reiniciar tudo:    ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml restart'"
echo ""
echo -e "${YELLOW}⚠️  Próximos passos:${NC}"
echo "   1. Configure SSL/HTTPS no nginx (se ainda não tiver)"
echo "   2. Configure DNS para apontar ${DOMAIN} para ${SERVER_HOST}"
echo "   3. Teste o aplicativo em https://${DOMAIN}"
echo ""
