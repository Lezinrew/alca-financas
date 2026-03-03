-- =============================================================================
-- Migration: 20260303_000004_triggers
-- Description: Database triggers for automatic column updates
-- Dependencies: 20260303_000002_functions.sql (requires update_updated_at_column())
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

-- =============================================================================
-- TRIGGERS: update_updated_at
-- =============================================================================
-- Atualiza automaticamente coluna updated_at em UPDATE
-- Usa função update_updated_at_column() definida em 000002_functions.sql
-- =============================================================================

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_categories_updated_at
  BEFORE UPDATE ON public.categories
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_accounts_updated_at
  BEFORE UPDATE ON public.accounts
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at
  BEFORE UPDATE ON public.transactions
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

COMMIT;

-- =============================================================================
-- Migration complete: Triggers ready
-- Schema is now fully initialized
-- =============================================================================
