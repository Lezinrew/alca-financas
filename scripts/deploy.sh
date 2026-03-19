#!/bin/bash
# ================================================================
# Deploy Script - Alça Finanças
# ================================================================
# Uso: ./scripts/deploy.sh [environment]
# Environments: local, production
# ================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validate arguments
ENVIRONMENT=${1:-local}

if [[ ! "$ENVIRONMENT" =~ ^(local|production)$ ]]; then
  log_error "Ambiente inválido: $ENVIRONMENT"
  echo "Uso: ./scripts/deploy.sh [local|production]"
  exit 1
fi

log_info "🚀 Iniciando deploy para ambiente: $ENVIRONMENT"

# ================================================================
# LOCAL DEPLOYMENT (para testes locais com build de produção)
# ================================================================
if [[ "$ENVIRONMENT" == "local" ]]; then
  log_info "📦 Deploy local - Build completo de produção"

  # Verificar se .env existe
  if [[ ! -f .env ]]; then
    log_error "Arquivo .env não encontrado!"
    log_info "Copie .env.example para .env e configure"
    exit 1
  fi

  # Parar containers existentes
  log_info "⏹️  Parando containers existentes..."
  docker compose -f docker-compose.prod.yml down 2>/dev/null || true

  # Build backend
  log_info "🔨 Building backend..."
  docker compose -f docker-compose.prod.yml build backend

  # Build frontend
  log_info "🔨 Building frontend..."
  rm -rf frontend/dist build/frontend
  mkdir -p build/frontend

  log_info "📦 Instalando dependências do frontend..."
  docker run --rm \
    -v "$(pwd)/frontend:/app" \
    -w /app \
    node:22-alpine \
    sh -c "npm ci"

  log_info "🏗️  Compilando frontend..."
  docker run --rm \
    -v "$(pwd)/frontend:/app" \
    -w /app \
    node:22-alpine \
    sh -c "npm run build"

  log_info "📋 Copiando build para nginx..."
  cp -a frontend/dist/. build/frontend/

  # Verificar se build foi criado
  if [[ ! -f build/frontend/index.html ]]; then
    log_error "Build do frontend falhou! index.html não encontrado"
    exit 1
  fi

  # Iniciar serviços
  log_info "🚀 Iniciando serviços..."
  docker compose -f docker-compose.prod.yml up -d

  # Aguardar serviços ficarem prontos
  log_info "⏳ Aguardando serviços iniciarem..."
  sleep 5

  # Health checks
  log_info "🔍 Verificando saúde dos serviços..."

  # Check backend
  if curl -f -s http://localhost:8001/health > /dev/null 2>&1; then
    log_success "Backend: OK"
  else
    log_warning "Backend: health check falhou (pode estar inicializando)"
  fi

  # Check frontend
  if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
    log_success "Frontend: OK"
  else
    log_warning "Frontend: Não acessível"
  fi

  log_success "✅ Deploy local completo!"
  echo ""
  log_info "Acesse a aplicação:"
  echo "  Frontend: http://localhost:3000"
  echo "  Backend:  http://localhost:8001"
  echo ""
  log_info "Ver logs: docker compose -f docker-compose.prod.yml logs -f"
  log_info "Parar:    docker compose -f docker-compose.prod.yml down"

# ================================================================
# PRODUCTION DEPLOYMENT (no servidor via SSH)
# ================================================================
elif [[ "$ENVIRONMENT" == "production" ]]; then
  log_info "🏭 Deploy de produção via SSH"

  # Verificar variáveis de ambiente
  if [[ -z "$PROD_HOST" ]] || [[ -z "$PROD_USER" ]]; then
    log_error "Variáveis PROD_HOST e PROD_USER devem estar definidas!"
    echo ""
    echo "Configure em .env ou exporte:"
    echo "  export PROD_HOST='seu-servidor.com'"
    echo "  export PROD_USER='seu-usuario'"
    exit 1
  fi

  # Carregar .env se existir
  if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
  fi

  log_warning "⚠️  Deploy de produção - Confirme que os testes passaram!"
  read -p "Deseja continuar? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Deploy cancelado pelo usuário"
    exit 0
  fi

  # Get current commit
  CURRENT_COMMIT=$(git rev-parse HEAD)
  CURRENT_BRANCH=$(git branch --show-current)

  log_info "Branch: $CURRENT_BRANCH"
  log_info "Commit: $CURRENT_COMMIT"

  # Deploy no servidor
  log_info "🔗 Conectando ao servidor: $PROD_USER@$PROD_HOST"

  ssh "$PROD_USER@$PROD_HOST" << EOF
    set -e

    echo "📂 Navegando para /var/www/alca-financas"
    cd /var/www/alca-financas

    echo "📥 Fazendo pull das mudanças"
    git fetch origin
    git reset --hard $CURRENT_COMMIT
    git clean -fd

    echo "🔨 Building backend"
    docker compose -f docker-compose.prod.yml build backend

    echo "🚀 Reiniciando backend"
    docker compose -f docker-compose.prod.yml up -d backend

    echo "🔨 Building frontend"
    rm -rf frontend/dist build/frontend
    mkdir -p build/frontend

    docker run --rm \
      -v \$(pwd)/frontend:/app \
      -w /app \
      node:22-alpine \
      sh -c "npm ci && npm run build"

    cp -a frontend/dist/. build/frontend/

    echo "🚀 Reiniciando frontend"
    docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

    echo "✅ Deploy completo!"
    docker compose -f docker-compose.prod.yml ps
EOF

  log_success "✅ Deploy de produção concluído!"
  echo ""
  log_info "Verificar status:"
  echo "  ssh $PROD_USER@$PROD_HOST 'cd /var/www/alca-financas && docker compose -f docker-compose.prod.yml ps'"
  echo ""
  log_info "Ver logs:"
  echo "  ssh $PROD_USER@$PROD_HOST 'cd /var/www/alca-financas && docker compose -f docker-compose.prod.yml logs -f'"

fi

log_success "🎉 Deploy finalizado com sucesso!"
