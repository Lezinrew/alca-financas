
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

# Carregar .env do backend para SUPABASE_URL/SUPABASE_KEY
if [ -f "$BACKEND_DIR/.env" ]; then
  set -a
  . "$BACKEND_DIR/.env"
  set +a
fi

# Logs com data/hora
TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend-$TS.log"
FRONTEND_LOG="$LOG_DIR/frontend-$TS.log"

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
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
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

# Banco de dados: apenas Supabase (obrigatório)
echo -e "${BLUE}==> Verificando configuração Supabase${NC}"
# Aceita ambos nomes: SUPABASE_SERVICE_ROLE_KEY (padrão) ou SUPABASE_KEY (legacy)
SUPABASE_KEY_VALUE="${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_KEY:-}}"
if [ -z "${SUPABASE_URL:-}" ] || [ -z "$SUPABASE_KEY_VALUE" ]; then
  echo -e "${RED}❌ SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurados${NC}"
  echo -e "${YELLOW}💡 Configure no arquivo backend/.env ou .env:${NC}"
  echo -e "   ${BLUE}SUPABASE_URL=https://seu-projeto.supabase.co${NC}"
  echo -e "   ${BLUE}SUPABASE_SERVICE_ROLE_KEY=eyJ... (Project Settings > API > service_role)${NC}"
  exit 1
fi
# Aceita chave nova (sb_secret_...) ou antiga (eyJ...)
if ! echo "$SUPABASE_KEY_VALUE" | grep -qE '^(eyJ|sb_secret_)'; then
  echo -e "${YELLOW}⚠️  SUPABASE_SERVICE_ROLE_KEY deve ser a service_role key (eyJ...) ou sb_secret_...${NC}"
  echo -e "   Em Supabase: Project Settings > API > Project API keys > service_role."
  exit 1
fi
echo -e "${GREEN}✅ Supabase configurado${NC}"


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
python -c "import flask, supabase, pydantic" 2>/dev/null || {
    echo -e "  ${RED}❌ Erro ao importar dependências básicas (flask, supabase, pydantic)${NC}"
    exit 1
}
echo -e "  ${GREEN}✅ Todas as dependências instaladas${NC}"


# Variáveis de ambiente padrão
export SECRET_KEY="${SECRET_KEY:-dev-secret-key}"

# CORS - Sempre inclui localhost em portas comuns
CORS_BASE="http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000"
export CORS_ORIGINS="${CORS_ORIGINS:-$CORS_BASE}"

echo "==> Iniciando backend"

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

# Salvar porta do backend antes de sobrescrever para o frontend
BACKEND_PORT_FINAL=$PORT

echo -e "  ${GREEN}✅ Backend irá iniciar na porta $BACKEND_PORT_FINAL${NC}"

# Frontend sempre usa porta 3000 (conforme vite.config.js)
FRONTEND_PORT=3000
export FRONTEND_URL="http://localhost:$FRONTEND_PORT"

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
  if curl -sS http://localhost:"$BACKEND_PORT_FINAL"/api/health 2>/dev/null | grep -q '"status"'; then
    echo " - ok"
    break
  fi
  echo -n "."
  sleep 1
done
echo

# Verificação final do backend
if ! curl -sS http://localhost:"$BACKEND_PORT_FINAL"/api/health 2>/dev/null | grep -q '"status"'; then
  echo ""
  echo -e "${RED}❌ Backend não está respondendo em localhost:$BACKEND_PORT_FINAL${NC}"
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
  echo "   • Verifique SUPABASE_URL e SUPABASE_KEY no backend/.env (service_role JWT)"
  echo "   • Verifique se há erros de sintaxe no código"
  exit 1
fi

echo "==> Preparando frontend (instalando dependências)"
cd "$FRONTEND_DIR"
npm install

# URL do backend para o frontend - SEMPRE usa localhost para evitar problemas CORS
# Vite usa VITE_API_URL, não REACT_APP_*
export VITE_API_URL="http://localhost:$BACKEND_PORT_FINAL"
echo -e "  ${GREEN}✅ Frontend configurado para usar: http://localhost:$BACKEND_PORT_FINAL${NC}"

# Criar/atualizar .env do frontend
cat > "$FRONTEND_DIR/.env" << EOF
# Auto-generated by alca_start_mac.sh
VITE_API_URL=http://localhost:$BACKEND_PORT_FINAL
EOF

# Adicionar IP local ao CORS se disponível (sempre inclui porta 3000)
if [ -n "$HOST_IP" ]; then
  export CORS_ORIGINS="$CORS_ORIGINS,http://$HOST_IP:3000,http://$HOST_IP:5173,http://$HOST_IP:8001,http://$HOST_IP:5000"
  echo -e "  ${GREEN}✅ CORS configurado para localhost e $HOST_IP${NC}"
else
  echo -e "  ${GREEN}✅ CORS configurado para localhost (porta 3000)${NC}"
fi

echo "==> Iniciando frontend de desenvolvimento (Vite)"

# Frontend sempre usa porta 3000 (conforme vite.config.js com strictPort: true)
FRONTEND_PORT=3000

# Verificar se a porta 3000 está disponível
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "  ${RED}❌ Porta 3000 ainda está ocupada após tentativa de liberação${NC}"
    echo -e "  ${YELLOW}💡 Tente parar manualmente o processo na porta 3000:${NC}"
    echo -e "     ${BLUE}lsof -ti:3000 | xargs kill -9${NC}"
    exit 1
fi

echo -e "  ${GREEN}✅ Frontend irá iniciar na porta $FRONTEND_PORT${NC}"

# Forçar Vite a usar porta 3000 via variável de ambiente
export PORT=$FRONTEND_PORT

nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$REPO_DIR/.frontend.pid"

# Aguardar Vite subir na porta 3000
echo -n "Aguardando frontend (Vite) ficar pronto na porta 3000"
VITE_READY=0
for i in {1..40}; do
  if curl -sS http://localhost:3000 >/dev/null 2>&1; then
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
  echo -e "${RED}❌ Frontend não está respondendo na porta 3000${NC}"
  echo ""
  echo -e "${BLUE}📋 Últimas 30 linhas do log:${NC}"
  echo -e "${YELLOW}────────────────────────────────────────${NC}"
  tail -30 "$FRONTEND_LOG"
  echo -e "${YELLOW}────────────────────────────────────────${NC}"
  echo ""
  echo -e "${BLUE}📄 Log completo: ${YELLOW}$FRONTEND_LOG${NC}"
  echo ""
  echo -e "${YELLOW}💡 Dicas:${NC}"
  echo "   • Verifique se a porta 3000 está realmente livre"
  echo "   • Verifique se há erros no log do frontend"
  echo "   • Tente parar manualmente processos na porta 3000"
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
}

trap cleanup EXIT INT TERM

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Alça Finanças está rodando!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📍 URLs:${NC}"
echo -e "   🌐 Frontend:  ${YELLOW}http://localhost:$FRONTEND_PORT${NC}"
echo -e "   🔧 Backend:   ${YELLOW}http://localhost:$BACKEND_PORT_FINAL${NC}"
echo -e "   🗄️  Banco:     ${YELLOW}Supabase${NC}"
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


