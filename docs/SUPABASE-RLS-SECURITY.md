# Supabase RLS — Segurança e Políticas (Production-Grade)

## 1. Visão geral do schema e RLS atual

### 1.1 Tabelas com RLS habilitado (schema atual)

| Tabela         | RLS | Coluna de isolamento | Políticas atuais (pré-migração) |
|----------------|-----|----------------------|----------------------------------|
| `users`        | Sim | `id`                 | SELECT/INSERT/UPDATE com `USING (true)` |
| `categories`   | Sim | `user_id`            | SELECT + "manage" (ALL) com `USING (true)` |
| `accounts`     | Sim | `user_id`            | SELECT + "manage" (ALL) com `USING (true)` |
| `transactions` | Sim | `user_id`            | SELECT + "manage" (ALL) com `USING (true)` |
| `oauth_states` | Não | —                    | Nenhuma (tabela sem user_id) |

### 1.2 Políticas inseguras identificadas

Todas as políticas atuais são inseguras:

- **USING (true)** — qualquer conexão que respeite RLS vê todas as linhas.
- **WITH CHECK (true)** — qualquer conexão pode inserir/atualizar sem restrição de `user_id`.

Com isso, **não há isolamento real por usuário no banco**: a proteção hoje é só na aplicação (filtro por `request.user_id`).

---

## 2. Arquitetura atual: backend com `service_role`

### 2.1 Como o backend acessa o Supabase

- O backend usa **SUPABASE_SERVICE_ROLE_KEY** (ou `SUPABASE_KEY` legado).
- A **service_role key** no Supabase **ignora RLS**: todas as políticas são contornadas.
- Autenticação é **custom** (Flask + JWT próprio), com usuários em `public.users` (não em `auth.users`).
- Não há uso de `auth.uid()` hoje; o Supabase não conhece o “usuário atual” por JWT.

### 2.2 Risco com service_role + RLS “true”

| Risco | Descrição |
|-------|-----------|
| **Vazamento de service_role** | Qualquer cliente com essa chave lê/escreve **todos** os dados, sem limite por usuário. |
| **Bug na aplicação** | Se uma query deixar de filtrar por `user_id`, todos os registros ficam acessíveis. |
| **RLS ineficaz** | Políticas com `USING (true)` não adicionam nenhuma defesa no banco. |

Ou seja: **a segurança hoje depende 100% da aplicação**. RLS não acrescenta camada extra enquanto o backend usar service_role.

### 2.3 Por que ainda aplicar políticas seguras

- **Defesa em profundidade:** se no futuro alguém usar a **anon key** (por engano ou em novo cliente), RLS já restringe por usuário.
- **Preparação para Supabase Auth:** políticas com `auth.uid()` ficam prontas para quando/se migrarem.
- **Boa prática:** schema já nasce correto para cenários onde RLS é respeitado.

---

## 3. Opções de arquitetura e qual script usar

### 3.1 Cenário A: Manter custom auth + service_role (atual)

- **Efeito das novas políticas:** **nenhum** no backend atual (service_role continua bypassando RLS).
- **Recomendação:** aplicar mesmo assim o script **baseado em `auth.uid()`** (003) para:
  - Proteger uso acidental da anon key (retorno vazio se não houver JWT de auth).
  - Deixar o schema pronto para migração futura para Supabase Auth.

**Scripts a usar:**

1. `002_drop_insecure_rls_policies.sql`
2. `003_rls_secure_policies.sql` (políticas com `auth.uid()`)

### 3.2 Cenário B: Migrar para Supabase Auth

- Frontend/backend passam a usar JWT do Supabase Auth.
- `auth.uid()` passa a ser o identificador do usuário.
- É necessário alinhar `public.users.id` com `auth.users.id` (mesmo UUID), por trigger ou no signup.

**Scripts:** os mesmos do Cenário A. As políticas com `auth.uid()` passam a ser efetivas para qualquer cliente que use a **anon key** + JWT do Supabase.

### 3.3 Cenário C: Manter custom auth mas usar conexão PostgreSQL que respeita RLS

- Backend usa **SUPABASE_DB_URL** (psycopg2) e, no início de cada request, executa:
  `SELECT set_config('app.current_user_id', '<user_id>', true);`
- Cria-se um **role** que não seja service_role (ex.: `app_user`) e as políticas usam `current_app_user_id()`.

**Scripts:**

1. `002_drop_insecure_rls_policies.sql`
2. `003_alternative_rls_session_variable.sql` (políticas com `current_app_user_id()`)

**Importante:** o cliente Supabase REST com service_role **não** envia `set_config` por request; essa alternativa só faz sentido com conexão SQL direta por request (ou pool que seta o contexto por request).

---

## 4. Scripts SQL — resumo e ordem de execução

### 4.1 Remover políticas inseguras

**Arquivo:** `backend/database/migrations/002_drop_insecure_rls_policies.sql`

- Remove todas as políticas atuais com nomes do schema original.
- Execute **uma vez** no SQL Editor do Supabase (projeto de produção ou staging).

### 4.2 Aplicar políticas seguras (recomendado: auth.uid())

**Arquivo:** `backend/database/migrations/003_rls_secure_policies.sql`

- Cria políticas por tabela:
  - **users:** SELECT e UPDATE onde `auth.uid() = id`.
  - **categories, accounts, transactions:** SELECT / INSERT / UPDATE / DELETE onde `auth.uid() = user_id`.
  - **oauth_states:** RLS ativado, **sem** política para anon (acesso só via service_role).

Execute **depois** do 002.

### 4.3 Alternativa: políticas com variável de sessão

**Arquivo:** `backend/database/migrations/003_alternative_rls_session_variable.sql`

- Cria a função `current_app_user_id()` (lê `app.current_user_id` da sessão).
- Cria políticas equivalentes às acima, mas com `user_id = current_app_user_id()` (e em `users`, `id = current_app_user_id()`).
- Use **apenas** se for adotar o Cenário C (conexão direta + `set_config` por request). **Não** use junto com o 003 baseado em `auth.uid()` no mesmo ambiente (escolha um dos dois).

### 4.4 Verificação pós-migração

**Arquivo:** `backend/database/migrations/004_verify_rls.sql`

- Lista tabelas com RLS.
- Lista todas as políticas (nome, comando, USING, WITH CHECK).
- Aponta políticas ainda inseguras (USING/WITH CHECK = `true`).
- Contagem de políticas por tabela.

Execute após 002 e 003 (ou 003_alternative) e confira que não restam políticas com `true` e que as contagens batem com o esperado.

---

## 5. Garantias por operação (após migração)

Com **003_rls_secure_policies.sql** (auth.uid()):

| Tabela         | SELECT              | INSERT              | UPDATE              | DELETE              |
|----------------|---------------------|---------------------|---------------------|---------------------|
| users          | `id = auth.uid()`   | — (só service_role) | `id = auth.uid()`   | — (só service_role)  |
| categories     | `user_id = auth.uid()` | `user_id = auth.uid()` | `user_id = auth.uid()` | `user_id = auth.uid()` |
| accounts       | idem                | idem                | idem                | idem                |
| transactions   | idem                | idem                | idem                | idem                |
| oauth_states   | — (anon sem política) | —                  | —                   | —                   |

Com **003_alternative_rls_session_variable.sql**, troque `auth.uid()` por `current_app_user_id()` e exija que o backend chame `set_config('app.current_user_id', user_id, true)` por request.

---

## 6. Impacto técnico

### 6.1 Backend atual (service_role)

- **Nenhuma mudança de comportamento:** service_role continua ignorando RLS.
- Nenhuma alteração obrigatória em código para continuar funcionando.

### 6.2 Uso da anon key (hoje ou no futuro)

- Sem JWT do Supabase Auth (ou sem `set_config` no Cenário C): SELECT/INSERT/UPDATE/DELETE nas tabelas com RLS retornam 0 linhas ou falham (comportamento desejado).
- Com JWT do Supabase Auth (e `public.users.id` = `auth.users.id`): acesso apenas aos dados do próprio usuário.

### 6.3 oauth_states

- RLS ativado, sem política para anon: acesso apenas com service_role (backend). Fluxo OAuth atual segue funcionando.

### 6.4 Migração futura para Supabase Auth

- Garantir que criação/atualização de `public.users` esteja alinhada a `auth.users` (ex.: trigger em `auth.users` que insere/atualiza `public.users` com o mesmo `id`).
- Assim, `auth.uid()` em RLS corresponde ao `user_id` / `id` usados na aplicação.

---

## 7. Checklist de aplicação

- [ ] Backup do banco ou uso de ambiente de staging.
- [ ] Executar `002_drop_insecure_rls_policies.sql`.
- [ ] Executar `003_rls_secure_policies.sql` (ou 003_alternative, se for Cenário C).
- [ ] Executar `004_verify_rls.sql` e validar:
  - [ ] Nenhuma política com `qual = 'true'` ou `with_check = 'true'`.
  - [ ] Contagem de políticas por tabela conforme esperado.
- [ ] Rodar testes da aplicação (backend continua com service_role).
- [ ] Documentar no projeto qual cenário (A, B ou C) está em uso e qual 003 foi aplicado.

---

*Documento alinhado ao RAIO-X e aos scripts em `backend/database/migrations/`.*
