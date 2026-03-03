-- =============================================================================
-- 006_create_tenants.sql
-- Multi-tenant core tables: tenants and tenant_members
-- =============================================================================

BEGIN;

-- Tenants table (organization-level)
CREATE TABLE IF NOT EXISTS public.tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tenant members (user ↔ tenant with role)
CREATE TABLE IF NOT EXISTS public.tenant_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner','admin','member','viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint to avoid duplicate memberships
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'tenant_members_tenant_user_unique'
    ) THEN
        ALTER TABLE public.tenant_members
        ADD CONSTRAINT tenant_members_tenant_user_unique
        UNIQUE (tenant_id, user_id);
    END IF;
END$$;

-- Indexes (idempotent)
CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant_id
    ON public.tenant_members(tenant_id);

CREATE INDEX IF NOT EXISTS idx_tenant_members_user_id
    ON public.tenant_members(user_id);

COMMIT;

