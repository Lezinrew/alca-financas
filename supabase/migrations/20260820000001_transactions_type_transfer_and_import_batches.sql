-- =============================================================================
-- Migration: Suporte a transferências internas e governança de lotes OFX
-- Data: 2026-08-20
-- =============================================================================

-- 1. Atualizar CHECK constraint em public.transactions para permitir 'transfer'
ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_type_check;
ALTER TABLE public.transactions ADD CONSTRAINT transactions_type_check 
    CHECK (((type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying, 'transfer'::character varying])::text[])));

COMMENT ON CONSTRAINT transactions_type_check ON public.transactions IS 
    'Tipos válidos de transação: income (receita), expense (despesa), transfer (transferência interna).';

-- 2. Criar tabela de auditoria e governança de importações (import_batches)
CREATE TABLE IF NOT EXISTS public.import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    account_id UUID REFERENCES public.accounts(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    file_format TEXT NOT NULL DEFAULT 'ofx',
    total_parsed INT NOT NULL DEFAULT 0,
    imported_count INT NOT NULL DEFAULT 0,
    ignored_count INT NOT NULL DEFAULT 0,
    duplicate_count INT NOT NULL DEFAULT 0,
    unclassified_count INT NOT NULL DEFAULT 0,
    total_income NUMERIC(15,2) DEFAULT 0.00,
    total_expense NUMERIC(15,2) DEFAULT 0.00,
    total_transfer NUMERIC(15,2) DEFAULT 0.00,
    ledger_balance NUMERIC(15,2),
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('preview', 'completed', 'rolled_back')),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    rolled_back_at TIMESTAMPTZ
);

-- 3. Adicionar coluna import_batch_id na tabela transactions
ALTER TABLE public.transactions ADD COLUMN IF NOT EXISTS import_batch_id UUID REFERENCES public.import_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_transactions_import_batch_id ON public.transactions(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_import_batches_tenant_user ON public.import_batches(tenant_id, user_id);

-- 4. RLS para import_batches
ALTER TABLE public.import_batches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS import_batches_select ON public.import_batches;
DROP POLICY IF EXISTS import_batches_insert ON public.import_batches;
DROP POLICY IF EXISTS import_batches_update ON public.import_batches;
DROP POLICY IF EXISTS import_batches_delete ON public.import_batches;

CREATE POLICY import_batches_select ON public.import_batches
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.tenant_members tm
            WHERE tm.tenant_id = import_batches.tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY import_batches_insert ON public.import_batches
    FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.tenant_members tm
            WHERE tm.tenant_id = import_batches.tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY import_batches_update ON public.import_batches
    FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.tenant_members tm
            WHERE tm.tenant_id = import_batches.tenant_id
              AND tm.user_id = auth.uid()
        )
    );

CREATE POLICY import_batches_delete ON public.import_batches
    FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.tenant_members tm
            WHERE tm.tenant_id = import_batches.tenant_id
              AND tm.user_id = auth.uid()
        )
    );

GRANT SELECT, INSERT, UPDATE, DELETE ON public.import_batches TO authenticated;
