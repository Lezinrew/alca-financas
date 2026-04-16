-- =============================================================================
-- Limpeza: tenants "personal-{uuid}" SEM nenhum tenant_members (órfãos).
-- Cenário: fallback antigo criou a linha em public.tenants e falhou o membership
--          (FK para public.users), deixando slug duplicado (23505) no próximo login.
--
-- Uso: Supabase Dashboard → SQL Editor → colar → primeiro só o bloco PREVIEW,
--      depois descomentar DELETE se a lista estiver correta.
-- =============================================================================

-- PREVIEW: órfãos (recomendado rodar antes)
SELECT t.id, t.slug, t.name, t.created_at
FROM public.tenants t
WHERE t.slug LIKE 'personal-%'
  AND NOT EXISTS (
    SELECT 1 FROM public.tenant_members tm WHERE tm.tenant_id = t.id
  )
ORDER BY t.created_at DESC;

-- DELETE (descomente após validar o preview)
-- DELETE FROM public.tenants t
-- WHERE t.slug LIKE 'personal-%'
--   AND NOT EXISTS (
--     SELECT 1 FROM public.tenant_members tm WHERE tm.tenant_id = t.id
--   );
