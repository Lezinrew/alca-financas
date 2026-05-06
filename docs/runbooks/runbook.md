# Runbook operacional — Alça Finanças

**Fonte única de verdade** para estado do sistema, pendências e próximos passos operacionais. Deve ser atualizado quando se fechar tarefas P0, após deploys relevantes, ou mudança de premissas (auth, banco, URLs).

**Última revisão do documento de estrutura:** 2026-04-29

---

## 1. Estado atual do sistema

- **Entrega em produção:** aplicação web (React) + API (Flask) com **Supabase** (Postgres + Auth + RLS). Banco **não** roda no `docker-compose` padrão; credenciais vêm de `.env`.
- **Multi-tenant:** tabelas `tenants` / `tenant_members`; isolamento reforçado com migrations de RLS (ex. `20260416000003_*`, `20260416000004_*` no repositório).
- **Backends de chat:** (a) rotas `/api/chatbot` no Flask com integração **OpenClaw** opcional (`docker compose --profile openclaw`); (b) serviço separado `services/chatbot` para fluxo baseado em regras, quando utilizado.
- **Automação n8n:** em geral **fora** deste repositório no dia a dia; VPS Hostinger com Nginx/SSL documentado em `docs/N8N-VPS-SETUP.md` e `scripts/setup-n8n-nginx-ssl.sh`.
- **Mobile:** pasta `mobile/` (Expo) — evolução independente do web.
- **CI:** GitHub Actions (`.github/workflows/ci.yml`) em `main` / `develop` para `backend/`, `frontend/`, `scripts/`, `docs/`, etc.

## 2. Contexto válido (premissas para trabalhar)

- Repositório: **alca-financas** (Flask + React + Supabase, não MongoDB em runtime atual).
- Branches de integração: tipicamente `**main`** e `**develop**` (ver workflows).
- Configuração local: copiar `**.env.example` → `.env**` na raiz; `SECRET_KEY` com **≥ 32 caracteres** (exigido por `backend/app.py`).
- API local padrão: `http://localhost:8001` · Frontend dev: `http://localhost:3000` (ou conforme `FRONTEND_PORT` / compose).
- Migrations: aplicar no **Supabase de cada ambiente** (dev/staging/prod) a partir de `supabase/migrations/` — o repositório não substitui a disciplina de aplicar SQL no projeto certo.
- Não versionar **secrets**; usar apenas `.env.example` e gestão segura de credenciais.

## 3. Última execução relevante


| Data       | Evento                                                                                                                                                                                                                                                                                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-04-29 | Correção de duplicidade de categorias na importação OFX/CSV: normalização de nomes no backend, reutilização tenant/legado, script `scripts/sql/deduplicate_categories.sql`, query de inspeção `scripts/sql/inspect_duplicate_categories.sql` e migration `backend/database/migrations/016_unique_category_normalized.sql` para índice único funcional. |
| 2026-04-29 | Higienização da raiz do repositório: remoção de artefatos legados (`*.h2d`, logs versionados, backups SQL vazios, arquivos `~`, chave SSH local `alca_financas_deploy*`, ficheiros locais `.gitconfig`/`1cd`) e reforço do `.gitignore` para prevenir recidiva. |
| 2026-04-23 | Adição da camada de **governança** na raiz e em `docs/` (README, `system-design.md`, runbook, ADRs, guia de agente, `infra/`, `n8n/`) para recuperabilidade humana e por agentes.                                                                                                                                                                      |


(Atualize esta tabela após deploys, cortes de release ou mudanças de auth/banco.)

## 4. Pendências (operacional / risco)

Itens a validar com o **estado real** de cada ambiente; prioridades históricas do projeto constam de `AGENTS.md` (secção *Current Priorities*):

- Garantir que **migrations pendentes** do repositório estão **aplicadas** em **cada** projeto Supabase (dev/prod) — especialmente ficheiros `20260416`*, `20260417*`, RLS.
- Executar `scripts/sql/deduplicate_categories.sql` em cada ambiente antes de aplicar a migration `016_unique_category_normalized.sql`.
- Validar no produto (dropdown de categorias em Transações) que não há equivalentes duplicadas por nome/normalização após import OFX.
- Rotacionar imediatamente qualquer credencial/chave previamente versionada (incluindo `alca_financas_deploy`, removida da raiz em 2026-04-29) e manter apenas via cofre seguro.
- Alinhar **segredos** (`SUPABASE_JWT_SECRET`, chaves, `SECRET_KEY`) entre o que o Auth emite e o que o backend valida; evitar 401 inesperados em `/api/`*.
- Onde o **OpenClaw** for usado: confirmar `OPENCLAW_GATEWAY_TOKEN` e rede entre bridge e gateway (`docker-compose.yml`).
- **n8n** no VPS: confirmar `WEBHOOK_URL` / `N8N_HOST` e TLS apontando para o n8n escutando em `127.0.0.1:5678` por trás do Nginx (ver `docs/N8N-VPS-SETUP.md`).
- `public.transaction_tenant_inconsistencies` é tabela **diagnóstica/backend-only**; não é `user-scoped` (sem `user_id`) e não deve entrar em wipe de dados por utilizador.

## 5. Próximos passos (sugestão)

1. Executar `scripts/sql/inspect_duplicate_categories.sql` (baseline) e guardar evidência por ambiente.
2. Executar `scripts/sql/deduplicate_categories.sql` e revalidar inspeção sem duplicados elegíveis.
3. Aplicar `backend/database/migrations/016_unique_category_normalized.sql` após limpeza concluída.
4. Fazer **smoke test**: login, import OFX, dropdown de categorias sem duplicadas visuais, criação manual de categoria (variação de caixa/espaços) bloqueando duplicata.
5. Atualizar este runbook com **data** e **resultado** do smoke; manter `AGENTS.md` e este ficheiro coerentes.

## 6. Histórico resumido


| Período           | Notas                                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-04-29        | Limpeza de legado na raiz + endurecimento do `.gitignore` para artefatos locais (logs, `*.h2d`, backups SQL, chaves locais, ficheiros temporários). |
| 2026-04-29        | Hardening de categorias: deduplicação SQL + normalização no backend + índice único funcional para evitar regressão de duplicatas na importação. |
| 2026-03 a 2026-04 | Consolidação do schema Supabase: init, funções, RLS, hardening, `financial_expenses`, admin/audit, ajustes em transações.                       |
| Migração legado   | Dados e docs antigos (Mongo, etc.) em `legacy/`; runtime atual é Supabase.                                                                      |
| Sempre            | CI em GitHub; deploy documentado em vários `docs/DEPLOY*.md` e scripts em `scripts/`.                                                           |


---

*Quem altera o comportamento de produção ou o schema: atualize a **secção 1–3** e acrescente linha em **6** se for um marco.*