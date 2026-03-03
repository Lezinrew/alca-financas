## tenant-core — Threats (STRIDE-lite)

### Spoofing
- **Risk:** A user for Tenant A forges identifiers to access data from Tenant B.
- **Mitigations:**
  - All queries use `tenant_id` from the resolved context, never from client payloads.
  - RLS enforces `tenant_id = current_tenant_id()` in addition to any `user_id` checks.

### Tampering
- **Risk:** Client sends a body with forged `tenant_id`.
- **Mitigations:**
  - Backend overwrites or ignores `tenant_id` from the request body.
  - Only server-side context (JWT claim / membership resolution) determines `tenant_id`.

### Information Disclosure
- **Risk:** Cross-tenant data leaks through reports, joins or cache tables.
- **Mitigations:**
  - All aggregations and reporting services must receive and apply `tenant_id`.
  - Any future cache tables (e.g. `reports_cache`) must include and filter by `tenant_id`.

### Elevation of Privilege
- **Risk:** Regular member becomes `owner` or `admin` of a tenant without authorization.
- **Mitigations:**
  - Tenant management endpoints enforce role checks (`owner`/`admin` only).
  - Changes to `tenant_members.role` are audited (future work via `admin-governance`).

### Denial of Service
- **Risk:** A single noisy tenant degrades performance for others.
- **Mitigations (future, via `infrastructure-platform`):**
  - Per-tenant rate limits and quotas.
  - Per-tenant dashboards/alerts for anomalous traffic or load.

