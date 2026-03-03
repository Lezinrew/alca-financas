## Skill: tenant-core

**Status:** Planned / In rollout  
**Domain:** Multi-tenant boundaries and tenant isolation (organizations & membership).

---

### Purpose

Provide a consistent, scalable multi-tenant model where:

- **Tenant = Organization**.
- All domain data (accounts, categories, transactions, etc.) is associated to a **tenant_id**.
- Supabase/Postgres **RLS** enforces tenant isolation for non-service-role access.
- The existing single-tenant behavior (user_id–scoped) continues to work during migration.

This skill owns the **tenancy model**, not feature-level behavior.

---

### Current Discovery (Phase 0)

**Auth mode**

- Backend supports two auth modes:
  - **Custom JWT** (`backend/utils/auth_utils.py`):
    - `generate_jwt(user_id)` issues tokens with claims:
      - `user_id`, `type` (`access` / `refresh` / `reset`), `exp`, `jti`.
    - `require_auth` decorator (used by most routes) parses `Authorization: Bearer <jwt>` and sets `request.user_id`.
  - **Supabase Auth** (`backend/utils/auth_utils_supabase.py`, `routes/auth_supabase.py`):
    - `require_auth_supabase` validates Supabase access token via `SupabaseAuthService.get_user`.
    - Sets `request.user_id` and `request.user`.
- `backend/app.py` selects which auth blueprint to register based on:
  - `USE_SUPABASE_AUTH` env flag and availability of `routes/auth_supabase`.
  - Default in current codebase: **custom JWT auth**.

**Ownership columns (user-scoped model)**

From `backend/database/schema.sql`:

- `users`:
  - Primary key: `id UUID`.
  - No tenant column yet.
- `categories`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.
- `accounts`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.
- `transactions`:
  - `user_id UUID NOT NULL REFERENCES users(id)`.
  - `category_id`, `account_id` are FKs into `categories` / `accounts`.

Repositories confirm this pattern:

- `backend/repositories/account_repository_supabase.py`:
  - `find_by_user(user_id)` → filter by `user_id`.
- `backend/repositories/category_repository_supabase.py`:
  - `find_by_user(user_id)` / `find_by_type(user_id, type)` → filter by `user_id`.
- `backend/repositories/transaction_repository_supabase.py`:
  - `find_by_filter(user_id, ...)` → `eq("user_id", user_id)`.
  - Additional helpers also filter by `user_id`.

**Domain tables that will require tenant_id**

Confirmed in schema or code:

- `users` — currently global; will become tenant-aware via membership (tenant_members).
- `categories` — has `user_id`; will gain `tenant_id`.
- `accounts` — has `user_id`; will gain `tenant_id`.
- `transactions` — has `user_id`; will gain `tenant_id`.

Potential future/derived tables (to be confirmed, marked as TODO):

- **budgets** — not present yet; expected future table for budgets/goals.
- **reports_cache** — not present; reports currently computed on-the-fly via services.
- **notifications** — implemented as email service; no dedicated DB table yet.
- **imports** — imports currently use `transactions`/`accounts` records; no dedicated imports table.

**RLS state today**

- `backend/database/schema.sql`:
  - `ALTER TABLE users/categories/accounts/transactions ENABLE ROW LEVEL SECURITY;`
  - Initial policies used `USING (true)` and were later hardened.
- `backend/database/migrations/002_drop_insecure_rls_policies.sql` + `003_rls_secure_policies.sql`:
  - Define secure policies based on **Supabase Auth** (`auth.uid()`) or, in the alternative migration, a custom session variable via `current_app_user_id()`:
    - Users: `auth.uid() = id`.
    - Categories/Accounts/Transactions: `auth.uid() = user_id`.
  - These policies mainly protect anon-key and future Supabase Auth flows; the backend uses `SUPABASE_SERVICE_ROLE_KEY` and bypasses RLS.

---

### Boundaries & Responsibilities

**Tenant-core owns:**

- `tenants` table (id, slug/name, metadata).
- `tenant_members` table:
  - `(tenant_id, user_id, role)` with roles: `owner | admin | member | viewer`.
- `tenant_id` column and related indexes on domain tables:
  - `accounts`, `categories`, `transactions` (and future: budgets, reports_cache, notifications, imports).
- RLS functions and policies that enforce:
  - `tenant_id = current_tenant_id()` for all non-service-role access.
- Backfill & migration strategy from user-scoped to tenant-scoped model.

**Tenant-core does NOT own:**

- Business rules of accounts, categories, transactions, reports, etc.
- Frontend UX for switching tenant/organization (delegated to feature skills).

---

### Code Locations (In Progress)

- **Database**
  - `backend/database/schema.sql`:
    - Baseline schema with `user_id` columns and RLS enabled.
  - `backend/database/migrations/006_create_tenants.sql`:
    - `tenants`, `tenant_members`, helper indexes and constraints.
  - `backend/database/migrations/007_add_tenant_id_columns.sql`:
    - Adds nullable `tenant_id` to `categories`, `accounts`, `transactions` + indexes.
  - `backend/database/migrations/008_backfill_tenant_data.sql`:
    - Creates a default tenant per user and backfills `tenant_id` based on membership.
  - `backend/database/migrations/009_tenant_rls_policies.sql`:
    - Adds `current_tenant_id()` helper and RLS enablement for tenant tables.
  - `backend/database/migrations/010_tenant_domain_rls.sql`:
    - Narrows legacy user_id-only policies to `tenant_id IS NULL`.
    - Adds tenant-aware RLS policies for `categories`, `accounts`, `transactions` where `tenant_id IS NOT NULL`.

- **Docs**
  - `docs/04-database/tenancy.md` — central tenancy design & migration guide (including 010 rollout).

---

### Dependencies

- **Upstream**
  - `authentication`:
    - Provides user identity (`user_id`) and JWTs.
    - Will eventually carry `tenant_id` claim or allow switch via API.
  - `users-profile`:
    - Base ownership entity for membership; each member is a `users` row.
  - `infrastructure-platform`:
    - RLS engine, Supabase configuration, CI/CD of migrations.

- **Downstream**
  - `accounts`, `categories`, `transactions` (direct):
    - Must include `tenant_id` and filter queries accordingly.
  - `dashboard`, `reports`:
    - Aggregate over tenant-scoped data.
  - `imports-integrations`, `notifications`, `ai-insights`, `admin-governance`:
    - Must respect tenant boundaries when reading/writing domain data.

---

### References

- `backend/database/schema.sql`
- `backend/database/migrations/002_drop_insecure_rls_policies.sql`
- `backend/database/migrations/003_rls_secure_policies.sql`
- `backend/database/migrations/003_alternative_rls_session_variable.sql`
- `backend/utils/auth_utils.py`
- `backend/utils/auth_utils_supabase.py`
- `backend/repositories/*_repository_supabase.py`
- `docs/04-database/tenancy.md` (once created)

