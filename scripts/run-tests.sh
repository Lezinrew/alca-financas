#!/bin/bash

###############################################################################
# Run Tests - Alça Finanças
# Script para executar todos os testes (unit, integration, e2e)
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
TEST_TYPE=${1:-all}
ENVIRONMENT=${2:-local}

echo -e "${BLUE}🧪 Executando testes do Alça Finanças${NC}"
echo -e "Tipo: ${YELLOW}$TEST_TYPE${NC}"
echo -e "Ambiente: ${YELLOW}$ENVIRONMENT${NC}"
echo ""

# Set environment
export NODE_ENV=$ENVIRONMENT
export TEST_ENV=$ENVIRONMENT

# Function to run backend tests
run_backend_tests() {
    echo -e "${BLUE}🔧 Executando testes do Backend...${NC}"
    cd backend

    # Activate venv
    # Activate venv
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}❌ Ambiente virtual não encontrado. Execute deploy-local.sh primeiro.${NC}"
        exit 1
    fi

    # Run tests
    if [ "$TEST_TYPE" = "unit" ] || [ "$TEST_TYPE" = "all" ]; then
        echo -e "${YELLOW}📝 Testes unitários e gerais...${NC}"
        # Run tests in tests/unit AND tests/test_*.py
        pytest tests/unit tests/test_*.py -v --cov=. --cov-report=term --cov-report=html
    fi

    if [ "$TEST_TYPE" = "integration" ] || [ "$TEST_TYPE" = "all" ]; then
        echo -e "${YELLOW}🔗 Testes de integração...${NC}"
        pytest tests/integration -v --cov=. --cov-report=term --cov-report=html
    fi

    cd ..
    echo -e "${GREEN}✅ Testes do Backend concluídos${NC}\n"
}

# Function to run frontend tests
run_frontend_tests() {
    echo -e "${BLUE}🎨 Executando testes do Frontend...${NC}"
    cd frontend

    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${RED}❌ node_modules não encontrado. Execute npm install primeiro.${NC}"
        exit 1
    fi

    # Run unit tests
    if [ "$TEST_TYPE" = "unit" ] || [ "$TEST_TYPE" = "all" ]; then
        echo -e "${YELLOW}📝 Testes unitários...${NC}"
        npm run test:run -- --coverage
    fi

    cd ..
    echo -e "${GREEN}✅ Testes do Frontend concluídos${NC}\n"
}

# Function to run E2E tests
run_e2e_tests() {
    echo -e "${BLUE}🌐 Executando testes E2E...${NC}"
    cd frontend

    # Install Playwright if needed
    if [ ! -d "node_modules/@playwright" ]; then
        echo -e "${YELLOW}📦 Instalando Playwright...${NC}"
        npx playwright install --with-deps
    fi

    # Run E2E tests
    echo -e "${YELLOW}🎭 Executando Playwright...${NC}"

    if [ "$ENVIRONMENT" = "production" ]; then
        export TEST_ENV=production
        npx playwright test --config=playwright.config.ts
    else
        export TEST_ENV=local
        # Start dev server in background
        npm run dev > /dev/null 2>&1 &
        DEV_PID=$!

        # Wait for server
        echo "⏳ Aguardando servidor de desenvolvimento..."
        sleep 5

        # Run tests
        npx playwright test --config=playwright.config.ts

        # Kill dev server
        kill $DEV_PID || true
    fi

    cd ..
    echo -e "${GREEN}✅ Testes E2E concluídos${NC}\n"
}

# Main execution
case $TEST_TYPE in
    unit)
        run_backend_tests
        run_frontend_tests
        ;;
    integration)
        run_backend_tests
        ;;
    e2e)
        run_e2e_tests
        ;;
    backend)
        run_backend_tests
        ;;
    frontend)
        run_frontend_tests
        ;;
    all)
        run_backend_tests
        run_frontend_tests
        run_e2e_tests
        ;;
    *)
        echo -e "${RED}❌ Tipo de teste inválido: $TEST_TYPE${NC}"
        echo "Uso: ./run-tests.sh [unit|integration|e2e|backend|frontend|all] [local|production]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Todos os testes concluídos com sucesso!${NC}"
echo ""
echo "📊 Relatórios de cobertura:"
echo "   Backend: backend/htmlcov/index.html"
echo "   Frontend: frontend/coverage/index.html"
echo ""
echo "🎭 Relatório Playwright:"
echo "   frontend/playwright-report/index.html"
echo ""
