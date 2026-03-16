-- =============================================================================
-- Migration: merchant_category_aliases (aliases de comerciante/descrição -> categoria)
-- Objetivo: camada persistente para mapear descrições recorrentes (ex.: Nubank OFX)
-- Dependencies: 20260303_000001_init.sql, 20260303_000002_functions.sql
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- ---------------------------------------------------------------------------
-- Tabela de aliases de comerciante/descrição para categorias
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.merchant_category_aliases (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id uuid NULL,
    user_id uuid NULL,
    match_type text NOT NULL, -- 'exact', 'prefix', 'contains'
    match_value text NOT NULL, -- valor original (para referência)
    normalized_value text NOT NULL, -- valor normalizado (lowercase, sem espaços extras)
    category_name text NOT NULL,
    category_type text NOT NULL, -- 'income' ou 'expense'
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT merchant_alias_match_type_check CHECK (match_type IN ('exact', 'prefix', 'contains')),
    CONSTRAINT merchant_alias_category_type_check CHECK (category_type IN ('income', 'expense'))
);

-- Unicidade por escopo + tipo + valor normalizado
ALTER TABLE public.merchant_category_aliases
  ADD CONSTRAINT merchant_alias_unique_scope UNIQUE (tenant_id, user_id, match_type, normalized_value, category_type);

-- Índices úteis
CREATE INDEX IF NOT EXISTS idx_merchant_alias_user_tenant
  ON public.merchant_category_aliases (tenant_id, user_id);

CREATE INDEX IF NOT EXISTS idx_merchant_alias_normalized
  ON public.merchant_category_aliases (normalized_value);

-- Triggers de updated_at
DROP TRIGGER IF EXISTS update_merchant_aliases_updated_at ON public.merchant_category_aliases;
CREATE TRIGGER update_merchant_aliases_updated_at
  BEFORE UPDATE ON public.merchant_category_aliases
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------------
-- Aliases globais iniciais (Nubank / merchants comuns)
-- Escopo global: tenant_id e user_id nulos
-- ---------------------------------------------------------------------------
INSERT INTO public.merchant_category_aliases
  (tenant_id, user_id, match_type, match_value, normalized_value, category_name, category_type)
VALUES
  -- Postos de combustível
  (NULL, NULL, 'contains', 'POSTO', lower(trim('POSTO')), 'Transporte', 'expense'),
  (NULL, NULL, 'contains', 'POSTO MINEIRAO', lower(trim('POSTO MINEIRAO')), 'Transporte', 'expense'),

  -- Restaurantes / alimentação
  (NULL, NULL, 'contains', 'RESTAURANTE', lower(trim('RESTAURANTE')), 'Alimentação', 'expense'),
  (NULL, NULL, 'contains', 'DIJAN RESTAURANTE', lower(trim('DIJAN RESTAURANTE')), 'Alimentação', 'expense'),
  (NULL, NULL, 'contains', 'JL PRODUTOS ALIMEMTICI', lower(trim('JL PRODUTOS ALIMEMTICI')), 'Alimentação', 'expense'),

  -- Baby / filhos
  (NULL, NULL, 'contains', 'LULI BABY', lower(trim('LULI BABY')), 'Filhos', 'expense'),
  (NULL, NULL, 'contains', 'BABY', lower(trim('BABY')), 'Filhos', 'expense'),

  -- Lazer / entretenimento
  (NULL, NULL, 'contains', 'GENTRETENIMENTO', lower(trim('GENTRETENIMENTO')), 'Lazer', 'expense'),

  -- Educação
  (NULL, NULL, 'contains', 'COMPANHIA BRASILEIRA DE EDUCACAO', lower(trim('COMPANHIA BRASILEIRA DE EDUCACAO')), 'Educação', 'expense'),

  -- Marketplace / compras online
  (NULL, NULL, 'contains', 'PIX MARKETPLACE', lower(trim('PIX MARKETPLACE')), 'Compras online', 'expense'),
  (NULL, NULL, 'contains', 'MERCADO PAGO', lower(trim('MERCADO PAGO')), 'Compras online', 'expense'),

  -- Pix enviado / recebido
  (NULL, NULL, 'contains', 'TRANSFERÊNCIA ENVIADA PELO PIX', lower(trim('TRANSFERÊNCIA ENVIADA PELO PIX')), 'Pix Enviado', 'expense'),
  (NULL, NULL, 'contains', 'TRANSFERENCIA ENVIADA PELO PIX', lower(trim('TRANSFERENCIA ENVIADA PELO PIX')), 'Pix Enviado', 'expense'),
  (NULL, NULL, 'contains', 'TRANSFERÊNCIA RECEBIDA PELO PIX', lower(trim('TRANSFERÊNCIA RECEBIDA PELO PIX')), 'Pix Recebido', 'income'),
  (NULL, NULL, 'contains', 'TRANSFERENCIA RECEBIDA PELO PIX', lower(trim('TRANSFERENCIA RECEBIDA PELO PIX')), 'Pix Recebido', 'income')
ON CONFLICT (tenant_id, user_id, match_type, normalized_value, category_type) DO NOTHING;

COMMIT;

