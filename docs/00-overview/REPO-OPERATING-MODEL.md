# REPO OPERATING MODEL — Alça Finanças

> Documento interno para orientar como evoluir este repositório com segurança, respeitando a arquitetura atual.

## 1. Visão geral

- **Backend**: `backend/` — Flask 3 + Supabase/PostgreSQL, arquitetura `routes → services → repositories → database/utils`, com RLS e tenancy forte.
- **Frontend Web**: `frontend/` — React 18 + TypeScript + Vite, `AuthContext` e `api.ts` como ponto central de chamadas HTTP.
- **Chatbot / AI**:
  - Chatbot de regras: `services/chatbot/app.py` falando com a API (`/api/...`).
  - Chatbot LLM via OpenClaw: `backend/routes/chatbot.py` → `OpenClawService` → `services/openclaw_bridge/app.py` → gateway OpenClaw (`services/openclaw/`).
- **Banco de dados**: Supabase, migrations em `backend/database/migrations` e `supabase/migrations`.
- **Infra / Deploy**: Docker (`docker-compose*.yml`), scripts `scripts/dev/*`, `scripts/prod/*`, CI em `.github/workflows/ci.yml`.

Este documento descreve **como** trabalhar dentro desse modelo sem quebrar runtime, Docker ou deploy.

## 2. Componentes de runtime

### 2.1 Backend (`backend/`)

- **Entrypoint**: `backend/app.py`
  - Carrega `.env`, valida `SECRET_KEY`, configura CORS, sessão e OAuth (Google).
  - Inicializa Supabase (`database/init_db`, `get_db`) e registra blueprints:
    - `routes/auth.py`, `routes/auth_supabase.py`
    - `routes/transactions.py`, `routes/accounts.py`, `routes/categories.py`
    - `routes/dashboard.py`, `routes/reports.py`, `routes/admin.py`, `routes/tenants.py`
    - `routes/chatbot.py`
  - Aplica rate limiting via `extensions.limiter`.

- **Camadas principais**:
  - Rotas HTTP: `backend/routes/*.py` (adapters REST).
  - Serviços: `backend/services/*.py` (lógica de negócio).
  - Repositórios: `backend/repositories/*_supabase.py` (acesso Supabase).
  - Infra e utilitários: `database/*`, `utils/*`, `metrics.py`, `extensions.py`.

### 2.2 Frontend (`frontend/`)

- Entrypoints: `src/main.tsx`, `src/App.tsx`.
- Contexts:
  - `AuthContext.tsx` (sessão, login/register, storage de tokens).
  - `ThemeContext.tsx`.
- HTTP:
  - `utils/api.ts` (Axios, base URL `VITE_API_URL`, interceptors de auth/401).
- Features:
  - `components/{dashboard,transactions,accounts,categories,reports,credit-cards,planning,settings,profile,import,chat/*}.tsx`.

### 2.3 Chatbot e AI

- **Chatbot LLM (via OpenClaw)**:
  - Rota: `backend/routes/chatbot.py` (`/api/chatbot/*`).
  - Service: `backend/services/openclaw_service.py`.
  - Repository: `backend/repositories/chatbot_repository.py` (`chatbot_conversations` no Supabase).
  - Bridge: `services/openclaw_bridge/app.py` (FastAPI + CLI `openclaw`).
  - Gateway: `services/openclaw/` (Docker, `openclaw.json`, `SYSTEM_PROMPT.md`).

- **Chatbot de regras**:
  - Serviço independente: `services/chatbot/app.py` (FastAPI).
  - Usa JWT da aplicação, fala com `API_BASE_URL` (`/api/accounts`, `/api/transactions`, `/api/dashboard`, etc.).
  - UI Web: `frontend/src/components/chat/ChatWidget.tsx` (HTTP/WS para `chat.alcahub.com.br` ou `127.0.0.1:8100`).

## 3. Fluxos ponta a ponta (resumo)

### 3.1 Fluxo API financeiro

1. Frontend chama `utils/api.ts` com `Authorization: Bearer <JWT>`.
2. Flask (`backend/app.py`) recebe em `/api/...` e roteia via `routes/*.py`.
3. Decorators de auth (`require_auth`, `require_auth_supabase`) validam o token.
4. Rota chama service (`services/*_service.py`).
5. Service usa repository Supabase (`*_repository_supabase.py`).
6. Resposta JSON volta para o frontend.

### 3.2 Fluxo chatbot LLM (OpenClaw)

1. Cliente chama `POST /api/chatbot/chat` com `Authorization: Bearer <token>`.
2. `routes/chatbot.py`:
   - Valida token via `@token_required` (`utils/auth_utils_supabase.py`).
   - Aplica rate limiting (`@limiter.limit("20 per minute")`).
   - Valida `message` e `conversation_id` + ownership (`ChatbotRepository`).
3. Chama `OpenClawService.chat(message, user_id, conversation_id)`.
4. `OpenClawService`:
   - Aplica filtro de keywords suspeitas (prompt injection).
   - Faz `POST {OPENCLAW_BRIDGE_URL}/chat` (default `http://openclaw-bridge:8089`).
5. `openclaw-bridge/app.py`:
   - Executa CLI `openclaw agent --session-id ... --message ... --json`.
   - Se sucesso, devolve `{ message, conversation_id, metadata }`.
6. Service adapta para `{ success, message, conversation_id, metadata }`.
7. Rota persiste/atualiza conversa em Supabase via `ChatbotRepository`.
8. Resposta volta ao cliente.

### 3.3 Fluxo chatbot de regras

1. `ChatWidget.tsx` envia mensagem para `services/chatbot` (HTTP/WS) com o mesmo JWT.
2. `services/chatbot/app.py`:
   - Decodifica token com `JWT_SECRET`.
   - Usa o mesmo token para chamar a API Flask (`API_BASE_URL + /api/...`).
   - Monta resposta textual via `build_reply`.

## 4. Fluxo de autenticação (resumo)

### 4.1 JWT da aplicação

1. Frontend chama `authAPI.login` (`/api/auth/login`).
2. `routes/auth.py`:
   - Valida payload com Pydantic.
   - Busca usuário (`UserRepository`), verifica senha (`auth_utils.check_password`).
   - Gera tokens (`auth_utils.generate_jwt`).
3. `AuthContext.tsx`:
   - Salva `access_token`, `refresh_token`, `user` em `tokenStorage`.
   - Marca `isAuthenticated=true`.
4. `utils/api.ts`:
   - Interceptor adiciona `Authorization: Bearer <access_token>`.
   - Em `401` válido, limpa storage e redireciona para `/login`.

### 4.2 Supabase Auth + unificação

- `utils/auth_utils_supabase.py`:
  - Primeiro tenta validar JWT da app (`verify_jwt`).
  - Se falhar, tenta autenticar via `SupabaseAuthService.get_user(access_token)`.
  - Decorators:
    - `require_auth_supabase`, `admin_required_supabase`, `token_required` (chatbot).

## 5. Fluxo de deploy (resumo)

1. **Configuração de env**:
   - `.env.production` com:
     - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
     - `SECRET_KEY`, `JWT_SECRET`, `CORS_ORIGINS`, `BACKEND_PORT`, `FRONTEND_PORT`.
     - `OPENCLAW_*`, `OPENCLAW_BRIDGE_URL`, `OPENCLAW_GATEWAY_URL`.
2. **Build**: `./scripts/prod/build.sh`
   - Build do frontend (`npm run build` → `build/frontend`).
   - Build da imagem do backend (Dockerfile).
3. **Migrações DB**:
   - `./scripts/prod/migrate.sh` + scripts em `scripts/db/*`.
   - Migrations em `backend/database/migrations` e `supabase/migrations`.
4. **Subir stack**:
   - `docker-compose -f docker-compose.prod.yml up -d`.
   - Serviços: `backend`, `frontend` (nginx servindo `build/frontend`), `openclaw-gateway`, `openclaw-bridge`.
5. **Proxy / domínio**:
   - Nginx/Traefik (`nginx-vps.conf`, `frontend/nginx.prod.conf`) roteando para backend, frontend e chatbot.
6. **CI/CD**:
   - `.github/workflows/ci.yml`:
     - Lint + testes backend (mock Supabase).
     - Testes + build frontend.

## 6. Mapa de impacto (safe vs risky)

### 6.1 Arquivos mais seguros de modificar

- **Frontend UI/UX**:
  - `frontend/src/components/ui/*`.
  - `frontend/src/components/{dashboard,transactions,accounts,categories,reports,planning,settings,profile,import}/*`.
  - Estilos e i18n: `frontend/src/index.css`, `tailwind.config.js`, `frontend/src/i18n/locales/*.json`.

- **Backend domínio (sem auth/tenancy)**:
  - `backend/services/{transaction,account,category,report,import}_service.py`.
  - `backend/utils/{money_utils,date_utils}.py`.

- **Documentação e testes**:
  - `docs/**`, `README.md`, `supabase/README.md`.
  - `backend/tests/**`, `frontend/src/__tests__/**`.

### 6.2 Arquivos de alto risco

- **Bootstrap / infra backend**:
  - `backend/app.py`, `extensions.py`, `metrics.py`, `gunicorn.conf.py`.

- **Autenticação**:
  - `backend/utils/{auth_utils,auth_utils_supabase}.py`.
  - `backend/routes/{auth,auth_supabase}.py`, `backend/schemas/auth_schemas.py`, `backend/services/supabase_auth_service.py`.
  - `frontend/src/contexts/AuthContext.tsx`, `frontend/src/utils/{api,tokenStorage}.ts`.

- **Tenancy / RLS**:
  - `backend/database/migrations/*tenant*`, `backend/database/schema.sql`.
  - `supabase/migrations/*.sql`, `supabase/snapshots/*`.
  - `backend/utils/tenant_context.py`.

- **Chatbot & OpenClaw**:
  - `backend/routes/chatbot.py`, `backend/services/openclaw_service.py`, `backend/repositories/chatbot_repository.py`.
  - `services/openclaw_bridge/app.py`, `services/openclaw/*` (Dockerfiles, `openclaw.json`, `SYSTEM_PROMPT.md`).
  - `services/chatbot/app.py`, `frontend/src/components/chat/ChatWidget.tsx`.

- **Docker, Nginx e scripts de produção**:
  - `docker-compose*.yml`.
  - `backend/Dockerfile*`, `frontend/Dockerfile*`, `services/*/Dockerfile`.
  - `nginx-vps.conf`, `frontend/nginx.prod.conf`.
  - `scripts/prod/*.sh`, `scripts/deploy-docker-remote.sh`, `scripts/deploy-quick-update.sh`.
  - `.github/workflows/ci.yml`.

## 7. Padrões a seguir para novas mudanças

1. **Reutilizar arquitetura existente**:
   - Backend: sempre seguir `route → service → repository → database/utils`.
   - Frontend: adicionar novas APIs em `utils/api.ts` e componentes em `components/<feature>/*`, registrando rotas em `App.tsx`.

2. **Minimizar mudanças e preservar compatibilidade**:
   - Evitar alterar contratos de rotas existentes (URLs, payloads, status codes).
   - Se precisar mudar contrato, atualizar ao mesmo tempo:
     - `frontend/src/utils/api.ts`.
     - Tests relevantes.
     - Documentação em `docs/`.

3. **Mudanças em auth, tenancy ou chatbot**:
   - Sempre:
     - Revisar `docs/SUPABASE-RLS-SECURITY.md`, `docs/04-database/tenancy.md`, `CHATBOT_DEPLOYMENT_GUIDE.md` e `services/openclaw/SYSTEM_PROMPT.md`.
     - Adicionar logs/observabilidade antes de refactors grandes.
     - Validar em ambiente de staging (ou com `SKIP_DB_INIT=true` e testes) antes da produção.

4. **Migrations e banco**:
   - Nunca editar migrations antigas.
   - Sempre criar novas migrations em `backend/database/migrations` ou `supabase/migrations`, com entrada correspondente em `supabase/MIGRATION_AUDIT.md`.

5. **Deploy e Docker**:
   - Evitar renomear serviços ou portas em `docker-compose*.yml` sem revisar:
     - `OPENCLAW_*` e `API_BASE_URL` nos serviços dependentes.
     - Configs de Nginx/Traefik.
   - Testar `./scripts/prod/build.sh` e `./scripts/prod/migrate.sh` localmente ou em staging antes de aplicar em produção.

## 8. Estratégia recomendada para futuras tarefas

1. **Primeiro entender, depois mudar**:
   - Ler docs em `docs/00-overview/RAIO-X-ARQUITETURA-COMPLETO.md`, `docs/ENVIRONMENTS.md`, `docs/DEPLOY-DO-ZERO.md`.
   - Mapear rotas, serviços e repositórios afetados antes de tocar código.

2. **Começar por observabilidade em fluxos críticos**:
   - Para `/api/auth/*`, `/api/chatbot/*`, tenancy e deploy:
     - Adicionar logs e métricas mínimos em pontos chave (entrada, saída, erros).
     - Só depois refatorar, baseado em dados reais.

3. **Refactors em pequenos passos**:
   - Preferir mudanças pequenas e isoladas (1 fluxo de cada vez: auth, chatbot, tenancy, etc.).
   - Garantir testes automatizados cobrindo o caminho afetado antes de grandes alterações.

4. **Manter sempre compatibilidade com runtime e Docker**:
   - Checar impacto em:
     - Variáveis de ambiente.
     - Nomes de serviços/hosts Docker.
     - Scripts de deploy que assumem certos caminhos/serviços.

