#!/usr/bin/env bash
# Rebuild do frontend em produção no VPS com VITE_SUPABASE_* vindos do .env na raiz do projeto.
# Uso (no servidor):
#   cd /var/www/alca-financas
#   chmod +x scripts/rebuild-frontend-prod-on-server.sh
#   ./scripts/rebuild-frontend-prod-on-server.sh
#
# O .env deve conter (como em .env.example):
#   VITE_SUPABASE_URL=https://xxxx.supabase.co
#   VITE_SUPABASE_ANON_KEY=eyJ...   (chave anon, não service_role)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERRO: não existe $ENV_FILE — crie com VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY"
  exit 1
fi

# Só as variáveis necessárias ao Vite (evita passar o .env inteiro ao docker)
TMP_ENV="$(mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT
if ! grep -E '^VITE_SUPABASE_URL=' "$ENV_FILE" >>"$TMP_ENV" 2>/dev/null; then
  echo "ERRO: $ENV_FILE não define VITE_SUPABASE_URL"
  exit 1
fi
if ! grep -E '^VITE_SUPABASE_ANON_KEY=' "$ENV_FILE" >>"$TMP_ENV" 2>/dev/null; then
  echo "ERRO: $ENV_FILE não define VITE_SUPABASE_ANON_KEY"
  exit 1
fi

echo "==> Limpando dist / build/frontend"
rm -rf frontend/dist build/frontend
mkdir -p build/frontend

echo "==> npm ci && npm run build (com env do Supabase)"
docker run --rm \
  --env-file "$TMP_ENV" \
  -v "$ROOT/frontend:/app" \
  -w /app \
  node:22-alpine \
  sh -lc "npm ci && npm run build"

echo "==> Copiando para nginx volume"
cp -a frontend/dist/. build/frontend/
chmod -R a+rX build/frontend

if [[ ! -f build/frontend/index.html ]]; then
  echo "ERRO: build/frontend/index.html ausente"
  exit 1
fi

echo "==> Recriando container frontend"
docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

echo "==> OK. Confirme: curl -sI http://127.0.0.1:3000/ | head -1"
echo "    E no bundle deve aparecer a URL do projeto: grep -r supabase.co build/frontend/assets/ | head -1"
