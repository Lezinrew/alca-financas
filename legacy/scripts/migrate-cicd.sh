#!/bin/bash
# ================================================================
# Script de Migração CI/CD - Alça Finanças
# ================================================================
# Aplica mudanças de simplificação de workflows
# SEGURO: Faz backup antes de remover arquivos
# ================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ================================================================
# VALIDAÇÕES PRÉ-MIGRAÇÃO
# ================================================================

log_info "🔍 Validando ambiente..."

# Verificar se está na raiz do projeto
if [[ ! -f "CICD-GUIDE.md" ]]; then
  log_error "Execute este script da raiz do projeto!"
  exit 1
fi

# Verificar se novos workflows foram criados
if [[ ! -f ".github/workflows/deploy-dev.yml" ]]; then
  log_error "Arquivo deploy-dev.yml não encontrado! Execute a criação primeiro."
  exit 1
fi

if [[ ! -f ".github/workflows/deploy-prod.yml" ]]; then
  log_error "Arquivo deploy-prod.yml não encontrado! Execute a criação primeiro."
  exit 1
fi

log_success "Validação OK"

# ================================================================
# BACKUP
# ================================================================

BACKUP_DIR=".cicd-backup-$(date +%Y%m%d-%H%M%S)"
log_info "📦 Criando backup em: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR/.github/workflows"

# Backup workflows antigos
if [[ -f ".github/workflows/ci.yml" ]]; then
  cp ".github/workflows/ci.yml" "$BACKUP_DIR/.github/workflows/"
  log_info "  ✓ Backup: ci.yml"
fi

# Backup docker-compose.dev.yml
if [[ -f "docker-compose.dev.yml" ]]; then
  cp "docker-compose.dev.yml" "$BACKUP_DIR/"
  log_info "  ✓ Backup: docker-compose.dev.yml"
fi

log_success "Backup completo em: $BACKUP_DIR"

# ================================================================
# CONFIRMAR COM USUÁRIO
# ================================================================

echo ""
log_warning "⚠️  ATENÇÃO: Esta migração irá:"
echo "  1. Arquivar .github/workflows/ci.yml"
echo "  2. Remover docker-compose.dev.yml (redundante)"
echo "  3. Manter deploy-dev.yml e deploy-prod.yml ativos"
echo ""
echo "Backup foi criado em: $BACKUP_DIR"
echo ""
read -p "Deseja continuar? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  log_info "Migração cancelada pelo usuário"
  exit 0
fi

# ================================================================
# ARQUIVAR WORKFLOWS LEGADOS
# ================================================================

log_info "📝 Arquivando workflows legados..."

# Criar diretório de arquivo
mkdir -p ".github/workflows-archived"

# Mover ci.yml para arquivo
if [[ -f ".github/workflows/ci.yml" ]]; then
  mv ".github/workflows/ci.yml" ".github/workflows-archived/ci.yml.bak"
  log_success "  ✓ Arquivado: ci.yml → workflows-archived/ci.yml.bak"
fi

# ================================================================
# REMOVER ARQUIVOS REDUNDANTES
# ================================================================

log_info "🗑️  Removendo arquivos redundantes..."

if [[ -f "docker-compose.dev.yml" ]]; then
  rm "docker-compose.dev.yml"
  log_success "  ✓ Removido: docker-compose.dev.yml"
fi

# ================================================================
# VALIDAÇÃO PÓS-MIGRAÇÃO
# ================================================================

log_info "🔍 Validando resultado..."

# Verificar workflows ativos
ACTIVE_WORKFLOWS=$(ls -1 .github/workflows/*.yml 2>/dev/null | wc -l)
log_info "  Workflows ativos: $ACTIVE_WORKFLOWS"

# Listar workflows
echo ""
log_info "📋 Workflows atuais:"
ls -1 .github/workflows/*.yml | while read -r file; do
  echo "  ✓ $(basename "$file")"
done

echo ""
log_info "📋 Workflows arquivados:"
ls -1 .github/workflows-archived/*.bak 2>/dev/null | while read -r file; do
  echo "  📦 $(basename "$file")"
done || echo "  (nenhum)"

# ================================================================
# INSTRUÇÕES FINAIS
# ================================================================

echo ""
echo "========================================="
log_success "✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO"
echo "========================================="
echo ""
log_info "📝 Próximos passos:"
echo ""
echo "1. Revisar mudanças:"
echo "   git status"
echo ""
echo "2. Testar workflow DEV localmente:"
echo "   # Criar branch de teste"
echo "   git checkout -b test/cicd-migration"
echo "   git add ."
echo "   git commit -m 'ci: migrar para deploy-dev/deploy-prod workflows'"
echo "   git push origin test/cicd-migration"
echo "   # Criar PR para develop"
echo ""
echo "3. Validar no GitHub Actions:"
echo "   https://github.com/Lezinrew/alca-financas/actions"
echo ""
echo "4. Se tudo OK, mergear para develop e depois main"
echo ""
log_info "📖 Documentação completa: CICD-GUIDE.md"
echo ""
log_warning "⚠️  Backup disponível em: $BACKUP_DIR"
echo "   (pode remover após validação completa)"
echo ""
