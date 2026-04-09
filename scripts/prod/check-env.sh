#!/usr/bin/env bash
# Valida variáveis críticas do .env de produção (sem imprimir valores).
# Uso na VPS: ./scripts/prod/check-env.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERRO: ficheiro não encontrado: $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

err=0
need() {
  local k="$1"
  local v="${!k:-}"
  if [[ -z "${v// }" ]]; then
    echo "ERRO: $k está vazio ou ausente (obrigatório em produção)."
    err=1
  else
    echo "OK: $k definido (${#v} caracteres)"
  fi
}

echo "==> A verificar $ENV_FILE"
need SUPABASE_URL
need SUPABASE_SERVICE_ROLE_KEY
need SUPABASE_JWT_SECRET
need SECRET_KEY
need CORS_ORIGINS

if [[ "$err" -ne 0 ]]; then
  echo ""
  echo "Corrija o .env e volte a correr. Sem SUPABASE_JWT_SECRET o login mostra 401 em /api/accounts e /api/auth/bootstrap."
  exit 1
fi
echo "==> Todas as chaves obrigatórias estão preenchidas."
