-- =============================================================================
-- Migration: 20260726000003_merchant_aliases_remove_personal_global_seed
-- Description:
--   O seed inicial de merchant_category_aliases (20260318000001) inseriu
--   aliases de estabelecimentos pessoais/hiperlocais com escopo GLOBAL
--   (tenant_id IS NULL AND user_id IS NULL) — ou seja, visível e aplicado
--   a QUALQUER tenant que exista ou venha a existir nesta instância.
--
--   Isso é o mesmo problema do achado S6 (CATEGORY_KEYWORDS hardcoded em
--   Python), só que já persistido em banco: 'LULI BABY', 'DIJAN RESTAURANTE',
--   'JL PRODUTOS ALIMEMTICI' e 'POSTO MINEIRAO' são nomes de estabelecimento
--   de um único usuário, não classificadores genéricos.
--
--   Esta migration remove APENAS essas 4 entradas do escopo global. Termos
--   genéricos (POSTO, RESTAURANTE, BABY, PIX MARKETPLACE, MERCADO PAGO,
--   COMPANHIA BRASILEIRA DE EDUCACAO — nome legal real de empresa, não
--   pessoal) permanecem, por serem aplicáveis a qualquer tenant.
--
--   Se o usuário titular ainda quiser esses 4 aliases específicos, deve
--   recriá-los escopados ao próprio tenant_id/user_id via a API de
--   merchant-aliases (routes/merchant_aliases.py) — não como seed global.
--
-- COMO APLICAR: supabase db push, ou colar no SQL Editor.
-- IDEMPOTÊNCIA: DELETE com WHERE explícito, seguro para rodar mais de uma vez.
--
-- ROLLBACK: reinserir as linhas originais de 20260318000001 se necessário.
-- =============================================================================

BEGIN;

SET client_min_messages = warning;

DELETE FROM public.merchant_category_aliases
WHERE tenant_id IS NULL
  AND user_id IS NULL
  AND normalized_value IN (
    lower(trim('POSTO MINEIRAO')),
    lower(trim('DIJAN RESTAURANTE')),
    lower(trim('JL PRODUTOS ALIMEMTICI')),
    lower(trim('LULI BABY'))
  );

COMMIT;
