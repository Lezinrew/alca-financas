#!/usr/bin/env bash
# ================================
# DEV UP - Alça Finanças
# ================================
# Starts backend and frontend development servers

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
MOBILE_DIR="$REPO_DIR/mobile"

# Parse flags
BACKEND_ONLY=false
FRONTEND_ONLY=false
MOBILE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            shift
            ;;
        --mobile)
            MOBILE_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--backend-only|--frontend-only|--mobile]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🚀 Alça Finanças - Starting Development Environment${NC}"
echo ""

# ================================
# Load Environment Variables
# ================================
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
    echo -e "${GREEN}✅ Loaded .env${NC}"
else
    echo -e "${RED}❌ .env file not found${NC}"
    echo -e "${YELLOW}   Run: ./scripts/dev/setup.sh${NC}"
    exit 1
fi

# Validação: fluxo ativo exige Supabase JWT + SECRET_KEY (sem default silencioso de JWT_SECRET legado)
if [ -z "${SUPABASE_JWT_SECRET:-}" ] || [ "$SUPABASE_JWT_SECRET" = "your-supabase-jwt-secret-min-32-chars" ]; then
    echo -e "${RED}❌ SUPABASE_JWT_SECRET ausente ou ainda com placeholder do .env.example.${NC}"
    echo -e "${YELLOW}   Defina SUPABASE_JWT_SECRET no .env (Supabase → Project Settings → API → JWT Secret).${NC}"
    exit 1
fi

if [ -z "${SECRET_KEY:-}" ] || [ "$SECRET_KEY" = "your-flask-secret-key-min-32-chars" ]; then
    echo -e "${RED}❌ SECRET_KEY ausente ou ainda com placeholder do .env.example.${NC}"
    echo -e "${YELLOW}   Gere com: openssl rand -hex 32 e defina SECRET_KEY no .env${NC}"
    exit 1
fi

# Set defaults
export BACKEND_PORT="${BACKEND_PORT:-8001}"
export FRONTEND_PORT="${FRONTEND_PORT:-3000}"
export HOST="${HOST:-0.0.0.0}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000}"

# ================================
# Stop Existing Services
# ================================
echo -e "${YELLOW}==> Stopping existing services...${NC}"

# Stop via PIDs
for pidfile in .backend.pid .frontend.pid .mobile.pid; do
    if [ -f "$REPO_DIR/$pidfile" ]; then
        PID=$(cat "$REPO_DIR/$pidfile")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "  🛑 Stopping $(basename $pidfile .pid) (PID: $PID)"
            kill "$PID" 2>/dev/null || true
        fi
        rm -f "$REPO_DIR/$pidfile"
    fi
done

# Free ports
echo "  🔍 Checking ports..."
for PORT in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  🛑 Freeing port $PORT"
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
    fi
done

sleep 1
echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

# ================================
# Setup Logs
# ================================
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
BACKEND_LOG="$LOG_DIR/backend-$TS.log"
FRONTEND_LOG="$LOG_DIR/frontend-$TS.log"
MOBILE_LOG="$LOG_DIR/mobile-$TS.log"

# ================================
# Start Backend
# ================================
if [ "$FRONTEND_ONLY" = false ]; then
    echo -e "${BLUE}==> Starting backend (Flask)...${NC}"

    cd "$BACKEND_DIR"

    # Check venv
    if [ ! -d ".venv" ]; then
        echo -e "${RED}❌ Backend virtual environment not found${NC}"
        echo -e "${YELLOW}   Run: ./scripts/dev/setup.sh${NC}"
        exit 1
    fi

    # Activate venv and start
    source .venv/bin/activate

    # Export variables for backend
    export PORT="$BACKEND_PORT"

    nohup python app.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$REPO_DIR/.backend.pid"

    echo -e "  ${GREEN}✅ Backend starting (PID: $BACKEND_PID)${NC}"
    echo -e "  📝 Log: $BACKEND_LOG"

    # Wait for backend health
    echo -n "  ⏳ Waiting for backend to be ready"
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
        exit 1
    fi

    echo -e "  🌐 Backend: ${YELLOW}http://localhost:$BACKEND_PORT${NC}"
    echo ""
fi

# ================================
# Start Frontend
# ================================
if [ "$BACKEND_ONLY" = false ] && [ "$MOBILE_ONLY" = false ]; then
    echo -e "${BLUE}==> Starting frontend (Vite)...${NC}"

    cd "$FRONTEND_DIR"

    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${RED}❌ Frontend dependencies not installed${NC}"
        echo -e "${YELLOW}   Run: ./scripts/dev/setup.sh${NC}"
        exit 1
    fi

    # Create frontend .env
    cat > "$FRONTEND_DIR/.env" << EOF
# Auto-generated by scripts/dev/up.sh
VITE_API_URL=http://localhost:$BACKEND_PORT
EOF

    # Start frontend
    export PORT="$FRONTEND_PORT"

    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$REPO_DIR/.frontend.pid"

    echo -e "  ${GREEN}✅ Frontend starting (PID: $FRONTEND_PID)${NC}"
    echo -e "  📝 Log: $FRONTEND_LOG"

    # Wait for frontend
    echo -n "  ⏳ Waiting for frontend to be ready"
    for i in {1..40}; do
        if curl -sS "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
            echo " - ${GREEN}ready!${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done

    if ! curl -sS "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
        echo ""
        echo -e "  ${YELLOW}⚠️  Frontend may still be starting...${NC}"
        echo -e "  ${YELLOW}📋 Check log: $FRONTEND_LOG${NC}"
    else
        echo -e "  🌐 Frontend: ${YELLOW}http://localhost:$FRONTEND_PORT${NC}"
    fi

    echo ""
fi

# ================================
# Start Mobile (Optional)
# ================================
if [ "$MOBILE_ONLY" = true ] && [ -d "$MOBILE_DIR" ]; then
    echo -e "${BLUE}==> Starting mobile (Expo)...${NC}"

    cd "$MOBILE_DIR"

    if [ ! -d "node_modules" ]; then
        echo -e "${RED}❌ Mobile dependencies not installed${NC}"
        echo -e "${YELLOW}   Run: ./scripts/dev/setup.sh${NC}"
        exit 1
    fi

    nohup npm start > "$MOBILE_LOG" 2>&1 &
    MOBILE_PID=$!
    echo $MOBILE_PID > "$REPO_DIR/.mobile.pid"

    echo -e "  ${GREEN}✅ Mobile starting (PID: $MOBILE_PID)${NC}"
    echo -e "  📝 Log: $MOBILE_LOG"
    echo ""
fi

# ================================
# Cleanup Handler
# ================================
cleanup() {
    echo ""
    echo -e "${YELLOW}==> Shutting down...${NC}"
    for pidfile in .backend.pid .frontend.pid .mobile.pid; do
        if [ -f "$REPO_DIR/$pidfile" ]; then
            PID=$(cat "$REPO_DIR/$pidfile")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
            fi
            rm -f "$REPO_DIR/$pidfile"
        fi
    done
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# ================================
# Summary
# ================================
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Development Environment Running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 Services:${NC}"
if [ "$FRONTEND_ONLY" = false ]; then
    echo -e "   🔧 Backend:  ${YELLOW}http://localhost:$BACKEND_PORT${NC}"
fi
if [ "$BACKEND_ONLY" = false ] && [ "$MOBILE_ONLY" = false ]; then
    echo -e "   🌐 Frontend: ${YELLOW}http://localhost:$FRONTEND_PORT${NC}"
fi
if [ "$MOBILE_ONLY" = true ]; then
    echo -e "   📱 Mobile:   ${YELLOW}Check terminal output${NC}"
fi
echo ""
echo -e "${BLUE}🛠️  Commands:${NC}"
echo -e "   Stop:   ${YELLOW}./scripts/dev/down.sh${NC}"
echo -e "   Health: ${YELLOW}./scripts/dev/doctor.sh${NC}"
echo -e "   Logs:   ${YELLOW}tail -f logs/*.log${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop all services${NC}"
echo ""

# Follow logs
if [ "$FRONTEND_ONLY" = false ] && [ "$BACKEND_ONLY" = false ]; then
    tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG"
elif [ "$FRONTEND_ONLY" = true ]; then
    tail -n +1 -f "$FRONTEND_LOG"
elif [ "$BACKEND_ONLY" = true ]; then
    tail -n +1 -f "$BACKEND_LOG"
elif [ "$MOBILE_ONLY" = true ]; then
    tail -n +1 -f "$MOBILE_LOG"
fi
