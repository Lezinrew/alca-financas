#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"

cd "$BACKEND_DIR"

echo -e "${BLUE}🧪 Executando testes do Alça Finanças...${NC}"
echo ""

# Verificar se virtualenv existe
if [ ! -d .venv ]; then
    echo -e "${RED}❌ Virtualenv não encontrado. Execute ./alca_start_mac.sh primeiro.${NC}"
    exit 1
fi

# Ativar virtualenv
source .venv/bin/activate

# Verificar se pytest está instalado
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  pytest não encontrado. Instalando dependências de teste...${NC}"
    pip install pytest pytest-cov pytest-mock > /dev/null
fi

# Rodar testes com cobertura
echo -e "${BLUE}📊 Rodando testes com cobertura...${NC}"
echo ""

python3 -m pytest tests/ \
    --cov=. \
    --cov-report=term-missing:skip-covered \
    --cov-report=html \
    --cov-fail-under=70 \
    -v \
    "$@"

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Todos os testes passaram!${NC}"
    echo -e "${BLUE}📊 Relatório HTML: ${YELLOW}backend/htmlcov/index.html${NC}"
    echo ""
    echo "Para abrir o relatório:"
    echo "  open backend/htmlcov/index.html"
else
    echo -e "${RED}❌ Alguns testes falharam${NC}"
    exit $TEST_EXIT_CODE
fi
