-- =============================================================================
-- 009_tenant_rls_policies.sql
-- Tenant-aware RLS helper and policies (non-breaking for service_role)
-- =============================================================================

BEGIN;

-- Helper function to resolve current tenant id
-- Priority:
-- 1) JWT claim: request.jwt.claim.tenant_id (Supabase Auth / custom JWT with tenant claim)
-- 2) Session variable: app.current_tenant_id (for direct Postgres connections using set_config)
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claim.tenant_id', true), '')::uuid,
    NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  );
$$;

COMMENT ON FUNCTION public.current_tenant_id() IS
  'Returns the current tenant_id from JWT claim (request.jwt.claim.tenant_id) or app.current_tenant_id session variable.';

-- Enable RLS on tenants and tenant_members (access typically via backend/service_role)
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_members ENABLE ROW LEVEL SECURITY;

-- Conservative policies: no anon access; service_role bypasses RLS.
-- (No explicit policies for anon here.)

-- NOTE:
-- Existing user_id-based RLS policies (003_rls_secure_policies.sql or
-- 003_alternative_rls_session_variable.sql) remain in place.
-- As long as the backend uses service_role, these policies do not affect it.
-- Tenant-aware policies should be introduced carefully in a future iteration,
-- after the application starts using tenant_id in queries and/or JWT claims.

COMMIT;

