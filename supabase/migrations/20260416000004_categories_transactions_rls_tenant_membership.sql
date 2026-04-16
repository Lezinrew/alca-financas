-- =============================================================================
-- Migration: categories + transactions RLS via tenant_members
--   Mesmo racional que 20260416000003_accounts_rls_tenant_membership.sql:
--   access token Supabase padrão não traz tenant_id no JWT →
--   current_tenant_id() NULL → 42501 em INSERT/SELECT direto no PostgREST.
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

-- -----------------------------------------------------------------------------
-- categories
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS categories_tenant_policy_select ON public.categories;
DROP POLICY IF EXISTS categories_tenant_policy_insert ON public.categories;
DROP POLICY IF EXISTS categories_tenant_policy_update ON public.categories;
DROP POLICY IF EXISTS categories_tenant_policy_delete ON public.categories;

CREATE POLICY categories_tenant_policy_select ON public.categories
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

CREATE POLICY categories_tenant_policy_insert ON public.categories
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

CREATE POLICY categories_tenant_policy_update ON public.categories
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

CREATE POLICY categories_tenant_policy_delete ON public.categories
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

-- -----------------------------------------------------------------------------
-- transactions
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS transactions_tenant_policy_select ON public.transactions;
DROP POLICY IF EXISTS transactions_tenant_policy_insert ON public.transactions;
DROP POLICY IF EXISTS transactions_tenant_policy_update ON public.transactions;
DROP POLICY IF EXISTS transactions_tenant_policy_delete ON public.transactions;

CREATE POLICY transactions_tenant_policy_select ON public.transactions
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

CREATE POLICY transactions_tenant_policy_insert ON public.transactions
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

CREATE POLICY transactions_tenant_policy_update ON public.transactions
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

CREATE POLICY transactions_tenant_policy_delete ON public.transactions
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
