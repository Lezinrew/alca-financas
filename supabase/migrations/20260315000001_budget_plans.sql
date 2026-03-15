-- =============================================================================
-- Migration: budget_monthly + budget_plans (Planning module)
-- Separação clara: planejamento (budget_*) vs transações reais (transactions).
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- -----------------------------------------------------------------------------
-- budget_monthly: receita planejada e % economia por tenant/mês
-- Uma linha por (tenant_id, month, year).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.budget_monthly (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    month smallint NOT NULL,
    year smallint NOT NULL,
    planned_income numeric(15,2) NOT NULL DEFAULT 0,
    savings_percentage numeric(5,2) NOT NULL DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT budget_monthly_month_check CHECK (month >= 1 AND month <= 12),
    CONSTRAINT budget_monthly_year_check CHECK (year >= 2020 AND year <= 2100),
    CONSTRAINT budget_monthly_savings_check CHECK (savings_percentage >= 0 AND savings_percentage <= 100)
);

ALTER TABLE ONLY public.budget_monthly ADD CONSTRAINT budget_monthly_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.budget_monthly
    ADD CONSTRAINT budget_monthly_tenant_month_year_unique UNIQUE (tenant_id, month, year);
ALTER TABLE ONLY public.budget_monthly
    ADD CONSTRAINT budget_monthly_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_budget_monthly_tenant_year_month
    ON public.budget_monthly USING btree (tenant_id, year, month);

-- -----------------------------------------------------------------------------
-- budget_plans: valor planejado por categoria por tenant/mês
-- planned_amount = limite/orça para essa categoria no mês.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.budget_plans (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    month smallint NOT NULL,
    year smallint NOT NULL,
    category_id uuid NOT NULL,
    planned_amount numeric(15,2) NOT NULL DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT budget_plans_month_check CHECK (month >= 1 AND month <= 12),
    CONSTRAINT budget_plans_year_check CHECK (year >= 2020 AND year <= 2100)
);

ALTER TABLE ONLY public.budget_plans ADD CONSTRAINT budget_plans_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.budget_plans
    ADD CONSTRAINT budget_plans_tenant_month_year_category_unique UNIQUE (tenant_id, month, year, category_id);
ALTER TABLE ONLY public.budget_plans
    ADD CONSTRAINT budget_plans_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.budget_plans
    ADD CONSTRAINT budget_plans_category_id_fkey
    FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_budget_plans_tenant_year_month
    ON public.budget_plans USING btree (tenant_id, year, month);
CREATE INDEX IF NOT EXISTS idx_budget_plans_category_id
    ON public.budget_plans USING btree (category_id);

-- RLS: backend usa service_role (bypass). Policies para uso futuro com client.
ALTER TABLE public.budget_monthly ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.budget_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY budget_monthly_tenant_select ON public.budget_monthly
    FOR SELECT USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_monthly_tenant_insert ON public.budget_monthly
    FOR INSERT WITH CHECK (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_monthly_tenant_update ON public.budget_monthly
    FOR UPDATE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_monthly_tenant_delete ON public.budget_monthly
    FOR DELETE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));

CREATE POLICY budget_plans_tenant_select ON public.budget_plans
    FOR SELECT USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_plans_tenant_insert ON public.budget_plans
    FOR INSERT WITH CHECK (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_plans_tenant_update ON public.budget_plans
    FOR UPDATE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY budget_plans_tenant_delete ON public.budget_plans
    FOR DELETE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));

COMMIT;
