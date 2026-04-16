# RUNTIME ALIGNMENT REPORT

## Resumo executivo

- ✅ **Fato:** runtime principal atual é `frontend (Vite/Nginx) -> backend Flask :8001 -> Supabase`, com chatbot migrando para `backend/routes/chatbot.py`.
- ⚠️ **Fato:** ainda existe implementação paralela em `services/chatbot/app.py` (FastAPI :8100), com CORS/endpoints diferentes da rota Flask.
- ❌ **Fato:** há drift de documentação relevante (múltiplos docs ainda apontam `localhost:5000`, `JWT_SECRET` legado e fluxo WebSocket antigo).
- ⚠️ **Fato:** frontend usa base de API coerente (`VITE_API_URL` + fallback `http://localhost:8001`), mas coexistem componentes de chat com contratos de resposta diferentes.
- ⚠️ **Fato:** `docker-compose.prod.yml` não inclui serviço `chatbot`, enquanto docs descrevem chatbot dedicado em produção.
- ✅ **Fato (git):** mudanças locais em auth/chatbot/CORS/compose já existem no diff e caminham para unificar em `SUPABASE_JWT_SECRET`.

Legenda usada:
- **Fato:** confirmado em código/diff atual
- **Hipótese:** inferência técnica provável, requer validação runtime
- **Pendência:** falta evidência conclusiva apenas por leitura estática

## Mapa real de serviços

- ✅ **Fato:** `backend/app.py` expõe API Flask em `:8001`, health em `/api/health`, e registra `chatbot_bp` em `/api/chatbot`.
- ✅ **Fato:** `docker-compose.yml` (dev) sobe `backend` + `frontend` e perfis OpenClaw; não sobe `services/chatbot` por padrão.
- ⚠️ **Fato:** `services/chatbot/app.py` existe e roda FastAPI (`/api/chat`, `/api/chat/ws`) quando executado isoladamente.
- ⚠️ **Fato:** `docker-compose.prod.yml` sobe `backend` + `frontend` + OpenClaw, sem serviço chatbot dedicado.
- ⚠️ **Hipótese:** em produção atual, chat funcional depende do endpoint Flask `/api/chatbot/*`; qualquer dependência de `/api/chat*` tende a falhar.

## Mapa real de endpoints consumidos pelo frontend

- ✅ **Fato:** `frontend/src/utils/api.ts` usa `API_BASE_URL = {host}/api` e consome:
  - `auth/*`
  - `categories*`
  - `accounts*`
  - `transactions*` (+ `/transactions/facets`, `/transactions/import`)
  - `reports/overview`
  - `planning/month*`
  - `goals*`
  - `dashboard`, `dashboard-advanced`
  - `admin/*`
  - `chatbot/*` (`chat`, `conversations`, `health`)
- ✅ **Fato:** `frontend/src/components/chat/ChatWidget.tsx` usa HTTP direto para:
  - dev: `http://localhost:8001/api/chatbot/chat`
  - prod: `/api/chatbot/chat`
  - WS opcional: `VITE_CHAT_WS_URL` (sem fallback automático)
- ⚠️ **Fato:** `frontend/src/components/Chatbot.tsx` também chama `api.post('/chatbot/chat')`, mas espera shape de resposta diferente (`success/message`), potencialmente divergente do `ChatWidget`.
- ⚠️ **Pendência:** qual componente de chat está ativo no fluxo principal da UI não foi validado em runtime.

## Estado atual de CORS

### Origens configuradas por serviço

- ✅ **Backend Flask (`backend/app.py`)**
  - Lê `CORS_ORIGINS`.
  - Fallback explícito:  
    `http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:3001`.
- ✅ **Dev Compose (`docker-compose.yml`)**
  - Default `CORS_ORIGINS` inclui localhost e 127.0.0.1 nas portas 3000/3001/5173.
- ⚠️ **Chatbot FastAPI (`services/chatbot/app.py`)**
  - `allow_origins` hardcoded: `https://alcahub.cloud`, `https://www.alcahub.cloud`, `http://localhost:5173`, `http://localhost:3000`.
  - Não inclui `127.0.0.1`.

### Divergência localhost vs 127.0.0.1

- ✅ **Fato:** backend Flask trata ambos explicitamente.
- ❌ **Fato:** chatbot FastAPI não trata `127.0.0.1`.
- ⚠️ **Hipótese:** se frontend/QA usar `127.0.0.1` contra FastAPI, haverá bloqueio CORS.

## Estado atual de JWT/auth

- ✅ **Fato:** validação principal de API protegida usa `@require_auth` (`backend/utils/auth_utils.py`) com `verify_supabase_jwt()`.
- ✅ **Fato:** `verify_supabase_jwt` usa `SUPABASE_JWT_SECRET` (HS256) ou JWKS; comentários indicam `JWT_SECRET/CHATBOT_JWT_SECRET` como legado.
- ⚠️ **Fato:** `backend/utils/auth_utils.py` ainda contém geração/decodificação de JWT legado (`JWT_SECRET`) para fluxos antigos.
- ⚠️ **Fato:** `backend/utils/auth_utils_supabase.py` (usado por `token_required` do chatbot Flask) ainda aceita fallback de JWT da app via `verify_jwt()` legado.
- ✅ **Fato:** `services/chatbot/app.py` foi alterado para usar `SUPABASE_JWT_SECRET` no `jwt.decode`.
- ✅ **Fato:** `backend/routes/chatbot.py` exige token em `/chat`/`/conversations*`; `/health` é público.

### Onde `JWT` / `SUPABASE_JWT_SECRET` aparece

- `backend/app.py`
- `backend/utils/supabase_jwt.py`
- `backend/utils/auth_utils.py`
- `backend/utils/auth_utils_supabase.py`
- `backend/routes/auth.py`
- `backend/routes/auth_supabase.py`
- `services/chatbot/app.py`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- múltiplos arquivos de docs/legacy docs (incluindo referências antigas a `JWT_SECRET`)

## Divergências entre código e documentação

- ❌ **Fato:** `PROJECT_CONTEXT.md` e partes de `ARCHITECTURE.md`/`ENVIRONMENTS.md` ainda descrevem chatbot principal como FastAPI + WS em `:8100`.
- ❌ **Fato:** código frontend/backend já migrou consumo principal para `/api/chatbot/*` no Flask.
- ❌ **Fato:** documentação operacional ainda cita backend `localhost:5000` em diversos docs (`docs/TESTING.md`, `docs/backend_api_qa_checklist.md`), enquanto runtime real é `:8001`.
- ⚠️ **Fato:** docs descrevem checks com `JWT_SECRET`; código atual converge para `SUPABASE_JWT_SECRET`.
- ⚠️ **Pendência:** não há evidência estática de documento único canônico já alinhado 100% ao estado atual.

## Hardcodes e riscos

- ❌ **Fato:** hardcodes legados de URL/token em arquivos `legacy/docs/*` (incluindo exemplos de `JWT_SECRET` fixo e hosts antigos).
- ⚠️ **Fato:** `services/chatbot/app.py` possui `API_BASE_URL` default hardcoded para `http://127.0.0.1:8001`.
- ⚠️ **Fato:** `frontend/src/components/chat/ChatWidget.tsx` usa URL hardcoded local no fallback (`http://localhost:8001/api/chatbot`).
- ⚠️ **Fato:** `backend/routes/auth.py` contém blocos OAuth/backup com traços de compatibilidade Mongo/legado, aumentando risco de comportamento não homogêneo.
- ⚠️ **Hipótese:** coexistência de dois contratos de resposta de chat (`reply` vs `success/message`) pode causar erro silencioso dependendo do componente renderizado.

## Top 10 arquivos críticos

1. `backend/app.py` — bootstrap, CORS, seleção de auth route, registro de blueprints.
2. `backend/utils/supabase_jwt.py` — validação de assinatura JWT (núcleo de auth runtime).
3. `backend/utils/auth_utils.py` — `require_auth` ativo + funções legado JWT.
4. `backend/utils/auth_utils_supabase.py` — `token_required` do chatbot + fallback legado.
5. `backend/routes/auth.py` — bootstrap de usuário/tenant e endpoints sensíveis de autenticação.
6. `backend/routes/chatbot.py` — endpoint de chat em produção lógica atual.
7. `services/chatbot/app.py` — implementação paralela (FastAPI), potencial fonte de conflito operacional.
8. `frontend/src/utils/api.ts` — origem real de base URL e mapa de consumo `/api/*`.
9. `frontend/src/components/chat/ChatWidget.tsx` — integração de chat atual (HTTP + WS opcional).
10. `docker-compose.prod.yml` — definição real de runtime de produção (ausência de chatbot dedicado).

## Próximas correções prioritárias

1. ✅ **Prioridade P0:** fechar decisão arquitetural de chatbot (Flask único vs FastAPI dedicado) e remover caminho paralelo ativo.
2. ✅ **Prioridade P0:** eliminar fallback legado `JWT_SECRET` em cadeia de autenticação ativa (`auth_utils*`) para reduzir ambiguidade de validação.
3. ✅ **Prioridade P0:** alinhar documentação operacional canônica para `:8001`, `/api/chatbot/*`, `SUPABASE_JWT_SECRET` e estado real do compose.
4. ⚠️ **Prioridade P1:** padronizar contrato de resposta de chat entre `ChatWidget` e `Chatbot.tsx` (ou descontinuar um componente).
5. ⚠️ **Prioridade P1:** revisar CORS de todos os serviços para paridade `localhost` + `127.0.0.1`.
6. ⚠️ **Prioridade P1:** definir se produção terá chatbot separado; se sim, adicionar serviço/roteamento explícito em `docker-compose.prod.yml` + docs.
7. ⚠️ **Prioridade P1:** reduzir hardcodes de URL local para variáveis únicas e validar fallback consistente por ambiente.
8. ⚠️ **Prioridade P1:** validar fluxo completo `login -> /auth/bootstrap -> dashboard -> chat` com token real Supabase.

