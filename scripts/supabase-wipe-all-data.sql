-- =============================================================================
-- ZERAR BASE (Postgres + Supabase Auth) — Alça Finanças
-- =============================================================================
-- Apaga TODOS os dados de negócio em public.* e TODOS os utilizadores em auth.*.
-- Não remove: storage.* (buckets/objetos), realtime.*, nem tabelas auth.* além da
-- cadeia sessions/identities/users (schema auth é gerido pelo Supabase).
--
-- Inventário public típico do projeto (ajusta se criares novas tabelas):
-- accounts, admin_audit_logs, admin_notification_delivery, budget_monthly,
-- budget_plans, categories, chatbot_conversations, financial_expenses,
-- goal_contributions, goals, merchant_category_aliases, migration_log,
-- oauth_states, tenant_members, tenants, transaction_tenant_inconsistencies,
-- transactions, users
--
-- USO: Supabase SQL Editor (ou psql). Confirma o projeto (dev vs prod).
-- Depois: volta a criar conta / login; o bootstrap da API recria tenant se aplicável.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Dados da aplicação (public)
-- ---------------------------------------------------------------------------
TRUNCATE TABLE
  public.transaction_tenant_inconsistencies,
  public.transactions,
  public.goal_contributions,
  public.goals,
  public.financial_expenses,
  public.budget_plans,
  public.budget_monthly,
  public.chatbot_conversations,
  public.merchant_category_aliases,
  public.accounts,
  public.categories,
  public.tenant_members,
  public.tenants,
  public.admin_notification_delivery,
  public.admin_audit_logs,
  public.users,
  public.oauth_states,
  public.migration_log
CASCADE;

-- ---------------------------------------------------------------------------
-- 2) Supabase Auth (todos os utilizadores e sessões)
-- ---------------------------------------------------------------------------
DELETE FROM auth.refresh_tokens;
DELETE FROM auth.sessions;
DELETE FROM auth.identities;

-- Se falhar aqui por MFA, corre antes: DELETE FROM auth.mfa_challenges; DELETE FROM auth.mfa_factors;
DELETE FROM auth.users;

COMMIT;

-- Verificação (correr à parte; deve tudo dar 0)
-- SELECT COUNT(*) AS n FROM public.users;
-- SELECT COUNT(*) AS n FROM public.categories;
-- SELECT COUNT(*) AS n FROM auth.users;
