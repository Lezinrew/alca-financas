-- =============================================================================
-- Migration: accounts RLS via tenant_members (sem depender de current_tenant_id)
-- Problema:
--   Policies antigas exigiam tenant_id = public.current_tenant_id(), que lê
--   request.jwt.claim.tenant_id ou app.current_tenant_id. O access token padrão
--   do Supabase não inclui tenant_id → current_tenant_id() NULL → INSERT falha
--   com 42501 mesmo com user_id = auth.uid() e membership válido.
-- Solução:
--   Exigir apenas que (user_id, tenant_id) exista em tenant_members para o
--   auth.uid(), alinhado ao modelo de tenants_select_member / bootstrap.
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

DROP POLICY IF EXISTS accounts_tenant_policy_select ON public.accounts;
DROP POLICY IF EXISTS accounts_tenant_policy_insert ON public.accounts;
DROP POLICY IF EXISTS accounts_tenant_policy_update ON public.accounts;
DROP POLICY IF EXISTS accounts_tenant_policy_delete ON public.accounts;

CREATE POLICY accounts_tenant_policy_select ON public.accounts
  FOR SELECT
  TO authenticated
  USING (
    tenant_id IS NOT NULL
    AND auth.uid() = user_id
    AND EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = tenant_id
        AND tm.user_id = auth.uid()
    )
  );

CREATE POLICY accounts_tenant_policy_insert ON public.accounts
  FOR INSERT
  TO authenticated
  WITH CHECK (
    tenant_id IS NOT NULL
    AND auth.uid() = user_id
    AND EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = tenant_id
        AND tm.user_id = auth.uid()
    )
  );

CREATE POLICY accounts_tenant_policy_update ON public.accounts
  FOR UPDATE
  TO authenticated
  USING (
    tenant_id IS NOT NULL
    AND auth.uid() = user_id
    AND EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = tenant_id
        AND tm.user_id = auth.uid()
    )
  )
  WITH CHECK (
    tenant_id IS NOT NULL
    AND auth.uid() = user_id
    AND EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = tenant_id
        AND tm.user_id = auth.uid()
    )
  );

CREATE POLICY accounts_tenant_policy_delete ON public.accounts
  FOR DELETE
  TO authenticated
  USING (
    tenant_id IS NOT NULL
    AND auth.uid() = user_id
    AND EXISTS (
      SELECT 1
      FROM public.tenant_members tm
      WHERE tm.tenant_id = tenant_id
        AND tm.user_id = auth.uid()
    )
  );

COMMIT;
