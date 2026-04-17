# TODO.md - Alça Finanças

**Última atualização:** 2026-04-17  
**Status:** 🟡 Em progresso — P0-B (runtime único chatbot) e P0-D (docs mínimas) em curso; frente **auth/RLS/tenant** estável no código e nas migrations `00001`–`00004` (aplicar no Supabase de cada ambiente). **Admin:** migration `20260417000002` + código alinhados — aplicar migration em cada ambiente antes de usar purge em produção.

### Concluído recentemente (código na `main`)

- **Módulo administrativo (2026-04-17):** API `/api/admin/*` (stats, utilizadores, papel/estado, avisos inatividade, export CSV), auditoria em `admin_audit_logs`, notificações; **`POST /api/admin/users/<id>/purge`** (exclusão total: Auth + `public.users` com confirmação por e-mail; requer **`SUPABASE_SERVICE_ROLE_KEY`**).
- **UI admin modo escuro:** `AdminDashboard`, `UserManagement`, `UserDetail`, `AdminLogs` com tokens Tailwind `dark-surface` / `dark-border` / `dark-text-*`; modal de purge; ação `purge_user` nos logs.
- **429 em `GET /api/auth/me`:** rota isenta do limiter global no Flask + throttle no `AuthContext` ao sincronizar perfil com o backend.
- RLS `accounts` / `categories` / `transactions` por **membership** (`tenant_members`), sem depender de claim `tenant_id` no JWT (`20260416000003`, `20260416000004`).
- **Cliente Supabase singleton:** removido `set_session` em `get_user` sobre o cliente global; `sign_out` usa cliente efémero — evita PostgREST com JWT de utilizador e **42501** em writes após `GET /api/auth/me`.
- Smoke pós-deploy: `scripts/prod/smoke-auth-bootstrap.sh` cobre health → bootstrap → me → accounts → categories → transactions.
- Verificação SQL: `scripts/sql/verify_bootstrap_rls_and_data.sql`; checklist incidente: `backend/EXECUTION_TENANT_BOOTSTRAP_CHECKLIST.md`.
- **Runbook:** `EXECUTION_RUNBOOK.md` (secção Admin 2026-04-17); `supabase/DEPLOY_RUNBOOK.md` (migrations posteriores ao pacote 001–004).

---

## 🔥 PRIORIDADE 1 - SISTEMA SOBROU OU NÃO SOBRE

### 1.1 Docker Desktop não inicia no Windows
- **Hipótese:** Docker Desktop corrompido ou serviço parado
- **Arquivos:** `docker-compose.yml`, `docker-compose.prod.yml`
- **Impacto:** Sem containers = sem sistema em dev local
- **Ferramenta:** Cursor (debug Docker Desktop)
- **Prompt:**
  ```
  Docker Desktop no Windows está com erro:
  "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified"
  
  Analise:
  1. Verifique se o serviço DockerDesktopService está rodando
  2. Valide configurações do Docker Desktop (WSL2 backend?)
  3. Sugira comandos de reset/restart
  4. Se necessário, gere script de reinstalação limpa
  
  Contexto: Workspace Alça Finanças, preciso subir containers localmente.
  ```

### 1.2 Unificar docker-compose (dev vs prod)
- **Hipótese:** 3 arquivos docker-compose causam confusão deploy
- **Arquivos:** `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Impacto:** Deploy errado, variáveis de ambiente confusas
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Temos 3 arquivos docker-compose no Alça Finanças:
  - docker-compose.yml (base?)
  - docker-compose.dev.yml
  - docker-compose.prod.yml
  
  Analise os 3 arquivos e:
  1. Identifique sobreposições e conflitos
  2. Sugira estrutura unificada com override (compose override pattern)
  3. Mantenha segredos fora do git (.env)
  4. Garanta que dev espelhe produção em estrutura
  
  Gere novo docker-compose.yml base + docker-compose.override.yml exemplo.
  ```

---

## 🎯 PRIORIDADE 2 - FLUXO PRINCIPAL

### 2.1 Consolidar chatbot (backend vs services) ✅ EM VALIDAÇÃO
- **Status:** 🟡 Frontend migrado para backend Flask (2026-04-13)
- **Hipótese:** Chatbot tem implementação duplicada
- **Arquivos:** `backend/routes/chatbot.py`, `backend/chatbot/`, `services/chatbot/app.py`
- **Impacto:** WebSocket pode estar em serviço errado, autenticação falha
- **Mudanças aplicadas:**
  - ✅ `frontend/src/components/chat/ChatWidget.tsx` — URLs para `/api/chatbot`
  - ✅ `frontend/src/utils/api.ts` — chatbotAPI adicionado
  - ✅ `.env.example` — VITE_CHAT_API_URL apontando para Flask
  - ✅ `frontend/src/components/Chatbot.tsx` — alinhado a `chatbotAPI` (mesmo contrato Flask; não montado no `App.tsx`)
  - ✅ `backend/routes/chatbot.py` — `ChatbotRepository` lazy (import sem `get_db`)
  - ✅ `services/chatbot/README.md` — legado FastAPI documentado como não oficial
  - ✅ `EXECUTION_RUNBOOK.md` — secção P0-B (auditoria consumo UI / compose)
- **Próximos passos:**
  - [ ] Testar health: `curl http://localhost:8001/api/chatbot/health`
  - [ ] Testar login + chat no frontend (fluxo real autenticado)
  - [ ] Validar logs backend após uso de chat
  - [ ] Arquivar `services/chatbot/` após validação
- **Rollback:** `git checkout frontend/src/components/chat/ChatWidget.tsx frontend/src/utils/api.ts .env.example`

### 2.2 Validar autenticação Supabase JWT (parcial — RLS + singleton corrigidos no código)
- **Hipótese residual:** JWT expirando, drift de `SUPABASE_JWT_SECRET`, ou chave **anon** no backend em produção (PostgREST aplica RLS).
- **Arquivos:** `backend/utils/supabase_jwt.py`, `backend/routes/auth_supabase.py`, `backend/utils/auth_utils_supabase.py`, `backend/services/supabase_auth_service.py`, `backend/database/connection.py`
- **Impacto:** Usuários não logam, loop infinito, ou **42501** em dados se `SUPABASE_SERVICE_ROLE_KEY` não for a chave **service_role** (JWT com `role: service_role`).
- **Feito no código:** policies por `tenant_members`; sem `set_session` no singleton; warning se JWT da API ≠ `service_role`.
- **Pendente em ambiente:** confirmar env de produção e migrations aplicadas no projeto Supabase.
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Auth do Alça usa Supabase JWT.
  
  Verifique:
  1. backend/utils/supabase_jwt.py - validação do token
  2. backend/routes/auth_supabase.py - fluxo login
  3. backend/utils/auth_utils_supabase.py - helpers
  
  Teste mentalmente o fluxo:
  Login → JWT → RLS policies → Query
  
  Identifique pontos de falha e gere fix.
  ```

---

## 📊 PRIORIDADE 3 - DADOS E CÁLCULOS

### 3.1 Unificar migrations do Supabase
- **Hipótese:** Migrations em 3 pastas diferentes, ordem desconhecida
- **Arquivos:** `backend/database/migrations/`, `backend/migrations/`, `supabase/migrations/`
- **Impacto:** Produção com schema errado, queries falham
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Temos migrations em 3 lugares:
  1. backend/database/migrations/ (002-015, tenant RLS)
  2. backend/migrations/ (chatbot)
  3. supabase/migrations/ (20260303_*, schema base)
  
  Analise:
  1. Qual a ordem correta de aplicação?
  2. Há duplicações?
  3. Há conflitos de tabelas/colunas?
  
  Gere:
  - migration_master.md com ordem exata
  - Script único de migração
  - Rollback script
  ```

### 3.2 Validar cálculos financeiros (money_utils)
- **Hipótese:** Decimais/rounding causando erros de centavos
- **Arquivos:** `backend/utils/money_utils.py`
- **Impacto:** Relatórios errados, usuário perde confiança
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Analise backend/utils/money_utils.py
  
  Verifique:
  1. Usa Decimal ou float?
  2. Round em que ponto (banco ou app)?
  3. Soma/subtração de transações
  4. Cálculo de saldo de cartões
  
  Gere testes unitários para:
  - Transação de R$ 0,01
  - Soma de 1000 transações
  - Juros de cartão
  ```

---

## 🎨 PRIORIDADE 4 - UX E DASHBOARD

### 4.1 Dashboard performance (queries N+1)
- **Hipótese:** Dashboard faz queries em loop por categoria/conta
- **Arquivos:** `backend/routes/dashboard.py`, `backend/services/report_service.py`
- **Impacto:** Dashboard lento (>5s), usuário abandona
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Dashboard do Alça está lento.
  
  Analise:
  1. backend/routes/dashboard.py - endpoints
  2. backend/services/report_service.py - queries
  
  Identifique:
  - Queries N+1 (loop por categoria/conta)
  - Falta de indexes
  - Dados não agregados no banco
  
  Sugira otimizações com:
  - JOINs adequados
  - Materialized views se necessário
  - Cache de KPIs
  ```

### 4.2 Frontend dist no git (poluição)
- **Hipótese:** Build do frontend commitado acidentalmente
- **Arquivos:** `.gitignore`, `frontend/dist/`
- **Impacto:** Repo inchado, deploy confuso
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Verifique se frontend/dist/ está no .gitignore.
  
  Se não estiver:
  1. Adicione ao .gitignore
  2. Gere comando git para remover do histórico (git rm --cached -r frontend/dist)
  3. Gere .gitignore completo para React+Vite
  
  Isso é crítico pra não poluir o repo.
  ```

---

## 🛠️ PRIORIDADE 5 - DÉBITO TÉCNICO

### 5.1 Python 3.9 obsoleto (urllib3 warning)
- **Hipótese:** Backend em Python 3.9, urllib3 v2 incompatível
- **Arquivos:** `backend/requirements.txt`, `backend/Dockerfile`, `backend/Dockerfile.prod`
- **Impacto:** Warnings em produção, possível vulnerabilidade
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Backend log mostra:
  "urllib3 v2 only supports OpenSSL 1.1.1+, currently compiled with LibreSSL 2.8.3"
  
  Backend usa Python 3.9 (backend/Dockerfile).
  
  Plano:
  1. Atualizar para Python 3.11 ou 3.12
  2. Atualizar requirements.txt compatível
  3. Testar migrations
  4. Atualizar Dockerfile.prod
  
  Gere diff completo.
  ```

### 5.2 Scripts de deploy duplicados
- **Hipótese:** 15+ scripts de deploy em `scripts/`, `legacy/scripts/`, raiz
- **Arquivos:** `scripts/*.sh`, `legacy/scripts/*.sh`, `alca_*.sh`
- **Impacto:** Deploy errado, ninguém sabe qual script usar
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Temos scripts em:
  - scripts/ (30+ arquivos)
  - legacy/scripts/ (15+ arquivos)
  - Raiz: alca_*.sh (10+ arquivos)
  
  Analise e:
  1. Identifique scripts obsoletos (legacy/)
  2. Unifique scripts ativos em scripts/dev/ e scripts/prod/
  3. Gere scripts/README.md com uso de cada
  4. Delete ou archive obsoletos
  
  Foque em: deploy, migrate, rebuild, setup.
  ```

### 5.3 Documentação fragmentada
- **Hipótese:** 50+ arquivos .md em `docs/`, `legacy/docs/`, raiz
- **Arquivos:** `docs/*.md`, `legacy/docs/*.md`, `DEPLOY*.md`, `README*.md`
- **Impacto:** Ninguém acha docs certa, repeating work
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Documentação do Alça está em:
  - docs/ (40+ arquivos)
  - legacy/docs/ (20+ arquivos)
  - Raiz: DEPLOY*.md, README*.md, QUICKSTART*.md
  
  Crie:
  1. docs/INDEX.md organizado por categoria
  2. Mova obsoletos para docs/archive/
  3. Mantenha apenas 3-5 na raiz (README, DEPLOY, QUICKSTART)
  4. Gere mapa mental da docs
  
  Categorias: Deploy, Auth, Database, Features, Troubleshooting.
  ```

---

## 📋 ORDEM DE ATAQUE RECOMENDADA

| Semana | Foco | Entregas |
|--------|------|----------|
| **Semana 1** | Prioridade 1 | Docker rodando, compose unificado |
| **Semana 2** | Prioridade 2 | Chatbot consolidado, auth validada |
| **Semana 3** | Prioridade 3 | Migrations unificadas, cálculos testados |
| **Semana 4** | Prioridade 4 | Dashboard rápido, frontend limpo |
| **Semana 5** | Prioridade 5 | Python atualizado, scripts organizados |

---

## 🚨 RISCOS IMEDIATOS

1. **Docker parado** = dev travado
2. **Chatbot duplicado** = ambiguidade de runtime até P0-B fechado
3. **Migrations não aplicadas no Supabase remoto** = schema/RLS divergente do repo (`00001`–`00004` e posteriores, **incl. admin `20260417000002`**)
4. **`SUPABASE_SERVICE_ROLE_KEY` errada (anon no lugar de service_role)** = 42501 em writes mesmo com código correto; **purge admin** devolve `503 service_role_required` sem chave de serviço
5. **Python 3.9** = urllib3 pode quebrar em update
6. **`scripts/supabase-wipe-all-data.sql`** = destrutivo total; só em dev/staging com projeto confirmado no Supabase

---

## 📝 NOTAS

- Backend está rodando no Mac (192.168.1.60), workspace no Windows
- Validar qual máquina é "produção local" antes de deploy
- Estado canónico de execução: `EXECUTION_RUNBOOK.md` + `EXECUTION_BASELINE.md` (não existe `MEMORY.md` na raiz; usar estes + `ARCHITECTURE.md`)
