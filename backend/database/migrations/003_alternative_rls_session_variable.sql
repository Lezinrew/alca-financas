-- =============================================================================
-- Migration 003 (Alternativa): RLS com variável de sessão (custom auth, sem Supabase Auth)
-- Alça Finanças - Use apenas se o backend NÃO usar Supabase Auth e quiser
--                que RLS restrinja acesso quando usar uma conexão que respeita RLS.
-- =============================================================================
-- REQUISITO: O backend deve chamar, no início de cada request (por conexão),
--   SELECT set_config('app.current_user_id', '<user_id_uuid>', true);
-- Isso exige uso de SUPABASE_DB_URL (psycopg2) e conexão por request ou
-- middleware que injeta o user_id na sessão. O cliente Supabase REST (service_role)
-- NÃO suporta set_config por request; portanto com service_role esta alternativa
-- NÃO tem efeito (RLS continua bypassed).
--
-- Use esta alternativa apenas se migrar para conexão PostgreSQL direta por request
-- com um role que NÃO seja bypass de RLS (ex.: role "app_user" sem bypass).
-- =============================================================================

BEGIN;

-- Função auxiliar: retorna user_id da sessão (NULL se não definido)
CREATE OR REPLACE FUNCTION public.current_app_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid;
$$;

-- Comentário para documentação
COMMENT ON FUNCTION public.current_app_user_id() IS
  'Retorna o user_id definido por set_config(app.current_user_id, ...) na sessão. Usado por RLS quando não se usa Supabase Auth.';

-- -----------------------------------------------------------------------------
-- USERS (acesso apenas à própria linha: id = current_app_user_id())
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "users_select_own" ON public.users;
CREATE POLICY "users_select_own"
  ON public.users
  FOR SELECT
  USING (id = public.current_app_user_id());

DROP POLICY IF EXISTS "users_update_own" ON public.users;
CREATE POLICY "users_update_own"
  ON public.users
  FOR UPDATE
  USING (id = public.current_app_user_id())
  WITH CHECK (id = public.current_app_user_id());

-- -----------------------------------------------------------------------------
-- CATEGORIES
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "categories_select_own" ON public.categories;
CREATE POLICY "categories_select_own"
  ON public.categories
  FOR SELECT
  USING (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "categories_insert_own" ON public.categories;
CREATE POLICY "categories_insert_own"
  ON public.categories
  FOR INSERT
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "categories_update_own" ON public.categories;
CREATE POLICY "categories_update_own"
  ON public.categories
  FOR UPDATE
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "categories_delete_own" ON public.categories;
CREATE POLICY "categories_delete_own"
  ON public.categories
  FOR DELETE
  USING (user_id = public.current_app_user_id());

-- -----------------------------------------------------------------------------
-- ACCOUNTS
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "accounts_select_own" ON public.accounts;
CREATE POLICY "accounts_select_own"
  ON public.accounts
  FOR SELECT
  USING (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "accounts_insert_own" ON public.accounts;
CREATE POLICY "accounts_insert_own"
  ON public.accounts
  FOR INSERT
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "accounts_update_own" ON public.accounts;
CREATE POLICY "accounts_update_own"
  ON public.accounts
  FOR UPDATE
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "accounts_delete_own" ON public.accounts;
CREATE POLICY "accounts_delete_own"
  ON public.accounts
  FOR DELETE
  USING (user_id = public.current_app_user_id());

-- -----------------------------------------------------------------------------
-- TRANSACTIONS
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "transactions_select_own" ON public.transactions;
CREATE POLICY "transactions_select_own"
  ON public.transactions
  FOR SELECT
  USING (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "transactions_insert_own" ON public.transactions;
CREATE POLICY "transactions_insert_own"
  ON public.transactions
  FOR INSERT
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "transactions_update_own" ON public.transactions;
CREATE POLICY "transactions_update_own"
  ON public.transactions
  FOR UPDATE
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS "transactions_delete_own" ON public.transactions;
CREATE POLICY "transactions_delete_own"
  ON public.transactions
  FOR DELETE
  USING (user_id = public.current_app_user_id());

-- -----------------------------------------------------------------------------
-- OAUTH_STATES
-- -----------------------------------------------------------------------------
ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;
-- Sem política para anon/app: acesso apenas por service_role ou role com bypass.

COMMIT;
