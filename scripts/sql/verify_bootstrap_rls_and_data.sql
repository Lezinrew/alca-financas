-- =============================================================================
-- Verificação pós-migrations de bootstrap/RLS
-- Execute no Supabase SQL Editor após:
--   1) 20260416000001_reconcile_public_users_with_auth.sql
--   2) 20260416000002_rls_bootstrap_hardening.sql
-- =============================================================================

-- 1) Duplicidades por email normalizado em public.users (esperado: 0 linhas)
SELECT lower(trim(email)) AS email_norm, COUNT(*) AS qty
FROM public.users
GROUP BY lower(trim(email))
HAVING COUNT(*) > 1
ORDER BY qty DESC, email_norm;

-- 2) Usuários em auth.users sem linha correspondente em public.users (esperado: 0 linhas)
SELECT au.id AS auth_user_id, au.email
FROM auth.users au
LEFT JOIN public.users pu ON pu.id = au.id
WHERE au.email IS NOT NULL
  AND trim(au.email) <> ''
  AND pu.id IS NULL
ORDER BY au.created_at DESC
LIMIT 100;

-- 3) Memberships órfãos (FK quebrada lógica) (esperado: 0)
SELECT COUNT(*) AS orphan_memberships
FROM public.tenant_members tm
LEFT JOIN public.users u ON u.id = tm.user_id
LEFT JOIN public.tenants t ON t.id = tm.tenant_id
WHERE u.id IS NULL OR t.id IS NULL;

-- 4) Usuários sem workspace (esperado: idealmente 0 após bootstrap)
SELECT u.id AS user_id, u.email
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1
  FROM public.tenant_members tm
  WHERE tm.user_id = u.id
)
ORDER BY u.created_at DESC
LIMIT 100;

-- 5) Policies RLS críticas existentes (inspeção)
SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('users', 'tenant_members', 'tenants')
ORDER BY tablename, policyname;

