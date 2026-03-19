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

    # Iniciar serviços
    docker compose up -d

    # Aguardar
    log_info "⏳ Aguardando serviços iniciarem..."
    sleep 5

    # Status
    docker compose ps

    log_success "✅ Ambiente iniciado!"
    echo ""
    echo "Acesse:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8001"
    echo ""
    echo "Ver logs:  ./scripts/local-dev.sh logs"
    echo "Parar:     ./scripts/local-dev.sh stop"
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
