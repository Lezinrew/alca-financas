## tenant-core — Test Strategy

### Goals

- Verify that tenant isolation is enforced at both database and API layers.
- Ensure that backfill and migrations are safe to run more than once.

### DB-level Tests (PostgreSQL / Supabase)

Using a dedicated test database or schema:

- Seed:
  - 2 users: `user_a`, `user_b`.
  - 2 tenants: `tenant_a`, `tenant_b`.
  - Memberships:
    - `tenant_a` ↔ `user_a`
    - `tenant_b` ↔ `user_b`
  - Sample rows in `accounts`, `categories`, `transactions` for both tenants.
- Assertions:
  - When `current_tenant_id() = tenant_a`, queries only return rows for `tenant_a`.
  - Inserting/updating a row with mismatched `tenant_id` fails RLS checks.

### API-level Tests (pytest)

Add tests (e.g. `backend/tests/test_tenancy_api.py`) that:

- Authenticate as `user_a` and simulate `tenant_a` vs `tenant_b` context.
- Confirm that:
  - `GET /api/accounts`, `/api/categories`, `/api/transactions` never return data from another tenant.
  - (When implemented) `/api/tenants` lists only tenants the user belongs to.

### Migration Tests

- Validate that running migrations `006_create_tenants.sql`–`009_tenant_rls_policies.sql` on a snapshot with existing data:
  - Does not delete or corrupt existing rows.
  - Sets `tenant_id` consistently for all domain tables.
  - Can be safely re-run without errors (idempotent DDL and guarded backfill).

