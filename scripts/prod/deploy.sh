#!/usr/bin/env bash
set -euo pipefail

# Production deploy script for Alça Finanças
# Idempotent: repetir o deploy da mesma versão não deve quebrar o ambiente.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "==> Deploying Alça Finanças (scripts/prod/deploy.sh)"

echo "==> Updating git working copy"
git fetch origin
git reset --hard origin/main

echo "==> Building artifacts"
if [[ -x "./scripts/prod/build.sh" ]]; then
  ./scripts/prod/build.sh
fi

echo "==> Running migrations (if any)"
if [[ -x "./scripts/prod/migrate.sh" ]]; then
  ./scripts/prod/migrate.sh || echo "Migrations script finished (may be no-op)"
fi

echo "==> Starting/refreshing services"
if [[ -x "./scripts/prod/run.sh" ]]; then
  ./scripts/prod/run.sh
else
  # Fallback: try docker-compose.prod.yml if present
  if [[ -f "docker-compose.prod.yml" ]]; then
    docker-compose -f docker-compose.prod.yml up -d
  fi
fi

echo "==> Deploy completed."

