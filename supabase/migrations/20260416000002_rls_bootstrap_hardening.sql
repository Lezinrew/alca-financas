-- =============================================================================
-- Migration: RLS hardening for bootstrap/auth consistency
-- Objetivo:
--   1) Tornar policies de public.users compatíveis com auth.uid() e app.current_user_id().
--   2) Permitir leitura segura de tenant_members/tenants para o próprio utilizador autenticado.
--   3) Manter escrita sensível (create tenant/membership) via backend service_role.
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- -----------------------------------------------------------------------------
-- Garantir RLS ativo
-- -----------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_members ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- users: select/update/insert próprio perfil
-- Compatível com:
--   - backend com set_config('app.current_user_id', ...)
--   - Supabase Auth direto (auth.uid())
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own ON public.users
  FOR SELECT
  TO authenticated
  USING (id = COALESCE(public.current_app_user_id(), auth.uid()));

DROP POLICY IF EXISTS users_update_own ON public.users;
CREATE POLICY users_update_own ON public.users
  FOR UPDATE
  TO authenticated
  USING (id = COALESCE(public.current_app_user_id(), auth.uid()))
  WITH CHECK (id = COALESCE(public.current_app_user_id(), auth.uid()));

-- Permite criar apenas o próprio perfil (defesa em profundidade).
DROP POLICY IF EXISTS users_insert_own ON public.users;
CREATE POLICY users_insert_own ON public.users
  FOR INSERT
  TO authenticated
  WITH CHECK (id = auth.uid());

-- -----------------------------------------------------------------------------
-- tenant_members: leitura apenas dos próprios memberships
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS tenant_members_select_own ON public.tenant_members;
CREATE POLICY tenant_members_select_own ON public.tenant_members
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- tenants: leitura apenas de tenants onde o user é membro
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS tenants_select_member ON public.tenants;
CREATE POLICY tenants_select_member ON public.tenants
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = public.tenants.id
        AND tm.user_id = auth.uid()
    )
  );

COMMIT;

