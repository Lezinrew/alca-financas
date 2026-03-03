## tenant-core — Invariants

1. **Tenant Isolation**
   - A user must never see or modify data for a tenant they are not a member of.
   - All domain queries must eventually be constrained by both `user_id` and `tenant_id`.

2. **Stable Tenant IDs**
   - Once assigned, `tenant_id` for a given record must not change.
   - Moving data between tenants should be treated as a migration, not an update.

3. **Membership Integrity**
   - `(tenant_id, user_id)` in `tenant_members` is unique.
   - Removing a user from a tenant immediately revokes access to that tenant’s data (via RLS + repository filters).

4. **At Least One Owner**
   - Each tenant should have at least one `owner` (soft invariant enforced at API/service layer).

5. **Backwards Compatibility During Migration**
   - While `tenant_id` is being introduced and backfilled, application behavior must remain correct when filtering only by `user_id`.
   - New code paths must be additive and guarded (e.g. feature flags or presence of `tenant_id`), not destructive.\n*** End Patch"} ***!
