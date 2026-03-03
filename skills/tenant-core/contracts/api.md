## tenant-core — API Contracts (Planned)

> NOTE: These endpoints are **not** implemented yet; they are part of the target multi-tenant architecture and must be added carefully to avoid breaking current flows.

### GET /api/tenants

- **Description:** List tenants (organizations) that the authenticated user belongs to.
- **Auth:** Required (custom JWT or Supabase Auth).
- **Response 200:**
  - `[{ id: UUID, name: string, slug: string, role: 'owner' | 'admin' | 'member' | 'viewer' }]`

### POST /api/tenants/switch

- **Description:** Switch the active tenant for the current session/JWT.
- **Auth:** Required.
- **Body:**
  - `{ "tenant_id": "UUID" }`
- **Behavior (planned):**
  - Validate membership in `tenant_members`.
  - Issue a new token with a `tenant_id` claim **or** persist active tenant in a secure server-side session.
  - Should not break existing clients that do not send tenant information (default tenant remains active).

### POST /api/tenants/invite (TODO)

- **Description:** Invite another user to a tenant with a given role.
- **Status:** TODO — depends on product decisions for invitations and onboarding.

