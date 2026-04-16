#!/usr/bin/env bash
# Smoke test de auth/bootstrap/tenant usando variáveis do .env.
# Uso:
#   ./scripts/prod/smoke-auth-bootstrap.sh
#   ACCESS_TOKEN=... ./scripts/prod/smoke-auth-bootstrap.sh
#   ./scripts/prod/smoke-auth-bootstrap.sh /caminho/.env

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

normalize_base_url() {
  local raw="$1"
  raw="$(printf '%s' "$raw" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  raw="${raw%/}"
  if [[ "$raw" == */api ]]; then
    raw="${raw%/api}"
  fi
  echo "$raw"
}

pick_base_url() {
  if [[ -n "${SMOKE_BASE_URL:-}" ]]; then
    normalize_base_url "$SMOKE_BASE_URL"
    return
  fi

  if [[ -n "${API_BASE_URL:-}" ]]; then
    normalize_base_url "$API_BASE_URL"
    return
  fi

  if [[ -n "${VITE_API_URL:-}" ]]; then
    normalize_base_url "$VITE_API_URL"
    return
  fi

  if [[ -n "${FRONTEND_URL:-}" ]]; then
    normalize_base_url "$FRONTEND_URL"
    return
  fi

  echo ""
}

BASE_URL="$(pick_base_url)"
if [[ -z "$BASE_URL" ]]; then
  echo "ERRO: não consegui inferir BASE_URL do .env"
  echo "Defina uma destas variáveis: SMOKE_BASE_URL, API_BASE_URL, VITE_API_URL ou FRONTEND_URL"
  exit 1
fi

if [[ -z "${ACCESS_TOKEN:-}" ]]; then
  echo "Cole um access token Supabase válido (não é gravado em disco):"
  read -r ACCESS_TOKEN
fi

if [[ -z "${ACCESS_TOKEN// }" ]]; then
  echo "ERRO: ACCESS_TOKEN vazio"
  exit 1
fi

API_URL="$BASE_URL/api"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

run_check() {
  local method="$1"
  local url="$2"
  local outfile="$3"
  shift 3

  local status
  status="$(curl -sS -o "$outfile" -w "%{http_code}" -X "$method" "$url" "$@")"
  echo "$status"
}

print_step() {
  echo ""
  echo "==> $1"
}

print_step "Health: $API_URL/health"
health_status="$(run_check "GET" "$API_URL/health" "$TMP_DIR/health.json")"
echo "HTTP $health_status"
cat "$TMP_DIR/health.json" || true

print_step "Bootstrap: $API_URL/auth/bootstrap"
bootstrap_status="$(run_check "POST" "$API_URL/auth/bootstrap" "$TMP_DIR/bootstrap.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json")"
echo "HTTP $bootstrap_status"
cat "$TMP_DIR/bootstrap.json" || true

print_step "Auth me: $API_URL/auth/me"
me_status="$(run_check "GET" "$API_URL/auth/me" "$TMP_DIR/me.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN")"
echo "HTTP $me_status"
cat "$TMP_DIR/me.json" || true

print_step "Accounts: $API_URL/accounts"
accounts_status="$(run_check "GET" "$API_URL/accounts" "$TMP_DIR/accounts.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN")"
echo "HTTP $accounts_status"
cat "$TMP_DIR/accounts.json" || true

print_step "Categories: $API_URL/categories"
categories_status="$(run_check "GET" "$API_URL/categories" "$TMP_DIR/categories.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN")"
echo "HTTP $categories_status"
cat "$TMP_DIR/categories.json" || true

print_step "Transactions: $API_URL/transactions"
transactions_status="$(run_check "GET" "$API_URL/transactions?page=1&limit=5" "$TMP_DIR/transactions.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN")"
echo "HTTP $transactions_status"
cat "$TMP_DIR/transactions.json" || true

echo ""
echo "==> Resumo"
echo "health:        $health_status"
echo "bootstrap:     $bootstrap_status"
echo "auth/me:       $me_status"
echo "accounts:      $accounts_status"
echo "categories:    $categories_status"
echo "transactions:  $transactions_status"

if [[ "$bootstrap_status" != "200" || "$me_status" != "200" || "$accounts_status" != "200" \
  || "$categories_status" != "200" || "$transactions_status" != "200" ]]; then
  echo ""
  echo "SMOKE FALHOU"
  echo "Esperado: bootstrap=200, auth/me=200, accounts=200, categories=200, transactions=200"
  exit 2
fi

echo ""
echo "SMOKE OK"
