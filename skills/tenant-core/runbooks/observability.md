## tenant-core — Observability

### Key Signals

- **Logs**
  - Tenant creation events (`INSERT` into `tenants`).
  - Membership changes (`INSERT`/`UPDATE`/`DELETE` on `tenant_members`).
  - RLS-related errors surfaced by application (e.g. permission denied).

- **Metrics (future)**
  - Number of tenants per user.
  - Number of active tenants.
  - Requests per tenant (labelled by `tenant_id`).

- **Traces (future)**
  - Attach `tenant_id` as a span attribute in any distributed tracing system.

### Debugging Checklist

1. Confirm the active `tenant_id` for the request context:
   - From JWT claim, header, or server-side session (depending on implementation).
2. Validate `tenant_members` rows for the user:
   - Ensure the user is a member of the expected tenant with the proper role.
3. Check RLS policies for affected tables:
   - Ensure policies reference `tenant_id` and `current_tenant_id()` correctly.

