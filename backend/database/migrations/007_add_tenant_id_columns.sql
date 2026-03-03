-- =============================================================================
-- 007_add_tenant_id_columns.sql
-- Add nullable tenant_id to domain tables (phased migration)
-- =============================================================================

BEGIN;

-- Categories: add tenant_id (nullable) and composite index
ALTER TABLE public.categories
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

CREATE INDEX IF NOT EXISTS idx_categories_tenant_user
    ON public.categories(tenant_id, user_id);

-- Accounts: add tenant_id (nullable) and composite index
ALTER TABLE public.accounts
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

CREATE INDEX IF NOT EXISTS idx_accounts_tenant_user
    ON public.accounts(tenant_id, user_id);

-- Transactions: add tenant_id (nullable) and composite index
ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

CREATE INDEX IF NOT EXISTS idx_transactions_tenant_user_date
    ON public.transactions(tenant_id, user_id, date DESC);

COMMIT;

