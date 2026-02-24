-- =============================================================================
-- Migration 002: Remover políticas RLS inseguras (USING true / WITH CHECK true)
-- Alça Finanças - PostgreSQL + Supabase
-- =============================================================================
-- Execute este script ANTES de 003_rls_secure_policies.sql.
-- Remove todas as políticas atuais que não restringem por user_id.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- USERS
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own data" ON public.users;
DROP POLICY IF EXISTS "Users can insert own data" ON public.users;
DROP POLICY IF EXISTS "Users can update own data" ON public.users;

-- -----------------------------------------------------------------------------
-- CATEGORIES
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own categories" ON public.categories;
DROP POLICY IF EXISTS "Users can manage own categories" ON public.categories;

-- -----------------------------------------------------------------------------
-- ACCOUNTS
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own accounts" ON public.accounts;
DROP POLICY IF EXISTS "Users can manage own accounts" ON public.accounts;

-- -----------------------------------------------------------------------------
-- TRANSACTIONS
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own transactions" ON public.transactions;
DROP POLICY IF EXISTS "Users can manage own transactions" ON public.transactions;

-- -----------------------------------------------------------------------------
-- OAUTH_STATES
-- Remover políticas se existirem (schema original não define políticas aqui).
-- -----------------------------------------------------------------------------
-- Nenhuma política nomeada no schema; deixar como está.

COMMIT;
