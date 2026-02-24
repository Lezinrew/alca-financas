#!/usr/bin/env bash
# Deploy script para VPS Hostinger - alcahub.com.br
# Uso: ./scripts/deploy-vps.sh [backend|frontend|full]

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações
VPS_IP="${VPS_IP:-76.13.239.220}"  # Definir via environment ou pedir
VPS_USER="${VPS_USER:-alcaapp}"
DOMAIN="alcahub.cloud"
API_DOMAIN="api.alcahub.cloud"

# Função para imprimir mensagens
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Verificar se VPS_IP está definido
if [ -z "$VPS_IP" ]; then
    read -p "Digite o IP do VPS: " VPS_IP
    [ -z "$VPS_IP" ] && print_error "IP do VPS é obrigatório"
fi

# Função para deploy do backend
deploy_backend() {
    print_info "Iniciando deploy do backend..."

    # Fazer commit das alterações locais
    print_info "Fazendo commit das alterações..."
    if ! git diff --quiet; then
        ./scripts/git-commit-push.sh "deploy: Atualizações antes do deploy"
    fi

    # SSH e atualizar no servidor
    print_info "Conectando ao VPS e atualizando backend..."
    ssh ${VPS_USER}@${VPS_IP} << 'ENDSSH'
set -e
su - alcaapp << 'ENDSU'
cd alca-financas
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt --quiet
exit
ENDSU
sudo supervisorctl restart alca-backend
echo "Backend reiniciado com sucesso"
ENDSSH

    print_info "Backend deploy completo!"
    print_info "Testando: https://${API_DOMAIN}/api/health"
    sleep 3
    curl -s https://${API_DOMAIN}/api/health && echo
}

# Função para deploy do frontend
deploy_frontend() {
    print_info "Iniciando deploy do frontend..."

    # Build local
    print_info "Fazendo build do frontend..."
    cd frontend

    # Verificar se .env.production existe
    if [ ! -f .env.production ]; then
        print_warn "Arquivo .env.production não encontrado!"
        print_warn "⚠️ Crie um arquivo no caminho frontend/.env.production com suas chaves de API reais antes do build."
        print_warn "Exemplo do conteúdo:"
        echo "VITE_API_URL=https://${API_DOMAIN}"
        echo "VITE_SUPABASE_URL=https://<seu-projeto>.supabase.co"
        echo "VITE_SUPABASE_ANON_KEY=sb_publishable_..."
        exit 1
    fi

    npm install --silent
    npm run build

    # Upload para VPS
    print_info "Fazendo upload para VPS..."
    rsync -avz --delete dist/ ${VPS_USER}@${VPS_IP}:/var/www/${DOMAIN}/

    cd ..
    print_info "Frontend deploy completo!"
    print_info "Acesse: https://${DOMAIN}"
}

# Função para deploy completo
deploy_full() {
    print_info "Iniciando deploy completo (backend + frontend)..."
    deploy_backend
    echo
    deploy_frontend
    echo
    print_info "========================================="
    print_info "DEPLOY COMPLETO!"
    print_info "========================================="
    print_info "Frontend: https://${DOMAIN}"
    print_info "Backend:  https://${API_DOMAIN}/api/health"
    print_info "========================================="
}

# Parse de argumentos
case "${1:-full}" in
    backend)
        deploy_backend
        ;;
    frontend)
        deploy_frontend
        ;;
    full)
        deploy_full
        ;;
    *)
        echo "Uso: $0 [backend|frontend|full]"
        echo "  backend  - Deploy apenas do backend"
        echo "  frontend - Deploy apenas do frontend"
        echo "  full     - Deploy completo (padrão)"
        exit 1
        ;;
esac
