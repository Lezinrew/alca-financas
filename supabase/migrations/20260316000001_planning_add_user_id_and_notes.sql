-- =============================================================================
-- Migration: budget_plans — add user_id, notes; unique by (tenant_id, user_id, year, month, category_id)
-- Dependencies: 20260315000001_budget_plans.sql, 20260303_000002_functions.sql
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- Add user_id (nullable first for backfill)
ALTER TABLE public.budget_plans
  ADD COLUMN IF NOT EXISTS user_id uuid;

-- Backfill: one user per tenant (first member)
UPDATE public.budget_plans bp
SET user_id = (
  SELECT tm.user_id
  FROM public.tenant_members tm
  WHERE tm.tenant_id = bp.tenant_id
  ORDER BY tm.created_at ASC
  LIMIT 1
)
WHERE bp.user_id IS NULL;

ALTER TABLE public.budget_plans
  ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE public.budget_plans
  DROP CONSTRAINT IF EXISTS budget_plans_user_id_fkey;
ALTER TABLE public.budget_plans
  ADD CONSTRAINT budget_plans_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- Add notes
ALTER TABLE public.budget_plans
  ADD COLUMN IF NOT EXISTS notes text;

-- planned_amount >= 0
ALTER TABLE public.budget_plans
  DROP CONSTRAINT IF EXISTS budget_plans_planned_positive;
ALTER TABLE public.budget_plans
  ADD CONSTRAINT budget_plans_planned_positive CHECK (planned_amount >= 0);

-- Drop old unique, add new unique with user_id
ALTER TABLE public.budget_plans
  DROP CONSTRAINT IF EXISTS budget_plans_tenant_month_year_category_unique;
ALTER TABLE public.budget_plans
  ADD CONSTRAINT budget_plans_tenant_user_year_month_category_unique
  UNIQUE (tenant_id, user_id, month, year, category_id);

-- Index for list by user/tenant/month/year
CREATE INDEX IF NOT EXISTS idx_budget_plans_tenant_user_year_month
  ON public.budget_plans USING btree (tenant_id, user_id, year, month);

-- Trigger updated_at (reuse existing function)
DROP TRIGGER IF EXISTS update_budget_plans_updated_at ON public.budget_plans;
CREATE TRIGGER update_budget_plans_updated_at
  BEFORE UPDATE ON public.budget_plans
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_budget_monthly_updated_at ON public.budget_monthly;
CREATE TRIGGER update_budget_monthly_updated_at
  BEFORE UPDATE ON public.budget_monthly
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

COMMIT;
