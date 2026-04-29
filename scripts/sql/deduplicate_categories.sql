-- Deduplicação de categorias (PostgreSQL / Supabase)
--
-- Pré-requisitos:
--   1) Backup da base (especialmente public.categories e public.transactions).
--   2) Executar em janela de manutenção se o volume for alto.
--
-- Regra de grupo: mesmo user_id + type + nome normalizado (trim, espaços colapsados, lower),
-- desde que exista no máximo um tenant_id distinto não nulo no grupo (não funde dois workspaces).
--
-- Canónica: tenant_id preenchido > legado NULL; depois mais transações; depois created_at mais antigo.
--
-- Idempotente: segunda execução não altera nada se já não houver duplicados.
--
-- Depois de correr com sucesso, aplique a migration 016_unique_category_normalized.sql (índice único).

BEGIN;

WITH cat_norm AS (
  SELECT
    c.id,
    c.user_id,
    c.tenant_id,
    c.type,
    lower(trim(regexp_replace(btrim(c.name), '\s+', ' ', 'g'))) AS norm_name,
    c.created_at
  FROM public.categories c
),
dup_groups AS (
  SELECT user_id, type, norm_name
  FROM cat_norm
  GROUP BY user_id, type, norm_name
  HAVING COUNT(*) > 1
    AND count(DISTINCT CASE WHEN tenant_id IS NOT NULL THEN tenant_id::text END) <= 1
),
ranked AS (
  SELECT
    cn.id,
    cn.user_id,
    cn.type,
    cn.norm_name,
    ROW_NUMBER() OVER (
      PARTITION BY cn.user_id, cn.type, cn.norm_name
      ORDER BY
        CASE WHEN cn.tenant_id IS NOT NULL THEN 0 ELSE 1 END,
        (SELECT COUNT(*)::bigint FROM public.transactions t WHERE t.category_id = cn.id) DESC,
        cn.created_at ASC NULLS LAST,
        cn.id::text
    ) AS rn
  FROM cat_norm cn
  INNER JOIN dup_groups dg
    ON dg.user_id = cn.user_id AND dg.type = cn.type AND dg.norm_name = cn.norm_name
),
loser_to_canonical AS (
  SELECT l.id AS loser_id, c.id AS canon_id
  FROM ranked l
  INNER JOIN ranked c
    ON c.rn = 1
    AND l.user_id = c.user_id
    AND l.type = c.type
    AND l.norm_name = c.norm_name
  WHERE l.rn > 1
)
UPDATE public.transactions t
SET category_id = m.canon_id,
    updated_at = NOW()
FROM loser_to_canonical m
WHERE t.category_id = m.loser_id;

WITH cat_norm AS (
  SELECT
    c.id,
    c.user_id,
    c.tenant_id,
    c.type,
    lower(trim(regexp_replace(btrim(c.name), '\s+', ' ', 'g'))) AS norm_name,
    c.created_at
  FROM public.categories c
),
dup_groups AS (
  SELECT user_id, type, norm_name
  FROM cat_norm
  GROUP BY user_id, type, norm_name
  HAVING COUNT(*) > 1
    AND count(DISTINCT CASE WHEN tenant_id IS NOT NULL THEN tenant_id::text END) <= 1
),
ranked AS (
  SELECT
    cn.id,
    cn.user_id,
    cn.type,
    cn.norm_name,
    ROW_NUMBER() OVER (
      PARTITION BY cn.user_id, cn.type, cn.norm_name
      ORDER BY
        CASE WHEN cn.tenant_id IS NOT NULL THEN 0 ELSE 1 END,
        (SELECT COUNT(*)::bigint FROM public.transactions t WHERE t.category_id = cn.id) DESC,
        cn.created_at ASC NULLS LAST,
        cn.id::text
    ) AS rn
  FROM cat_norm cn
  INNER JOIN dup_groups dg
    ON dg.user_id = cn.user_id AND dg.type = cn.type AND dg.norm_name = cn.norm_name
),
loser_to_canonical AS (
  SELECT l.id AS loser_id
  FROM ranked l
  WHERE l.rn > 1
)
DELETE FROM public.categories c
WHERE c.id IN (SELECT loser_id FROM loser_to_canonical)
  AND NOT EXISTS (
    SELECT 1 FROM public.transactions t WHERE t.category_id = c.id
  );

COMMIT;
