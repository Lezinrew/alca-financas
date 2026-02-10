#!/usr/bin/env bash
# ================================
# DEV DOWN - Alça Finanças
# ================================
# Stops all development services

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🛑 Alça Finanças - Stopping Development Environment${NC}"
echo ""

STOPPED_COUNT=0

# ================================
# Stop Services via PID Files
# ================================
echo -e "${YELLOW}==> Stopping services...${NC}"

for pidfile in .backend.pid .frontend.pid .mobile.pid; do
    if [ -f "$REPO_DIR/$pidfile" ]; then
        PID=$(cat "$REPO_DIR/$pidfile")
        SERVICE_NAME=$(basename "$pidfile" .pid)

        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "  🛑 Stopping ${SERVICE_NAME} (PID: $PID)"
            kill "$PID" 2>/dev/null || true

            # Wait for graceful shutdown
            for i in {1..5}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done

            # Force kill if still running
            if ps -p "$PID" > /dev/null 2>&1; then
                echo -e "  ⚠️  Force killing ${SERVICE_NAME}"
                kill -9 "$PID" 2>/dev/null || true
            fi

            STOPPED_COUNT=$((STOPPED_COUNT + 1))
        fi

        rm -f "$REPO_DIR/$pidfile"
    fi
done

# ================================
# Free Ports (Fallback)
# ================================
echo ""
echo -e "${YELLOW}==> Checking ports...${NC}"

# Load env to get port numbers
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env" 2>/dev/null || true
    set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

for PORT in "$BACKEND_PORT" "$FRONTEND_PORT" 5173; do
    PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "  🛑 Freeing port $PORT"
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
        STOPPED_COUNT=$((STOPPED_COUNT + 1))
    fi
done

# ================================
# Summary
# ================================
echo ""
if [ $STOPPED_COUNT -gt 0 ]; then
    echo -e "${GREEN}✅ Stopped $STOPPED_COUNT service(s)${NC}"
else
    echo -e "${YELLOW}ℹ️  No services were running${NC}"
fi

echo ""
echo -e "${BLUE}💡 To start again:${NC}"
echo -e "   ${YELLOW}./scripts/dev/up.sh${NC}"
echo ""
