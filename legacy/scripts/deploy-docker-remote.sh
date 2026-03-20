#!/usr/bin/env bash
###############################################################################
# Deploy Remoto - Alça Finanças com Docker (Supabase)
# Script moderno para deploy via SSH usando Docker Compose
# Uso: ./scripts/deploy-docker-remote.sh [--debug]
###############################################################################

set -e

# Debug mode
DEBUG_MODE=false
if [ "$1" = "--debug" ] || [ "$1" = "-d" ]; then
    DEBUG_MODE=true
    set -x
fi

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
SERVER_PASSWORD="${SERVER_PASSWORD:-}"
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

# Configurar autenticação SSH
USE_SSHPASS=false
SSH_CMD="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$SERVER_SSH_KEY" ]; then
    # Usar chave SSH se fornecida
    log_info "Usando chave SSH para autenticação"
    SSH_CMD="$SSH_CMD -i $SERVER_SSH_KEY"
else
    # Pedir senha uma única vez
    if [ -z "$SERVER_PASSWORD" ]; then
        echo -e "${YELLOW}Chave SSH não configurada. Usando autenticação por senha.${NC}"
        read -sp "Digite a senha SSH para ${SERVER_USER}@${SERVER_HOST}: " SERVER_PASSWORD
        echo ""
    fi

    # Verificar se sshpass está instalado
    if ! command -v sshpass &> /dev/null; then
        log_warn "sshpass não encontrado. Instalando..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install hudochenkov/sshpass/sshpass 2>/dev/null || log_error "Instale sshpass: brew install hudochenkov/sshpass/sshpass"
            else
                log_error "Instale Homebrew ou sshpass manualmente"
            fi
        else
            sudo apt-get update -qq && sudo apt-get install -y -qq sshpass 2>/dev/null || log_error "Instale sshpass: sudo apt-get install sshpass"
        fi
    fi

    USE_SSHPASS=true
    SSH_CMD="sshpass -p '$SERVER_PASSWORD' $SSH_CMD"
fi

SSH_CMD="$SSH_CMD ${SERVER_USER}@${SERVER_HOST}"

# Função para executar comandos remotos (com output visível)
remote_exec() {
    if [ "$DEBUG_MODE" = true ]; then
        echo "[DEBUG] Executando: $1" >&2
    fi

    local output
    local exit_code

    output=$(eval "$SSH_CMD \"$1\"" 2>&1)
    exit_code=$?

    # Filtrar warnings SSH
    echo "$output" | grep -v "Warning: Permanently added" | grep -v "^$" || true

    if [ "$DEBUG_MODE" = true ]; then
        echo "[DEBUG] Exit code: $exit_code" >&2
    fi

    return $exit_code
}

# Função para executar comandos remotos silenciosos (para testes)
remote_exec_silent() {
    if [ "$DEBUG_MODE" = true ]; then
        echo "[DEBUG] Executando (silent): $1" >&2
    fi
    eval "$SSH_CMD \"$1\"" > /dev/null 2>&1
}

# Testar conexão
log_info "Testando conexão SSH..."
if ! remote_exec_silent "echo 'OK'"; then
    log_error "Não foi possível conectar ao servidor via SSH. Verifique credenciais."
fi
log_success "Conexão SSH estabelecida"

# 1. Verificar/Instalar dependências
log_info "Verificando dependências no servidor..."

echo -n "  → Verificando Docker... "
if remote_exec_silent "command -v docker"; then
    echo "✓ já instalado"
else
    echo "instalando..."
    remote_exec "curl -fsSL https://get.docker.com | sh" | tail -5
    log_success "Docker instalado"
fi

echo -n "  → Verificando Docker Compose... "
if remote_exec_silent "command -v docker-compose"; then
    echo "✓ já instalado"
else
    echo "instalando..."
    remote_exec "curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose"
    log_success "Docker Compose instalado"
fi

log_success "Docker e Docker Compose prontos"

# 2. Criar/atualizar diretório do projeto
log_info "Preparando diretório do projeto..."

echo "  → Criando diretório ${PROJECT_DIR}..."
if ! remote_exec "mkdir -p ${PROJECT_DIR}"; then
    log_error "Falha ao criar diretório ${PROJECT_DIR}"
fi
echo "  → Diretório pronto: ${PROJECT_DIR}"

echo "  → Verificando repositório Git..."
if remote_exec "test -d ${PROJECT_DIR}/.git && echo 'exists' || echo 'not_exists'" | grep -q "exists"; then
    echo "  → Repositório existe, atualizando..."
    echo "  → Executando: git fetch origin"
    if ! remote_exec "cd ${PROJECT_DIR} && git fetch origin 2>&1"; then
        log_error "Falha no git fetch"
    fi
    echo "  → Executando: git reset --hard origin/main"
    if ! remote_exec "cd ${PROJECT_DIR} && git reset --hard origin/main 2>&1"; then
        log_error "Falha no git reset"
    fi
else
    echo "  → Repositório não existe, clonando..."
    echo "  → Executando: git clone (pode demorar 1-2 min)"
    # Clonar direto no diretório atual (.) para evitar subpasta
    if ! remote_exec "cd ${PROJECT_DIR} && git clone https://github.com/Lezinrew/alca-financas.git . 2>&1"; then
        log_error "Falha ao clonar repositório"
    fi
fi

log_success "Código atualizado"

# 3. Configurar arquivo .env
log_info "Configurando arquivo .env no servidor..."

# Detectar credenciais Supabase do ambiente local
SUPABASE_URL_LOCAL="${SUPABASE_URL:-}"
SUPABASE_SERVICE_ROLE_KEY_LOCAL="${SUPABASE_SERVICE_ROLE_KEY:-}"
SUPABASE_ANON_KEY_LOCAL="${SUPABASE_ANON_KEY:-}"
VITE_SUPABASE_URL_LOCAL="${VITE_SUPABASE_URL:-}"
VITE_SUPABASE_ANON_KEY_LOCAL="${VITE_SUPABASE_ANON_KEY:-}"

# Se não estiver no environment, tentar ler do .env local
if [ -z "$SUPABASE_URL_LOCAL" ] && [ -f ".env" ]; then
    log_info "Lendo credenciais do arquivo .env local..."
    SUPABASE_URL_LOCAL=$(grep "^SUPABASE_URL=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    SUPABASE_SERVICE_ROLE_KEY_LOCAL=$(grep "^SUPABASE_SERVICE_ROLE_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    SUPABASE_ANON_KEY_LOCAL=$(grep "^SUPABASE_ANON_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    VITE_SUPABASE_URL_LOCAL=$(grep "^VITE_SUPABASE_URL=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    VITE_SUPABASE_ANON_KEY_LOCAL=$(grep "^VITE_SUPABASE_ANON_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
fi

# Usar VITE vars como fallback se as principais não existirem
SUPABASE_URL_LOCAL="${SUPABASE_URL_LOCAL:-$VITE_SUPABASE_URL_LOCAL}"
SUPABASE_ANON_KEY_LOCAL="${SUPABASE_ANON_KEY_LOCAL:-$VITE_SUPABASE_ANON_KEY_LOCAL}"

# Verificar se encontrou credenciais
if [ -n "$SUPABASE_URL_LOCAL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY_LOCAL" ]; then
    log_success "Credenciais Supabase detectadas localmente!"
    log_info "  URL: ${SUPABASE_URL_LOCAL}"

    # Gerar secrets seguros
    SECRET_KEY_GEN=$(openssl rand -hex 32 2>/dev/null || echo "CHANGE_ME_$(date +%s)")
    JWT_SECRET_GEN=$(openssl rand -hex 32 2>/dev/null || echo "CHANGE_ME_JWT_$(date +%s)")

    # Criar .env no servidor com credenciais detectadas
    log_info "Criando .env no servidor com suas credenciais..."
    remote_exec "cat > ${PROJECT_DIR}/.env << 'ENVEOF'
# Supabase
SUPABASE_URL=${SUPABASE_URL_LOCAL}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY_LOCAL}
${SUPABASE_ANON_KEY_LOCAL:+SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY_LOCAL}}

# Backend
SECRET_KEY=${SECRET_KEY_GEN}
JWT_SECRET=${JWT_SECRET_GEN}
BACKEND_PORT=8001
FLASK_ENV=production
HOST=0.0.0.0

# CORS
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

# Frontend Build
VITE_API_URL=https://${DOMAIN}
VITE_SUPABASE_URL=${SUPABASE_URL_LOCAL}
${SUPABASE_ANON_KEY_LOCAL:+VITE_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY_LOCAL}}
ENVEOF
"
    log_success "Arquivo .env criado com suas credenciais!"

elif ! remote_exec "test -f ${PROJECT_DIR}/.env"; then
    # Não encontrou credenciais locais e .env remoto não existe
    log_warn "Credenciais Supabase não encontradas no ambiente local!"
    log_warn "Criando .env template no servidor..."

    SECRET_KEY_GEN=$(openssl rand -hex 32 2>/dev/null || echo "CHANGE_ME_$(date +%s)")
    JWT_SECRET_GEN=$(openssl rand -hex 32 2>/dev/null || echo "CHANGE_ME_JWT_$(date +%s)")

    remote_exec "cat > ${PROJECT_DIR}/.env << 'ENVEOF'
# Supabase (CONFIGURE ESTAS VARIÁVEIS!)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend
SECRET_KEY=${SECRET_KEY_GEN}
JWT_SECRET=${JWT_SECRET_GEN}
BACKEND_PORT=8001
FLASK_ENV=production
HOST=0.0.0.0

# CORS
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

# Frontend Build
VITE_API_URL=https://${DOMAIN}
VITE_SUPABASE_URL=https://seu-projeto.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
ENVEOF
"

    log_error "Configure o arquivo ${PROJECT_DIR}/.env com suas credenciais Supabase!

Para definir credenciais localmente antes de rodar o script:
  export SUPABASE_URL='https://seu-projeto.supabase.co'
  export SUPABASE_SERVICE_ROLE_KEY='eyJ...'
  export SUPABASE_ANON_KEY='eyJ...'

Ou crie um arquivo .env na raiz do projeto com essas variáveis."
else
    log_success "Arquivo .env já existe no servidor"
fi

# 4. Build do frontend com configurações de produção
log_info "Fazendo build do frontend..."
echo "  → Criando diretório build/frontend..."
remote_exec "cd ${PROJECT_DIR} && mkdir -p build/frontend"
echo "  → Iniciando build do frontend (pode demorar 2-3 minutos)..."
echo "  → Executando: npm install && npm run build"
if remote_exec "cd ${PROJECT_DIR} && \
    docker run --rm \
        -v ${PROJECT_DIR}/frontend:/app \
        -v ${PROJECT_DIR}/build/frontend:/app/dist \
        -w /app \
        -e VITE_API_URL=https://${DOMAIN} \
        -e VITE_SUPABASE_URL=${SUPABASE_URL_LOCAL} \
        -e VITE_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY_LOCAL} \
        node:20-alpine sh -c 'npm install --quiet && npm run build' 2>&1"; then
    log_success "Frontend buildado"
else
    log_error "Falha no build do frontend"
fi

# 5. Build das imagens Docker
log_info "Construindo imagens Docker..."
echo "  → Building backend image..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml build backend" 2>&1 | grep -E '(Step|Successfully|ERROR|error)' | tail -10 || true
echo "  → Building frontend image..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml build frontend" 2>&1 | grep -E '(Step|Successfully|ERROR|error)' | tail -10 || true
log_success "Imagens construídas"

# 6. Parar containers antigos
log_info "Parando containers antigos..."
echo "  → Executando docker-compose down..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml down --remove-orphans 2>&1" || echo "  → Nenhum container rodando"

echo "  → Limpando containers órfãos..."
remote_exec "docker ps -a --filter 'name=alca-financas' --format '{{.ID}}' | xargs -r docker rm -f 2>&1" || true

echo "  → Verificando porta 8001..."
remote_exec "lsof -ti:8001 | xargs -r kill -9 2>&1" || true
remote_exec "fuser -k 8001/tcp 2>&1" || echo "  → Porta 8001 livre"

echo "  → Verificando porta 80..."
remote_exec "lsof -ti:80 | xargs -r kill -9 2>&1" || true
remote_exec "fuser -k 80/tcp 2>&1" || echo "  → Porta 80 livre"

# 7. Iniciar containers
log_info "Iniciando containers..."
echo "  → Executando docker-compose up -d..."
remote_exec "cd ${PROJECT_DIR} && docker-compose -f docker-compose.prod.yml up -d 2>&1"
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
