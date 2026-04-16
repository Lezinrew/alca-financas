-- =============================================================================
-- Migration: reconcile public.users with auth.users (email-based)
-- Objetivo:
--   1) Corrigir conflitos de bootstrap quando o email já existe em public.users
--      com outro id (legado), enquanto o usuário autenticado tem auth.users.id diferente.
--   2) Reconciliar memberships (tenant_members) para o id canônico de auth.users.
--   3) Limpar registros legados de public.users quando não houver mais referências.
--
-- Segurança:
--   - Idempotente: pode ser executada mais de uma vez.
--   - Só reconcilia quando há match por email normalizado entre auth.users e public.users
--     com IDs diferentes.
-- =============================================================================

BEGIN;

SET statement_timeout = 0;
SET lock_timeout = 0;

-- -----------------------------------------------------------------------------
-- 1) Normalizar e criar mapeamento canônico (auth_id) <-> legado (public.users.id)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS tmp_user_reconcile_map;
CREATE TEMP TABLE tmp_user_reconcile_map (
  canonical_user_id uuid NOT NULL,
  legacy_user_id uuid NOT NULL,
  email_norm text NOT NULL,
  PRIMARY KEY (canonical_user_id, legacy_user_id)
) ON COMMIT DROP;

INSERT INTO tmp_user_reconcile_map (canonical_user_id, legacy_user_id, email_norm)
SELECT
  au.id AS canonical_user_id,
  pu.id AS legacy_user_id,
  lower(trim(au.email)) AS email_norm
FROM auth.users au
JOIN public.users pu
  ON lower(trim(pu.email)) = lower(trim(au.email))
WHERE au.email IS NOT NULL
  AND trim(au.email) <> ''
  AND au.id <> pu.id;

-- -----------------------------------------------------------------------------
-- 2) Garantir linha em public.users para o id canônico do auth.users
--    (caso ainda não exista)
--    Nota: quando o email já está preso ao legacy_user_id, cria temporariamente
--    com email interno para evitar violação de users_email_key.
-- -----------------------------------------------------------------------------
INSERT INTO public.users (id, email, name, password, settings, auth_providers, is_admin)
SELECT
  m.canonical_user_id AS id,
  CASE
    WHEN EXISTS (
      SELECT 1
      FROM public.users u_conf
      WHERE lower(trim(u_conf.email)) = m.email_norm
        AND u_conf.id <> m.canonical_user_id
    )
    THEN m.canonical_user_id::text || '@users.internal'
    ELSE m.email_norm
  END AS email,
  COALESCE(
    nullif(trim((au.raw_user_meta_data ->> 'name')), ''),
    split_part(m.email_norm, '@', 1),
    'Usuário'
  ) AS name,
  NULL::bytea AS password,
  '{"currency":"BRL","theme":"light","language":"pt"}'::jsonb AS settings,
  '[]'::jsonb AS auth_providers,
  false AS is_admin
FROM tmp_user_reconcile_map m
JOIN auth.users au ON au.id = m.canonical_user_id
LEFT JOIN public.users pu ON pu.id = m.canonical_user_id
WHERE pu.id IS NULL
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 3) Reconciliar tenant_members do usuário legado -> usuário canônico
-- -----------------------------------------------------------------------------
INSERT INTO public.tenant_members (tenant_id, user_id, role)
SELECT
  tm.tenant_id,
  m.canonical_user_id AS user_id,
  tm.role
FROM public.tenant_members tm
JOIN tmp_user_reconcile_map m
  ON m.legacy_user_id = tm.user_id
LEFT JOIN public.tenant_members tm2
  ON tm2.tenant_id = tm.tenant_id
 AND tm2.user_id = m.canonical_user_id
WHERE tm2.id IS NULL
ON CONFLICT (tenant_id, user_id) DO NOTHING;

DELETE FROM public.tenant_members tm
USING tmp_user_reconcile_map m
WHERE tm.user_id = m.legacy_user_id;

-- -----------------------------------------------------------------------------
-- 4) Reconciliar tabelas com FK user_id -> public.users(id)
--    (quando existentes no schema atual)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.categories') IS NOT NULL THEN
    UPDATE public.categories c
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE c.user_id = m.legacy_user_id;
  END IF;

  IF to_regclass('public.accounts') IS NOT NULL THEN
    UPDATE public.accounts a
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE a.user_id = m.legacy_user_id;
  END IF;

  IF to_regclass('public.transactions') IS NOT NULL THEN
    UPDATE public.transactions t
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE t.user_id = m.legacy_user_id;
  END IF;

  IF to_regclass('public.goals') IS NOT NULL THEN
    UPDATE public.goals g
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE g.user_id = m.legacy_user_id;
  END IF;

  IF to_regclass('public.goal_contributions') IS NOT NULL THEN
    UPDATE public.goal_contributions gc
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE gc.user_id = m.legacy_user_id;
  END IF;

  IF to_regclass('public.budget_plans') IS NOT NULL THEN
    -- Evita violar unique (tenant_id, user_id, month, year, category_id)
    DELETE FROM public.budget_plans bp_old
    USING public.budget_plans bp_new, tmp_user_reconcile_map m
    WHERE bp_old.user_id = m.legacy_user_id
      AND bp_new.user_id = m.canonical_user_id
      AND bp_old.tenant_id = bp_new.tenant_id
      AND bp_old.month = bp_new.month
      AND bp_old.year = bp_new.year
      AND bp_old.category_id IS NOT DISTINCT FROM bp_new.category_id;

    UPDATE public.budget_plans bp
    SET user_id = m.canonical_user_id
    FROM tmp_user_reconcile_map m
    WHERE bp.user_id = m.legacy_user_id;
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 5) Limpar public.users legados reconciliados, somente sem referências remanescentes
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  q text;
BEGIN
  q := '
    DELETE FROM public.users u
    USING tmp_user_reconcile_map m
    WHERE u.id = m.legacy_user_id
      AND NOT EXISTS (SELECT 1 FROM public.tenant_members tm WHERE tm.user_id = u.id)
  ';

  IF to_regclass('public.categories') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.categories c WHERE c.user_id = u.id)';
  END IF;
  IF to_regclass('public.accounts') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.accounts a WHERE a.user_id = u.id)';
  END IF;
  IF to_regclass('public.transactions') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.transactions t WHERE t.user_id = u.id)';
  END IF;
  IF to_regclass('public.goals') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.goals g WHERE g.user_id = u.id)';
  END IF;
  IF to_regclass('public.goal_contributions') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.goal_contributions gc WHERE gc.user_id = u.id)';
  END IF;
  IF to_regclass('public.budget_plans') IS NOT NULL THEN
    q := q || ' AND NOT EXISTS (SELECT 1 FROM public.budget_plans bp WHERE bp.user_id = u.id)';
  END IF;

  EXECUTE q;
END $$;

-- -----------------------------------------------------------------------------
-- 6) Restaurar email canônico após limpeza do legado (se não houver conflito)
-- -----------------------------------------------------------------------------
UPDATE public.users u
SET email = m.email_norm
FROM tmp_user_reconcile_map m
WHERE u.id = m.canonical_user_id
  AND lower(trim(u.email)) <> m.email_norm
  AND NOT EXISTS (
    SELECT 1
    FROM public.users u2
    WHERE lower(trim(u2.email)) = m.email_norm
      AND u2.id <> u.id
  );

COMMIT;

