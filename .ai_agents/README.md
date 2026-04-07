# Modelos Ollama — Alça Finanças

Modelfiles locais para `ollama create`. **Não** coloques chaves ou `.env` aqui.

## Modelos base (puxar antes)

```bash
ollama pull qwen2.5-coder:32b
ollama pull llama3.1:8b
# Se falhar, ver tags disponíveis em https://ollama.com/library
ollama pull deepseek-coder-v2:lite
```

Se `deepseek-coder-v2:lite` não existir na tua versão do Ollama, tenta `ollama search deepseek` ou usa outra tag listada e edita a linha `FROM` em `ops.modelfile`.

## Registar os três agentes

Na **raiz do repositório**:

```bash
chmod +x ./.ai_agents/update_agents.sh
./.ai_agents/update_agents.sh
```

Ou manualmente:

```bash
ollama create alca-senior -f .ai_agents/senior.modelfile
ollama create alca-ops -f .ai_agents/ops.modelfile
ollama create alca-writer -f .ai_agents/writer.modelfile
```

## Uso

```bash
ollama run alca-senior "..."
ollama run alca-ops "..."
ollama run alca-writer "..."
```

## Ficheiros

| Ficheiro        | Modelo base              | Parâmetros principais      |
|----------------|--------------------------|----------------------------|
| `senior.modelfile`   | `qwen2.5-coder:32b`      | `temperature 0.2`          |
| `ops.modelfile`      | `deepseek-coder-v2:lite` | `temperature 0.3`          |
| `writer.modelfile`   | `llama3.1:8b`            | `temperature 0.45`         |

Atualiza o `SYSTEM` nos Modelfiles quando a arquitectura em `docs/` mudar significativamente.
