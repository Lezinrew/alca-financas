#!/usr/bin/env bash
# ================================
# PROD RUN - Alça Finanças
# ================================
# Runs the application in production mode

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$REPO_DIR/build"
BACKEND_DIR="$BUILD_DIR/backend"
FRONTEND_DIR="$BUILD_DIR/frontend"

echo -e "${BLUE}🚀 Alça Finanças - Production Run${NC}"
echo ""

# ================================
# Check Build Exists
# ================================
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}❌ Build directory not found${NC}"
    echo -e "${YELLOW}   Run: ./scripts/prod/build.sh${NC}"
    exit 1
fi

# ================================
# Load Production Environment
# ================================
echo -e "${BLUE}==> Loading production environment...${NC}"

if [ -f "$REPO_DIR/.env.production" ]; then
    ENV_FILE="$REPO_DIR/.env.production"
    echo -e "${GREEN}✅ Using .env.production${NC}"
elif [ -f "$REPO_DIR/.env" ]; then
    ENV_FILE="$REPO_DIR/.env"
    echo -e "${YELLOW}⚠️  Using .env (consider creating .env.production)${NC}"
else
    echo -e "${RED}❌ No environment file found${NC}"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# ================================
# Validate Required Variables
# ================================
echo -e "${BLUE}==> Validating environment variables...${NC}"

REQUIRED_VARS=(
    "SUPABASE_URL"
    "SUPABASE_SERVICE_ROLE_KEY"
    "SECRET_KEY"
    "JWT_SECRET"
)

MISSING_VARS=()
PLACEHOLDER_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        MISSING_VARS+=("$var")
    elif [[ "${!var}" =~ (your-|change-|placeholder|dev-secret) ]]; then
        PLACEHOLDER_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Missing required variables:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "   - $var"
    done
    exit 1
fi

if [ ${#PLACEHOLDER_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Variables appear to be placeholders (UNSAFE for production):${NC}"
    for var in "${PLACEHOLDER_VARS[@]}"; do
        echo -e "   - $var = ${!var}"
    done
    echo ""
    echo -e "${YELLOW}💡 Generate secure secrets:${NC}"
    echo -e "   openssl rand -hex 32"
    exit 1
fi

echo -e "${GREEN}✅ Environment validated${NC}"
echo ""

# ================================
# Set Production Defaults
# ================================
export FLASK_ENV=production
export NODE_ENV=production
export BACKEND_PORT="${BACKEND_PORT:-8001}"
export HOST="${HOST:-0.0.0.0}"

# ================================
# Setup Backend
# ================================
echo -e "${BLUE}==> Setting up backend...${NC}"

cd "$BACKEND_DIR"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "  📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
source .venv/bin/activate
echo "  📦 Installing production dependencies..."

if [ -f "requirements.prod.txt" ]; then
    pip install -r requirements.prod.txt --quiet
else
    pip install -r requirements.txt --quiet
fi

echo -e "  ${GREEN}✅ Backend ready${NC}"
echo ""

# ================================
# Check Frontend Build
# ================================
echo -e "${BLUE}==> Checking frontend build...${NC}"

if [ ! -d "$FRONTEND_DIR" ] || [ -z "$(ls -A $FRONTEND_DIR)" ]; then
    echo -e "${RED}❌ Frontend build not found${NC}"
    echo -e "${YELLOW}   Run: ./scripts/prod/build.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Frontend build found${NC}"
echo ""

# ================================
# Detect Production Server
# ================================
echo -e "${BLUE}==> Selecting production server...${NC}"

USE_GUNICORN=false

if command -v gunicorn >/dev/null 2>&1; then
    USE_GUNICORN=true
    echo -e "${GREEN}✅ Will use gunicorn (production-grade)${NC}"
else
    echo -e "${YELLOW}⚠️  gunicorn not found, using Flask dev server${NC}"
    echo -e "${YELLOW}   For production, install gunicorn:${NC}"
    echo -e "      pip install gunicorn"
fi

echo ""

# ================================
# Start Backend
# ================================
echo -e "${BLUE}==> Starting backend...${NC}"

cd "$BACKEND_DIR"
source .venv/bin/activate

LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
BACKEND_LOG="$LOG_DIR/backend-prod-$TS.log"

if [ "$USE_GUNICORN" = true ]; then
    # Gunicorn production server
    echo "  🚀 Starting gunicorn..."
    gunicorn \
        --bind "$HOST:$BACKEND_PORT" \
        --workers 4 \
        --timeout 30 \
        --access-logfile "$LOG_DIR/access-$TS.log" \
        --error-logfile "$BACKEND_LOG" \
        --log-level info \
        --worker-class sync \
        "app:app" &
    BACKEND_PID=$!
else
    # Flask development server (not recommended for production)
    echo "  ⚠️  Starting Flask dev server..."
    export PORT="$BACKEND_PORT"
    python app.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
fi

echo $BACKEND_PID > "$REPO_DIR/.backend.prod.pid"

echo -e "  ${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo -e "  📝 Log: $BACKEND_LOG"

# Wait for backend health
echo -n "  ⏳ Waiting for backend"
for i in {1..30}; do
    if curl -sS "http://localhost:$BACKEND_PORT/api/health" 2>/dev/null | grep -q '"status"'; then
        echo " - ${GREEN}ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -sS "http://localhost:$BACKEND_PORT/api/health" 2>/dev/null | grep -q '"status"'; then
    echo ""
    echo -e "  ${RED}❌ Backend failed to start${NC}"
    echo -e "  ${YELLOW}📋 Last 20 lines of log:${NC}"
    tail -20 "$BACKEND_LOG" | sed 's/^/     /'
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""

# ================================
# Serve Frontend
# ================================
echo -e "${BLUE}==> Frontend serving options:${NC}"
echo ""
echo -e "${YELLOW}Option 1: Serve via backend (Flask static files)${NC}"
echo -e "   The backend can serve the frontend build at /"
echo -e "   Configure this in backend/app.py if not already set up"
echo ""
echo -e "${YELLOW}Option 2: Serve via nginx (recommended)${NC}"
echo -e "   Install nginx and configure:"
echo ""
echo -e "${BLUE}   server {${NC}"
echo -e "${BLUE}       listen 80;${NC}"
echo -e "${BLUE}       server_name your-domain.com;${NC}"
echo -e "${BLUE}${NC}"
echo -e "${BLUE}       # Frontend${NC}"
echo -e "${BLUE}       location / {${NC}"
echo -e "${BLUE}           root $FRONTEND_DIR;${NC}"
echo -e "${BLUE}           try_files \$uri \$uri/ /index.html;${NC}"
echo -e "${BLUE}       }${NC}"
echo -e "${BLUE}${NC}"
echo -e "${BLUE}       # Backend API${NC}"
echo -e "${BLUE}       location /api {${NC}"
echo -e "${BLUE}           proxy_pass http://localhost:$BACKEND_PORT;${NC}"
echo -e "${BLUE}           proxy_set_header Host \$host;${NC}"
echo -e "${BLUE}           proxy_set_header X-Real-IP \$remote_addr;${NC}"
echo -e "${BLUE}       }${NC}"
echo -e "${BLUE}   }${NC}"
echo ""
echo -e "${YELLOW}Option 3: Serve via Python http.server (testing only)${NC}"
read -p "Start a simple file server for frontend? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    FRONTEND_PORT="${FRONTEND_PORT:-3000}"
    cd "$FRONTEND_DIR"
    python3 -m http.server "$FRONTEND_PORT" > "$LOG_DIR/frontend-prod-$TS.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$REPO_DIR/.frontend.prod.pid"
    echo -e "${GREEN}✅ Frontend server started on port $FRONTEND_PORT${NC}"
    echo ""
fi

# ================================
# Cleanup Handler
# ================================
cleanup() {
    echo ""
    echo -e "${YELLOW}==> Shutting down...${NC}"
    if [ -f "$REPO_DIR/.backend.prod.pid" ]; then
        PID=$(cat "$REPO_DIR/.backend.prod.pid")
        kill "$PID" 2>/dev/null || true
        rm -f "$REPO_DIR/.backend.prod.pid"
    fi
    if [ -f "$REPO_DIR/.frontend.prod.pid" ]; then
        PID=$(cat "$REPO_DIR/.frontend.prod.pid")
        kill "$PID" 2>/dev/null || true
        rm -f "$REPO_DIR/.frontend.prod.pid"
    fi
    echo -e "${GREEN}✅ Shutdown complete${NC}"
}

trap cleanup EXIT INT TERM

# ================================
# Summary
# ================================
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Production Environment Running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 Services:${NC}"
echo -e "   🔧 Backend:  ${YELLOW}http://localhost:$BACKEND_PORT${NC}"
if [ -f "$REPO_DIR/.frontend.prod.pid" ]; then
    echo -e "   🌐 Frontend: ${YELLOW}http://localhost:${FRONTEND_PORT:-3000}${NC}"
fi
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "   Backend: ${YELLOW}$BACKEND_LOG${NC}"
echo ""
echo -e "${BLUE}🔧 Process IDs:${NC}"
echo -e "   Backend: ${YELLOW}$BACKEND_PID${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop${NC}"
echo ""

# Follow backend log
tail -n +1 -f "$BACKEND_LOG"
