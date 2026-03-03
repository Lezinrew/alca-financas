## Multi-Tenant Architecture — Tenancy & RLS

**Repository:** Alça Finanças  
**Datastore:** Supabase (PostgreSQL)  
**Tenant model:** Tenant = Organization

---

### 1. Current State (Discovery)

**Auth modes**

- **Custom JWT (default)** — `backend/utils/auth_utils.py`:
  - Tokens carry: `user_id`, `type` (`access`/`refresh`/`reset`), `exp`, `jti`.
  - `require_auth` decorator extracts `user_id` and attaches to `request.user_id`.
- **Supabase Auth (optional)** — `backend/utils/auth_utils_supabase.py`:
  - `require_auth_supabase` validates access token via `SupabaseAuthService`.
  - Attaches `request.user_id` and `request.user`.
- `backend/app.py` chooses between `routes/auth.py` and `routes/auth_supabase.py` based on `USE_SUPABASE_AUTH`.

**Ownership columns (user-scoped)**

From `backend/database/schema.sql`:

- `users`:
  - `id UUID PRIMARY KEY`.
- `categories`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.
- `accounts`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.
- `transactions`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.

Repositories enforce this:

- `AccountRepository.find_by_user(user_id)` → filter by `user_id`.
- `CategoryRepository.find_by_user(user_id)` → filter by `user_id`.
- `TransactionRepository.find_by_filter(user_id, ...)` → `eq("user_id", user_id)`.

**RLS policies (today)**

- Tables `users`, `categories`, `accounts`, `transactions` have RLS enabled.
- `backend/database/migrations/003_rls_secure_policies.sql`:
  - Uses `auth.uid()` to restrict rows to the Supabase-authenticated user.
- `backend/database/migrations/003_alternative_rls_session_variable.sql`:
  - Defines `current_app_user_id()` using `current_setting('app.current_user_id', true)` as an alternative when not using Supabase Auth.
- The backend uses `SUPABASE_SERVICE_ROLE_KEY`, which **bypasses RLS**, so current behavior is governed by application filters.

---

### 2. Target Tenancy Model

**Core entities (see `skills/tenant-core/skill.md`)**

- `tenants`:
  - Represents an organization/workspace.
- `tenant_members`:
  - Joins `tenants` and `users` with a `role` (`owner`, `admin`, `member`, `viewer`).

**Domain tables with tenant_id**

Add nullable `tenant_id UUID` to:

- `categories`
- `accounts`
- `transactions`

Future candidates:

- `budgets` (when table exists)
- `reports_cache`, `notifications`, `imports` (once concrete schemas exist)

The migration path is **phased and backwards-compatible**:

1. Introduce `tenants` / `tenant_members`.
2. Add nullable `tenant_id` columns and indexes.
3. Backfill `tenant_id` based on existing `user_id`.
4. Gradually move application logic to use `tenant_id` while preserving `user_id` filters.
5. Optionally enforce `tenant_id NOT NULL` when safe.

---

### 3. Migrations (Planned)

> Existing migrations go up to `005_*`. The following numbers assume new files:

#### 006_create_tenants.sql

- Create tables:
  - `tenants`
  - `tenant_members`
- Add basic indexes:
  - `UNIQUE (slug)`
  - `UNIQUE (tenant_id, user_id)`
  - Indexes on `(tenant_id)` and `(user_id)`.
- Idempotent with `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

#### 007_add_tenant_id_columns.sql

- For each domain table:
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS tenant_id UUID;`
  - Add indices:
    - `categories`: `idx_categories_tenant_user (tenant_id, user_id)`
    - `accounts`: `idx_accounts_tenant_user (tenant_id, user_id)`
    - `transactions`: `idx_transactions_tenant_user_date (tenant_id, user_id, date DESC)`
- Columns remain **NULLABLE** during migration.

#### 008_backfill_tenant_data.sql

- For every existing `users` row:
  - Insert a default tenant (if not present), e.g.:
    - `name = '<user-name-or-email-prefix> workspace'`
    - `slug = 'u_' || substring(email from '^[^@]+') || '_' || left(id::text, 8)`
  - Insert membership `tenant_members(tenant_id, user_id, role='owner')` if not exists.
- For each domain table row where `tenant_id IS NULL`:
  - Join with `tenant_members` on `user_id` and set `tenant_id` accordingly.
- Script must be **guarded** against duplicates:
  - Use `INSERT ... ON CONFLICT DO NOTHING` style patterns where available.

#### 009_tenant_rls_policies.sql

- Introduce a helper function:

```sql
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  COALESCE(
    nullif(current_setting('request.jwt.claim.tenant_id', true), '')::uuid,
    nullif(current_setting('app.current_tenant_id', true), '')::uuid
  );
$$;
```

- Update RLS for domain tables to include tenant context:
  - Example (Supabase-authenticated clients with `tenant_id` claim):

```sql
DROP POLICY IF EXISTS transactions_tenant_policy ON public.transactions;
CREATE POLICY transactions_tenant_policy
  ON public.transactions
  FOR ALL
  USING (
    current_tenant_id() IS NOT NULL
    AND tenant_id = current_tenant_id()
  )
  WITH CHECK (
    current_tenant_id() IS NOT NULL
    AND tenant_id = current_tenant_id()
  );
```

- For `categories` and `accounts`, use similar policies combining `user_id` and `tenant_id` as needed.
- For non-Supabase contexts, `app.current_tenant_id` can be set via `set_config` in a role that does not bypass RLS.

> Note: The backend currently uses `service_role` and bypasses RLS, so these policies mainly protect direct Supabase access and future tenant-aware tokens.

#### 010_tenant_domain_rls.sql

- Introduces **tenant-aware RLS** for domain tables while keeping rollout non-breaking:
  - **Step A (soft)** — this migration:
    - Narrows legacy user_id-based policies (`*_select_own`, `*_insert_own`, etc.) to rows where `tenant_id IS NULL`:
      - Example for `transactions_select_own`:
        - `USING (tenant_id IS NULL AND auth.uid() = user_id)`.
    - Adds new tenant-aware policies for rows with `tenant_id IS NOT NULL`:
      - `USING (tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id)`.
      - `WITH CHECK` mirrors the same condition.
  - **Step B (hard)** — future migration `011_*`:
    - Can safely drop or further tighten the legacy `tenant_id IS NULL` policies once all data and tokens are tenant-aware.

---

### 4. Tenant Resolution Strategy

**Priority order:**

1. **JWT claim `tenant_id`** (for Supabase Auth or custom JWT with extended claims).
2. **Session variable `app.current_tenant_id`** (for direct Postgres connections that respect RLS).
3. **Application-level membership resolution** (for the Flask backend using service_role — RLS bypassed; enforcement happens in repositories/services).

**Backend contract (high-level):**

- A request is associated to exactly one active tenant:
  - For custom JWT:
    - Future tokens may include `tenant_id`; until then, tenant resolution can be done via:
      - Default tenant for the user (from `tenant_members`).
      - Optional `X-Tenant-Id` header, validated against membership.
  - For Supabase Auth:
    - Preferred: embed `tenant_id` in the Supabase JWT.
    - Alternative: use a second token or header to select tenant, validated against membership.

---

### 5. Safety & Non-Breaking Guarantees

- **Existing behavior preserved:**
  - Application continues to filter by `user_id` in repositories.
  - `tenant_id` starts as nullable and is always computed server-side (never trusted from clients).
  - RLS changes affect only non-service-role contexts (anon, future app roles).

- **Phased rollout:**
  - DB schema and RLS prepared first.
  - Backend repository and service code updated to accept tenant context gradually.
  - Frontend/UI for tenant switching and selection can be added later without blocking.

---

### 6. Testing Tenant Isolation

**DB-level tests (see `skills/tenant-core/tests/test-strategy.md`):**

- Seed users, tenants, memberships and domain data.
- Verify that `current_tenant_id()` restricts visibility correctly.

