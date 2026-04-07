#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ollama create alca-senior -f .ai_agents/senior.modelfile
ollama create alca-ops -f .ai_agents/ops.modelfile
ollama create alca-writer -f .ai_agents/writer.modelfile

echo "Agentes do Alça Finanças atualizados com sucesso."
echo "Teste: ollama run alca-senior --help"
