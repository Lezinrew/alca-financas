-- =====================================================
-- MIGRATION 002: Fix Row Level Security (RLS) Policies
-- =====================================================
-- CRÍTICO: Corrige políticas RLS que permitiam acesso
-- não autorizado a dados de outros usuários
--
-- Execute no Supabase SQL Editor:
-- https://app.supabase.com/project/_/sql
-- =====================================================

-- 1. REMOVER políticas antigas (inseguras)
DROP POLICY IF EXISTS "Users can view own data" ON users;
DROP POLICY IF EXISTS "Users can insert own data" ON users;
DROP POLICY IF EXISTS "Users can update own data" ON users;
DROP POLICY IF EXISTS "Users can view own categories" ON categories;
DROP POLICY IF EXISTS "Users can manage own categories" ON categories;
DROP POLICY IF EXISTS "Users can view own accounts" ON accounts;
DROP POLICY IF EXISTS "Users can manage own accounts" ON accounts;
DROP POLICY IF EXISTS "Users can view own transactions" ON transactions;
DROP POLICY IF EXISTS "Users can manage own transactions" ON transactions;

-- 2. CRIAR políticas SEGURAS para USERS
-- Nota: auth.uid() retorna o ID do usuário autenticado no Supabase Auth

CREATE POLICY "users_select_own" ON users
    FOR SELECT
    USING (id::text = auth.uid()::text);

CREATE POLICY "users_insert_own" ON users
    FOR INSERT
    WITH CHECK (id::text = auth.uid()::text);

CREATE POLICY "users_update_own" ON users
    FOR UPDATE
    USING (id::text = auth.uid()::text);

-- Não permitir DELETE de usuários via RLS (usar endpoint admin)
-- Se precisar, adicione:
-- CREATE POLICY "users_delete_own" ON users
--     FOR DELETE USING (id::text = auth.uid()::text);

-- 3. CRIAR políticas SEGURAS para CATEGORIES

CREATE POLICY "categories_select_own" ON categories
    FOR SELECT
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "categories_insert_own" ON categories
    FOR INSERT
    WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "categories_update_own" ON categories
    FOR UPDATE
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "categories_delete_own" ON categories
    FOR DELETE
    USING (user_id::text = auth.uid()::text);

-- 4. CRIAR políticas SEGURAS para ACCOUNTS

CREATE POLICY "accounts_select_own" ON accounts
    FOR SELECT
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "accounts_insert_own" ON accounts
    FOR INSERT
    WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "accounts_update_own" ON accounts
    FOR UPDATE
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "accounts_delete_own" ON accounts
    FOR DELETE
    USING (user_id::text = auth.uid()::text);

-- 5. CRIAR políticas SEGURAS para TRANSACTIONS

CREATE POLICY "transactions_select_own" ON transactions
    FOR SELECT
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "transactions_insert_own" ON transactions
    FOR INSERT
    WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "transactions_update_own" ON transactions
    FOR UPDATE
    USING (user_id::text = auth.uid()::text);

CREATE POLICY "transactions_delete_own" ON transactions
    FOR DELETE
    USING (user_id::text = auth.uid()::text);

-- 6. VERIFICAR que RLS está habilitado (redundante mas garante)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- VALIDAÇÃO (executar após aplicar migration)
-- =====================================================
-- Execute estas queries para confirmar que está funcionando:

-- 1. Ver policies criadas
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
-- FROM pg_policies
-- WHERE tablename IN ('users', 'categories', 'accounts', 'transactions')
-- ORDER BY tablename, policyname;

-- 2. Verificar RLS habilitado
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE tablename IN ('users', 'categories', 'accounts', 'transactions');

-- ✅ Migration completa - RLS agora está SEGURO
