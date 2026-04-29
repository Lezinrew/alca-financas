-- Índice único funcional: impede novas duplicatas equivalentes (nome normalizado + tipo + user + tenant).
-- Executar APÓS scripts/sql/deduplicate_categories.sql (ou garantir que não existem violações).
--
-- tenant_id NULL partilha o mesmo valor sentinela para legado (alinhado ao backend: um legado por chave).

CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_tenant_type_normname
ON public.categories (
  user_id,
  COALESCE(tenant_id::text, '__legacy_null__'),
  type,
  lower(trim(regexp_replace(btrim(name), '\s+', ' ', 'g')))
);
