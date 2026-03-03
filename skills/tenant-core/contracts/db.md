## tenant-core — Database Contracts

### Tables (planned)

1. `tenants`
   - `id UUID PRIMARY KEY DEFAULT uuid_generate_v4()`
   - `name TEXT NOT NULL`
   - `slug TEXT UNIQUE NOT NULL`  -- organization identifier
   - `created_at TIMESTAMPTZ DEFAULT NOW()`
   - `updated_at TIMESTAMPTZ DEFAULT NOW()`

2. `tenant_members`
   - `id UUID PRIMARY KEY DEFAULT uuid_generate_v4()`
   - `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `role TEXT NOT NULL CHECK (role IN ('owner','admin','member','viewer'))`
   - `created_at TIMESTAMPTZ DEFAULT NOW()`
   - `updated_at TIMESTAMPTZ DEFAULT NOW()`
   - Unique constraint `(tenant_id, user_id)`

### Domain tables with `tenant_id` (phased migration)

Planned additions (via idempotent migrations):

- `categories`
  - Add nullable `tenant_id UUID`.
  - Index: `CREATE INDEX IF NOT EXISTS idx_categories_tenant_user ON categories(tenant_id, user_id);`

- `accounts`
  - Add nullable `tenant_id UUID`.
  - Index: `CREATE INDEX IF NOT EXISTS idx_accounts_tenant_user ON accounts(tenant_id, user_id);`

- `transactions`
  - Add nullable `tenant_id UUID`.
  - Index: `CREATE INDEX IF NOT EXISTS idx_transactions_tenant_user_date ON transactions(tenant_id, user_id, date DESC);`

Future candidate tables (TODO, once schema exists):

- `budgets`
- `reports_cache`
- `notifications` (if persisted)
- `imports` (if a dedicated table is introduced)

All changes must be done with `IF NOT EXISTS`/guarded DDL so migrations can be safely re-run. 

### Migrations overview

- `006_create_tenants.sql` — creates `tenants` and `tenant_members`.
- `007_add_tenant_id_columns.sql` — adds nullable `tenant_id` to domain tables and indexes.
- `008_backfill_tenant_data.sql` — backfills `tenant_id` using `tenant_members`.
- `009_tenant_rls_policies.sql` — defines `current_tenant_id()` helper and enables RLS on tenant tables.
- `010_tenant_domain_rls.sql` — introduces tenant-aware RLS for `categories`, `accounts`, `transactions` while keeping legacy user_id-only policies for rows with `tenant_id IS NULL`.

