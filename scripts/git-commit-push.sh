#!/usr/bin/env bash
# Uso: ./scripts/git-commit-push.sh "mensagem do commit"
# Ou:  GIT_COMMIT_MSG="mensagem" ./scripts/git-commit-push.sh
# Permite que Claude CLI (ou CI) faça commit + push sem prompt interativo.

set -e
cd "$(dirname "$0")/.."

MSG="${1:-$GIT_COMMIT_MSG}"
if [ -z "$MSG" ]; then
  echo "Uso: $0 \"mensagem do commit\""
  echo "Ou:  GIT_COMMIT_MSG=\"mensagem\" $0"
  exit 1
fi

git add -A
if git diff --staged --quiet; then
  echo "Nada para commitar (working tree clean)."
  exit 0
fi
git commit -m "$MSG"
git push origin main
echo "Commit enviado para origin/main."
