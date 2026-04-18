-- =============================================================================
-- Migration: 20260417120001_transactions_entry_source_and_payable_source_tx
-- Description:
--   - transactions.entry_source: manual | csv | ofx (origem do registo)
--   - transactions.fitid: id OFX para deduplicação (se ainda não existir)
--   - financial_expenses.source_transaction_id: ligação opcional 1:1 à transação
--
-- COMO APLICAR (confirma o projeto Supabase: dev vs prod)
--   1) CLI: na raiz do repo, com CLI ligado ao projeto certo:
--        supabase db push
--      (ou `supabase migration up` conforme o vosso fluxo.)
--   2) SQL Editor: colar o conteúdo deste ficheiro e executar uma vez.
--
-- PRÉ-REQUISITO: tabelas public.transactions e public.financial_expenses já existentes.
-- IDEMPOTÊNCIA: usa IF NOT EXISTS / DROP CONSTRAINT IF EXISTS onde aplicável.
--
-- ROLLBACK (manual, só se necessário):
--   ALTER TABLE public.financial_expenses DROP CONSTRAINT IF EXISTS financial_expenses_source_transaction_id_fkey;
--   DROP INDEX IF EXISTS idx_financial_expenses_unique_source_tx;
--   DROP INDEX IF EXISTS idx_financial_expenses_tenant_source_tx;
--   ALTER TABLE public.financial_expenses DROP COLUMN IF EXISTS source_transaction_id;
--   DROP INDEX IF EXISTS idx_transactions_tenant_account_fitid;
--   ALTER TABLE public.transactions DROP COLUMN IF EXISTS fitid;
--   ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_entry_source_check;
--   ALTER TABLE public.transactions DROP COLUMN IF EXISTS entry_source;
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

-- ---------------------------------------------------------------------------
-- transactions
-- ---------------------------------------------------------------------------
ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS entry_source text;

UPDATE public.transactions
SET entry_source = 'manual'
WHERE entry_source IS NULL;

ALTER TABLE public.transactions
    ALTER COLUMN entry_source SET DEFAULT 'manual';

ALTER TABLE public.transactions
    ALTER COLUMN entry_source SET NOT NULL;

ALTER TABLE public.transactions
    DROP CONSTRAINT IF EXISTS transactions_entry_source_check;

ALTER TABLE public.transactions
    ADD CONSTRAINT transactions_entry_source_check CHECK (
        entry_source = ANY (ARRAY['manual'::text, 'csv'::text, 'ofx'::text])
    );

ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS fitid text;

CREATE INDEX IF NOT EXISTS idx_transactions_tenant_account_fitid
    ON public.transactions (tenant_id, account_id, fitid)
    WHERE fitid IS NOT NULL AND account_id IS NOT NULL;

COMMENT ON COLUMN public.transactions.entry_source IS 'Origem: manual (UI/API), csv ou ofx (importação).';
COMMENT ON COLUMN public.transactions.fitid IS 'Financial Institution Transaction ID (OFX), para dedupe.';

-- ---------------------------------------------------------------------------
-- financial_expenses → transactions (opcional, ON DELETE SET NULL)
-- ---------------------------------------------------------------------------
ALTER TABLE public.financial_expenses
    ADD COLUMN IF NOT EXISTS source_transaction_id uuid;

COMMENT ON COLUMN public.financial_expenses.source_transaction_id IS 'Transação de origem quando a conta a pagar foi gerada a partir do livro.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'financial_expenses_source_transaction_id_fkey'
    ) THEN
        ALTER TABLE ONLY public.financial_expenses
            ADD CONSTRAINT financial_expenses_source_transaction_id_fkey
            FOREIGN KEY (source_transaction_id)
            REFERENCES public.transactions (id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_expenses_unique_source_tx
    ON public.financial_expenses (source_transaction_id)
    WHERE source_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_financial_expenses_tenant_source_tx
    ON public.financial_expenses (tenant_id, source_transaction_id)
    WHERE source_transaction_id IS NOT NULL;

COMMIT;
