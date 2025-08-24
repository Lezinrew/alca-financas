#!/usr/bin/env bash
set -euo pipefail

echo "==> Parando containers antigos..."
docker compose down

echo "==> Buildando e subindo novamente..."
docker compose up -d --build

echo
echo "==> Status atual:"
docker compose ps

echo
echo "==> Logs do backend (CTRL+C para sair)"
docker compose logs -f backend
