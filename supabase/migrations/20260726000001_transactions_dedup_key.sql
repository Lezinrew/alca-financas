-- =============================================================================
-- Migration: 20260726000001_transactions_dedup_key
-- Description:
--   - transactions.dedup_key: chave de deduplicação universal, calculada na
--     aplicação para TODO formato de importação (csv e ofx), não só fitid
--     (que só existe para OFX). Resolve duplicação silenciosa de CSV
--     reimportado (achado S4 do HARDCODE_AUDIT/análise comparativa).
--   - Fórmula (calculada em backend/services/import_service.py):
--       date | round(amount, 2) | upper(strip_accents(description)) | account_id | type
--   - Só é preenchida para transações importadas (entry_source IN ('csv','ofx')).
--     Transações manuais ficam com dedup_key NULL — o índice único é parcial
--     (WHERE dedup_key IS NOT NULL), então dois lançamentos manuais idênticos
--     no mesmo dia continuam permitidos.
--
-- COMO APLICAR (confirma o projeto Supabase: dev vs prod)
--   1) CLI: na raiz do repo, com CLI ligado ao projeto certo:
--        supabase db push
--   2) SQL Editor: colar o conteúdo deste ficheiro e executar uma vez.
--
-- PRÉ-REQUISITO: tabela public.transactions já existente com entry_source (20260417120001).
-- IDEMPOTÊNCIA: usa IF NOT EXISTS onde aplicável.
--
-- ROLLBACK (manual, só se necessário):
--   DROP INDEX IF EXISTS idx_transactions_tenant_dedup_key;
--   ALTER TABLE public.transactions DROP COLUMN IF EXISTS dedup_key;
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS dedup_key text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_tenant_dedup_key
    ON public.transactions (tenant_id, dedup_key)
    WHERE dedup_key IS NOT NULL;

COMMENT ON COLUMN public.transactions.dedup_key IS
    'Chave de deduplicação universal (csv + ofx). NULL para lançamentos manuais. Ver import_service.compute_dedup_key.';

COMMIT;

-- =============================================================================
-- NOTA: esta migration não faz backfill do histórico já importado antes dela
-- existir (transações antigas ficam com dedup_key NULL). Reimportar um arquivo
-- já carregado antes desta migration pode não ser pego pelo dedup_key para
-- essas linhas antigas especificamente — o fitid (quando presente, OFX)
-- continua funcionando como segunda camada de proteção independente.
-- =============================================================================
