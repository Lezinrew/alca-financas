# Prompt — Codex: entender o projeto e refatorar tenant / bootstrap

Copie o bloco **«Texto do prompt»** para o Codex (ou outro agente de código). Anexe ou indique os caminhos dos ficheiros listados em **Contexto do repositório**.

---

## Texto do prompt (copiar daqui)

```
És um engenheiro sénior em Python (Flask) e TypeScript (React). Vais trabalhar no repositório **Alça Finanças**: app de finanças pessoais com **Flask 3** + **Supabase (PostgreSQL)** + **React/Vite** no frontend.

## Objetivo

**Entender** o modelo multi-tenant e **refatorar** o código para que o bug de workspace/tenant fique **impossível de regressar** (ordem de operações, queries Supabase, testes e mensagens claras). Não alargues o escopo a features novas.

## Sintoma do bug (produção)

- Utilizador autentica com **Supabase Auth** (JWT válido).
- **`POST /api/auth/bootstrap`** e depois **`GET /api/accounts`**, **`/api/categories`**, **`/api/transactions`**, etc. devolvem **403** com corpo:
  - `{"code":"tenant_required","error":"Nenhum workspace disponível. Não foi possível criar um workspace padrão."}`
- Ou o utilizador via nos logs/console **403** em todas as páginas após login.

## Causas raiz (deves validar no código e consolidar)

1. **Ordem do decorator vs FK**  
   `tenant_members.user_id` referencia **`public.users(id)`** (migração `006_create_tenants.sql`).  
   Se **`@require_tenant`** correr **antes** do corpo de **`bootstrap_user`**, o código tenta criar membership **antes** de existir linha em **`public.users`** → falha silenciosa → `ensure_default_tenant` devolve `None` → 403.

   **Correção esperada:** em `POST /api/auth/bootstrap`, só **`@require_auth`** no topo; garantir **`public.users`** primeiro; só depois criar tenant + `tenant_members`.

2. **Query PostgREST frágil**  
   Listar workspaces com embed **`tenant_members` + `tenants!inner(...)`** pode falhar ou vir vazio se a relação não estiver exposta como o cliente espera → o backend julga que não há tenant.

   **Correção esperada:** `TenantRepository` deve resolver memberships com **`tenant_members` apenas** (select `tenant_id`, `role`) e, se necessário, **N queries** (ou batch) a **`tenants`** por `id`, **sem** depender de embed implícito para o caminho crítico de login.

3. **Tenant “órfão”**  
   Se **`tenants`** foi inserido mas **`tenant_members`** falhou (ex.: FK), um segundo insert de tenant pode falhar por **`slug` UNIQUE** (`personal-{user_id}`). O código deve **recuperar** o tenant existente pelo slug e **apenas** inserir o membership.

4. **Deploy**  
   Respostas com `tenant_required` no **bootstrap** indicam por vezes **imagem Docker antiga** (código sem o fix). A refatoração deve incluir **comentário mínimo** ou **teste** que tornem óbvio que o bootstrap não pode voltar a ter `@require_tenant` antes do user existir.

## Ficheiros que deves ler primeiro

- `backend/database/migrations/006_create_tenants.sql` — FKs `tenant_members` → `tenants` e `users`
- `backend/routes/auth.py` — rota `bootstrap_user` e ordem dos decorators
- `backend/utils/tenant_context.py` — `resolve_tenant_id`, `require_tenant`, códigos `tenant_required` / `tenant_forbidden`
- `backend/repositories/tenant_repository.py` — `get_user_tenants`, `get_default_tenant_id`, `ensure_default_tenant`, `user_is_member`
- `frontend/src/contexts/AuthContext.tsx` (ou equivalente) — quando chama `bootstrap` após login
- `frontend/src/utils/api.ts` — função `bootstrap`

## Tarefas de refatoração (obrigatórias)

1. **Invariante única documentada em docstring** na rota bootstrap: “nunca exigir tenant antes de `public.users` existir”.
2. **Um só sítio** para “garantir user + tenant mínimo” (função de serviço ou método de repositório bem nomeado), evitando duplicar lógica entre `bootstrap` e `resolve_tenant_id` se fizer sentido **sem** criar dependências circulares.
3. **`TenantRepository` robusto:** sem embed quebrável no path crítico; recuperação de slug duplicado; logs com `user_id` **sem** dados sensíveis.
4. **Códigos HTTP e JSON:**  
   - Falha de bootstrap por BD/migração: preferir **503** ou **500** com código estável (ex. `tenant_bootstrap_failed`), **não** confundir com `tenant_required` (falta de tenant após auth).  
   - Documentar no docstring da API a diferença.
5. **Testes** (mínimo viável):  
   - Teste de unidade ou integração com Supabase **mockado** que simula: user novo → bootstrap cria `users` depois membership → retorno 200 com `tenant_id`.  
   - Opcional: teste que garante que `get_user_tenants` não usa só embed `tenants!inner` como única fonte de verdade (ou que o fallback existe).

6. **Curto parágrafo** em `docs/ENVIRONMENTS.md` ou `docs/TROUBLESHOOTING-AUTH-LOGIN-LOOP.md` (só o necessário): ordem bootstrap + FK + comando `curl` de smoke para `/api/auth/bootstrap`.

## Restrições

- Não mudar contratos públicos do frontend sem necessidade (`bootstrap` response shape mantém `ok` + `tenant_id` se já existir).
- Não commitar secrets; `.env` continua fora do git.
- Não remover `@require_tenant` das rotas de dados **após** o bootstrap estar garantido; o problema é **especificamente** a ordem no bootstrap e a resiliência do repositório.
- Mantém estilo e idioma do código existente (comentários podem ser PT-BR se o ficheiro já misturar).

## Critério de sucesso

- Novo utilizador (só Supabase Auth, sem linha em `public.users`): **primeiro** `POST /api/auth/bootstrap` → **200**; pedidos subsequentes com `@require_tenant` → **200** (ou listas vazias), **não** 403 `tenant_required`.
- Código e testes deixam claro **por que** `@require_tenant` não pode envolver o bootstrap antes do user existir.

Entrega: diff focado, lista de ficheiros tocados, e instruções breves para validar na VPS (`docker compose build backend`, smoke `curl`).
```

---

## Contexto do repositório (para ti, antes de colar no Codex)

| Área | Caminho |
|------|---------|
| Migração tenants | `backend/database/migrations/006_create_tenants.sql` |
| Bootstrap | `backend/routes/auth.py` |
| Tenant HTTP | `backend/utils/tenant_context.py` |
| Dados tenant | `backend/repositories/tenant_repository.py` |
| Deploy backend | `docker-compose.prod.yml`, `docs/ENVIRONMENTS.md` |

Depois de gerar o patch no Codex, alinha com **`docs/INDEX.md`** se quiseres uma entrada para este prompt (opcional).
