#!/usr/bin/env bash
set -euo pipefail

# Rollback script for Alça Finanças
# NOTE: This is a scaffolding script. The exact rollback strategy depends on
# how images/tags are managed in production.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

TARGET_VERSION="${1:-}"

if [[ -z "${TARGET_VERSION}" ]]; then
  echo "Usage: scripts/prod/rollback.sh <git-tag-or-commit>"
  echo "Example: scripts/prod/rollback.sh v1.2.3"
  exit 1
fi

echo "==> Rolling back Alça Finanças to ${TARGET_VERSION}"

echo "==> Checking out specified version"
git fetch --all --tags
git checkout "${TARGET_VERSION}"

echo "==> Rebuilding and restarting services for ${TARGET_VERSION}"
if [[ -x "./scripts/prod/build.sh" ]]; then
  ./scripts/prod/build.sh
fi

if [[ -x "./scripts/prod/run.sh" ]]; then
  ./scripts/prod/run.sh
else
  if [[ -f "docker-compose.prod.yml" ]]; then
    docker-compose -f docker-compose.prod.yml up -d
  fi
fi

echo "==> Rollback to ${TARGET_VERSION} completed."
echo "TODO: Adjust this strategy if production uses image tags instead of git checkout."

