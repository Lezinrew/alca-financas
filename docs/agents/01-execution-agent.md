# Agente de execução — Alça Finanças

Guia curto para **agentes** (e para humanos a operar no mesmo modo). Não substitui `AGENTS.md`; complementa a parte de “como retomar sem contexto”.

## Leitura obrigatória (ordem)

1. [README.md](../../README.md) — stack, arranque local, mapa de pastas.  
2. [system-design.md](../../system-design.md) — componentes, fluxo de dados, entidades.  
3. [docs/runbooks/runbook.md](../runbooks/runbook.md) — o que está valendo, pendências, última ação.  
4. [AGENTS.md](../../AGENTS.md) — agentes por domínio, red lines, convenções.

Se a tarefa for **Supabase/RLS**, ler também o skill Supabase (se ativo) e `docs/04-database/tenancy.md` / `supabase/README.md`.

## Como retomar o projeto do zero (sessão nova)

1. Clonar o repositório e abrir a raiz.  
2. Copiar `.env.example` → `.env` e preencher Supabase + `SECRET_KEY` (32+ caracteres).  
3. Subir com `docker compose up -d` **ou** `./scripts/local-dev.sh start`.  
4. Chamar `GET http://localhost:8001/api/health`.  
5. Se o trabalho envolver dados: verificar no runbook se há migrations pendentes **no ambiente** do utilizador.  
6. Só então abrir tarefa específica (ficheiro, bug, feature).

## Regras de execução

- **Não refatorar** fora do pedido; não “limpar” código não relacionado.  
- **Não inventar** funcionalidades ou integrações inexistentes no repo.  
- **Não expor** credenciais em commits, comentários ou documentação.  
- **Mudanças de schema** → novo ficheiro em `supabase/migrations/`, nunca edição ad hoc só no painel.  
- **Produção ou dados reais** → tratar como sensível: backup, confirmação, alinhado com `AGENTS.md` (red lines).  
- **Depois de alterar o comportamento do sistema** visível a equipa ou a deploy: atualizar **`docs/runbooks/runbook.md`**.

## Especialização rápida

| Área | Onde começar |
|------|----------------|
| API / tenant | `backend/app.py`, `backend/routes/`, `backend/utils/tenant_context.py` |
| Auth | `backend/routes/auth_supabase.py`, `backend/utils/supabase_jwt.py` |
| UI | `frontend/src/`, `frontend/src/contexts/AuthContext.tsx` |
| Chat / OpenClaw | `backend/routes/chatbot.py`, `services/openclaw_bridge/`, `services/openclaw/` |
| Automação | `docs/N8N-VPS-SETUP.md`, `scripts/setup-n8n-nginx-ssl.sh` |
| Testes | `backend/tests/`, `frontend` (Vitest/Playwright em `e2e/`) |

## Saída esperada

Para tarefas concluídas, o agente deve deixar o runbook e os ficheiros de decisão **coerentes** com o que mudou, e indicar de forma explícita se **migração** precisa de ser aplicada no Supabase do utilizador.
