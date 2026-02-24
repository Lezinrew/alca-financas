-- =============================================================================
-- Migration 003: RLS Secure Policies (Production-Grade)
-- Alça Finanças - PostgreSQL + Supabase
-- =============================================================================
-- OBJETIVO: Substituir políticas inseguras (USING true) por políticas restritas
--           por user_id (ou auth.uid() quando usar Supabase Auth).
--
-- CONTEXTO ATUAL: Backend usa SUPABASE_SERVICE_ROLE_KEY.
--   - A chave service_role BYPASSA RLS no Supabase.
--   - Estas políticas NÃO afetam o backend atual; protegem cenários onde
--     a anon key for usada (ex.: cliente direto, futuro uso de Supabase Auth).
--
-- PRÉ-REQUISITO: Execute 002_drop_insecure_rls_policies.sql antes.
--
-- SE O PROJETO AINDA NÃO USA SUPABASE AUTH:
--   auth.uid() será NULL para requisições anon. Políticas retornarão 0 linhas
--   (comportamento seguro). O backend com service_role não é afetado.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. USERS
-- Cada usuário só pode ver e atualizar o próprio registro (id = auth.uid()).
-- INSERT: apenas backend (service_role) ou trigger; anon sem política = negado.
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "users_select_own" ON public.users;
CREATE POLICY "users_select_own"
  ON public.users
  FOR SELECT
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "users_update_own" ON public.users;
CREATE POLICY "users_update_own"
  ON public.users
  FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- INSERT em users: não permitir via anon (criação por backend/signup flow).
-- Se usar Supabase Auth + trigger para criar linha em public.users, anon não precisa de INSERT aqui.

-- -----------------------------------------------------------------------------
-- 2. CATEGORIES
-- Acesso apenas a linhas onde user_id = auth.uid().
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "categories_select_own" ON public.categories;
CREATE POLICY "categories_select_own"
  ON public.categories
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "categories_insert_own" ON public.categories;
CREATE POLICY "categories_insert_own"
  ON public.categories
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "categories_update_own" ON public.categories;
CREATE POLICY "categories_update_own"
  ON public.categories
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "categories_delete_own" ON public.categories;
CREATE POLICY "categories_delete_own"
  ON public.categories
  FOR DELETE
  USING (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- 3. ACCOUNTS
-- Acesso apenas a linhas onde user_id = auth.uid().
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "accounts_select_own" ON public.accounts;
CREATE POLICY "accounts_select_own"
  ON public.accounts
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "accounts_insert_own" ON public.accounts;
CREATE POLICY "accounts_insert_own"
  ON public.accounts
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "accounts_update_own" ON public.accounts;
CREATE POLICY "accounts_update_own"
  ON public.accounts
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "accounts_delete_own" ON public.accounts;
CREATE POLICY "accounts_delete_own"
  ON public.accounts
  FOR DELETE
  USING (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- 4. TRANSACTIONS
-- Acesso apenas a linhas onde user_id = auth.uid().
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "transactions_select_own" ON public.transactions;
CREATE POLICY "transactions_select_own"
  ON public.transactions
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "transactions_insert_own" ON public.transactions;
CREATE POLICY "transactions_insert_own"
  ON public.transactions
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "transactions_update_own" ON public.transactions;
CREATE POLICY "transactions_update_own"
  ON public.transactions
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "transactions_delete_own" ON public.transactions;
CREATE POLICY "transactions_delete_own"
  ON public.transactions
  FOR DELETE
  USING (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- 5. OAUTH_STATES
-- Tabela sem user_id; usada apenas pelo backend no fluxo OAuth.
-- Não expor via anon: não criar políticas permissivas para anon.
-- Com RLS ativo e sem política, anon não acessa; service_role continua bypass.
-- -----------------------------------------------------------------------------
ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- Nenhuma política para anon: acesso apenas via service_role (backend).

COMMIT;
