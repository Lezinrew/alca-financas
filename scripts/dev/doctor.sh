#!/usr/bin/env bash
# ================================
# DEV DOCTOR - Alça Finanças
# ================================
# Validates development environment health

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🏥 Alça Finanças - Environment Health Check${NC}"
echo ""

ISSUES=0
WARNINGS=0

# ================================
# Check Environment File
# ================================
echo -e "${BLUE}[1/6] Environment Configuration${NC}"

if [ ! -f "$REPO_DIR/.env" ]; then
    echo -e "  ${RED}❌ .env file not found${NC}"
    ISSUES=$((ISSUES + 1))
else
    echo -e "  ${GREEN}✅ .env file exists${NC}"

    # Load and check variables
    set -a
    source "$REPO_DIR/.env" 2>/dev/null || true
    set +a

    # Check critical variables
    REQUIRED_VARS=(
        "SUPABASE_URL"
        "SUPABASE_SERVICE_ROLE_KEY"
        "SECRET_KEY"
    )

    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var:-}" ]; then
            echo -e "  ${RED}❌ $var not set${NC}"
            ISSUES=$((ISSUES + 1))
        else
            # Check if it's still a placeholder
            if [[ "${!var}" =~ (your-|change-|placeholder) ]]; then
                echo -e "  ${YELLOW}⚠️  $var appears to be a placeholder${NC}"
                WARNINGS=$((WARNINGS + 1))
            else
                echo -e "  ${GREEN}✅ $var is set${NC}"
            fi
        fi
    done

    # Check optional but recommended
    RECOMMENDED_VARS=("JWT_SECRET" "CORS_ORIGINS")
    for var in "${RECOMMENDED_VARS[@]}"; do
        if [ -z "${!var:-}" ]; then
            echo -e "  ${YELLOW}⚠️  $var not set (will use default)${NC}"
            WARNINGS=$((WARNINGS + 1))
        else
            echo -e "  ${GREEN}✅ $var is set${NC}"
        fi
    done
fi

echo ""

# ================================
# Check Dependencies
# ================================
echo -e "${BLUE}[2/6] Dependencies${NC}"

# Python
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "  ${RED}❌ python3 not found${NC}"
    ISSUES=$((ISSUES + 1))
else
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "  ${GREEN}✅ python3 $PYTHON_VERSION${NC}"
fi

# Node
if ! command -v node >/dev/null 2>&1; then
    echo -e "  ${RED}❌ node not found${NC}"
    ISSUES=$((ISSUES + 1))
else
    NODE_VERSION=$(node --version)
    echo -e "  ${GREEN}✅ node $NODE_VERSION${NC}"
fi

# Check backend venv
if [ -d "$REPO_DIR/backend/.venv" ]; then
    echo -e "  ${GREEN}✅ Backend virtual environment exists${NC}"
else
    echo -e "  ${YELLOW}⚠️  Backend virtual environment not found${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check frontend node_modules
if [ -d "$REPO_DIR/frontend/node_modules" ]; then
    echo -e "  ${GREEN}✅ Frontend dependencies installed${NC}"
else
    echo -e "  ${YELLOW}⚠️  Frontend dependencies not installed${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ================================
# Check Services Status
# ================================
echo -e "${BLUE}[3/6] Services Status${NC}"

# Get ports
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Check backend
if [ -f "$REPO_DIR/.backend.pid" ]; then
    BACKEND_PID=$(cat "$REPO_DIR/.backend.pid")
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Backend running (PID: $BACKEND_PID)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Backend PID file exists but process not running${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "  ${YELLOW}ℹ️  Backend not running${NC}"
fi

# Check frontend
if [ -f "$REPO_DIR/.frontend.pid" ]; then
    FRONTEND_PID=$(cat "$REPO_DIR/.frontend.pid")
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Frontend running (PID: $FRONTEND_PID)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Frontend PID file exists but process not running${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "  ${YELLOW}ℹ️  Frontend not running${NC}"
fi

echo ""

# ================================
# Check Backend Health Endpoint
# ================================
echo -e "${BLUE}[4/6] Backend Health${NC}"

if curl -sf "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    HEALTH_RESPONSE=$(curl -s "http://localhost:$BACKEND_PORT/api/health")
    echo -e "  ${GREEN}✅ Backend health endpoint responding${NC}"
    echo -e "     Response: $HEALTH_RESPONSE"
else
    echo -e "  ${RED}❌ Backend health endpoint not accessible${NC}"
    echo -e "     URL: http://localhost:$BACKEND_PORT/api/health"
    if [ -f "$REPO_DIR/.backend.pid" ]; then
        ISSUES=$((ISSUES + 1))
    else
        echo -e "     ${YELLOW}(Backend is not running)${NC}"
    fi
fi

echo ""

# ================================
# Check Frontend Accessibility
# ================================
echo -e "${BLUE}[5/6] Frontend Accessibility${NC}"

if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Frontend accessible at http://localhost:$FRONTEND_PORT${NC}"
else
    echo -e "  ${RED}❌ Frontend not accessible${NC}"
    echo -e "     URL: http://localhost:$FRONTEND_PORT"
    if [ -f "$REPO_DIR/.frontend.pid" ]; then
        ISSUES=$((ISSUES + 1))
    else
        echo -e "     ${YELLOW}(Frontend is not running)${NC}"
    fi
fi

echo ""

# ================================
# Check Supabase Connectivity
# ================================
echo -e "${BLUE}[6/6] Supabase Connectivity${NC}"

if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_ANON_KEY:-}" ]; then
    # Simple connectivity check
    if curl -sf "$SUPABASE_URL/rest/v1/" \
        -H "apikey: $SUPABASE_ANON_KEY" \
        -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
        >/dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Supabase is reachable${NC}"
        echo -e "     URL: $SUPABASE_URL"
    else
        echo -e "  ${RED}❌ Cannot reach Supabase${NC}"
        echo -e "     URL: $SUPABASE_URL"
        echo -e "     Check credentials and network connection"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "  ${YELLOW}⚠️  Supabase credentials not configured${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ================================
# Summary
# ================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ISSUES -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Environment is healthy.${NC}"
    EXIT_CODE=0
elif [ $ISSUES -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Health check complete with $WARNINGS warning(s)${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}❌ Health check failed with $ISSUES issue(s) and $WARNINGS warning(s)${NC}"
    EXIT_CODE=1
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $ISSUES -gt 0 ] || [ $WARNINGS -gt 0 ]; then
    echo -e "${BLUE}💡 Suggested Actions:${NC}"

    if [ $ISSUES -gt 0 ]; then
        echo -e "   ${YELLOW}1. Fix critical issues above${NC}"
    fi

    if [ $WARNINGS -gt 0 ]; then
        echo -e "   ${YELLOW}2. Review warnings and resolve if needed${NC}"
    fi

    if [ ! -d "$REPO_DIR/backend/.venv" ] || [ ! -d "$REPO_DIR/frontend/node_modules" ]; then
        echo -e "   ${YELLOW}3. Run setup: ./scripts/dev/setup.sh${NC}"
    fi

    if [ ! -f "$REPO_DIR/.backend.pid" ] && [ ! -f "$REPO_DIR/.frontend.pid" ]; then
        echo -e "   ${YELLOW}4. Start services: ./scripts/dev/up.sh${NC}"
    fi

    echo ""
fi

echo -e "${BLUE}📚 Documentation:${NC}"
echo -e "   ${YELLOW}docs/ENVIRONMENTS.md${NC} - Environment configuration guide"
echo -e "   ${YELLOW}README.md${NC} - Project overview"
echo ""

exit $EXIT_CODE
