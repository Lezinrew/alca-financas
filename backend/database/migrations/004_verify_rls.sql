-- =============================================================================
-- Script de verificação pós-migração RLS
-- Alça Finanças - Execute no SQL Editor do Supabase após 002_drop e 003_apply
-- =============================================================================
-- Objetivo: Validar que RLS está ativo e que políticas estão restritas por
--           user_id / auth.uid(), e que não restam políticas USING (true).
-- =============================================================================

-- 1) Tabelas com RLS habilitado
SELECT
  schemaname,
  tablename,
  rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('users', 'categories', 'accounts', 'transactions', 'oauth_states')
ORDER BY tablename;

-- 2) Políticas por tabela (nome, comando, qual, with_check)
SELECT
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual AS using_expression,
  with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('users', 'categories', 'accounts', 'transactions', 'oauth_states')
ORDER BY tablename, policyname;

-- 3) Detectar políticas inseguras (qual = 'true' ou with_check = 'true')
SELECT
  tablename,
  policyname,
  'USING (true) ou WITH CHECK (true) - INSECURO' AS alert
FROM pg_policies
WHERE schemaname = 'public'
  AND (qual = 'true' OR with_check = 'true');

-- 4) Contagem esperada de políticas por tabela
-- users: 2 (select_own, update_own)
-- categories: 4 (select, insert, update, delete)
-- accounts: 4
-- transactions: 4
-- oauth_states: 0 (RLS on, sem política anon)
SELECT
  tablename,
  COUNT(*) AS policy_count
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('users', 'categories', 'accounts', 'transactions', 'oauth_states')
GROUP BY tablename
ORDER BY tablename;

-- 5) Teste de isolamento (executar como role anon ou com auth.uid() nulo)
-- Em uma sessão com SET ROLE anon; SELECT auth.uid(); deve retornar NULL.
-- Então SELECT em users/categories/accounts/transactions deve retornar 0 linhas.
-- (Não executar em produção com dados reais sem cuidado.)
/*
SET ROLE anon;
SELECT auth.uid();
SELECT COUNT(*) FROM public.users;
SELECT COUNT(*) FROM public.categories;
SET ROLE postgres;
*/
