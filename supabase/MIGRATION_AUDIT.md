# 🔍 AUDIT: Migrations Canônicas — Alça Finanças

**Data:** 2026-03-03
**Auditor:** DevOps/Database Architect
**Objetivo:** Estabilizar migrations para ambiente reprodutível do zero

---

## A) DIAGNÓSTICO — PROBLEMAS CRÍTICOS IDENTIFICADOS

### 🔴 **P0 — CRÍTICO (Quebra Execução)**

#### 1. **init.sql contém comandos psql que quebram migration**
```
Linha 9:   \restrict o0kL7X6UkD8n3cDTm2M5KNqssHEDHrcos94VtbXdXoS4R8f6ekYRJtR7Ly9MK4Z
Linha 780: \unrestrict o0kL7X6UkD8n3cDTm2M5KNqssHEDHrcos94VtbXdXoS4R8f6ekYRJtR7Ly9MK4Z
```

**Impacto:** Migration falha ao executar (comandos `\` são específicos de psql CLI).
**Solução:** Remover completamente essas linhas.

---

#### 2. **functions.sql e policies.sql são TSV dumps, não SQL executável**

**functions.sql:**
```
-- 20260303_000002_functions.sql
-- Functions
 schema |           name           |                 definition
--------+--------------------------+------------------------------------------------
 public | current_app_user_id      | CREATE OR REPLACE FUNCTION...
```

**Formato:** Tabela TSV com cabeçalho (schema|name|definition).
**Problema:** Não é executável como SQL. Postgres vai falhar ao interpretar.
**Solução:** Reescrever como statements `CREATE FUNCTION` puros.

**policies.sql:** Mesmo problema — dump TSV ao invés de SQL.

**triggers.sql:** Mesmo problema — dump TSV ao invés de SQL.

---

#### 3. **init.sql contém TUDO (functions, triggers, policies)**

**Conteúdo duplicado:**
- Linhas 44-76: 3 funções (current_app_user_id, current_tenant_id, dev_seed_account, update_updated_at_column)
- Linhas 511-533: 4 triggers (update_*_updated_at)
- Linhas 619-773: 17 policies + ALTER TABLE ENABLE RLS

**Problema:**
- Violação de separação de responsabilidades
- Duplicação com arquivos 002/003/004
- Dificulta manutenção

**Solução:**
- Manter no init.sql APENAS: CREATE TABLE, ALTER TABLE ADD CONSTRAINT, CREATE INDEX
- Mover functions → 000002_functions.sql
- Mover policies + RLS → 000003_rls_policies.sql
- Mover triggers → 000004_triggers.sql

---

### 🟠 **P1 — ALTO (Segurança e Ordem)**

#### 4. **Policies usam TO public (inseguro)**

**Exemplo atual:**
```sql
CREATE POLICY accounts_tenant_policy_select
ON public.accounts FOR SELECT
TO public  -- ❌ PERIGOSO: qualquer role, incluindo anon
USING (tenant_id = current_tenant_id() AND auth.uid() = user_id);
```

**Problema:** `TO public` permite acesso por roles não autenticadas (anon).
**Solução:** Trocar para `TO authenticated` (padrão Supabase).

---

#### 5. **Policies conflitantes/duplicadas em users**

**Estado atual:**
```sql
-- Policy 1 (permissiva)
CREATE POLICY "Users can insert own data" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view own data" ON users FOR SELECT USING (true);

-- Policy 2 (restritiva)
CREATE POLICY users_select_own ON users FOR SELECT USING (id = current_app_user_id());
CREATE POLICY users_update_own ON users FOR UPDATE USING (id = current_app_user_id());
```

**Problema:** 2 policies para mesma operação (SELECT em users). Postgres vai fazer OR lógico.
**Risco:** Policy permissiva (`USING (true)`) sempre ganha.

**Solução:**
- Remover policies "Users can X" (permissivas)
- Manter apenas users_select_own/users_update_own (restritas por current_app_user_id)

---

#### 6. **Falta ALTER TABLE ENABLE RLS explícito antes das policies**

**Atual:** `ALTER TABLE ENABLE RLS` está misturado com policies no init.sql.
**Problema:** Se removermos policies do init, perderemos o ENABLE RLS.

**Solução:**
- Adicionar explicitamente no policies.sql:
```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_states ENABLE ROW LEVEL SECURITY;
```

---

### 🟡 **P2 — MÉDIO (Qualidade e Manutenção)**

#### 7. **Falta cabeçalho padronizado e statement_timeout**

**Recomendação:**
```sql
-- =============================================================================
-- Migration: 20260303_000001_init
-- Description: Base schema (tables, constraints, indexes)
-- Dependencies: None
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_min_messages = warning;

-- ... SQL aqui ...

COMMIT;
```

**Benefício:** Proteção contra locks longos, logging controlado.

---

#### 8. **Falta idempotência em algumas partes**

**Problema:** pg_dump gera `CREATE TABLE` sem `IF NOT EXISTS`.
**Risco:** Re-executar migration falha.

**Solução:** Adicionar `IF NOT EXISTS` onde fizer sentido (ou aceitar que migrations rodam 1x apenas).

---

## B) TODO PRIORIZADO

### 🔴 **P0 — CRÍTICO (Esta Sprint)**

| # | Tarefa | Arquivo Afetado | Esforço | Risco |
|---|--------|----------------|---------|-------|
| 1 | Remover `\restrict` e `\unrestrict` do init.sql | 000001_init.sql | 5min | Baixo |
| 2 | Remover FUNCTIONS do init.sql (linhas 44-143) | 000001_init.sql | 10min | Médio |
| 3 | Remover TRIGGERS do init.sql (linhas 508-533) | 000001_init.sql | 5min | Baixo |
| 4 | Remover POLICIES do init.sql (linhas 616-773) | 000001_init.sql | 10min | Médio |
| 5 | Remover ALTER TABLE ENABLE RLS do init.sql | 000001_init.sql | 5min | Baixo |
| 6 | Reescrever functions.sql como SQL executável | 000002_functions.sql | 15min | Baixo |
| 7 | Reescrever policies.sql como SQL executável | 000003_rls_policies.sql | 20min | Médio |
| 8 | Reescrever triggers.sql como SQL executável | 000004_triggers.sql | 10min | Baixo |
| 9 | Adicionar ALTER TABLE ENABLE RLS no policies.sql | 000003_rls_policies.sql | 10min | Baixo |
| 10 | Trocar `TO public` por `TO authenticated` | 000003_rls_policies.sql | 10min | Alto |

**Total P0:** ~2h de trabalho focado

---

### 🟠 **P1 — ALTO (Próxima Sprint)**

| # | Tarefa | Arquivo Afetado | Esforço |
|---|--------|----------------|---------|
| 11 | Remover policies permissivas de users | 000003_rls_policies.sql | 10min |
| 12 | Adicionar cabeçalho padronizado (BEGIN/COMMIT) | Todos | 20min |
| 13 | Adicionar comentários de dependências | Todos | 15min |
| 14 | Criar script de validação (checklist.sh) | scripts/db/ | 30min |
| 15 | Testar migrations do zero em Postgres local | - | 1h |

**Total P1:** ~2h15min

---

### 🟡 **P2 — MÉDIO (Backlog)**

| # | Tarefa | Esforço |
|---|--------|---------|
| 16 | Criar README.md com guia de uso | 30min |
| 17 | Adicionar IF NOT EXISTS onde aplicável | 20min |
| 18 | Criar seed.sql (dev data) | 1h |
| 19 | Documentar processo de export/compare | 30min |
| 20 | Adicionar CI check de migrations | 1h |

**Total P2:** ~3h20min

---

## C) RISCOS IDENTIFICADOS

### 🔴 Risco Alto

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **Policies com TO public permitem acesso anon** | Alta | Crítico | Trocar para `TO authenticated` |
| **Migrations não executam (TSV format)** | Alta | Bloqueador | Reescrever como SQL puro |
| **Comandos `\restrict` quebram pipeline** | Alta | Bloqueador | Remover linhas |

### 🟠 Risco Médio

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **Duplicação de functions causa conflito** | Média | Alto | Remover do init.sql |
| **Policies permissivas em users** | Média | Alto | Remover "Users can X" policies |
| **Falta transaction wrapper** | Média | Médio | Adicionar BEGIN/COMMIT |

---

## D) ORDEM DE EXECUÇÃO RECOMENDADA

### Após Correções (Estado Final)

```
1. 20260303_000001_init.sql
   └─> CREATE EXTENSION, CREATE TABLE, ALTER TABLE ADD CONSTRAINT, CREATE INDEX
   └─> FK constraints
   └─> NADA MAIS (sem functions, triggers, policies)

2. 20260303_000002_functions.sql
   └─> CREATE FUNCTION current_app_user_id()
   └─> CREATE FUNCTION current_tenant_id()
   └─> CREATE FUNCTION dev_seed_account()
   └─> CREATE FUNCTION update_updated_at_column()

3. 20260303_000003_rls_policies.sql
   └─> ALTER TABLE ... ENABLE ROW LEVEL SECURITY
   └─> CREATE POLICY ... (todas as policies)

4. 20260303_000004_triggers.sql
   └─> CREATE TRIGGER update_*_updated_at
```

**Validação de Dependências:**
- ✅ Triggers dependem de functions → OK (functions antes)
- ✅ Policies dependem de functions → OK (functions antes)
- ✅ Tudo depende de tabelas → OK (init primeiro)

---

## E) PRÓXIMOS PASSOS IMEDIATOS

### Sprint Atual (Esta Semana)

1. **Executar P0.1-P0.5**: Limpar init.sql
2. **Executar P0.6-P0.8**: Reescrever functions/policies/triggers
3. **Executar P0.9-P0.10**: Adicionar RLS + corrigir roles
4. **Testar localmente**: `psql < init.sql && psql < functions.sql && ...`
5. **Commit changes**: Ver seção F (Commits Sugeridos)

### Sprint Seguinte

6. **Executar P1**: Adicionar headers, validação, testes
7. **Documentar**: README.md com guia de uso
8. **CI Integration**: Script de validação no pipeline

---

## F) COMMITS SUGERIDOS (Ver seção seguinte para diffs)

### Commit 1: `fix(migrations): remove pg_dump artifacts from init.sql`
- Remove `\restrict` e `\unrestrict`
- Remove `-- PostgreSQL database dump` headers
- Remove `Owner: -` comments

### Commit 2: `refactor(migrations): separate functions from init.sql`
- Move functions do init → functions.sql
- Reescreve functions.sql como SQL executável

### Commit 3: `refactor(migrations): separate policies and RLS from init.sql`
- Move policies do init → policies.sql
- Adiciona ALTER TABLE ENABLE RLS
- Reescreve policies.sql como SQL executável
- **SECURITY**: Troca `TO public` → `TO authenticated`

### Commit 4: `refactor(migrations): separate triggers from init.sql`
- Move triggers do init → triggers.sql
- Reescreve triggers.sql como SQL executável

### Commit 5: `fix(migrations): remove permissive user policies`
- Remove "Users can insert/update/view own data" (USING true)
- Mantém apenas users_select_own/users_update_own

### Commit 6: `docs(migrations): add README and validation script`
- Cria supabase/README.md
- Cria scripts/db/validate-migrations.sh

---

## G) CHECKLIST DE VALIDAÇÃO

### Pré-Commit
- [ ] Nenhum comando `\` em arquivos .sql
- [ ] Nenhum `Owner: -` ou `COMMENT ON SCHEMA`
- [ ] Todos os arquivos começam com cabeçalho padronizado
- [ ] Todos os arquivos são SQL puro (sem TSV)

### Pós-Commit (Local)
```bash
# Criar DB vazio
createdb alca_test

# Aplicar migrations em ordem
psql alca_test < supabase/migrations/20260303_000001_init.sql
psql alca_test < supabase/migrations/20260303_000002_functions.sql
psql alca_test < supabase/migrations/20260303_000003_rls_policies.sql
psql alca_test < supabase/migrations/20260303_000004_triggers.sql

# Validar
psql alca_test -c "\dt"  # Deve listar 7 tabelas
psql alca_test -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public';"  # ~15 policies
psql alca_test -c "SELECT current_tenant_id();"  # Deve retornar NULL (ok)
psql alca_test -c "\df public.*"  # Deve listar 4 functions

# Cleanup
dropdb alca_test
```

### Pós-Deploy (Staging)
- [ ] Backend conecta sem erro
- [ ] Queries com tenant_id funcionam
- [ ] RLS bloqueia acesso cross-tenant
- [ ] service_role bypassa RLS (backend)

---

## H) RESUMO EXECUTIVO

**Estado Atual:** ❌ Migrations não reprodutíveis (TSV format, duplicação, comandos psql)
**Estado Alvo:** ✅ Migrations limpas, separadas, executáveis, seguras

**Trabalho Total:** ~7h30min (P0+P1+P2)
**Crítico P0:** ~2h (pode ser feito hoje)
**Risco Atual:** 🔴 Alto (ambiente não reprodutível, policies inseguras)
**Risco Pós-Fix:** 🟢 Baixo (migrations versionadas, testáveis, documentadas)

---

**Próxima Ação:** Gerar patches (ver arquivo seguinte: `MIGRATION_PATCHES.md`)
