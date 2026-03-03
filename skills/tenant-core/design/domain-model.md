## tenant-core — Domain Model

### Core Entities

- **Tenant (Organization)**
  - Represents an organization/workspace.
  - Identified by `id` and human-friendly `slug`.
  - May include additional metadata later (billing, plan, locale, etc.).

- **TenantMember**
  - Join entity between `tenants` and `users`.
  - Attributes:
    - `tenant_id`
    - `user_id`
    - `role` ∈ {`owner`, `admin`, `member`, `viewer`}

### Relationships

- `Tenant 1..* TenantMember` — each tenant has one or more members.
- `User 1..* TenantMember` — each user can belong to multiple tenants.
- `Tenant 1..* Accounts/Categories/Transactions` — via `tenant_id` on domain tables.

### Tenant Resolution (Conceptual)

- **Custom JWT auth (current default)**
  - Tokens today carry only `user_id` (no `tenant_id` claim).
  - For multi-tenant rollout, a new claim `tenant_id` can be added without breaking existing consumers (extra claim is ignored by current code).
  - Backend request context will derive `tenant_id` from:
    - JWT claim (preferred), or
    - Header like `X-Tenant-Id` validated against `tenant_members` (fallback).

- **Supabase Auth (optional mode)**
  - Recommended: extend Supabase JWT to include a `tenant_id` custom claim.
  - Fallback: resolve tenant via membership in the application layer and set RLS context (e.g. via `set_config` or by issuing a tenant-aware anon token).

See `docs/04-database/tenancy.md` for RLS-level design and migration details. 

