#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BLUE}🛑 Parando Alça Finanças...${NC}"
echo ""

# Parar via PIDs
STOPPED_SERVICES=0

if [ -f "$REPO_DIR/.frontend.pid" ]; then
    PID=$(cat "$REPO_DIR/.frontend.pid")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "  🛑 Parando Frontend (PID: $PID)"
        kill "$PID" 2>/dev/null || true
        STOPPED_SERVICES=$((STOPPED_SERVICES + 1))
    fi
    rm -f "$REPO_DIR/.frontend.pid"
fi

if [ -f "$REPO_DIR/.backend.pid" ]; then
    PID=$(cat "$REPO_DIR/.backend.pid")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "  🛑 Parando Backend (PID: $PID)"
        kill "$PID" 2>/dev/null || true
        STOPPED_SERVICES=$((STOPPED_SERVICES + 1))
    fi
    rm -f "$REPO_DIR/.backend.pid"
fi

if [ -f "$REPO_DIR/.mongo_logs.pid" ]; then
    PID=$(cat "$REPO_DIR/.mongo_logs.pid")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID" 2>/dev/null || true
    fi
    rm -f "$REPO_DIR/.mongo_logs.pid"
fi

# Parar MongoDB Docker se existir e foi iniciado pelo script
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^alca_mongo$'; then
    echo "  🛑 Parando MongoDB (Docker)"
    docker stop alca_mongo > /dev/null 2>&1 || true
    STOPPED_SERVICES=$((STOPPED_SERVICES + 1))
fi

# Liberar portas se ainda estiverem ocupadas
echo "  🔍 Verificando portas..."
for PORT in 3000 5000 5173 8001; do
    PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  🛑 Liberando porta $PORT"
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
    fi
done

echo ""
if [ $STOPPED_SERVICES -gt 0 ]; then
    echo -e "${GREEN}✅ $STOPPED_SERVICES serviço(s) parado(s)${NC}"
else
    echo -e "${YELLOW}ℹ️  Nenhum serviço estava rodando${NC}"
fi
