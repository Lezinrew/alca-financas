#!/bin/bash
# ================================================================
# Script de Correção - Ambiente Local
# ================================================================
# Aplica correções para problemas:
# 1. Frontend npm not found
# 2. OpenClaw Invalid --bind
# 3. Melhorias de healthcheck e robustez
# ================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ================================================================
# VERIFICAÇÕES
# ================================================================

log_info "🔍 Verificando ambiente..."

# Verificar se está na raiz
if [[ ! -f "docker-compose.yml" ]]; then
  log_error "Execute este script da raiz do projeto!"
  exit 1
fi

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
  log_error "Docker não está rodando! Inicie o Docker primeiro."
  exit 1
fi

log_success "Verificações OK"

# ================================================================
# PARAR AMBIENTE ATUAL
# ================================================================

log_info "🛑 Parando ambiente atual..."

docker compose down 2>/dev/null || true

log_success "Ambiente parado"

# ================================================================
# VERIFICAR SE CORREÇÕES JÁ FORAM APLICADAS
# ================================================================

log_info "📋 Verificando correções..."

NEEDS_FIX=0

# Verificar Dockerfile.dev
if [[ ! -f "frontend/Dockerfile.dev" ]]; then
  log_warning "  ⚠️  frontend/Dockerfile.dev não encontrado (será criado)"
  NEEDS_FIX=1
else
  log_success "  ✓ frontend/Dockerfile.dev existe"
fi

# Verificar se docker-compose.yml foi atualizado
if grep -q "dockerfile: Dockerfile.dev" docker-compose.yml; then
  log_success "  ✓ docker-compose.yml usa Dockerfile.dev"
else
  log_warning "  ⚠️  docker-compose.yml precisa ser atualizado"
  NEEDS_FIX=1
fi

# Verificar openclaw bind
if grep -q 'OPENCLAW_GATEWAY_BIND: "lan"' docker-compose.yml; then
  log_success "  ✓ OpenClaw bind configurado corretamente"
else
  log_warning "  ⚠️  OpenClaw bind precisa ser corrigido"
  NEEDS_FIX=1
fi

if [[ $NEEDS_FIX -eq 0 ]]; then
  log_info "✅ Todas correções já aplicadas!"
  echo ""
  log_info "Reconstruindo ambiente com as correções..."
else
  log_error "❌ Algumas correções ainda não foram aplicadas"
  echo ""
  log_info "Por favor, aplique as correções primeiro:"
  echo "  1. Criar frontend/Dockerfile.dev"
  echo "  2. Atualizar docker-compose.yml"
  echo ""
  log_info "Ou siga o arquivo LOCAL-DEV-TROUBLESHOOTING.md"
  exit 1
fi

# ================================================================
# REBUILD COMPLETO
# ================================================================

log_info "🔨 Rebuilding containers..."

# Remove imagens antigas
log_info "  Removendo imagens antigas..."
docker compose down --rmi local 2>/dev/null || true

# Build com cache limpo para garantir mudanças
log_info "  Building imagens (pode demorar alguns minutos)..."
docker compose build --no-cache

log_success "Build completo"

# ================================================================
# VERIFICAR .ENV
# ================================================================

log_info "📄 Verificando arquivo .env..."

if [[ ! -f ".env" ]]; then
  log_warning "  ⚠️  Arquivo .env não encontrado"
  if [[ -f ".env.example" ]]; then
    log_info "  Copiando .env.example → .env"
    cp .env.example .env
    log_warning "  ⚠️  Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env!"
  else
    log_error "  ❌ .env.example também não encontrado!"
    log_info "  Crie arquivo .env com as variáveis necessárias"
    exit 1
  fi
fi

# Verificar variáveis críticas
if ! grep -q "SUPABASE_URL=" .env || ! grep -q "SUPABASE_SERVICE_ROLE_KEY=" .env; then
  log_warning "  ⚠️  Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env!"
fi

# Verificar OpenClaw token
if ! grep -q "OPENCLAW_GATEWAY_TOKEN=" .env || [ -z "$(grep OPENCLAW_GATEWAY_TOKEN= .env | cut -d'=' -f2)" ]; then
  log_warning "  ⚠️  OPENCLAW_GATEWAY_TOKEN não configurado"
  log_info "  Para gerar token: openssl rand -hex 32"
  log_info "  Adicione ao .env: OPENCLAW_GATEWAY_TOKEN=<seu-token>"
fi

# ================================================================
# SUBIR AMBIENTE
# ================================================================

log_info "🚀 Iniciando ambiente corrigido..."

docker compose up -d

log_info "⏳ Aguardando serviços inicializarem (30s)..."
sleep 30

# ================================================================
# VALIDAÇÕES
# ================================================================

log_info "🔍 Validando ambiente..."

echo ""
echo "╔════════════════════════════════════════╗"
echo "║     VALIDAÇÃO DO AMBIENTE LOCAL        ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Status dos containers
log_info "1️⃣  Status dos containers:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""

# Health check backend
log_info "2️⃣  Backend health check:"
if curl -f -s http://localhost:8001/api/health > /dev/null 2>&1; then
  log_success "  ✅ Backend está saudável"
  curl -s http://localhost:8001/api/health | head -1
else
  log_warning "  ⚠️  Backend ainda inicializando ou com erro"
  log_info "  Verificar logs: docker compose logs backend"
fi

echo ""

# Health check frontend
log_info "3️⃣  Frontend health check:"
if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
  log_success "  ✅ Frontend está acessível"
else
  log_warning "  ⚠️  Frontend ainda inicializando ou com erro"
  log_info "  Verificar logs: docker compose logs frontend"
fi

echo ""

# Verificar logs de erro
log_info "4️⃣  Verificando logs recentes por erros..."
ERROR_COUNT=$(docker compose logs --tail=100 2>&1 | grep -i "error\|fatal\|crash" | grep -v "healthcheck" | wc -l)
if [[ $ERROR_COUNT -eq 0 ]]; then
  log_success "  ✅ Nenhum erro crítico nos logs recentes"
else
  log_warning "  ⚠️  Encontrados $ERROR_COUNT erros nos logs"
  log_info "  Ver logs: ./scripts/local-dev.sh logs | grep -i error"
fi

# ================================================================
# RESULTADO FINAL
# ================================================================

echo ""
echo "========================================="
log_success "✅ AMBIENTE LOCAL CORRIGIDO"
echo "========================================="
echo ""
log_info "Acesse:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8001"
echo "  Health:   http://localhost:8001/api/health"
echo ""
log_info "Comandos úteis:"
echo "  Ver logs:       ./scripts/local-dev.sh logs"
echo "  Status:         ./scripts/local-dev.sh status"
echo "  Parar:          ./scripts/local-dev.sh stop"
echo "  Troubleshoot:   cat LOCAL-DEV-TROUBLESHOOTING.md"
echo ""
log_warning "📖 Leia LOCAL-DEV-TROUBLESHOOTING.md para detalhes das correções"
echo ""
