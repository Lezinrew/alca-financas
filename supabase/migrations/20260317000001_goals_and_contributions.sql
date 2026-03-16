-- =============================================================================
-- Migration: goals + goal_contributions (módulo Metas)
-- Dependencies: 20260303_000001_init.sql (tenants, users), 20260303_000002_functions.sql (update_updated_at_column)
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- -----------------------------------------------------------------------------
-- goals: metas financeiras de longo prazo
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.goals (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    title text NOT NULL,
    description text,
    target_amount numeric(15,2) NOT NULL DEFAULT 0,
    current_amount numeric(15,2) NOT NULL DEFAULT 0,
    target_date date,
    image_url text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT goals_target_amount_non_negative CHECK (target_amount >= 0),
    CONSTRAINT goals_current_amount_non_negative CHECK (current_amount >= 0),
    CONSTRAINT goals_status_check CHECK (status IN ('active', 'completed', 'paused'))
);

ALTER TABLE ONLY public.goals ADD CONSTRAINT goals_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_goals_tenant_id ON public.goals USING btree (tenant_id);
CREATE INDEX IF NOT EXISTS idx_goals_user_id ON public.goals USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_goals_tenant_user ON public.goals USING btree (tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON public.goals USING btree (status);

-- -----------------------------------------------------------------------------
-- goal_contributions: aportes/depósitos em direção à meta
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.goal_contributions (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    goal_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    amount numeric(15,2) NOT NULL,
    date timestamp with time zone DEFAULT now(),
    source_type text,
    source_reference_id uuid,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT goal_contributions_amount_positive CHECK (amount > 0)
);

ALTER TABLE ONLY public.goal_contributions ADD CONSTRAINT goal_contributions_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.goal_contributions
    ADD CONSTRAINT goal_contributions_goal_id_fkey
    FOREIGN KEY (goal_id) REFERENCES public.goals(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.goal_contributions
    ADD CONSTRAINT goal_contributions_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.goal_contributions
    ADD CONSTRAINT goal_contributions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_goal_contributions_goal_id ON public.goal_contributions USING btree (goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_contributions_tenant_id ON public.goal_contributions USING btree (tenant_id);
CREATE INDEX IF NOT EXISTS idx_goal_contributions_user_id ON public.goal_contributions USING btree (user_id);
CREATE INDEX IF NOT EXISTS idx_goal_contributions_date ON public.goal_contributions USING btree (date);

-- RLS
ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.goal_contributions ENABLE ROW LEVEL SECURITY;

CREATE POLICY goals_tenant_select ON public.goals
    FOR SELECT USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goals_tenant_insert ON public.goals
    FOR INSERT WITH CHECK (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goals_tenant_update ON public.goals
    FOR UPDATE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goals_tenant_delete ON public.goals
    FOR DELETE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));

CREATE POLICY goal_contributions_tenant_select ON public.goal_contributions
    FOR SELECT USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goal_contributions_tenant_insert ON public.goal_contributions
    FOR INSERT WITH CHECK (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goal_contributions_tenant_update ON public.goal_contributions
    FOR UPDATE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));
CREATE POLICY goal_contributions_tenant_delete ON public.goal_contributions
    FOR DELETE USING (tenant_id IN (SELECT tenant_id FROM public.tenant_members WHERE user_id = current_setting('app.current_user_id', true)::uuid));

-- Triggers updated_at
DROP TRIGGER IF EXISTS update_goals_updated_at ON public.goals;
CREATE TRIGGER update_goals_updated_at
    BEFORE UPDATE ON public.goals
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

COMMIT;
