# Dev e prod ao mesmo tempo — o que costuma “partir”

Quando se tenta fazer **desenvolvimento local** e **produção (VPS)** funcionarem em paralelo, o erro mais comum é **reutilizar um único `.env` ou copiar variáveis cruzadas**. O sintoma típico é **login OK no Supabase** mas **401 em `/api/*`** no site em produção (ou o contrário no local).

## Porquê?

1. **Um projeto Supabase ≠ outro**  
   Se no PC usas `SUPABASE_URL` / `SUPABASE_JWT_SECRET` do projeto **dev** e o frontend em `alcahub.cloud` foi buildado com `VITE_SUPABASE_*` do **prod** (ou o inverso), o token emitido por um projeto **nunca** passa na validação do backend configurado para o outro.

2. **JWT Secret tem de ser do mesmo projeto que emite o token**  
   `SUPABASE_JWT_SECRET` no Flask tem de ser o **JWT Secret** (Settings → API) do **mesmo** `SUPABASE_URL` que o utilizador usa no login (o mesmo `VITE_SUPABASE_URL` no build).

3. **`VITE_*` é “congelado” no build**  
   O que está em `npm run build` no servidor **não** lê o teu `.env` local. Se buildaste com URLs de dev e o backend em prod usa outro Supabase → 401.

4. **`VITE_API_URL` em produção**  
   Em prod costuma ficar **vazio** ou **URL absoluta correta** para a API pública. Se apontar para `http://localhost:8001`, o browser dos utilizadores chama o **computador deles**, não o teu servidor.

5. **Dois backends a usar o mesmo `.env` na VPS**  
   Se alteraste o `.env` em `/var/www/alca-financas` para “parecer dev” (URLs locais, outro Supabase), **produção** deixa de validar os tokens certos.

## Regra prática

| Onde | Ficheiro / origem | Regra |
|------|-------------------|--------|
| **Máquina local** | `.env` na raiz (não commitar) | Um conjunto coerente: mesmo `SUPABASE_*` + frontend `vite`/`npm run dev` com o **mesmo** projeto Supabase. |
| **VPS produção** | `.env` só no servidor + secrets CI | Outro conjunto **só** para prod: `SUPABASE_URL` + `SUPABASE_JWT_SECRET` + build com `VITE_SUPABASE_*` **desse** projeto. |
| **Dois Supabase (dev + prod)** | Dois projetos no dashboard | Nunca misturar: backend prod **só** vê prod; local **só** vê dev. |

## Como recuperar produção

1. No Supabase **de produção**: copiar **Project URL** e **JWT Secret** (e anon para o frontend).  
2. No servidor: `.env` do backend com `SUPABASE_URL` e `SUPABASE_JWT_SECRET` **desse** projeto.  
3. Rebuild do frontend com `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` **desse** mesmo projeto.  
4. Limpar dados do site em `alcahub.cloud` e voltar a entrar.  
5. Ver [`TROUBLESHOOTING-AUTH-LOGIN-LOOP.md`](TROUBLESHOOTING-AUTH-LOGIN-LOOP.md) se persistir 401.

Para um **prompt reutilizável** (lista de hipóteses + plano de triagem) a usar com um LLM, ver [`PROMPT-DIAGNOSTICO-DEV-PROD-AUTH.md`](PROMPT-DIAGNOSTICO-DEV-PROD-AUTH.md).

## Opcional: dois ficheiros locais

- `.env.development` / `.env.production.local` (cada um com o seu Supabase), **sem** commit.  
- Nunca fazer `scp` do `.env` do laptop para a VPS sem rever linha a linha.
