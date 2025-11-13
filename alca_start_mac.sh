
#!/usr/bin/env bash
set -euo pipefail

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

echo "==> Verificando dependências básicas (python3, pip, node, npm)"
command -v python3 >/dev/null 2>&1 || { echo "Erro: python3 não encontrado"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "Erro: pip3 não encontrado"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Erro: node não encontrado"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Erro: npm não encontrado"; exit 1; }

echo "==> Garantindo que o MongoDB esteja em execução (localhost:27017)"
MONGO_STARTED_BY_SCRIPT=""
if command -v brew >/dev/null 2>&1 && brew list --formula | grep -q "^mongodb-community$"; then
  brew services start mongodb-community || true
else
  echo "Homebrew MongoDB não encontrado. Tentando via Docker..."
  if command -v docker >/dev/null 2>&1; then
    if ! docker ps --format '{{.Names}}' | grep -q '^alca_mongo$'; then
      if docker ps -a --format '{{.Names}}' | grep -q '^alca_mongo$'; then
        docker start alca_mongo >/dev/null
      else
        mkdir -p "$REPO_DIR/mongo_data"
        docker run -d --name alca_mongo -p 27017:27017 -v "$REPO_DIR/mongo_data":/data/db mongo:6 >/dev/null
      fi
    fi
    (docker logs -f alca_mongo > "$MONGO_LOG" 2>&1 & echo $! > "$REPO_DIR/.mongo_logs.pid") || true
    MONGO_STARTED_BY_SCRIPT="docker"
  else
    echo "Erro: nem MongoDB (brew) nem Docker disponíveis. Instale um deles para rodar o banco."
  fi
fi

# Aguardar MongoDB responder na porta 27017
echo -n "Aguardando MongoDB em localhost:27017"
for i in {1..60}; do
  if nc -z localhost 27017 >/dev/null 2>&1; then
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

# Verificação final do MongoDB
if ! nc -z localhost 27017 >/dev/null 2>&1; then
  echo "Erro: MongoDB não está acessível em localhost:27017. Abortei o start."
  echo "Dicas: inicie o Docker Desktop OU instale/start o mongodb-community via Homebrew."
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

# Variáveis de ambiente padrão (pode sobrescrever antes de rodar este script)
export SECRET_KEY="${SECRET_KEY:-dev-secret-key}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:3000}"
export MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/alca_financas}"
export MONGO_DB="${MONGO_DB:-alca_financas}"

echo "==> Iniciando backend (porta 8001)"

# Carregar variáveis do backend/.env se existir
if [ -f "$BACKEND_DIR/.env" ]; then
  set -a
  . "$BACKEND_DIR/.env"
  set +a
fi

# Defaults seguros
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8001}"
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
  if curl -sS http://localhost:"$PORT"/api/health >/dev/null; then
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

echo "==> Preparando frontend (instalando dependências)"
cd "$FRONTEND_DIR"
npm install

# URL do backend para o frontend (usa IP local para acesso de outras máquinas)
if [ -n "$HOST_IP" ]; then
  export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-http://$HOST_IP:$PORT}"
else
  export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-http://localhost:$PORT}"
fi

# Ampliar CORS para IP local nos ports comuns do Vite
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:3001,http://localhost:3002}"
if [ -n "$HOST_IP" ]; then
  export CORS_ORIGINS="$CORS_ORIGINS,http://$HOST_IP:3000,http://$HOST_IP:3001,http://$HOST_IP:3002"
fi

echo "==> Iniciando frontend de desenvolvimento (Vite)"
nohup npm run dev -- --host > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$REPO_DIR/.frontend.pid"

# Aguardar Vite subir
echo -n "Aguardando frontend (Vite) ficar pronto"
for i in {1..30}; do
  if curl -sS http://localhost:3000 >/dev/null; then
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

echo "==> Abrindo no navegador: http://localhost:3000"
if command -v open >/dev/null 2>&1; then
  open "http://localhost:3000" || true
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

echo
echo "==> Serviços em execução:"
echo "MongoDB:       localhost:27017 (${MONGO_STARTED_BY_SCRIPT:-externo})"
echo "Backend PID:   $BACKEND_PID (logs: $BACKEND_LOG)"
echo "Frontend PID:  $FRONTEND_PID (logs: $FRONTEND_LOG)"
echo
echo "==> Acompanhando logs (CTRL+C para sair e encerrar)"
tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG"


