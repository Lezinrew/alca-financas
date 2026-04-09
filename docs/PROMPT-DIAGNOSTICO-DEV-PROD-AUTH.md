# Prompt: diagnóstico dev + prod + auth (Alça Finanças)

Copie o bloco abaixo e cole num assistente (Claude, ChatGPT, etc.) **junto com** os outputs que pedimos (sem colar secrets completos — use `***` ou primeiros/últimos caracteres).

---

## Texto do prompt (copiar daqui)

```
Contexto: app Alça Finanças — React/Vite + Flask (Gunicorn) + Supabase Auth.
O utilizador tentou fazer desenvolvimento local e produção (VPS/domínio) ao mesmo tempo e passou a ter problemas (401 na API, loop de login, CORS, ou login Supabase OK mas /api/* falha).

Tarefa:
1) Listar TODAS as hipóteses plausíveis, agrupadas por categoria.
2) Para cada hipótese: sintoma típico no browser (Network) + o que verificar (env, build, nginx) + como confirmar ou descartar.
3) Ordenar um plano de triagem em 5–10 passos (do mais rápido ao mais invasivo).
4) Dizer explicitamente quando o problema é só configuração vs. bug de código.

Categorias obrigatórias a cobrir:

A) Cruzamento de ambientes Supabase
   - Frontend build com VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY de um projeto; backend com SUPABASE_URL/SUPABASE_JWT_SECRET de outro.
   - Dois projetos Supabase (dev e prod) misturados no mesmo .env ou copiado .env laptop → VPS.

B) JWT e backend
   - SUPABASE_JWT_SECRET errado, vazio, ou de projeto diferente (HS256).
   - SUPABASE_JWT_AUD definido e não bater com claim aud do token.
   - JWKS vs HS256 (projeto em modo assimétrico vs secret legacy).

C) Vite / build de produção
   - VITE_* não injetadas no build (site mostra erro de Supabase não configurado).
   - VITE_API_URL apontando para localhost em bundle servido em domínio público.
   - Build antigo em cache / CDN servindo JS com URLs antigas.

D) Nginx / proxy
   - Header Authorization não repassado ao upstream (401 mesmo com token válido).
   - Proxy para porta errada; 502 → CORS fantasma no browser.

E) Browser / sessão
   - localStorage sb-* de outro projeto ou utilizador apagado e recriado (refresh_token inválido).
   - Mesmo browser a alternar entre localhost:5173 e alcahub.cloud sem limpar storage.

F) CORS
   - CORS_ORIGINS no Flask sem o origin exato do front (incl. www vs apex).
   - 502 do proxy sem headers CORS (diagnóstico parece CORS mas raiz é upstream).

G) Docker / servidor
   - docker-compose ou systemd a carregar .env errado.
   - Duas instâncias do backend com configs diferentes.

H) Base de dados / Auth manual
   - Scripts SQL a mexer em auth.users em conflito com Supabase Auth (hash, sessões).
   - RLS ou policies não relacionadas a JWT 401 no Flask (mas mencionar se sintoma for “dados vazios” vs 401).

Saída desejada:
- Tabela ou lista: Hipótese | Sintomas | Checks | Resultado esperado se for essa a causa.
- Um parágrafo “mais provável primeiro” quando os sintomas forem: login Supabase OK + 401 em /api/accounts ou /api/auth/bootstrap.
- Lembrete: nunca pedir para colar service_role ou JWT secret completo em chat; usar confirmação “mesmo ref X.supabase.co em FE e BE” e “secret do mesmo projeto no dashboard”.
```

---

## Como usar

1. Cole o prompt acima no assistente.
2. Anexe ou cole **apenas**:
   - URLs públicas (domínio do front e da API, sem tokens).
   - Lista de **nomes** de variáveis presentes no `.env` do servidor (não os valores).
   - Screenshots ou lista de pedidos **falhados** no Network (URL + status + nome do pedido).
   - Trecho **redigido** de `curl -I` ou resposta de `/api/auth/me` com Bearer (sem o token completo).
3. Leia também no repo: `docs/DEV-E-PROD-SEM-MISTURAR-ENV.md` e `docs/TROUBLESHOOTING-AUTH-LOGIN-LOOP.md`.

## Relação com outros docs

| Documento | Uso |
|-----------|-----|
| `docs/DEV-E-PROD-SEM-MISTURAR-ENV.md` | Regras para não misturar env |
| `docs/TROUBLESHOOTING-AUTH-LOGIN-LOOP.md` | Passo a passo 401 / refresh / nginx |
| `docs/FIX-502-CORS-LOGIN.md` | 502 + CORS em produção |
| Este ficheiro | Prompt genérico para explorar **todas** as possibilidades |
