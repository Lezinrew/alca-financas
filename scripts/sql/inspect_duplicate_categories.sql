-- Lista grupos de categorias duplicadas (mesmo utilizador, tipo e nome normalizado).
-- Útil no SQL Editor do Supabase antes/depois da deduplicação.

SELECT
  c.user_id,
  c.type,
  lower(trim(regexp_replace(btrim(c.name), '\s+', ' ', 'g'))) AS norm_name,
  COUNT(*) AS category_rows,
  count(DISTINCT CASE WHEN c.tenant_id IS NOT NULL THEN c.tenant_id::text END) AS distinct_nonnull_tenants,
  array_agg(c.id ORDER BY c.created_at) AS category_ids,
  array_agg(c.name ORDER BY c.created_at) AS names,
  array_agg(c.tenant_id::text ORDER BY c.created_at) AS tenant_ids
FROM public.categories c
GROUP BY c.user_id, c.type, lower(trim(regexp_replace(btrim(c.name), '\s+', ' ', 'g')))
HAVING COUNT(*) > 1
ORDER BY c.user_id, norm_name;
