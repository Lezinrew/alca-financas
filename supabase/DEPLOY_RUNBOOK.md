# 🚀 Runbook de Deploy — Database Migrations

**Versão:** 1.0
**Última Atualização:** 2026-03-03
**Responsável:** DevOps/Database Team
**Status:** ✅ Validado em Staging

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Pré-Requisitos](#pré-requisitos)
3. [Checklist Pré-Deploy](#checklist-pré-deploy)
4. [Processo de Deploy](#processo-de-deploy)
5. [Validação Pós-Deploy](#validação-pós-deploy)
6. [Rollback](#rollback)
7. [Troubleshooting](#troubleshooting)

---

## 📖 Visão Geral

Este runbook documenta o processo completo de deploy de migrations do banco de dados Alça Finanças em qualquer ambiente (staging, produção).

### Migrations Canônicas

```
supabase/migrations/
├── 20260303_000001_init.sql         ← Schema (tables, constraints, indexes)
├── 20260303_000002_functions.sql    ← Helper functions
├── 20260303_000003_rls_policies.sql ← RLS policies + hardening
└── 20260303_000004_triggers.sql     ← Triggers (updated_at)
```

**Ordem de execução:** SEMPRE `001 → 002 → 003 → 004`

### Dependências

| Migration | Depende de | Cria |
|-----------|------------|------|
| 001_init | - | Tabelas, constraints, indexes |
| 002_functions | 001_init | Functions (current_tenant_id, etc) |
| 003_rls_policies | 001_init, 002_functions | RLS policies |
| 004_triggers | 001_init, 002_functions | Triggers (updated_at) |

---

## ✅ Pré-Requisitos

### Acesso e Ferramentas

- [ ] Acesso ao Supabase Dashboard (admin)
- [ ] CLI tools instalados: `psql`, `git`
- [ ] Repositório atualizado: `git pull origin main`
- [ ] Credenciais de banco configuradas

### Variáveis de Ambiente

```bash
# Staging
export SUPABASE_STAGING_DB_URL="postgresql://postgres:SENHA@db.xxxxx.supabase.co:5432/postgres?sslmode=require"

# Produção
export SUPABASE_PROD_DB_URL="postgresql://postgres:SENHA@db.yyyyy.supabase.co:5432/postgres?sslmode=require"
```

⚠️ **NUNCA commite essas URLs no Git!** Use `.env` local ou secrets manager.

---

## 📝 Checklist Pré-Deploy

### 1. Verificações Técnicas

- [ ] **CI passou:** GitHub Actions workflow `validate-migrations` ✅
- [ ] **Migrations validadas localmente:**
  ```bash
  ./scripts/db/test-migrations-docker.sh
  ```
- [ ] **Código da aplicação compatível** com novo schema
- [ ] **Testes de integração passando** (backend + frontend)

### 2. Verificações Operacionais

- [ ] **Backup atual criado** (via Supabase Dashboard ou pg_dump)
- [ ] **Janela de manutenção agendada** (se necessário)
- [ ] **Equipe notificada** (desenvolvedores, suporte)
- [ ] **Plano de rollback preparado** (ver seção Rollback)

### 3. Verificações de Negócio

- [ ] **Stakeholders informados** (sócio/gerente aprovaram)
- [ ] **Documentação de mudanças atualizada**
- [ ] **Comunicação com usuários** (se downtime previsto)

---

## 🚀 Processo de Deploy

### Opção A: Via Supabase SQL Editor (Recomendado para Produção)

#### Passo 1: Acessar SQL Editor

1. Acesse: https://supabase.com/dashboard/project/[PROJECT_ID]/sql/new
2. Confirme que está no ambiente correto (Staging/Produção)

#### Passo 2: Criar Backup

```sql
-- Via SQL Editor, rode:
-- (Ou use Supabase Dashboard: Settings > Database > Backups)

-- Verificar estado atual
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';
```

#### Passo 3: Aplicar Migrations (Uma por Vez)

**⚠️ IMPORTANTE:** Execute uma migration por vez e aguarde confirmação de sucesso.

**Migration 1: init.sql**
```bash
# Copiar conteúdo de:
cat supabase/migrations/20260303_000001_init.sql

# Colar no SQL Editor e executar (Ctrl+Enter)
# Aguardar: "Success. No rows returned"
```

**Migration 2: functions.sql**
```bash
cat supabase/migrations/20260303_000002_functions.sql
# Colar e executar
```

**Migration 3: rls_policies.sql**
```bash
cat supabase/migrations/20260303_000003_rls_policies.sql
# Colar e executar
```

**Migration 4: triggers.sql**
```bash
cat supabase/migrations/20260303_000004_triggers.sql
# Colar e executar
```

#### Passo 4: Validar Deploy

```bash
# No terminal local:
./scripts/db/validate-migrations.sh $SUPABASE_PROD_DB_URL
```

**Resultado esperado:**
```
✅ VALIDATION PASSED
```

---

### Opção B: Via CLI (Staging ou Ambiente de Teste)

```bash
# 1. Conectar ao banco
export DATABASE_URL=$SUPABASE_STAGING_DB_URL

# 2. Aplicar migrations
psql $DATABASE_URL -f supabase/migrations/20260303_000001_init.sql
psql $DATABASE_URL -f supabase/migrations/20260303_000002_functions.sql
psql $DATABASE_URL -f supabase/migrations/20260303_000003_rls_policies.sql
psql $DATABASE_URL -f supabase/migrations/20260303_000004_triggers.sql

# 3. Validar
./scripts/db/validate-migrations.sh $DATABASE_URL
```

---

## ✅ Validação Pós-Deploy

### 1. Validação Automatizada

```bash
./scripts/db/validate-migrations.sh $SUPABASE_PROD_DB_URL
```

**Checks esperados:**
- ✅ Tables: 7/7
- ✅ Functions: 4/4
- ✅ RLS enabled: 7/7 tables
- ✅ Policies: 14
- ✅ No policies with TO public
- ✅ Triggers: 4/4

### 2. Validação Manual

```sql
-- 1. Verificar tabelas
\dt public.*

-- 2. Verificar functions
\df public.*

-- 3. Verificar policies
SELECT schemaname, tablename, policyname, roles
FROM pg_policies
WHERE schemaname = 'public';

-- 4. Verificar RLS ativo
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';

-- 5. Testar functions
SELECT public.current_tenant_id();
SELECT public.current_app_user_id();
```

### 3. Validação da Aplicação

- [ ] **Backend:** Conecta sem erros
- [ ] **Backend:** Queries básicas funcionam (SELECT, INSERT, UPDATE)
- [ ] **Backend:** RLS funciona corretamente (tenant isolation)
- [ ] **Frontend:** Telas principais carregam
- [ ] **Frontend:** CRUD básico funciona
- [ ] **Testes E2E:** Suite crítica passa

---

## 🔄 Rollback

Se algo der errado, siga este processo:

### Rollback via Backup

**Opção 1: Restore via Supabase Dashboard**
1. Acesse: Settings > Database > Backups
2. Selecione backup anterior
3. Click "Restore"

**Opção 2: Restore via pg_restore**
```bash
# Se você criou backup com pg_dump:
pg_restore $SUPABASE_PROD_DB_URL < backup_prod_schema_20260303.sql
```

### Rollback Manual (Remover Migrations)

**⚠️ Use apenas se backup não disponível**

```sql
-- 1. Desabilitar RLS
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories DISABLE ROW LEVEL SECURITY;
-- ... (todas as 7 tabelas)

-- 2. Remover policies
DROP POLICY IF EXISTS users_select_own ON public.users;
-- ... (todas as policies)

-- 3. Remover triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON public.users;
-- ... (todos os triggers)

-- 4. Remover functions
DROP FUNCTION IF EXISTS public.current_tenant_id();
-- ... (todas as functions)

-- 5. Remover tabelas (CUIDADO: perde dados!)
DROP TABLE IF EXISTS public.transactions CASCADE;
DROP TABLE IF EXISTS public.accounts CASCADE;
-- ... (todas as tabelas)
```

---

## 🔧 Troubleshooting

### Erro: "relation already exists"

**Causa:** Migration já foi aplicada parcialmente.

**Solução:**
```sql
-- Verificar estado atual
\dt public.*

-- Se tabela existe mas está incompleta, dropar e recriar:
DROP TABLE IF EXISTS public.TABELA_PROBLEMA CASCADE;
-- Depois reaplique a migration
```

---

### Erro: "function does not exist"

**Causa:** Migrations aplicadas fora de ordem.

**Solução:** Sempre aplicar em ordem: 001 → 002 → 003 → 004

---

### Erro: "role 'authenticated' does not exist"

**Causa:** Supabase roles não existem (ambiente não é Supabase).

**Solução:**
```sql
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE anon NOLOGIN;
```

---

### RLS bloqueia acesso do backend

**Causa:** Backend usando anon key ao invés de service_role key.

**Solução:** Verificar `.env`:
```bash
# CORRETO:
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ERRADO:
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

### Policies permissivas (TO public) detectadas

**Causa:** Migration 003 não executou o bloco de hardening.

**Solução:**
```sql
-- Forçar todas policies para authenticated:
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT schemaname, tablename, policyname
    FROM pg_policies
    WHERE schemaname = 'public'
  LOOP
    EXECUTE format(
      'ALTER POLICY %I ON %I.%I TO authenticated;',
      r.policyname, r.schemaname, r.tablename
    );
  END LOOP;
END $$;
```

---

## 📞 Suporte

**Problemas durante deploy?**

1. **Parar imediatamente** se erro crítico
2. **Não tentar "consertar na mão"** sem documentar
3. **Capturar logs de erro** completos
4. **Consultar seção Rollback** se necessário
5. **Escalar para time técnico** se bloqueado

**Contatos:**
- DevOps Lead: [email]
- Database Admin: [email]
- On-call: [telefone/slack]

---

## 📚 Referências

- [README.md](./README.md) — Guia de uso das migrations
- [MIGRATION_AUDIT.md](./MIGRATION_AUDIT.md) — Diagnóstico técnico
- [validate-migrations.sh](../scripts/db/validate-migrations.sh) — Script de validação
- [Supabase RLS Docs](https://supabase.com/docs/guides/auth/row-level-security)
- [PostgreSQL DDL](https://www.postgresql.org/docs/current/ddl.html)

---

**Última revisão:** 2026-03-03
**Próxima revisão:** Após primeiro deploy em produção
**Maintainer:** DevOps/Database Team
