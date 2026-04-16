# EXECUTION BASELINE

## 1. Resumo executivo

- O runtime local confirmado hoje é `frontend -> backend Flask :8001 -> Supabase`, com chat principal em `/api/chatbot/*`.
- Existe duplicidade de implementação de chatbot (`Flask` e `FastAPI`), gerando ambiguidade operacional e de contrato.
- O maior risco de segurança confirmado é exposição de segredo em arquivo versionado (`.cursor/mcp.json.recommended`) e hardcode de chave em script de hotfix.
- O maior risco de execução local é drift entre componentes de chat, contratos de resposta e documentação ainda desatualizada para portas/endpoints legados.
- Esta baseline consolida o que já foi levantado, sem novo diagnóstico amplo.

## 2. Fatos confirmados

- **[FATO]** Backend principal: `backend/app.py` em `:8001`, health em `/api/health`.
- **[FATO]** Frontend consome API base em `/api` e endpoints de chat em `/api/chatbot/*` (`frontend/src/utils/api.ts`, `frontend/src/components/chat/ChatWidget.tsx`).
- **[FATO]** Existe serviço paralelo de chatbot em `services/chatbot/app.py` (`/api/chat`, `/api/chat/ws`).
- **[FATO]** `docker-compose.yml` e `docker-compose.prod.yml` não sobem chatbot dedicado.
- **[FATO]** Estratégia de auth ativa converge para `SUPABASE_JWT_SECRET`, mas ainda há rastros de `JWT_SECRET` legado em scripts/utilitários.
- **[FATO]** Há segredo sensível em arquivo versionado recomendado e chave hardcoded em script operacional.
- **[FATO]** Há divergência documentada entre runtime real (`:8001`, `/api/chatbot/*`) e parte da documentação antiga.

## 3. Divergências ou ambiguidades entre relatórios

- **Chatbot principal vs legado**
  - Convergência: todos apontam coexistência Flask + FastAPI.
  - Ambiguidade: falta decisão formal se `services/chatbot/app.py` será descontinuado.
- **Contrato de resposta de chat**
  - `RUNTIME_ALIGNMENT_REPORT.md` indica possível divergência de shape entre `ChatWidget` e `Chatbot.tsx`.
  - `API_CONSUMPTION_MAP.md` confirma ambos chamando `/api/chatbot/chat`, mas destaca diferença na estratégia de token (manual vs interceptor).
- **JWT estratégia única**
  - Memória/runtime indicam convergência para `SUPABASE_JWT_SECRET`.
  - Auditoria de hardcode mostra persistência operacional de `JWT_SECRET` legado em scripts.
- **Risco mais crítico imediato**
  - `HARDCODE_AUDIT.md` prioriza exposição de segredo (segurança) como P0.
  - `RUNTIME_ALIGNMENT_REPORT.md` prioriza unificação arquitetural do chatbot/JWT.
  - Consolidação: ambos são P0 por impacto direto (segurança e runtime).
- **CORS**
  - Backend Flask cobre `localhost` e `127.0.0.1`.
  - FastAPI legado não cobre `127.0.0.1`, podendo falhar em cenários locais específicos.

## 4. P0 imediatos

1. **Eliminar exposição de segredos versionados** (**FATO confirmado**)
   - Impacto: segurança imediata.
   - Arquivos: `.cursor/mcp.json.recommended`, `scripts/hotfix-supabase-prod-simple.sh`.

2. **Fechar caminho único de runtime do chatbot** (**FATO confirmado; decisão pendente**)  
   - Impacto: estabilidade local e redução de conflito entre fluxos.
   - Arquivos: `backend/routes/chatbot.py`, `services/chatbot/app.py`, `frontend/src/components/chat/ChatWidget.tsx`, `frontend/src/components/Chatbot.tsx`, `frontend/src/utils/api.ts`.

3. **Remover ambiguidade de auth legado no caminho ativo** (**FATO confirmado**)  
   - Impacto: segurança e previsibilidade de autenticação.
   - Arquivos: `backend/utils/auth_utils.py`, `backend/utils/auth_utils_supabase.py`, `scripts/dev/up.sh`, `scripts/setup-env.sh`, `.env.example`.

4. **Alinhar documentação operacional mínima ao runtime real** (**FATO confirmado**)  
   - Impacto: evitar execução/deploy com premissas erradas.
   - Arquivos: `ARCHITECTURE.md`, `TODO.md`, docs que citam `:5000`/`/api/chat*`/`JWT_SECRET` legado.

## 5. P1 importantes

1. **Padronizar contrato funcional do chat no frontend** (**HIPÓTESE forte com evidência estática**)  
   - Risco: erro silencioso/intermitente conforme componente ativo.
   - Arquivos: `frontend/src/components/chat/ChatWidget.tsx`, `frontend/src/components/Chatbot.tsx`, `frontend/src/utils/api.ts`.

2. **Unificar matriz de configuração por ambiente (API/CORS)** (**FATO confirmado**)  
   - Risco: comportamento divergente entre dev/homolog/prod.
   - Arquivos: `backend/app.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`, `backend/.env.example`, `frontend/Dockerfile`, `mobile/src/api/client.ts`.

3. **Formalizar estratégia de deploy do frontend build em produção** (**FATO confirmado**)  
   - Risco: produção subir sem artefato esperado.
   - Arquivos: `docker-compose.prod.yml`, documentação operacional de deploy.

## 6. P2 dívida técnica

1. **Reduzir duplicações de defaults em scripts e entrypoints** (**FATO confirmado**)
   - Arquivos: `scripts/dev/up.sh`, `alca_start_mac.sh`, `scripts/setup-env.sh`, `docker-compose.yml`, `.env.example`.

2. **Limpar documentação legada/histórica com hardcodes** (**FATO confirmado**)
   - Arquivos: `docs/`, `legacy/` e guias operacionais antigos citados nos relatórios.

3. **Revisar WS opcional com token em query string** (**HIPÓTESE / validação runtime necessária**)
   - Arquivos: `frontend/src/components/chat/ChatWidget.tsx`, (serviço WS correspondente quando habilitado).

## 7. Arquivos críticos por prioridade

- **P0**
  - `.cursor/mcp.json.recommended`
  - `scripts/hotfix-supabase-prod-simple.sh`
  - `backend/routes/chatbot.py`
  - `services/chatbot/app.py`
  - `backend/utils/auth_utils.py`
  - `backend/utils/auth_utils_supabase.py`
  - `scripts/dev/up.sh`
  - `scripts/setup-env.sh`
  - `ARCHITECTURE.md`

- **P1**
  - `frontend/src/components/chat/ChatWidget.tsx`
  - `frontend/src/components/Chatbot.tsx`
  - `frontend/src/utils/api.ts`
  - `backend/app.py`
  - `docker-compose.yml`
  - `docker-compose.prod.yml`
  - `frontend/Dockerfile`
  - `mobile/src/api/client.ts`

- **P2**
  - `alca_start_mac.sh`
  - `.env.example`
  - `backend/.env.example`
  - `docs/*`
  - `legacy/*`

## 8. Ordem recomendada de execução

1. **Segurança primeiro (P0):** revogar/rotacionar segredos expostos e remover hardcodes sensíveis versionados.
2. **Runtime único (P0):** decisão formal do chatbot (Flask único vs serviço dedicado) e bloqueio do caminho paralelo.
3. **Auth sem ambiguidade (P0):** eliminar dependência prática de `JWT_SECRET` legado no fluxo ativo.
4. **Documentação mínima crítica (P0):** corrigir portas/endpoints/secrets canônicos para evitar operação errada.
5. **Contrato e configuração (P1):** padronizar chat frontend + matriz única de env/CORS/API.
6. **Dívida estrutural (P2):** limpeza de duplicações e docs legados.

## 9. Riscos de conflito entre agentes

- Alterações simultâneas em `backend/utils/auth_utils.py` e `backend/utils/auth_utils_supabase.py` podem quebrar autenticação de rotas diferentes.
- Alterações concorrentes em `frontend/src/components/chat/ChatWidget.tsx` e `frontend/src/components/Chatbot.tsx` podem reforçar divergência de contrato.
- Mudanças paralelas em `docker-compose*.yml` e docs operacionais podem deixar instruções inconsistentes.
- Refatoração do chatbot sem decisão explícita (Flask vs FastAPI) tende a gerar retrabalho e regressão.
- Edição de arquivos de segredo/config (`.cursor/mcp.json.recommended`, scripts de deploy) por múltiplos agentes aumenta risco de vazamento residual.

## 10. Critério de pronto da fase atual

- Não existe segredo real versionado nos arquivos rastreados.
- Existe apenas um caminho de chatbot oficialmente suportado no runtime local.
- Fluxo de autenticação ativo não depende de fallback legado para operar.
- Documentação operacional crítica reflete `:8001`, `/api/chatbot/*` e política atual de secrets.
- Prioridades P0 concluídas com validação funcional mínima de login + chat + health.

---

### o que pode ser executado já

- Rotação e saneamento de segredos expostos.
- Decisão arquitetural formal do chatbot e congelamento do caminho não oficial.
- Limpeza de `JWT_SECRET` legado nos scripts de execução.
- Atualização da documentação operacional mínima para runtime real.

### o que não deve ser alterado ainda

- Refatoração ampla de domínio financeiro fora dos pontos críticos de runtime/auth/chat.
- Mudanças estruturais grandes em banco/tenant sem fechar primeiro os P0 de segurança e execução local.
- Introdução de novos endpoints de chat antes da padronização de contrato entre componentes existentes.

### qual documento deve virar fonte principal de contexto

- `EXECUTION_BASELINE.md` (este documento), com `PROJECT_MEMORY_UNIVERSAL.md` como memória histórica complementar.
