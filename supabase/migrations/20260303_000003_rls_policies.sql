-- =============================================================================
-- Migration: 20260303_000003_rls_policies
-- Description: Row Level Security (RLS) policies
-- Dependencies: 20260303_000002_functions.sql (requires current_tenant_id(), current_app_user_id())
-- =============================================================================
-- SECURITY MODEL:
-- - Backend uses service_role (bypasses RLS)
-- - Policies protect direct Supabase client access (anon/authenticated)
-- - TO authenticated: apenas users autenticados (nunca anon)
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

-- =============================================================================
-- ENABLE ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- POLICIES: users
-- =============================================================================
-- Users podem ler/atualizar apenas próprio registro
-- Usa current_app_user_id() (session variable) ao invés de auth.uid()
-- =============================================================================

CREATE POLICY users_select_own ON public.users
  FOR SELECT
  TO authenticated
  USING (id = public.current_app_user_id());

CREATE POLICY users_update_own ON public.users
  FOR UPDATE
  TO authenticated
  USING (id = public.current_app_user_id())
  WITH CHECK (id = public.current_app_user_id());

-- Nota: INSERT em users é via backend/signup (service_role), não via RLS policy

-- =============================================================================
-- POLICIES: categories (tenant-aware)
-- =============================================================================
-- Requer: tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id
-- =============================================================================

CREATE POLICY categories_tenant_policy_select ON public.categories
  FOR SELECT
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY categories_tenant_policy_insert ON public.categories
  FOR INSERT
  TO authenticated
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY categories_tenant_policy_update ON public.categories
  FOR UPDATE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  )
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY categories_tenant_policy_delete ON public.categories
  FOR DELETE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

-- =============================================================================
-- POLICIES: accounts (tenant-aware)
-- =============================================================================

CREATE POLICY accounts_tenant_policy_select ON public.accounts
  FOR SELECT
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY accounts_tenant_policy_insert ON public.accounts
  FOR INSERT
  TO authenticated
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY accounts_tenant_policy_update ON public.accounts
  FOR UPDATE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  )
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY accounts_tenant_policy_delete ON public.accounts
  FOR DELETE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

-- =============================================================================
-- POLICIES: transactions (tenant-aware)
-- =============================================================================

CREATE POLICY transactions_tenant_policy_select ON public.transactions
  FOR SELECT
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY transactions_tenant_policy_insert ON public.transactions
  FOR INSERT
  TO authenticated
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY transactions_tenant_policy_update ON public.transactions
  FOR UPDATE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  )
  WITH CHECK (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

CREATE POLICY transactions_tenant_policy_delete ON public.transactions
  FOR DELETE
  TO authenticated
  USING (
    (tenant_id IS NOT NULL) AND
    (tenant_id = public.current_tenant_id()) AND
    (auth.uid() = user_id)
  );

-- =============================================================================
-- POLICIES: tenants / tenant_members
-- =============================================================================
-- Sem policies explícitas: acesso via service_role (backend apenas)
-- Frontend não acessa diretamente essas tabelas
-- =============================================================================

-- Nota: tenants e tenant_members têm RLS ativado mas sem policies.
-- Isso significa: anon/authenticated NÃO conseguem acessar.
-- Apenas service_role (backend) acessa essas tabelas.

-- =============================================================================
-- POLICIES: oauth_states
-- =============================================================================
-- Sem policies: acesso apenas via service_role (backend OAuth flow)
-- =============================================================================

COMMIT;

-- =============================================================================
-- Migration complete: RLS policies ready
-- Next: 20260303_000004_triggers.sql
-- =============================================================================
