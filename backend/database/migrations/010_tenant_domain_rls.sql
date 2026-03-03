-- =============================================================================
-- 010_tenant_domain_rls.sql
-- Tenant-aware RLS for domain tables (categories, accounts, transactions)
--
-- Rollout goals:
--   - Enforce tenant_id = current_tenant_id() for any row with tenant_id set.
--   - Preserve legacy user_id-based policies for rows where tenant_id IS NULL.
--   - Keep behavior non-breaking while the application migrates.
--
-- Identity: auth.uid() (Supabase Auth). For current_app_user_id() variants,
-- adapt this file accordingly.
--
-- POLICY MATRIX (table x command x policyname x expression)
-- ---------------------------------------------------------------------------
-- categories | SELECT  | categories_select_own (legacy)   | tenant_id IS NULL AND auth.uid() = user_id
-- categories | INSERT  | categories_insert_own (legacy)   | tenant_id IS NULL AND auth.uid() = user_id
-- categories | UPDATE  | categories_update_own (legacy)   | tenant_id IS NULL AND auth.uid() = user_id (USING + WITH CHECK)
-- categories | DELETE  | categories_delete_own (legacy)   | tenant_id IS NULL AND auth.uid() = user_id
-- categories | SELECT  | categories_tenant_policy_select  | tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id
-- categories | INSERT  | categories_tenant_policy_insert  | tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id (WITH CHECK)
-- categories | UPDATE  | categories_tenant_policy_update  | same (USING + WITH CHECK)
-- categories | DELETE  | categories_tenant_policy_delete  | same (USING)
-- accounts   | SELECT  | accounts_select_own (legacy)     | tenant_id IS NULL AND auth.uid() = user_id
-- accounts   | INSERT  | accounts_insert_own (legacy)     | tenant_id IS NULL AND auth.uid() = user_id
-- accounts   | UPDATE  | accounts_update_own (legacy)     | tenant_id IS NULL AND auth.uid() = user_id (USING + WITH CHECK)
-- accounts   | DELETE  | accounts_delete_own (legacy)     | tenant_id IS NULL AND auth.uid() = user_id
-- accounts   | SELECT  | accounts_tenant_policy_select   | tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id
-- accounts   | INSERT  | accounts_tenant_policy_insert   | (WITH CHECK) same
-- accounts   | UPDATE  | accounts_tenant_policy_update   | (USING + WITH CHECK) same
-- accounts   | DELETE  | accounts_tenant_policy_delete   | (USING) same
-- transactions | SELECT  | transactions_select_own (legacy)  | tenant_id IS NULL AND auth.uid() = user_id
-- transactions | INSERT  | transactions_insert_own (legacy)  | tenant_id IS NULL AND auth.uid() = user_id
-- transactions | UPDATE  | transactions_update_own (legacy)  | tenant_id IS NULL AND auth.uid() = user_id (USING + WITH CHECK)
-- transactions | DELETE  | transactions_delete_own (legacy)  | tenant_id IS NULL AND auth.uid() = user_id
-- transactions | SELECT  | transactions_tenant_policy_select | tenant_id IS NOT NULL AND tenant_id = current_tenant_id() AND auth.uid() = user_id
-- transactions | INSERT  | transactions_tenant_policy_insert | (WITH CHECK) same
-- transactions | UPDATE  | transactions_tenant_policy_update | (USING + WITH CHECK) same
-- transactions | DELETE  | transactions_tenant_policy_delete | (USING) same
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. CATEGORIES: guard (table + tenant_id exist), legacy ALTER, tenant policies
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  v_has_tenant_id boolean;
  v_table_exists boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'categories'
  ) INTO v_table_exists;
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'categories' AND column_name = 'tenant_id'
  ) INTO v_has_tenant_id;

  IF NOT v_table_exists OR NOT v_has_tenant_id THEN
    RETURN;
  END IF;

  -- Legacy: narrow to tenant_id IS NULL (only if policy exists)
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_select_own') THEN
    ALTER POLICY "categories_select_own" ON public.categories
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_insert_own') THEN
    ALTER POLICY "categories_insert_own" ON public.categories
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_update_own') THEN
    ALTER POLICY "categories_update_own" ON public.categories
      USING (tenant_id IS NULL AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_delete_own') THEN
    ALTER POLICY "categories_delete_own" ON public.categories
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;

  -- Tenant-aware: create each command policy only if missing
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_tenant_policy_select') THEN
    CREATE POLICY "categories_tenant_policy_select" ON public.categories
      FOR SELECT USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_tenant_policy_insert') THEN
    CREATE POLICY "categories_tenant_policy_insert" ON public.categories
      FOR INSERT WITH CHECK (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_tenant_policy_update') THEN
    CREATE POLICY "categories_tenant_policy_update" ON public.categories
      FOR UPDATE
      USING (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'categories' AND policyname = 'categories_tenant_policy_delete') THEN
    CREATE POLICY "categories_tenant_policy_delete" ON public.categories
      FOR DELETE USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
END$$;

-- -----------------------------------------------------------------------------
-- 2. ACCOUNTS: guard (table + tenant_id exist), legacy ALTER, tenant policies
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  v_has_tenant_id boolean;
  v_table_exists boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'accounts'
  ) INTO v_table_exists;
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'accounts' AND column_name = 'tenant_id'
  ) INTO v_has_tenant_id;

  IF NOT v_table_exists OR NOT v_has_tenant_id THEN
    RETURN;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_select_own') THEN
    ALTER POLICY "accounts_select_own" ON public.accounts
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_insert_own') THEN
    ALTER POLICY "accounts_insert_own" ON public.accounts
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_update_own') THEN
    ALTER POLICY "accounts_update_own" ON public.accounts
      USING (tenant_id IS NULL AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_delete_own') THEN
    ALTER POLICY "accounts_delete_own" ON public.accounts
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_tenant_policy_select') THEN
    CREATE POLICY "accounts_tenant_policy_select" ON public.accounts
      FOR SELECT USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_tenant_policy_insert') THEN
    CREATE POLICY "accounts_tenant_policy_insert" ON public.accounts
      FOR INSERT WITH CHECK (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_tenant_policy_update') THEN
    CREATE POLICY "accounts_tenant_policy_update" ON public.accounts
      FOR UPDATE
      USING (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'accounts' AND policyname = 'accounts_tenant_policy_delete') THEN
    CREATE POLICY "accounts_tenant_policy_delete" ON public.accounts
      FOR DELETE USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
END$$;

-- -----------------------------------------------------------------------------
-- 3. TRANSACTIONS: guard (table + tenant_id exist), legacy ALTER, tenant policies
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  v_has_tenant_id boolean;
  v_table_exists boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'transactions'
  ) INTO v_table_exists;
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'transactions' AND column_name = 'tenant_id'
  ) INTO v_has_tenant_id;

  IF NOT v_table_exists OR NOT v_has_tenant_id THEN
    RETURN;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_select_own') THEN
    ALTER POLICY "transactions_select_own" ON public.transactions
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_insert_own') THEN
    ALTER POLICY "transactions_insert_own" ON public.transactions
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_update_own') THEN
    ALTER POLICY "transactions_update_own" ON public.transactions
      USING (tenant_id IS NULL AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_delete_own') THEN
    ALTER POLICY "transactions_delete_own" ON public.transactions
      USING (tenant_id IS NULL AND auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_tenant_policy_select') THEN
    CREATE POLICY "transactions_tenant_policy_select" ON public.transactions
      FOR SELECT USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_tenant_policy_insert') THEN
    CREATE POLICY "transactions_tenant_policy_insert" ON public.transactions
      FOR INSERT WITH CHECK (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_tenant_policy_update') THEN
    CREATE POLICY "transactions_tenant_policy_update" ON public.transactions
      FOR UPDATE
      USING (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id)
      WITH CHECK (tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'transactions' AND policyname = 'transactions_tenant_policy_delete') THEN
    CREATE POLICY "transactions_tenant_policy_delete" ON public.transactions
      FOR DELETE USING (
        tenant_id IS NOT NULL AND tenant_id = public.current_tenant_id() AND auth.uid() = user_id
      );
  END IF;
END$$;

-- -----------------------------------------------------------------------------
-- 4. Verification: NOTICE per table (skipped vs applied)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  r RECORD;
  v_table_exists boolean;
  v_has_tenant_id boolean;
BEGIN
  FOR r IN (SELECT unnest(ARRAY['categories', 'accounts', 'transactions']) AS tbl) LOOP
    SELECT EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = r.tbl
    ) INTO v_table_exists;
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = r.tbl AND column_name = 'tenant_id'
    ) INTO v_has_tenant_id;

    IF NOT v_table_exists OR NOT v_has_tenant_id THEN
      RAISE NOTICE 'Skipped %: tenant_id missing', r.tbl;
    ELSE
      RAISE NOTICE 'Applied policies on %', r.tbl;
    END IF;
  END LOOP;
END$$;

COMMIT;
