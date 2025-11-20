
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
FRONTEND_DIR="$REPO_DIR/frontend"

# Logs com data/hora
TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend-$TS.log"
FRONTEND_LOG="$LOG_DIR/frontend-$TS.log"
MONGO_LOG="$LOG_DIR/mongo-$TS.log"

echo -e "${BLUE}🚀 Alça Finanças - Iniciando...${NC}"
echo ""

# Parar todos os serviços existentes primeiro
echo -e "${YELLOW}==> Parando serviços existentes...${NC}"

# Parar processos anteriores via PIDs salvos
if [ -f "$REPO_DIR/.frontend.pid" ]; then
    FPID=$(cat "$REPO_DIR/.frontend.pid")
    if ps -p "$FPID" > /dev/null 2>&1; then
        echo "  🛑 Parando Frontend (PID: $FPID)"
        kill "$FPID" 2>/dev/null || true
    fi
    rm -f "$REPO_DIR/.frontend.pid"
fi

if [ -f "$REPO_DIR/.backend.pid" ]; then
    BPID=$(cat "$REPO_DIR/.backend.pid")
    if ps -p "$BPID" > /dev/null 2>&1; then
        echo "  🛑 Parando Backend (PID: $BPID)"
        kill "$BPID" 2>/dev/null || true
    fi
    rm -f "$REPO_DIR/.backend.pid"
fi

# Parar processos que estão ocupando as portas
echo "  🔍 Verificando portas 3000, 5000, 5173, 8001..."

for PORT in 3000 5000 5173 8001; do
    PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  🛑 Liberando porta $PORT (PIDs: $PIDS)"
        echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
    fi
done

# Aguardar um pouco para as portas liberarem
sleep 2

echo -e "${GREEN}✅ Serviços anteriores parados${NC}"
echo ""

echo "==> Verificando dependências básicas (python3, pip, node, npm)"
command -v python3 >/dev/null 2>&1 || { echo "Erro: python3 não encontrado"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "Erro: pip3 não encontrado"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Erro: node não encontrado"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Erro: npm não encontrado"; exit 1; }

echo "==> Garantindo que o MongoDB esteja em execução (localhost:27017)"
MONGO_STARTED_BY_SCRIPT=""

# Função para verificar se Docker daemon está rodando
check_docker_daemon() {
  if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
      return 0
    else
      return 1
    fi
  else
    return 1
  fi
}

if command -v brew >/dev/null 2>&1 && brew list --formula | grep -q "^mongodb-community$"; then
  echo "  📦 Iniciando MongoDB via Homebrew..."
  brew services start mongodb-community || true
  MONGO_STARTED_BY_SCRIPT="brew"
else
  echo "  📦 Homebrew MongoDB não encontrado. Tentando via Docker..."
  if check_docker_daemon; then
    echo "  ✅ Docker daemon está rodando"
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^alca_mongo$'; then
      if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^alca_mongo$'; then
        echo "  🔄 Iniciando container MongoDB existente..."
        docker start alca_mongo >/dev/null 2>&1 || {
          echo -e "  ${RED}❌ Erro ao iniciar container alca_mongo${NC}"
          exit 1
        }
      else
        echo "  🆕 Criando novo container MongoDB..."
        mkdir -p "$REPO_DIR/mongo_data"
        docker run -d --name alca_mongo -p 27017:27017 -v "$REPO_DIR/mongo_data":/data/db mongo:6 >/dev/null 2>&1 || {
          echo -e "  ${RED}❌ Erro ao criar container MongoDB${NC}"
          exit 1
        }
      fi
    else
      echo "  ✅ Container MongoDB já está rodando"
    fi
    (docker logs -f alca_mongo > "$MONGO_LOG" 2>&1 & echo $! > "$REPO_DIR/.mongo_logs.pid") || true
    MONGO_STARTED_BY_SCRIPT="docker"
  else
    echo -e "  ${RED}❌ Docker não está disponível ou o daemon não está rodando${NC}"
    echo -e "  ${YELLOW}💡 Soluções:${NC}"
    echo -e "     1. Inicie o Docker Desktop e execute o script novamente"
    echo -e "     2. Instale MongoDB via Homebrew: ${BLUE}brew install mongodb-community${NC}"
    echo -e "     3. Inicie MongoDB manualmente e execute o script novamente"
    echo ""
    echo -e "  ${YELLOW}Verificando se MongoDB já está rodando em localhost:27017...${NC}"
    # Verifica se MongoDB já está rodando (pode ter sido iniciado manualmente)
    if nc -z localhost 27017 >/dev/null 2>&1; then
      echo -e "  ${GREEN}✅ MongoDB já está acessível em localhost:27017${NC}"
      MONGO_STARTED_BY_SCRIPT="externo"
    else
      echo -e "  ${RED}❌ MongoDB não está acessível${NC}"
      exit 1
    fi
  fi
fi

# Aguardar MongoDB responder na porta 27017
if [ "$MONGO_STARTED_BY_SCRIPT" != "externo" ]; then
  echo -n "  ⏳ Aguardando MongoDB em localhost:27017"
for i in {1..60}; do
  if nc -z localhost 27017 >/dev/null 2>&1; then
      echo -e " ${GREEN}- ok${NC}"
    break
  fi
  echo -n "."
  sleep 1
done
echo
fi

# Verificação final do MongoDB
if ! nc -z localhost 27017 >/dev/null 2>&1; then
  echo -e "${RED}❌ Erro: MongoDB não está acessível em localhost:27017${NC}"
  echo -e "${YELLOW}💡 Dicas:${NC}"
  echo -e "   • Inicie o Docker Desktop e execute o script novamente"
  echo -e "   • OU instale/start o mongodb-community via Homebrew: ${BLUE}brew install mongodb-community && brew services start mongodb-community${NC}"
  echo -e "   • OU inicie MongoDB manualmente e execute o script novamente"
  exit 1
fi

echo "==> Preparando backend (virtualenv + dependências)"
cd "$BACKEND_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# Verificar instalação de dependências críticas
echo "  🔍 Verificando dependências críticas..."
python -c "import email_validator" 2>/dev/null || {
    echo -e "  ${YELLOW}⚠️  email-validator não encontrado. Reinstalando...${NC}"
    pip install email-validator==2.2.0
}
python -c "import flask, pymongo, pydantic" 2>/dev/null || {
    echo -e "  ${RED}❌ Erro ao importar dependências básicas${NC}"
    exit 1
}
echo -e "  ${GREEN}✅ Todas as dependências instaladas${NC}"


# Variáveis de ambiente padrão
export SECRET_KEY="${SECRET_KEY:-dev-secret-key}"
export MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/alca_financas}"
export MONGO_DB="${MONGO_DB:-alca_financas}"

# CORS - Sempre inclui localhost em portas comuns
CORS_BASE="http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000"
export CORS_ORIGINS="${CORS_ORIGINS:-$CORS_BASE}"

echo "==> Iniciando backend"

# Carregar variáveis do backend/.env se existir
if [ -f "$BACKEND_DIR/.env" ]; then
  set -a
  . "$BACKEND_DIR/.env"
  set +a
fi

# Detectar porta disponível (preferência: 8001, fallback: 5000)
# Porta 5000 é frequentemente ocupada pelo AirPlay no macOS
BACKEND_PORT=8001
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "  ${YELLOW}⚠️  Porta 8001 ocupada, tentando 5000${NC}"
    BACKEND_PORT=5000
    # Verificar se 5000 também está ocupada (AirPlay)
    if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "  ${RED}❌ Portas 8001 e 5000 ocupadas. Libere uma das portas.${NC}"
        exit 1
    fi
fi

# Defaults seguros
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-$BACKEND_PORT}"

echo -e "  ${GREEN}✅ Backend irá iniciar na porta $PORT${NC}"
export MONGO_URI="${MONGO_URI:-${MONGO_URL:-mongodb://localhost:27017/alca_financas}}"
export MONGO_DB="${MONGO_DB:-alca_financas}"

# Detecta IP local para acesso em rede (fallback para hostname)
HOST_IP="${HOST_IP:-}"
if [ -z "$HOST_IP" ]; then
  # tenta en0 e depois Wi-Fi (device name pode variar)
  HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || true)
  if [ -z "$HOST_IP" ]; then
    HOST_IP=$(ipconfig getifaddr en1 2>/dev/null || true)
  fi
  if [ -z "$HOST_IP" ]; then
    HOST_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
  fi
  if [ -z "$HOST_IP" ]; then
    HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
fi
export HOST_IP

nohup python app.py > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$REPO_DIR/.backend.pid"

# Aguardar saúde do backend
echo -n "Aguardando backend ficar pronto"
for i in {1..30}; do
  if curl -sS http://localhost:"$PORT"/api/health 2>/dev/null | grep -q '"status"'; then
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

# Verificação final do backend
if ! curl -sS http://localhost:"$PORT"/api/health 2>/dev/null | grep -q '"status"'; then
  echo ""
  echo -e "${RED}❌ Backend não está respondendo em localhost:$PORT${NC}"
  echo ""
  echo -e "${BLUE}📋 Últimas 30 linhas do log:${NC}"
  echo -e "${YELLOW}────────────────────────────────────────${NC}"
  tail -30 "$BACKEND_LOG"
  echo -e "${YELLOW}────────────────────────────────────────${NC}"
  echo ""
  echo -e "${BLUE}📄 Log completo: ${YELLOW}$BACKEND_LOG${NC}"
  echo ""
  echo -e "${YELLOW}💡 Dicas:${NC}"
  echo "   • Verifique se todas as dependências estão instaladas"
  echo "   • Verifique se o MongoDB está acessível"
  echo "   • Verifique se há erros de sintaxe no código"
  exit 1
fi

echo "==> Preparando frontend (instalando dependências)"
cd "$FRONTEND_DIR"
npm install

# URL do backend para o frontend - SEMPRE usa localhost para evitar problemas CORS
# Vite usa VITE_API_URL, não REACT_APP_*
export VITE_API_URL="http://localhost:$PORT"
echo -e "  ${GREEN}✅ Frontend configurado para usar: http://localhost:$PORT${NC}"

# Criar/atualizar .env do frontend
cat > "$FRONTEND_DIR/.env" << EOF
# Auto-generated by alca_start_mac.sh
VITE_API_URL=http://localhost:$PORT
EOF

# Adicionar IP local ao CORS se disponível
if [ -n "$HOST_IP" ]; then
  export CORS_ORIGINS="$CORS_ORIGINS,http://$HOST_IP:3000,http://$HOST_IP:5173,http://$HOST_IP:8001,http://$HOST_IP:5000"
  echo -e "  ${GREEN}✅ CORS configurado para localhost e $HOST_IP${NC}"
else
  echo -e "  ${GREEN}✅ CORS configurado para localhost${NC}"
fi

echo "==> Iniciando frontend de desenvolvimento (Vite)"

# Detectar porta disponível (preferência: 3000, fallback: 5173)
FRONTEND_PORT=3000
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "  ${YELLOW}⚠️  Porta 3000 ocupada, Vite usará porta padrão (5173)${NC}"
    FRONTEND_PORT=5173
fi

echo -e "  ${GREEN}✅ Frontend irá iniciar na porta $FRONTEND_PORT${NC}"

nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$REPO_DIR/.frontend.pid"

# Aguardar Vite subir (tenta ambas as portas)
echo -n "Aguardando frontend (Vite) ficar pronto"
VITE_READY=0
for i in {1..40}; do
  if curl -sS http://localhost:3000 >/dev/null 2>&1; then
    FRONTEND_PORT=3000
    VITE_READY=1
    echo " - ok"
    break
  elif curl -sS http://localhost:5173 >/dev/null 2>&1; then
    FRONTEND_PORT=5173
    VITE_READY=1
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

# Verificação final do frontend
if [ "$VITE_READY" -eq 0 ]; then
  echo -e "${RED}Erro: Frontend não está respondendo${NC}"
  echo "Verifique os logs: $FRONTEND_LOG"
  echo ""
  echo "Últimas linhas do log:"
  tail -20 "$FRONTEND_LOG"
  exit 1
fi

echo -e "${GREEN}==> Abrindo no navegador: http://localhost:$FRONTEND_PORT${NC}"
if command -v open >/dev/null 2>&1; then
  open "http://localhost:$FRONTEND_PORT" || true
fi

cleanup() {
  echo
  echo "==> Encerrando serviços..."
  if [ -f "$REPO_DIR/.frontend.pid" ] && kill -0 "$(cat "$REPO_DIR/.frontend.pid")" 2>/dev/null; then
    kill "$(cat "$REPO_DIR/.frontend.pid")" || true
    rm -f "$REPO_DIR/.frontend.pid"
  fi
  if [ -f "$REPO_DIR/.backend.pid" ] && kill -0 "$(cat "$REPO_DIR/.backend.pid")" 2>/dev/null; then
    kill "$(cat "$REPO_DIR/.backend.pid")" || true
    rm -f "$REPO_DIR/.backend.pid"
  fi
  if [ "${MONGO_STARTED_BY_SCRIPT}" = "docker" ]; then
    echo "Parando MongoDB (docker alca_mongo)"
    docker stop alca_mongo >/dev/null 2>&1 || true
    docker rm alca_mongo >/dev/null 2>&1 || true
    if [ -f "$REPO_DIR/.mongo_logs.pid" ] && kill -0 "$(cat "$REPO_DIR/.mongo_logs.pid")" 2>/dev/null; then
      kill "$(cat "$REPO_DIR/.mongo_logs.pid")" || true
      rm -f "$REPO_DIR/.mongo_logs.pid"
    fi
  fi
}

trap cleanup EXIT INT TERM

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Alça Finanças está rodando!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 URLs:${NC}"
echo -e "   🌐 Frontend:  ${YELLOW}http://localhost:$FRONTEND_PORT${NC}"
echo -e "   🔧 Backend:   ${YELLOW}http://localhost:$PORT${NC}"
echo -e "   🗄️  MongoDB:   ${YELLOW}mongodb://localhost:27017${NC} (${MONGO_STARTED_BY_SCRIPT:-externo})"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo -e "   Backend:  ${YELLOW}$BACKEND_LOG${NC}"
echo -e "   Frontend: ${YELLOW}$FRONTEND_LOG${NC}"
echo ""
echo -e "${BLUE}🔍 PIDs:${NC}"
echo -e "   Backend:  ${YELLOW}$BACKEND_PID${NC}"
echo -e "   Frontend: ${YELLOW}$FRONTEND_PID${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop all services${NC}"
echo ""
echo "==> Acompanhando logs..."
echo ""
tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG"


