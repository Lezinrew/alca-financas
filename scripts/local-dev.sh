#!/bin/bash
# ================================================================
# Local Development Script - Alça Finanças
# ================================================================
# Uso: ./scripts/local-dev.sh [start|stop|restart|logs|status]
# ================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

COMMAND=${1:-start}

case "$COMMAND" in
  start)
    log_info "🚀 Iniciando ambiente de desenvolvimento..."

    # Verificar .env
    if [[ ! -f .env ]]; then
      log_warning "Arquivo .env não encontrado! Copiando .env.example..."
      cp .env.example .env
      log_info "Configure o arquivo .env antes de continuar"
      exit 1
    fi

    # Verificar variáveis críticas
    if ! grep -q "SUPABASE_URL=" .env || ! grep -q "SUPABASE_SERVICE_ROLE_KEY=" .env; then
      log_warning "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env!"
    fi

    # Verificar se OpenClaw está configurado
    if ! grep -q "OPENCLAW_GATEWAY_TOKEN=" .env || [ -z "$(grep OPENCLAW_GATEWAY_TOKEN= .env | cut -d'=' -f2)" ]; then
      log_warning "⚠️  OPENCLAW_GATEWAY_TOKEN não configurado - OpenClaw será desabilitado"
      log_info "Para gerar token: openssl rand -hex 32"
    fi

    # Iniciar serviços
    log_info "🐳 Subindo containers..."
    docker compose up -d

    # Aguardar serviços ficarem saudáveis
    log_info "⏳ Aguardando serviços iniciarem (30s)..."
    sleep 15

    # Verificar health
    log_info "🔍 Verificando health dos serviços..."
    docker compose ps

    # Health check backend
    if curl -f -s http://localhost:8001/api/health > /dev/null 2>&1; then
      log_success "✅ Backend saudável"
    else
      log_warning "⚠️  Backend ainda inicializando ou com erro"
    fi

    # Health check frontend
    if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
      log_success "✅ Frontend saudável"
    else
      log_warning "⚠️  Frontend ainda inicializando ou com erro"
    fi

    echo ""
    log_success "✅ Ambiente iniciado!"
    echo ""
    echo "Acesse:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8001"
    echo "  Health:   http://localhost:8001/api/health"
    echo ""
    echo "Comandos úteis:"
    echo "  Ver logs:       ./scripts/local-dev.sh logs"
    echo "  Ver logs erro:  ./scripts/local-dev.sh logs | grep -i error"
    echo "  Status:         ./scripts/local-dev.sh status"
    echo "  Parar:          ./scripts/local-dev.sh stop"
    echo "  Rebuild:        ./scripts/local-dev.sh rebuild"
    ;;

  stop)
    log_info "⏹️  Parando ambiente..."
    docker compose down
    log_success "✅ Ambiente parado"
    ;;

  restart)
    log_info "🔄 Reiniciando ambiente..."
    docker compose restart
    log_success "✅ Ambiente reiniciado"
    ;;

  logs)
    log_info "📋 Exibindo logs (Ctrl+C para sair)..."
    docker compose logs -f
    ;;

  status)
    log_info "📊 Status dos serviços:"
    docker compose ps
    ;;

  rebuild)
    log_info "🔨 Rebuilding containers..."
    docker compose down
    docker compose build
    docker compose up -d
    log_success "✅ Rebuild completo"
    ;;

  clean)
    log_warning "🧹 Limpando containers, volumes e builds..."
    read -p "Isso apagará TODOS os dados locais. Continuar? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose down -v
      rm -rf frontend/dist build/frontend frontend/node_modules backend/__pycache__ backend/.pytest_cache
      log_success "✅ Limpeza completa"
    else
      log_info "Limpeza cancelada"
    fi
    ;;

  *)
    echo "Uso: ./scripts/local-dev.sh [start|stop|restart|logs|status|rebuild|clean]"
    echo ""
    echo "Comandos:"
    echo "  start    - Iniciar ambiente de desenvolvimento"
    echo "  stop     - Parar ambiente"
    echo "  restart  - Reiniciar serviços"
    echo "  logs     - Ver logs em tempo real"
    echo "  status   - Ver status dos containers"
    echo "  rebuild  - Rebuild completo (down + build + up)"
    echo "  clean    - Limpar tudo (containers + volumes + builds)"
    exit 1
    ;;
esac
