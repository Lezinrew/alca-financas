-- =============================================================================
-- Migration 005: Add Missing Account Columns (Fix PGRST204)
-- Alça Finanças - Execute no SQL Editor do Supabase
-- =============================================================================
-- OBJETIVO:
-- Corrigir o erro {'code': 'PGRST204', 'message': "Could not find the 'current_balance' column of 'accounts' in the schema cache"}.
-- O backend tenta inserir atributos de contas (inclusive cartões de crédito) que
-- não foram definidos no schema.sql original.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    -- 1. initial_balance
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='initial_balance') THEN
        ALTER TABLE public.accounts ADD COLUMN initial_balance DECIMAL(15, 2) DEFAULT 0.00;
    END IF;

    -- 2. current_balance
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='current_balance') THEN
        ALTER TABLE public.accounts ADD COLUMN current_balance DECIMAL(15, 2) DEFAULT 0.00;
    END IF;

    -- 3. institution
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='institution') THEN
        ALTER TABLE public.accounts ADD COLUMN institution VARCHAR(255);
    END IF;

    -- 4. is_active (mantém compatibilidade além de 'active')
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='is_active') THEN
        ALTER TABLE public.accounts ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;

    -- 5. closing_day (Para cartões de crédito)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='closing_day') THEN
        ALTER TABLE public.accounts ADD COLUMN closing_day INTEGER;
    END IF;

    -- 6. due_day (Para cartões de crédito)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='due_day') THEN
        ALTER TABLE public.accounts ADD COLUMN due_day INTEGER;
    END IF;

    -- 7. card_type (Para cartões de crédito)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='card_type') THEN
        ALTER TABLE public.accounts ADD COLUMN card_type VARCHAR(50);
    END IF;

    -- 8. account_id (Vínculo do cartão de crédito a uma conta-corrente)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='accounts' AND column_name='account_id') THEN
        ALTER TABLE public.accounts ADD COLUMN account_id UUID REFERENCES public.accounts(id) ON DELETE SET NULL;
    END IF;

END
$$;

-- Atualizar dados: migrar 'balance' legado para 'current_balance' e 'initial_balance', se aplicável
UPDATE public.accounts 
SET current_balance = balance, initial_balance = balance 
WHERE current_balance = 0.00 AND balance != 0.00;

-- Forçar o Supabase (PostgREST) a limpar o Schema Cache para reconhecer as novas colunas
NOTIFY pgrst, 'reload schema';

COMMIT;

-- FIM DA MIGRAÇÃO
