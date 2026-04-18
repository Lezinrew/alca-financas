# EXECUTION RUNBOOK (Fase Atual)

Base: `EXECUTION_BASELINE.md`  
Objetivo: executar P0 -> P1 -> P2 com menor risco de regressão e sem retrabalho entre agentes.

## 1) Regras operacionais da execução

- Executar em blocos sequenciais (não paralelizar blocos P0 entre si).
- **P0-A é bloqueador absoluto:** nenhum ajuste de runtime/auth/docs inicia antes de concluir P0-A.
- Cada bloco só inicia após critério de saída do bloco anterior.
- Registrar decisões no próprio arquivo ao final de cada bloco.
- Evitar mudanças fora dos arquivos listados do bloco.

## 2) Responsáveis sugeridos por trilha

- **Security owner:** segredos, tokens, hardcodes sensíveis.
- **Backend owner:** auth/JWT, chatbot backend, CORS backend.
- **Frontend owner:** contrato de chat, consumo de API, validação UI.
- **Infra/Docs owner:** compose, build/deploy, documentação canônica.

## 3) Bloco P0-A (Segurança imediata)

### Escopo

- Remover exposição de segredos versionados.
- Rotacionar credenciais comprometidas.

### Arquivos alvo

- `.cursor/mcp.json.recommended`
- `scripts/hotfix-supabase-prod-simple.sh`

### Checklist

- [ ] Revogar/rotacionar token exposto em provedor externo.
- [ ] Substituir segredos por placeholders.
- [ ] Garantir leitura de secrets via env/secrets manager.
- [ ] Confirmar que script falha se variável crítica não for fornecida.
- [ ] Revisar histórico local para evitar reintrodução dos mesmos valores.

### Critério de saída

- Nenhum segredo real permanece nesses arquivos.
- Time confirma rotação das credenciais antigas.
- Gate obrigatório liberado para iniciar qualquer outro bloco.

### Responsável principal

- Security owner

## 4) Bloco P0-B (Runtime único do chatbot)

### Escopo

- Fechar decisão oficial de runtime do chatbot com critério objetivo.
- Eliminar ambiguidade operacional da implementação paralela.

### Decisão alvo da fase atual

- **Caminho oficial (alvo):** Flask em `/api/chatbot/*` via `backend/routes/chatbot.py`.
- **Caminho a desativar/legado:** FastAPI em `services/chatbot/app.py` (`/api/chat`, `/api/chat/ws`) fora do fluxo padrão.
- **Critério para confirmar a decisão:** o caminho oficial deve estar ativo no frontend principal, responder health e chat autenticado, e não pode haver consumo ativo do caminho legado.

### Arquivos alvo

- `backend/routes/chatbot.py`
- `services/chatbot/app.py`
- `frontend/src/components/chat/ChatWidget.tsx`
- `frontend/src/components/Chatbot.tsx`
- `frontend/src/utils/api.ts`

### Checklist

- [ ] Formalizar decisão arquitetural em texto (1 fonte oficial).
- [ ] Definir explicitamente no código/docs qual é o caminho oficial e qual é legado.
- [ ] Desativar caminho não oficial (ou marcar explicitamente como legado inativo, sem uso no fluxo principal).
- [ ] Garantir que frontend usa apenas o caminho decidido.
- [ ] Confirmar que endpoint de health do caminho oficial responde.

### Critério de saída

- Existe uma única rota de execução oficial de chatbot no ambiente local.
- Não há consumo ativo do caminho alternativo na UI principal.
- Critério de decisão registrado e atendido (health + chat autenticado + frontend sem legado).

### Responsável principal

- Backend owner (com suporte do Frontend owner)

## 5) Bloco P0-C (Auth sem ambiguidade)

### Escopo

- Remover dependência prática de `JWT_SECRET` legado no fluxo ativo.

### Arquivos alvo

- `backend/utils/auth_utils.py`
- `backend/utils/auth_utils_supabase.py`
- `backend/services/supabase_auth_service.py` (sessão Auth **não** pode poluir o cliente PostgREST global)
- `backend/database/connection.py` (chave Supabase JWT: validar `role=service_role` no backend)
- `scripts/dev/up.sh`
- `scripts/setup-env.sh`
- `.env.example`

### Checklist

- [ ] Mapear exatamente onde `JWT_SECRET` ainda influencia runtime.
- [ ] Migrar scripts para `SUPABASE_JWT_SECRET` + `SECRET_KEY`.
- [ ] Ajustar validações para falhar com mensagem clara quando env crítica faltar.
- [ ] Validar login autenticado com token válido.
- [ ] Validar bootstrap após login.
- [ ] Validar carregamento do dashboard autenticado.
- [ ] Validar acesso de contas (`accounts`) com autenticação.
- [ ] Regressão **42501:** após `GET /api/auth/me`, `POST /api/accounts` (criar conta) deve responder **201** — confirma que o singleton não ficou com `set_session` do utilizador.
- [ ] Validar chat autenticado no caminho oficial.

### Critério de saída

- Fluxo de auth/chat funciona sem fallback legado.
- Scripts de setup/subida não exigem `JWT_SECRET` como caminho principal.
- Validação ponta a ponta de login -> bootstrap -> dashboard -> accounts (**incl. POST criar conta após `me`**) -> chat autenticado concluída.

### Responsável principal

- Backend owner

## 6) Bloco P0-D (Documentação mínima crítica)

### Escopo

- Alinhamento operacional mínimo da fase atual (não executar revisão documental ampla).
- Corrigir somente núcleo operacional: porta, endpoints e política de segredo vigente.

### Arquivos alvo

- `EXECUTION_RUNBOOK.md` (este ficheiro — registro de execução e gates)
- `ARCHITECTURE.md`
- `TODO.md`
- Documentos operacionais que ainda indiquem `:5000`, `/api/chat*` legado, `JWT_SECRET` como principal.

### Checklist

- [ ] Padronizar backend para `:8001`.
- [ ] Padronizar chat para `/api/chatbot/*` (se essa for a decisão do bloco P0-B).
- [ ] Padronizar política de segredo para estratégia vigente.
- [ ] Inserir referência explícita ao `EXECUTION_BASELINE.md`.
- [ ] Evitar expandir escopo para documentação histórica ampla nesta fase.

### Critério de saída

- Operação local consegue subir e testar fluxo básico apenas com docs atualizados.
- Escopo documental manteve foco operacional mínimo da fase.

### Responsável principal

- Infra/Docs owner

## 7) Bloco P1 (Confiabilidade e consistência)

### Escopo

- Contrato único de resposta de chat.
- Matriz única de configuração por ambiente.
- Pipeline de deploy com build explícito.

### Arquivos alvo

- `frontend/src/components/chat/ChatWidget.tsx`
- `frontend/src/components/Chatbot.tsx`
- `frontend/src/utils/api.ts`
- `backend/app.py`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `frontend/Dockerfile`
- `mobile/src/api/client.ts`

### Checklist

- [ ] Definir shape único de resposta do chat e aplicar em todos os consumidores.
- [ ] Unificar origem de `VITE_API_URL` por ambiente.
- [ ] Garantir alinhamento de `CORS_ORIGINS` entre runtime e compose.
- [ ] Tornar explícito no fluxo de produção o passo de build frontend.

### Critério de saída

- Web/mobile/chat usam padrões consistentes de URL, token e payload.

### Responsável principal

- Frontend owner + Backend owner + Infra/Docs owner

## 8) Bloco P2 (Dívida técnica controlada)

### Escopo

- Reduzir duplicações e ruído de documentação legado.

### Arquivos alvo

- `scripts/dev/up.sh`
- `alca_start_mac.sh`
- `scripts/setup-env.sh`
- `.env.example`
- `backend/.env.example`
- `docs/*`
- `legacy/*`

### Checklist

- [ ] Consolidar defaults sensíveis em fonte única.
- [ ] Marcar claramente conteúdo legado.
- [ ] Remover exemplos que induzam configuração incorreta.

### Critério de saída

- Onboarding técnico não depende de interpretação de múltiplas fontes conflitantes.

### Responsável principal

- Infra/Docs owner

## 9) Ordem macro recomendada

1. P0-A Segurança imediata
2. P0-B Runtime único do chatbot
3. P0-C Auth sem ambiguidade
4. P0-D Documentação mínima crítica
5. P1 Confiabilidade e consistência
6. P2 Dívida técnica

## 10) Gate de validação entre blocos

- **Gate 1 (após P0-A):** segurança saneada.
- **Gate 2 (após P0-B):** runtime de chat com caminho oficial único.
- **Gate 3 (após P0-C):** auth estável sem fallback legado.
- **Gate 4 (após P0-D):** docs operacionais suficientes para execução sem ambiguidade.
- **Gate 5 (após P1):** consistência entre canais e ambientes.

## 11) Registro rápido de execução (preencher durante a fase)

- **Data início:** 2026-04-14
- **Última atualização runbook:** 2026-04-17 (módulo administrativo, UI admin em modo escuro, exclusão total de conta, logs; ver secção **Admin** abaixo)
- **Atualização anterior:** 2026-04-16 (revisão operacional alinhada ao repo: RLS `00003`/`00004`, smoke estendido, fix singleton Supabase em `supabase_auth_service`, warning de role JWT em `connection.py`, P0-B UI/chatbot)
- **Bloco atual:** P0-D (documentação mínima crítica) e, em paralelo, **P0-B** (runtime único do chatbot) conforme capacidade do time
- **Responsável:** Backend owner + Infra/Docs owner (conforme trilha)
- **Status (frente auth/bootstrap/tenant):** migrations `20260416000001` … `20260416000004` aplicáveis em Supabase (reconcile + RLS users/tenants/members + **accounts** + **categories/transactions** via `tenant_members`); smoke **`/api/health` → bootstrap → me → accounts → categories → transactions`** (`scripts/prod/smoke-auth-bootstrap.sh`); regressão de conflito email legado coberta em CI por `backend/tests/unit/test_auth_bootstrap_service.py` (ex.: `test_bootstrap_reconciles_stale_email_without_memberships`, `test_bootstrap_blocks_conflicting_email_when_legacy_has_membership`) e `test_tenant_context.py` (fallback bootstrap); ver secção CI acima.
- **Histórico P0-C (contexto):** `JWT_SECRET` deixou de ser caminho principal do runtime ativo; `scripts/dev/up.sh` valida `SUPABASE_JWT_SECRET` e `SECRET_KEY`; fluxo principal é token Supabase nos helpers Supabase.
- **Próximo passo imediato:** fechar **P0-D** (docs mínimas + este runbook alinhado), avançar **P0-B** (chatbot único / sem consumo legado na UI) e, quando existir ambiente de teste dedicado, correr **E2E (Playwright)** manualmente ou reintegrar no CI com `if` condicionado a secrets.

### Atualização de execução — importação OFX Nubank (compatibilidade jan/fev/mar 2026)

- **Contexto:** importação de OFX do Nubank falhava com `400` na autodetecção de conta (`Não foi possível identificar a conta de destino...`) e havia perda de transações por parsing de valores negativos no fluxo de importação bancária.
- **Causa raiz (conta):**
  - variações de layout OFX Nubank (`BANKID` com zero à esquerda, `ACCTID` com hífen, `ORG=NU PAGAMENTOS S.A.`) não eram normalizadas de forma consistente;
  - uso de `find(... ) or find(...)` em elementos XML podia descartar nós válidos sem filhos (`Element` vazio é falsey), degradando extração de `BANKID/BRANCHID/ACCTID`.
- **Causa raiz (valores):**
  - parser de importação reaproveitava utilitário monetário global que rejeita `<= 0`; em extrato bancário isso removia débitos legítimos (valores negativos), reduzindo contagem importada.
- **Correções aplicadas (backend):**
  - `backend/services/account_detector.py`
    - normalização de instituição (`NU PAGAMENTOS` -> `Nubank`);
    - suporte a códigos bancários com e sem zero à esquerda (`0260/260`, etc.);
    - normalização de número de conta (remove pontuação/hífen);
    - fallback por nome de ficheiro (`NU_93015865_...ofx`) quando `ACCTID` ausente;
    - helper `_find_first_element(...)` para evitar curto-circuito indevido de nós XML.
  - `backend/routes/transactions.py`
    - passa `file.filename` para `extract_account_info_from_ofx(...)`, habilitando fallback e heurísticas por nome do ficheiro.
  - `backend/services/import_service.py`
    - parse monetário assinado para importação (`_parse_signed_money_value`) preservando sinal;
    - enriquecimento de OFX em `raw_data` (`memo_original`, `memo_type`, `counterparty_name`, `is_reversal`, `pix_details`);
    - normalização de descrição para Pix (`Pix recebido/enviado`, `Estorno Pix`) mantendo memo original para rastreio.
  - `backend/tests/test_import.py`
    - cobertura para layout real Nubank (`BANKID 0260`, `ACCTID` com hífen, `ORG NU PAGAMENTOS S.A.`);
    - cobertura para fallback por filename sem `ACCTID`;
    - cobertura para `CCACCTFROM` (cartão) e normalização de descrição Pix + `pix_details`.
- **Validação com ficheiros reais (Downloads):**
  - `NU_93015865_01JAN2026_31JAN2026.ofx` -> **119** transações;
  - `NU_93015865_01FEV2026_28FEV2026.ofx` -> **167** transações;
  - `NU_93015865_01MAR2026_15MAR2026.ofx` -> **74** transações;
  - conta detectada consistentemente: instituição `Nubank`, `account_number=93015865`, `bank_id=0260`, `branch_id=1`.
- **Status:** frente OFX Nubank estabilizada para lote mensal (jan/fev/mar) com deduplicação por `FITID` preservada no fluxo de importação.

### Atualização de execução — bootstrap/tenant (resolvido para fluxo validado)

- **Contexto:** após resolver a frente JWT (token Supabase válido aceito pelo backend), o bloqueio remanescente era `tenant_bootstrap_failed` em `POST /api/auth/bootstrap`, com cascata `tenant_required` em `/api/dashboard` e `/api/accounts`.
- **Causa raiz:** incompatibilidade da versão do client Supabase em uso com encadeamento `.insert(...).select(...)` no path crítico de bootstrap/tenant. O builder retornado por `insert()` não expunha `select()`, disparando `AttributeError` e interrompendo criação de estado mínimo.
- **Correções mínimas aplicadas:**
  - `backend/repositories/base_repository_supabase.py`: ajuste de criação para `insert(...).execute()` (removido `.select("*")` após insert no repositório base).
  - `backend/repositories/tenant_repository.py`: ajuste em `ensure_default_tenant()` para `insert(...).execute()` (removido `.select("id")` após insert de tenant).
- **Validação runtime (Bearer válido):**
  - `POST /api/auth/bootstrap` -> **200**
  - `GET /api/dashboard` -> **200**
  - `GET /api/accounts` -> **200**
- **Status da frente bootstrap/tenant:** resolvida para o fluxo validado (bootstrap cria/resolve tenant e elimina a cascata `tenant_required` nas rotas testadas).

### Atualização de execução — login/register 500 (concluída)

- **Contexto:** após a estabilização de bootstrap/tenant, a frente remanescente era `500` em `POST /api/auth/login` e `POST /api/auth/register`.
- **Causa estrutural:** o `500` de write incompatível em `public.users` **já estava eliminado** pela correção anterior no repositório base (remoção de encadeamento incompatível após `insert`).
- **Validação runtime (frente login/register):**
  - `POST /api/auth/register` -> **201** (validado)
  - `POST /api/auth/login` no cenário `Email not confirmed` -> **não retorna 500** (validado)
- **Ajuste mínimo de resposta de autenticação:** cenário `Email not confirmed` mapeado para **401** com mensagem adequada de autenticação.
- **Status da frente login/register 500:** concluída para o escopo definido.

### Atualização de execução — microfrente register rate limit (concluída)

- **Causa:** `email rate limit exceeded` retornado pelo Supabase Auth no fluxo de `POST /api/auth/register`.
- **Antes:** a rota de register não tratava explicitamente esse caso e devolvia **500**.
- **Agora:** o caso de rate limit foi mapeado para resposta controlada, retornando **429** com mensagem amigável.
- **Mensagem final:** `Muitas tentativas de cadastro no momento. Tente novamente em instantes.`
- **Validação confirmada:** `POST /api/auth/register` respondendo **429** com payload de erro amigável no cenário de rate limit.

### Atualização de execução — saneamento bootstrap/tenant + RLS (concluída)

- **Contexto:** ambiente apresentava conflito de identidade por email entre `auth.users` e `public.users`, causando `POST /api/auth/bootstrap` -> **503** (`tenant_bootstrap_failed`) e cascata `tenant_required` em páginas de dados.
- **Causa raiz:** email já vinculado a `public.users` legado com workspace/membership ativo para outro `id`, impedindo reconciliação do usuário autenticado atual.
- **Correção de dados aplicada (SQL):**
  - `supabase/migrations/20260416000001_reconcile_public_users_with_auth.sql`
  - Reconciliação por email normalizado (`auth.users` x `public.users`), migração de `tenant_members`/`user_id` para o `auth.users.id` canônico e limpeza segura de legados sem referências.
  - Hardenings de idempotência:
    - fallback de email temporário interno para evitar `users_email_key` durante reconciliação;
    - deleção dinâmica para tabelas opcionais (evita `42P01` quando tabela não existe).
- **Correção de RLS aplicada (SQL):**
  - `supabase/migrations/20260416000002_rls_bootstrap_hardening.sql`
  - Policies críticas em `public.users`, `public.tenant_members` e `public.tenants` para `authenticated`, compatíveis com `auth.uid()` e `current_app_user_id()`.
- **Accounts RLS (`20260416000003_accounts_rls_tenant_membership.sql`):**
  - Problema: policies antigas podiam depender de `current_tenant_id()` / claim `tenant_id` no JWT; o access token Supabase padrão **não** inclui `tenant_id` → `42501` em `accounts` mesmo com membership válido.
  - Solução: `SELECT`/`INSERT`/`UPDATE`/`DELETE` em `public.accounts` exigem `auth.uid() = user_id`, `tenant_id` preenchido e **EXISTS** em `tenant_members` para `(tenant_id, user_id)`, alinhado ao bootstrap.
- **Categories + transactions RLS (`20260416000004_categories_transactions_rls_tenant_membership.sql`):**
  - Mesmo racional que `00003`: evitar `42501` em leitura/escrita PostgREST quando o JWT não traz `tenant_id`; policies recriadas com `auth.uid() = user_id` e **EXISTS** em `tenant_members` para o par `(tenant_id, user_id)`.
- **Validação pós-migration:**
  - Script de verificação: `scripts/sql/verify_bootstrap_rls_and_data.sql`
  - Policies confirmadas:
    - `users_select_own`, `users_update_own`, `users_insert_own`
    - `tenant_members_select_own`
    - `tenants_select_member`
    - `accounts_tenant_policy_select`, `accounts_tenant_policy_insert`, `accounts_tenant_policy_update`, `accounts_tenant_policy_delete` (após `00003`)
    - `categories_tenant_policy_*` e `transactions_tenant_policy_*` (após `00004`; inspeção via query no fim de `verify_bootstrap_rls_and_data.sql`)
- **Smoke runtime final (local):**
  - `GET /api/health` -> **200**
  - `POST /api/auth/bootstrap` -> **200**
  - `GET /api/auth/me` -> **200**
  - `GET /api/accounts` -> **200**
  - `GET /api/categories` e `GET /api/transactions` incluídos no script de smoke (mesma ordem de dependência: bootstrap antes de dados tenant-aware).
  - Sweep de endpoints de páginas (dashboard/accounts/categories/transactions/planning/goals/reports/tenants) -> **200** no estado validado.
- **Status:** frente de bootstrap/workspace resolvida no runtime local validado.

### Atualização de execução — cliente Supabase singleton e 42501 em `accounts`

- **Sintoma:** `POST /api/accounts` com **500** / detalhe Postgres **42501** (`new row violates row-level security policy for table "accounts"`), por vezes só após o utilizador chamar `GET /api/auth/me` ou rotas que usam `SupabaseAuthService.get_user`.
- **Causa raiz:** `auth.set_session(access_token, …)` no **mesmo** cliente retornado por `get_supabase()` fazia o PostgREST passar a enviar o JWT do utilizador nas operações seguintes do repositório. As policies antigas exigiam `tenant_id = current_tenant_id()` derivado de claims que o access token padrão **não** inclui → falha no `WITH CHECK` do INSERT.
- **Correções aplicadas no backend:**
  - `backend/services/supabase_auth_service.py`: `get_user` usa apenas `auth.get_user(access_token)` **sem** `set_session` no singleton; `sign_out` usa **cliente Supabase efémero** (`create_client` local) para não poluir o global.
  - `backend/database/connection.py`: se a chave for JWT e o payload `role` ≠ `service_role`, regista **warning** (anon/authenticated no backend → RLS em writes).
- **Defesa em profundidade (SQL):** migrations `20260416000003` e `20260416000004` recriam policies de `accounts`, `categories` e `transactions` com **EXISTS** em `tenant_members` para `(tenant_id, auth.uid())`, alinhado ao modelo multi-tenant sem claim `tenant_id` no JWT.
- **Validação sugerida:** smoke `scripts/prod/smoke-auth-bootstrap.sh` + fluxo manual: login → me → criar conta → categorias/transações.

### Atualização de execução — CI, E2E e operações VPS (2026-04-16)

- **GitHub Actions — CI principal (`.github/workflows/ci.yml`):**
  - Job **Backend Tests**: corre subconjunto de unitários (bootstrap/tenant/transações + `test_auth_utils` sem testes JWT que exigem Mongo), incluindo regressão de bootstrap (`test_auth_bootstrap_service.py`: reconciliação de email legado sem membership vs bloqueio quando legado tem workspace; `test_tenant_context.py`: fallback), com `pymongo` instalado para import do `conftest`, `SECRET_KEY` com **≥ 32 caracteres** (exigência do `app.py`), `SKIP_DB_INIT=true` e chave Supabase em formato `eyJ…` ou `sb_secret_` (validação em `database/connection.py`).
  - **Cobertura:** o `backend/pytest.ini` fixa `--cov-fail-under=70` sobre `--cov=.`; no CI o job usa `-o addopts=…` e **`--cov-fail-under=0`** para não falhar só porque a suite parcial não cobre o monólito inteiro — o gate deste job é **falha de teste**, não percentagem global.
  - **Frontend — typecheck (`npx tsc --noEmit`):** o job compila todo o `src/`. O componente **`Chatbot.tsx`** (não montado no `App` por defeito) deve importar a instância axios **`default`** de `utils/api.ts` e usar um wrapper local para `POST /chatbot/chat`, em vez de depender só do export nomeado `chatbotAPI` — evita **`TS2614`** se o ficheiro de API divergir entre branches ou o export não existir no tipo visto pelo compilador.
  - **E2E Playwright:** removido do pipeline em cada push (evitava card **skipped** com `if: false`). Passa a existir workflow manual **`.github/workflows/e2e-playwright.yml`** — em GitHub: **Actions → E2E (Playwright) → Run workflow**. Quando houver stack E2E estável (API + Supabase de teste), reintegrar ou enriquecer esse ficheiro com secrets e `on: push` seletivo.
- **Backend — import do chatbot:** `backend/routes/chatbot.py` usa **`ChatbotRepository` lazy** (`_get_chatbot_repo()`): o import do módulo **não** chama `get_db()`; a ligação ao Supabase ocorre só na primeira rota que persiste ou valida conversas. Isto alinha o carregamento do `app` com `SKIP_DB_INIT=true` (CI / smoke sem registar blueprints de dados).
- **VPS / disco:** `No space left on device` em `git pull` costuma vir de **`/var/lib/containerd`** (snapshots + blobs). Liberar com `docker builder prune -af`, `docker image prune -a -f` e, se necessário, `docker compose down` + prune antes de voltar a fazer pull/build. Monitorizar `df -h /`.
- **Incidente tenant/bootstrap (enxuto):** `backend/EXECUTION_TENANT_BOOTSTRAP_CHECKLIST.md`
- **Smoke pós-deploy:** `scripts/prod/smoke-auth-bootstrap.sh` — inferir base com `SMOKE_BASE_URL` / `API_BASE_URL` / `VITE_API_URL` / `FRONTEND_URL` (URL **sem** sufixo `/api`; o script monta `$BASE_URL/api`); `ACCESS_TOKEN` por env ou stdin; valida **health, bootstrap, me, accounts, categories, transactions** (todos `200`).

### Atualização de execução — P0-B consumo oficial / UI (auditoria 2026-04-16)

- **Frontend:** `App.tsx` monta apenas **`ChatWidget`** → HTTP para **`/api/chatbot/chat`** (base `VITE_CHAT_API_URL` ou `/api/chatbot` em prod).
- **`Chatbot.tsx`:** não está referenciado no `App.tsx`; usa a mesma base URL e auth que **`api`** (`frontend/src/utils/api.ts`) e chama **`POST /api/chatbot/chat`** via wrapper local (alinhado ao `ChatWidget` e ao export `chatbotAPI` no mesmo ficheiro).
- **`chatbotAPI` (export em `api.ts`):** contrato canónico HTTP para chat no cliente; comentário explícito contra `/api/chat` e `/api/chat/ws` legados. O `Chatbot.tsx` duplica só o método `chat` em cima do `api` default para o typecheck não depender do export nomeado.
- **Contas / cartões:** unicidade de nome no backend é por **(utilizador, tenant, nome, tipo)** — uma **carteira** e um **cartão de crédito** podem partilhar o mesmo nome (ex.: “Nubank”); duplicata continua bloqueada no **mesmo tipo**. No UI de cartão, erros `4xx` do axios devem mostrar `response.data.error` quando existir.
- **`mobile/`:** sem referências a endpoints de chat legados (grep na data acima).
- **Compose:** `docker-compose.yml` / `docker-compose.prod.yml` não sobem `services/chatbot` por omissão; OpenClaw (gateway/bridge) é stack à parte.
- **Legado no repo:** `services/chatbot/app.py` (FastAPI) — ver **`services/chatbot/README.md`**. Próximo passo formal de P0-B: arquivoção/remoção após checklist de validação em produção, sem reintroduzir consumo `/api/chat*` na UI.

### Atualização de execução — Módulo administrativo, UI dark, exclusão total e `/api/auth/me` (2026-04-17)

- **Contexto:** painel admin com cartões claros no tema escuro; necessidade de **exclusão permanente** de conta (além de desativação lógica); risco de **429** por limite global do Flask-Limiter em rajadas de `GET /api/auth/me` (bootstrap, HMR, vários componentes).
- **Base de dados:** migration `supabase/migrations/20260417000002_admin_users_audit_notifications.sql` — `public.users` com `role`/`status`/timestamps de ciclo de vida; `public.admin_audit_logs`; `public.admin_notification_delivery`; checks e índices. **Aplicar no Supabase de cada ambiente** na ordem correta relativamente às migrations já existentes (`20260416000001`… e anteriores).
- **Backend (Flask):**
  - Rotas em `backend/routes/admin.py`: estatísticas, listagem/filtros de utilizadores, papel e estado, avisos de inatividade, export CSV, `POST /api/admin/users/<id>/purge` com corpo `{ "confirm_email": "<email do alvo>" }` (validação de e-mail, não auto-purge, não último admin).
  - **Purge:** apaga utilizador em **Auth** via `auth.admin.delete_user` (cliente criado com **`SUPABASE_SERVICE_ROLE_KEY`** obrigatória) e remove a linha em **`public.users`** (`AdminUserRepository.delete_user_row`); dados da app ligados ao `user_id` seguem **ON DELETE CASCADE** onde definido.
  - Serviços/repositórios: `admin_user_service`, `admin_user_repository`, `admin_audit_repository`, `admin_notification_service`, ciclo de vida / atividade conforme ficheiros em `backend/services/`.
  - **`GET /api/auth/me`:** `@limiter.exempt` em `backend/routes/auth.py` para não consumir o teto global por refreshes legítimos.
- **Frontend:** páginas `AdminDashboard`, `UserManagement`, `UserDetail`, `AdminLogs` com superfícies Tailwind alinhadas a tokens `dark-surface` / `dark-border` / `dark-text-*`; modal de purge com confirmação por e-mail; `adminAPI.purgeUser`; entrada de ação **`purge_user`** na UI de logs; campo de pesquisa admin com `id`/`name` para acessibilidade.
- **Script operacional (dev/staging):** `scripts/supabase-wipe-all-data.sql` — truncates em `public.*` + remoção em `auth.users`; **nunca** correr em produção sem backup e confirmação explícita do projeto no dashboard Supabase.
- **Validação sugerida:** login como admin → `/admin/dashboard` → `/admin/users` → ações não destrutivas; purge apenas em utilizador de teste com `SUPABASE_SERVICE_ROLE_KEY` configurada; `GET /api/auth/me` sem 429 em navegação normal; logs em `/admin/logs` com ação `purge_user` após purge.

## 12) Matriz operacional simplificada

| Bloco | Arquivos afetados (principal) | Risco dominante | Teste de validação |
|---|---|---|---|
| P0-A | `.cursor/mcp.json.recommended`, `scripts/hotfix-supabase-prod-simple.sh` | Vazamento/uso indevido de segredo | Confirmar placeholders + rotação concluída |
| P0-B | `backend/routes/chatbot.py`, `services/chatbot/app.py`, `frontend/src/components/chat/ChatWidget.tsx`, `frontend/src/components/Chatbot.tsx`, `frontend/src/utils/api.ts` | Runtime duplicado e comportamento ambíguo | `GET /api/chatbot/health` + chat autenticado no caminho oficial |
| P0-C | `backend/utils/auth_utils.py`, `backend/utils/auth_utils_supabase.py`, `scripts/dev/up.sh`, `scripts/setup-env.sh`, `.env.example` | Regressão de auth por legado JWT | Fluxo: login -> bootstrap -> dashboard -> accounts -> chat autenticado |
| P0-D | `EXECUTION_RUNBOOK.md`, `ARCHITECTURE.md`, `TODO.md`, docs operacionais críticos | Operação com premissas erradas | Subida local guiada somente por docs mínimos atualizados |
| P1 | `frontend/src/components/chat/ChatWidget.tsx`, `frontend/src/components/Chatbot.tsx`, `frontend/src/utils/api.ts`, `backend/app.py`, `docker-compose*.yml` | Inconsistência entre canais/ambientes | Teste de contrato único de chat + matriz env/CORS |
| P2 | `scripts/dev/up.sh`, `alca_start_mac.sh`, `scripts/setup-env.sh`, `.env.example`, `backend/.env.example`, `docs/*`, `legacy/*` | Ruído operacional e dívida recorrente | Checklist de onboarding sem conflito de fonte |

## 13) Patch units sugeridos

- **Patch 1 (P0-A):** saneamento e rotação de segredos expostos.
  - Escopo: apenas arquivos de segredo/hotfix.
  - Resultado esperado: gate de segurança liberado.
- **Patch 2 (P0-B):** definição e aplicação do runtime único de chatbot.
  - Escopo: backend/chatbot + consumidores frontend.
  - Resultado esperado: caminho oficial único em produção local.
- **Patch 3 (P0-C):** remoção de dependência de `JWT_SECRET` legado no fluxo ativo.
  - Escopo: auth utils + scripts/env.
  - Resultado esperado: validação ponta a ponta concluída.
- **Patch 4 (P0-D):** alinhamento documental mínimo operacional.
  - Escopo: arquitetura/todo/docs críticos apenas.
  - Resultado esperado: execução local sem ambiguidade de instrução.
- **Patch 5 (P1):** padronização de contrato de chat e matriz de configuração.
  - Escopo: frontend + backend + compose/dockerfile.
  - Resultado esperado: consistência entre web/mobile/chat e ambientes.
- **Patch 6 (P2):** limpeza de dívida técnica e fontes legadas conflitantes.
  - Escopo: scripts auxiliares e documentação histórica.
  - Resultado esperado: redução de retrabalho operacional.

## 14) Templates de PR (copiar e usar)

### PR 1 - P0-A

- **Title:** `P0-A: sanitiza segredos expostos e bloqueia uso sem env`

```md
## Summary
- Remove segredos versionados e substitui por placeholders seguros.
- Garante que scripts sensíveis dependam de variáveis obrigatórias em runtime.
- Fecha o gate de segurança para liberar os próximos blocos do runbook.

## Test plan
- [ ] Confirmar que `.cursor/mcp.json.recommended` não contém token real.
- [ ] Confirmar que `scripts/hotfix-supabase-prod-simple.sh` não contém chave hardcoded.
- [ ] Executar validação de ausência de segredos por busca no diff dos arquivos alterados.
- [ ] Validar que o script falha com mensagem clara quando env crítica não é fornecida.
- [ ] Confirmar rotação externa dos tokens previamente expostos.
```

### PR 2 - P0-B

- **Title:** `P0-B: define runtime oficial do chatbot e isola caminho legado`

```md
## Summary
- Formaliza Flask (`/api/chatbot/*`) como runtime oficial do chatbot nesta fase.
- Isola/desativa o caminho legado FastAPI para remover ambiguidade operacional.
- Alinha consumo frontend ao caminho oficial único.

## Test plan
- [ ] `GET /api/chatbot/health` retorna sucesso no ambiente local.
- [ ] Envio de mensagem no chat autenticado funciona no caminho oficial.
- [ ] Verificar que UI principal não consome endpoints legados (`/api/chat` ou `/api/chat/ws`).
- [ ] Confirmar que referências ao caminho legado estão marcadas como inativas/legado.
```

### PR 3 - P0-C

- **Title:** `P0-C: remove ambiguidade JWT legado e valida fluxo auth ponta a ponta`

```md
## Summary
- Remove dependência prática de `JWT_SECRET` legado no fluxo ativo.
- Padroniza scripts/validação para estratégia atual (`SUPABASE_JWT_SECRET` + `SECRET_KEY`).
- Endurece previsibilidade de autenticação em runtime local.

## Test plan
- [ ] Login autenticado funcionando com token válido.
- [ ] Bootstrap executa corretamente após login.
- [ ] Dashboard autenticado carrega sem regressão.
- [ ] Endpoints de accounts respondem com autenticação válida.
- [ ] Chat autenticado funciona no caminho oficial.
- [ ] Subida/setup não dependem de `JWT_SECRET` como caminho principal.
```

### PR 4 - P0-D

- **Title:** `P0-D: alinha documentação operacional mínima ao runtime atual`

```md
## Summary
- Atualiza somente documentação operacional mínima da fase atual.
- Alinha porta backend, endpoints oficiais e política de segredo vigente.
- Evita revisão documental ampla para não expandir escopo.

## Test plan
- [ ] Docs críticos indicam backend em `:8001`.
- [ ] Docs críticos indicam chatbot oficial em `/api/chatbot/*`.
- [ ] Docs críticos refletem estratégia de segredo vigente.
- [ ] Referência explícita ao `EXECUTION_BASELINE.md` adicionada.
- [ ] Time consegue subir e validar fluxo básico usando apenas docs mínimos atualizados.
```

### PR 5 - P1

- **Title:** `P1: padroniza contrato de chat e matriz de configuração por ambiente`

```md
## Summary
- Unifica contrato de resposta de chat entre consumidores frontend.
- Padroniza matriz de configuração (`VITE_API_URL`, CORS e afins) por ambiente.
- Reduz risco de inconsistência entre web/mobile/chat e compose.

## Test plan
- [ ] Fluxo de chat usa shape único de resposta em todos os consumidores ativos.
- [ ] `VITE_API_URL` está consistente por ambiente (dev/homolog/prod).
- [ ] `CORS_ORIGINS` alinhado entre runtime e compose.
- [ ] Build/deploy de produção deixa explícito e validado o passo de build frontend.
```

### PR 6 - P2

- **Title:** `P2: reduz dívida técnica de defaults e limpa documentação legada`

```md
## Summary
- Consolida defaults sensíveis para reduzir duplicação em scripts.
- Remove ruído operacional de documentação legada conflitante.
- Melhora previsibilidade de onboarding e manutenção.

## Test plan
- [ ] Scripts principais não redefinem defaults sensíveis de forma conflitante.
- [ ] `.env.example` e `backend/.env.example` permanecem coerentes com runtime.
- [ ] Conteúdo legado está claramente marcado.
- [ ] Onboarding técnico não depende de múltiplas fontes contraditórias.
```

---

## 6) Contas a pagar ↔ transações (2026-04-17)

### Escopo

- Rastrear **origem** das linhas do livro: `transactions.entry_source` (`manual` | `csv` | `ofx`) e `transactions.fitid` (OFX).
- Ligar contas a pagar à transação de origem: `financial_expenses.source_transaction_id` (único quando preenchido).
- API `POST /api/financial-expenses/from-transactions` com `{ "transaction_ids": ["…"] }` (só despesas; idempotente).
- UI: secção em Contas a pagar para colar UUIDs; coluna **Origem** nas tabelas; lista de Transações com etiqueta CSV/OFX.

### Arquivos / migration

- `supabase/migrations/20260417120001_transactions_entry_source_and_payable_source_tx.sql` — aplicar no Supabase de cada ambiente antes de usar os novos campos. O próprio ficheiro inclui no cabeçalho instruções de aplicação (`supabase db push` / SQL Editor) e notas de rollback manual.
- Backend: `backend/routes/transactions.py`, `backend/services/transaction_service.py`, `backend/routes/financial_expenses.py`, `backend/services/financial_expense_service.py`, `backend/repositories/financial_expense_repository_supabase.py`, `backend/utils/financial_expense_category_map.py`.
- Frontend: `frontend/src/utils/api.ts`, `frontend/src/types/transaction.ts`, `frontend/src/components/transactions/TransactionList.tsx`, `frontend/src/components/financial-expenses/FinancialExpensesPage.tsx`.

### Checklist pós-migration

- [ ] Import CSV/OFX cria transações com `entry_source` preenchido (`csv` ou `ofx`).
- [ ] Criação manual de transação grava `entry_source = manual`.
- [ ] `POST /financial-expenses/from-transactions` devolve `created` / `skipped` / `errors` e não duplica o mesmo `transaction_id`.
- [ ] Build frontend (`npm run build`) sem erros.
