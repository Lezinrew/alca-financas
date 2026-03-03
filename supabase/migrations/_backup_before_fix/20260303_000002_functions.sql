-- =============================================================================
-- Migration: 20260303_000002_functions
-- Description: Helper functions for RLS and triggers
-- Dependencies: 20260303_000001_init.sql (requires tables to exist)
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

-- =============================================================================
-- FUNCTION: current_app_user_id()
-- =============================================================================
-- Retorna o user_id definido via set_config('app.current_user_id', ...)
-- Usado quando não se usa Supabase Auth (conexões diretas ao Postgres)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.current_app_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid;
$$;

COMMENT ON FUNCTION public.current_app_user_id() IS
  'Retorna o user_id definido por set_config(app.current_user_id, ...) na sessão. Usado por RLS quando não se usa Supabase Auth.';

-- =============================================================================
-- FUNCTION: current_tenant_id()
-- =============================================================================
-- Retorna o tenant_id do contexto atual
-- Prioridade:
--   1. JWT claim: request.jwt.claim.tenant_id (Supabase Auth com custom claims)
--   2. Session variable: app.current_tenant_id (conexão direta Postgres)
-- =============================================================================

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

-- =============================================================================
-- FUNCTION: update_updated_at_column()
-- =============================================================================
-- Trigger function: atualiza automaticamente coluna updated_at em UPDATE
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.update_updated_at_column() IS
  'Trigger function to automatically update updated_at column on row UPDATE';

-- =============================================================================
-- FUNCTION: dev_seed_account() [SECURITY DEFINER]
-- =============================================================================
-- Helper para seed de desenvolvimento (bypassa RLS)
-- ATENÇÃO: SECURITY DEFINER = executa com privilégios do owner (postgres)
-- USO: Apenas em seeds de dev, nunca expor via API
-- =============================================================================

CREATE OR REPLACE FUNCTION public.dev_seed_account(
    p_name text,
    p_type text,
    p_user_id uuid,
    p_tenant_id uuid
)
RETURNS public.accounts
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_row public.accounts;
BEGIN
  INSERT INTO public.accounts (name, type, user_id, tenant_id)
  VALUES (p_name, p_type, p_user_id, p_tenant_id)
  RETURNING * INTO v_row;

  RETURN v_row;
END;
$$;

COMMENT ON FUNCTION public.dev_seed_account(text, text, uuid, uuid) IS
  'SECURITY DEFINER: Helper for dev seed data (bypasses RLS). DO NOT expose via API.';

COMMIT;

-- =============================================================================
-- Migration complete: Functions ready
-- Next: 20260303_000003_rls_policies.sql
-- =============================================================================
