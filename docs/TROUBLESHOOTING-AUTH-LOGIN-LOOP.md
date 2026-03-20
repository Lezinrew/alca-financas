# Login volta à tela de autenticação / Network com 401 e refresh falho

## O que o Network mostra

| Pedido | Significado |
|--------|-------------|
| `token?grant_type=password` **vermelho** | O **Supabase Auth** rejeitou email/senha (credenciais erradas, e-mail não confirmado, utilizador desativado) ou pedido bloqueado. Abra o pedido → **Resposta** / **Preview** e leia a mensagem JSON. |
| `token?grant_type=refresh_token` **vermelho** | O **refresh token** guardado no browser **já não existe** no projeto (ex.: apagou o utilizador no Dashboard e recriou com o mesmo e-mail — o `sub`/sessão mudou). |
| `bootstrap`, `accounts`, `dashboard-advanced` **401** | O **backend** não aceitou o JWT (`Authorization: Bearer`). Depois do interceptor: tenta `refreshSession`; se falhar → `signOut` → volta ao login. |
| `logout?scope=global` | Limpeza de sessão (normal após falha em cadeia). |

## Causa típica após “apagar e recriar” o utilizador no Supabase

1. O browser mantinha **sessão do utilizador antigo** (localStorage `sb-*`).
2. O refresh token é inválido → falha em cadeia → a app desloga.

## O que fazer (ordem)

1. **Limpar dados do site** em `alcahub.cloud`: DevTools → **Application** → **Storage** → **Clear site data** (ou janela anónima).
2. Entrar de novo com a **nova** palavra-passe do utilizador **novo** no Auth.
3. Confirmar no Supabase **Authentication → Users**: e-mail **Confirmed**, sem ban.

## O que o código já faz

- No **login**, antes de `signInWithPassword`, a app chama `signOut({ scope: 'local' })` e limpa tokens legados — reduz resíduos após recriar utilizador.
- No **Axios**, um **401** tenta `refreshSession` uma vez antes de deslogar.

## Se `password` continua vermelho

- Abra o pedido `token?grant_type=password` e veja o corpo (ex.: `invalid_grant`, `Email not confirmed`).
- Confirme que `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` no **build** do frontend são do **mesmo projeto** que o backend (`SUPABASE_URL` / JWT).

## Logs do backend: `401` com ~40–44 bytes no access log

Resposta típica: `{"error":"Token inválido ou expirado"}`. O **Bearer chegou** mas o Flask **não validou** o JWT.

1. **Mesmo projeto Supabase**  
   - `.env` do backend: `SUPABASE_URL=https://<ref>.supabase.co`  
   - Build do frontend: `VITE_SUPABASE_URL` com o **mesmo** `<ref>`.

2. **JWT Secret (HS256)**  
   - Dashboard Supabase → **Project Settings → API → JWT Secret** (Legacy)  
   - Backend: `SUPABASE_JWT_SECRET=<esse valor>`  
   - Se estiver vazio, o backend usa **JWKS**; aí o projeto tem de emitir tokens RS256 com `kid` válido. Misturar secret errado → 401.

3. **Audience opcional**  
   - Se definiste `SUPABASE_JWT_AUD` no backend, tem de coincidir com a claim `aud` do token (senão remove a variável).

4. **Nginx**  
   - Garantir que o header `Authorization` é repassado até o Gunicorn (no repo: `proxy_set_header Authorization $http_authorization;` em `nginx.conf` e em `nginx-vps.conf` no `location /`).

5. **Diagnóstico no servidor**  
   - Com `LOG_LEVEL` adequado, o backend regista `WARNING: Auth inválida (Supabase JWT): <motivo>` (sem expor o token).  
   - Teste manual: obtenha um `access_token` no browser (Application → Local Storage `sb-...-auth-token`) e:  
     `curl -s -H "Authorization: Bearer SEU_TOKEN" https://alcahub.cloud/api/auth/me`

## Scripts SQL manuais (`auth.users`)

Não misture **edição direta** em `auth.users` com o fluxo do **Supabase Auth** (hash Argon2, etc.). Preferir sempre **Dashboard** ou **API Auth** para criar/alterar utilizadores.
