-- =============================================================================
-- 008_backfill_tenant_data.sql
-- Backfill tenants, tenant_members and tenant_id on domain tables
-- =============================================================================

BEGIN;

-- 1) Create a default tenant per user (if not exists)
WITH user_data AS (
    SELECT
        u.id AS user_id,
        COALESCE(NULLIF(u.name, ''), split_part(u.email, '@', 1)) AS base_name,
        u.email
    FROM public.users u
),
inserted_tenants AS (
    INSERT INTO public.tenants (name, slug)
    SELECT
        base_name || ' workspace' AS name,
        -- slug: u_<email-prefix>_<first8-of-user-id>
        'u_' || regexp_replace(split_part(email, '@', 1), '[^a-zA-Z0-9_-]', '_', 'g') || '_' || LEFT(user_id::text, 8) AS slug
    FROM user_data ud
    WHERE NOT EXISTS (
        SELECT 1 FROM public.tenant_members tm WHERE tm.user_id = ud.user_id
    )
    RETURNING id, slug
)
-- No-op select to keep CTE chain valid
SELECT 1;

-- 2) Ensure each user has at least one tenant_members row
INSERT INTO public.tenant_members (tenant_id, user_id, role)
SELECT
    t.id AS tenant_id,
    u.id AS user_id,
    'owner'::text AS role
FROM public.users u
JOIN LATERAL (
    -- Prefer an existing tenant with a matching slug prefix; otherwise pick any
    SELECT t1.id
    FROM public.tenants t1
    ORDER BY
      (t1.slug LIKE 'u_' || split_part(u.email, '@', 1) || '%') DESC,
      t1.created_at ASC
    LIMIT 1
  ) AS t ON TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM public.tenant_members tm WHERE tm.user_id = u.id
)
ON CONFLICT ON CONSTRAINT tenant_members_tenant_user_unique DO NOTHING;

-- 3) Backfill tenant_id on categories
UPDATE public.categories c
SET tenant_id = tm.tenant_id
FROM public.tenant_members tm
WHERE
    c.tenant_id IS NULL
    AND c.user_id = tm.user_id;

-- 4) Backfill tenant_id on accounts
UPDATE public.accounts a
SET tenant_id = tm.tenant_id
FROM public.tenant_members tm
WHERE
    a.tenant_id IS NULL
    AND a.user_id = tm.user_id;

-- 5) Backfill tenant_id on transactions
UPDATE public.transactions t
SET tenant_id = tm.tenant_id
FROM public.tenant_members tm
WHERE
    t.tenant_id IS NULL
    AND t.user_id = tm.user_id;

COMMIT;

