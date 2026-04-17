-- =============================================================================
-- Migration: 20260417000001_financial_expenses
-- Description: Contas a pagar (financial_expenses) + RLS tenant/user + índices
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS public.financial_expenses (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    title text NOT NULL,
    description text,
    category text NOT NULL,
    subcategory text,
    amount_expected numeric(12, 2) NOT NULL DEFAULT 0,
    amount_paid numeric(12, 2) NOT NULL DEFAULT 0,
    due_date date,
    paid_at timestamp with time zone,
    competency_month integer,
    competency_year integer,
    is_recurring boolean NOT NULL DEFAULT false,
    recurrence_type text,
    installment_current integer,
    installment_total integer,
    payment_method text,
    source_type text,
    responsible_person text,
    vehicle_name text,
    notes text,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT financial_expenses_pkey PRIMARY KEY (id),
    CONSTRAINT financial_expenses_status_check CHECK (
        status = ANY (ARRAY['pending'::text, 'partial'::text, 'paid'::text, 'canceled'::text])
    ),
    CONSTRAINT financial_expenses_category_check CHECK (
        category = ANY (ARRAY[
            'moradia'::text,
            'educação'::text,
            'saúde'::text,
            'transporte'::text,
            'veículos'::text,
            'cartões'::text,
            'dívidas'::text,
            'família'::text,
            'serviços'::text,
            'utilidades'::text,
            'impostos'::text,
            'alimentação'::text,
            'pessoal'::text,
            'outros'::text
        ])
    ),
    CONSTRAINT financial_expenses_competency_month_check CHECK (
        competency_month IS NULL OR (competency_month >= 1 AND competency_month <= 12)
    ),
    CONSTRAINT financial_expenses_competency_year_check CHECK (
        competency_year IS NULL OR (competency_year >= 2000 AND competency_year <= 2100)
    ),
    CONSTRAINT financial_expenses_amounts_non_negative CHECK (
        amount_expected >= 0::numeric AND amount_paid >= 0::numeric
    ),
    CONSTRAINT financial_expenses_installments_check CHECK (
        (installment_current IS NULL AND installment_total IS NULL)
        OR (
            installment_current IS NOT NULL
            AND installment_total IS NOT NULL
            AND installment_current >= 1
            AND installment_total >= 1
            AND installment_current <= installment_total
        )
    )
);

ALTER TABLE ONLY public.financial_expenses
    ADD CONSTRAINT financial_expenses_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.financial_expenses
    ADD CONSTRAINT financial_expenses_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_competency
    ON public.financial_expenses (tenant_id, competency_year, competency_month);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_status
    ON public.financial_expenses (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_category
    ON public.financial_expenses (tenant_id, category);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_responsible
    ON public.financial_expenses (tenant_id, responsible_person);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_recurring
    ON public.financial_expenses (tenant_id, is_recurring);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_due_date
    ON public.financial_expenses (tenant_id, due_date);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_outstanding_due
    ON public.financial_expenses (tenant_id, due_date)
    WHERE status = ANY (ARRAY['pending'::text, 'partial'::text]);

CREATE TRIGGER update_financial_expenses_updated_at
    BEFORE UPDATE ON public.financial_expenses
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.financial_expenses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS financial_expenses_tenant_policy_select ON public.financial_expenses;
DROP POLICY IF EXISTS financial_expenses_tenant_policy_insert ON public.financial_expenses;
DROP POLICY IF EXISTS financial_expenses_tenant_policy_update ON public.financial_expenses;
DROP POLICY IF EXISTS financial_expenses_tenant_policy_delete ON public.financial_expenses;

CREATE POLICY financial_expenses_tenant_policy_select ON public.financial_expenses
    FOR SELECT
    TO authenticated
    USING (
        tenant_id IS NOT NULL
        AND auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM public.tenant_members tm
            WHERE tm.tenant_id = tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY financial_expenses_tenant_policy_insert ON public.financial_expenses
    FOR INSERT
    TO authenticated
    WITH CHECK (
        tenant_id IS NOT NULL
        AND auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM public.tenant_members tm
            WHERE tm.tenant_id = tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY financial_expenses_tenant_policy_update ON public.financial_expenses
    FOR UPDATE
    TO authenticated
    USING (
        tenant_id IS NOT NULL
        AND auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM public.tenant_members tm
            WHERE tm.tenant_id = tenant_id
              AND tm.user_id = auth.uid()
        )
    )
    WITH CHECK (
        tenant_id IS NOT NULL
        AND auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM public.tenant_members tm
            WHERE tm.tenant_id = tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY financial_expenses_tenant_policy_delete ON public.financial_expenses
    FOR DELETE
    TO authenticated
    USING (
        tenant_id IS NOT NULL
        AND auth.uid() = user_id
        AND EXISTS (
            SELECT 1
            FROM public.tenant_members tm
            WHERE tm.tenant_id = tenant_id
              AND tm.user_id = auth.uid()
        )
    );

COMMIT;
