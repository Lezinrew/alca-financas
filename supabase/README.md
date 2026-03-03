# 🗄️ Supabase Database Migrations — Alça Finanças

Migrations versionadas e reprodutíveis para o banco de dados Postgres/Supabase.

---

## 📋 Estrutura

```
supabase/
├── README.md                          ← Este arquivo
├── MIGRATION_AUDIT.md                 ← Diagnóstico técnico completo
├── migrations/
│   ├── 000_prod_snapshot.sql          ← Snapshot histórico (referência)
│   ├── 20260303_000001_init.sql       ← Base schema (tables, constraints, indexes)
│   ├── 20260303_000002_functions.sql  ← Helper functions (current_tenant_id, etc)
│   ├── 20260303_000003_rls_policies.sql ← Row Level Security policies
│   └── 20260303_000004_triggers.sql   ← Database triggers (updated_at)
└── seed.sql                           ← Dev seed data (futuro)
```

---

## 🚀 Aplicar Migrations

### Ambiente Local (Postgres direto)

```bash
# Criar database vazio
createdb alca_local

# Aplicar migrations em ordem
psql alca_local -f supabase/migrations/20260303_000001_init.sql
psql alca_local -f supabase/migrations/20260303_000002_functions.sql
psql alca_local -f supabase/migrations/20260303_000003_rls_policies.sql
psql alca_local -f supabase/migrations/20260303_000004_triggers.sql

# Validar (ver seção Validação abaixo)
```

### Supabase Cloud (SQL Editor)

1. Acesse: **Project Settings > Database > SQL Editor**
2. Execute migrations em ordem (copiar/colar cada arquivo)
3. Aguarde confirmação de sucesso antes de próxima
4. **NÃO execute migrations fora de ordem** (dependências)

### Supabase CLI (Recomendado)

```bash
# Inicializar (se ainda não feito)
supabase init

# Aplicar todas as migrations
supabase db reset

# Ou aplicar apenas novas
supabase db push
```

---

## ✅ Validação

### Script Automático

```bash
./scripts/db/validate-migrations.sh
```

### Validação Manual

```bash
# 1. Verificar tabelas existem
psql $DATABASE_URL -c "\dt public.*"
# Esperado: 7 tabelas (users, tenants, tenant_members, categories, accounts, transactions, oauth_states)

# 2. Verificar functions existem
psql $DATABASE_URL -c "\df public.*"
# Esperado: 4 functions (current_app_user_id, current_tenant_id, dev_seed_account, update_updated_at_column)

# 3. Verificar policies existem
psql $DATABASE_URL -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public';"
# Esperado: ~14 policies

# 4. Verificar RLS ativo
psql $DATABASE_URL -c "
  SELECT tablename, rowsecurity
  FROM pg_tables
  WHERE schemaname = 'public'
  AND rowsecurity = true;
"
# Esperado: 7 tabelas com RLS ativo

# 5. Verificar triggers existem
psql $DATABASE_URL -c "
  SELECT tgname, tgrelid::regclass
  FROM pg_trigger
  WHERE tgname LIKE 'update_%_updated_at';
"
# Esperado: 4 triggers (users, categories, accounts, transactions)

# 6. Testar current_tenant_id()
psql $DATABASE_URL -c "SELECT public.current_tenant_id();"
# Esperado: NULL (ok, sem sessão ativa)
```

---

## 🔐 Modelo de Segurança

### RLS (Row Level Security)

**Ativo em todas as tabelas:**
- ✅ users
- ✅ tenants
- ✅ tenant_members
- ✅ categories
- ✅ accounts
- ✅ transactions
- ✅ oauth_states

**Backend (service_role):**
- Bypassa RLS automaticamente
- Segurança implementada na camada de aplicação (Python/Flask)

**Frontend (authenticated role):**
- Sujeito a RLS policies
- Policies usam `auth.uid()` e `current_tenant_id()`
- Apenas dados do tenant corrente são acessíveis

**Anon role:**
- Bloqueado por padrão (sem policies permissivas)
- Acesso apenas via service_role (backend)

---

## 📝 Regras de Migração

### ✅ FAZER

- **Sempre criar migration para mudança de schema**
- **Testar em ambiente local antes de aplicar em prod**
- **Usar transações (BEGIN/COMMIT)** em todas as migrations
- **Documentar dependências** no cabeçalho
- **Versionar no Git** antes de aplicar em qualquer ambiente
- **Aplicar em ordem** (respeitando dependências)

### ❌ NÃO FAZER

- **NUNCA alterar schema via SQL Editor diretamente** (causa drift)
- **NUNCA commitar migrations com comandos psql** (`\d`, `\restrict`, etc)
- **NUNCA usar `TO public`** em policies (usar `TO authenticated`)
- **NUNCA aplicar migrations fora de ordem**
- **NUNCA rodar migrations sem backup** (em prod)

---

## 🔄 Exportar Estado Atual (Comparação)

Se você fez mudanças manuais no Supabase e precisa sincronizar:

```bash
# Exportar schema atual de produção
pg_dump $SUPABASE_DB_URL --schema-only --no-owner --no-acl > /tmp/schema_prod.sql

# Comparar com migrations
diff supabase/migrations/20260303_000001_init.sql /tmp/schema_prod.sql

# Se houver diff: criar nova migration com as mudanças
```

---

## 🆘 Troubleshooting

### Migration Falha com "relation already exists"

**Causa:** Tabela já existe (migration foi aplicada parcialmente).

**Solução:**
```bash
# Opção 1: Adicionar IF NOT EXISTS
# (Já implementado nas migrations atuais)

# Opção 2: Dropar e recriar (DEV APENAS!)
psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
# Depois reaplique todas as migrations
```

### Migration Falha com "function does not exist"

**Causa:** Migrations aplicadas fora de ordem.

**Solução:** Sempre aplicar em ordem:
1. init.sql (tabelas)
2. functions.sql (funções)
3. rls_policies.sql (policies)
4. triggers.sql (triggers)

### RLS bloqueia acesso do backend

**Causa:** Backend usando anon key ao invés de service_role key.

**Solução:**
```bash
# .env
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # service_role key
# NÃO: SUPABASE_ANON_KEY=...
```

### current_tenant_id() retorna NULL

**Causa:** JWT não tem claim `tenant_id` ou session variable não definida.

**Solução:**
```python
# Backend deve definir tenant_id no JWT:
payload = {
    'sub': user_id,
    'tenant_id': tenant_id,  # ← ADICIONAR
    'exp': datetime.utcnow() + timedelta(minutes=15)
}

# Ou para conexão direta Postgres:
cursor.execute("SET app.current_tenant_id = %s", (tenant_id,))
```

---

## 🗂️ Histórico

### 2026-03-03: Migrations Canônicas

- ✅ Criadas 4 migrations limpas e reprodutíveis
- ✅ Removido lixo de pg_dump (`\restrict`, TSV format)
- ✅ Separado schema em: init → functions → policies → triggers
- ✅ Segurança: `TO public` → `TO authenticated`
- ✅ Documentação completa

### Antes de 2026-03-03: Migrations Ad-hoc

- ❌ Alterações manuais via SQL Editor (não versionadas)
- ❌ Estado não reprodutível
- ❌ Drift entre repositório e Supabase

---

## 📚 Recursos

- [Supabase CLI Docs](https://supabase.com/docs/guides/cli)
- [PostgreSQL Migrations Best Practices](https://www.postgresql.org/docs/current/ddl-schemas.html)
- [Row Level Security Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [Audit Completo](./MIGRATION_AUDIT.md)

---

**Última Atualização:** 2026-03-03
**Maintainer:** DevOps/Database Team
