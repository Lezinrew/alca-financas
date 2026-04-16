# PROJECT_MEMORY_UNIVERSAL.md

Atualizado em: 2026-04-14  
Fonte: leitura de código, docs existentes e `git status`/`git diff` local.

## 1) Estado atual de runtime (fatos)

- Branch atual: `main` (tracking `origin/main`) com múltiplas alterações locais não commitadas.
- Backend principal: Flask em `backend/app.py`, porta `8001`, health em `/api/health`.
- Frontend principal: Vite em dev (porta `3000` no `docker-compose.yml`) e Nginx em prod (`docker-compose.prod.yml` com volume `./build/frontend`).
- Banco/Auth: Supabase (URL + service role key + validação JWT no backend).
- Chatbot: coexistem duas implementações no código:
  - Flask: `backend/routes/chatbot.py` com prefixo `/api/chatbot`.
  - FastAPI: `services/chatbot/app.py` com `/api/chat` e `/api/chat/ws`.
- Compose dev (`docker-compose.yml`) sobe `backend`, `frontend` e OpenClaw (via profile); não há serviço `chatbot` dedicado.
- Compose prod (`docker-compose.prod.yml`) sobe `backend`, `frontend`, `openclaw-gateway`, `openclaw-bridge`; também não há serviço `chatbot` dedicado.

## 2) Arquitetura atual (consolidada)

- Fluxo principal web: `Frontend -> /api (Flask backend) -> Supabase`.
- Chat no frontend foi migrado para rota Flask:
  - `frontend/src/components/chat/ChatWidget.tsx` aponta para `/api/chatbot/chat` (dev: `http://localhost:8001/api/chatbot`).
  - `frontend/src/utils/api.ts` adicionou `chatbotAPI` com endpoints `/chatbot/*`.
- WebSocket de chat no frontend ficou opcional por `VITE_CHAT_WS_URL`; sem essa env var, uso efetivo é HTTP.
- Backend reforça runtime de auth:
  - `backend/app.py` exige `SECRET_KEY` forte e valida presença de `SUPABASE_JWT_SECRET` em produção.
  - `backend/utils/supabase_jwt.py` documenta `SUPABASE_JWT_SECRET` como fonte única (comentário de compatibilidade para legado).

## 3) Problemas abertos (confirmados no estado atual)

- Chatbot duplicado ainda existe no repositório (`backend/routes/chatbot.py` e `services/chatbot/app.py`).
- Diferença entre documentação e código em partes do projeto (docs ainda descrevem FastAPI como chatbot principal em alguns trechos).
- Risco operacional em produção para frontend se `build/frontend` não estiver gerado antes do `docker compose -f docker-compose.prod.yml up`.
- Há alterações extensas ainda não commitadas em auth/tenant/bootstrap/chatbot/CORS/compose; estado está em transição.
- Arquivo SQL novo de manutenção (`scripts/sql/cleanup_orphan_personal_tenants.sql`) ainda não versionado.

## 4) Decisões vigentes no código (já refletidas no diff)

- Chat frontend direcionado para backend Flask (`/api/chatbot/*`) em vez de FastAPI (`/api/chat*`).
- CORS padrão no backend e no compose dev foi ampliado para cobrir `localhost` e `127.0.0.1` (portas 3000/3001/5173).
- Auth/bootstrap recebeu endurecimento para cenário multi-tenant:
  - `backend/services/bootstrap_service.py` ganhou fallback por claims JWT e tratamento de conflito/duplicidade.
  - `backend/repositories/tenant_repository.py` passou a validar existência em `public.users` antes de criar tenant padrão.
  - `backend/utils/tenant_context.py` evita caminho que poderia criar tenant sem garantir `public.users`.
- Repositório base Supabase (`backend/repositories/base_repository_supabase.py`) ajustado para `.insert(...).select("*")` e fallback de id.
- Compose dev e prod reforçam exigência de `SUPABASE_JWT_SECRET`.

## 5) Próximos passos (objetivos, sem suposição)

1. Validar runtime de chat via Flask:
   - `GET /api/chatbot/health`
   - fluxo login + envio de mensagem no frontend.
2. Decidir oficialmente se `services/chatbot/` será arquivado; se sim, remover referências e atualizar docs.
3. Alinhar documentação canônica com estado atual (`/api/chatbot/*`, porta backend `8001`, política JWT vigente).
4. Garantir rotina de deploy com build frontend explícito (`npm run build`) antes do compose de produção.
5. Aplicar o SQL de limpeza de tenants órfãos somente após preview e validação manual no Supabase.

## 6) Riscos atuais

- **Risco de inconsistência funcional do chat:** dois backends de chatbot coexistem com contratos e endpoints diferentes.
- **Risco de regressão de auth/tenant:** mudanças críticas estão em progresso e ainda não consolidadas por commit/teste de ponta a ponta.
- **Risco de deploy incompleto:** produção depende do artefato local `build/frontend`.
- **Risco de documentação desatualizada:** pode induzir operação/configuração incorreta (especialmente em chatbot/auth).

## 7) Evidências usadas neste levantamento

- `git status --short --branch` e `git diff -- .`
- `backend/app.py`
- `backend/routes/chatbot.py`
- `backend/services/bootstrap_service.py`
- `backend/repositories/base_repository_supabase.py`
- `backend/repositories/tenant_repository.py`
- `backend/utils/supabase_jwt.py`
- `backend/utils/tenant_context.py`
- `frontend/src/components/chat/ChatWidget.tsx`
- `frontend/src/utils/api.ts`
- `services/chatbot/app.py`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `ARCHITECTURE.md`
- `TODO.md`
- `RUNTIME_ALIGNMENT_REPORT.md`
- `scripts/sql/cleanup_orphan_personal_tenants.sql`
