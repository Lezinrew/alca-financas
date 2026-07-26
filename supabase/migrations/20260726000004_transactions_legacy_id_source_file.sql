-- =============================================================================
-- Migration: 20260726000004_transactions_legacy_id_source_file
-- Description:
--   transactions.legacy_id: preserva o ID sequencial inteiro do FinanceOS
--   (planilha Excel) para rastreabilidade após a migração — sem isso, uma
--   re-execução do script de migração não tem como saber quais linhas já
--   foram carregadas, e o histórico de 34 abas perde a referência cruzada
--   com a linha original da planilha.
--   transactions.source_file: preserva "Arquivo Origem" da TabelaTransacoes
--   (proveniência do import original, quando aplicável).
--
--   Parte da execução da ADR-0008 (FinanceOS) — ver
--   specs/proposals/2026-07-26-migracao-financeos-supabase-fase1.md §4.
--
-- COMO APLICAR: supabase db push, ou colar no SQL Editor.
-- IDEMPOTÊNCIA: usa IF NOT EXISTS.
--
-- ROLLBACK:
--   DROP INDEX IF EXISTS idx_transactions_tenant_legacy_id;
--   ALTER TABLE public.transactions DROP COLUMN IF EXISTS legacy_id;
--   ALTER TABLE public.transactions DROP COLUMN IF EXISTS source_file;
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS legacy_id integer,
    ADD COLUMN IF NOT EXISTS source_file text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_tenant_legacy_id
    ON public.transactions (tenant_id, legacy_id)
    WHERE legacy_id IS NOT NULL;

COMMENT ON COLUMN public.transactions.legacy_id IS
    'ID sequencial original da TabelaTransacoes do FinanceOS (Excel), preservado para rastreabilidade pós-migração (ADR-0008).';
COMMENT ON COLUMN public.transactions.source_file IS
    'Coluna "Arquivo Origem" original do FinanceOS, quando aplicável.';

COMMIT;
