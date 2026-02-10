# Chaves do Supabase (backend)

O backend aceita duas formas de chave para conectar ao Supabase.

## 1. Secret key nova (`sb_secret_...`)

- **Onde:** Project Settings → **API** → **Secret keys** → copie a chave `sb_secret_...`.
- **No .env:** `SUPABASE_KEY=sb_secret_...`
- O código adapta essa chave para o cliente Python (supabase-py só aceita JWT por padrão).

## 2. JWT legado (fallback)

Se a chave `sb_secret_...` der erro ("Invalid API key"), use o **JWT legado**:

- **Onde:** Project Settings → **API** → **JWT Keys**.
  - Se o painel mostrar chave **Legacy** ou **service_role** em formato JWT (começa com `eyJ...`), copie esse valor.
  - Em alguns projetos há aba "Legacy JWT Secret" ou opção para revelar as chaves antigas (anon / service_role em JWT).
- **No .env:** defina **SUPABASE_LEGACY_JWT** com esse JWT:
  ```env
  SUPABASE_LEGACY_JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```
- A **SUPABASE_LEGACY_JWT** tem prioridade sobre **SUPABASE_KEY**: se estiver definida e for um JWT (`eyJ...`), o backend usa ela.

## Ordem de uso

1. `SUPABASE_LEGACY_JWT` (se existir e for JWT)
2. `SUPABASE_SERVICE_KEY` (se existir)
3. `SUPABASE_KEY`

Assim você pode manter `SUPABASE_KEY=sb_secret_...` e, se der problema, adicionar só `SUPABASE_LEGACY_JWT=eyJ...` com o JWT do painel (JWT Keys / chave legada).
