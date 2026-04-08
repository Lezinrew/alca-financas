# Troubleshooting: 401 Loop após Login (Dev vs Prod)

## Sintoma

Após login aparentemente OK (ou após recriar utilizador no Supabase), o dashboard dispara **401** em:
- `GET /api/accounts`
- `GET /api/dashboard-advanced`
- `POST /api/auth/bootstrap`

Corpo da resposta: `{"error": "Token inválido ou expirado"}` (~40-44 bytes)

## Causa Raiz Comum: Mistura de Configs Dev/Prod

O erro **mais frequente** é reutilizar um único `.env` ou copiar variáveis cruzadas entre dev e prod.

### Por que isso causa 401?

1. **Um projeto Supabase ≠ outro**
   - Se o backend usa `SUPABASE_URL` / `SUPABASE_JWT_SECRET` do projeto **dev**
   - E o frontend foi buildado com `VITE_SUPABASE_*` do projeto **prod**
   - O token emitido por um projeto **nunca** passa na validação do backend configurado para o outro

2. **JWT Secret tem de ser do mesmo projeto que emite o token**
   - `SUPABASE_JWT_SECRET` no Flask **deve ser** o JWT Secret (Settings → API) do **mesmo** `SUPABASE_URL` que o utilizador usa no login

3. **`VITE_*` é "congelado" no build**
   - O que está em `npm run build` é fixo no bundle JavaScript
   - Se buildaste com URLs de dev e o backend em prod usa outro Supabase → 401

## Diagnóstico Passo a Passo

### 1. Verificar Configuração do Backend

```bash
# No servidor (SSH)
cd /var/www/alca-financas
grep -E "SUPABASE_URL|SUPABASE_JWT_SECRET" .env
```

**Validar:**
- `SUPABASE_JWT_SECRET` é o **JWT Secret** do Dashboard (Settings → API)
  - ⚠️ **NÃO** use o anon key
  - ⚠️ **NÃO** use o service role key

### 2. Testar JWT Manualmente

```bash
python3 backend/debug_jwt.py <access_token>
```

### 3. Verificar Logs do Backend

```bash
docker compose logs -f backend | grep -i "auth\|jwt\|401"
```

**Mensagens após o patch:**
- `JWT expirado - user precisa fazer refresh` → Normal
- `JWT com assinatura inválida (SUPABASE_JWT_SECRET errado?)` → **PROBLEMA**
- `JWT malformado` → Token corrompido

## Como Corrigir

### Cenário 1: Backend com Secret Errado

1. Acesse Supabase Dashboard → Settings → API → JWT Secret
2. Copie o **JWT Secret**
3. No servidor:
   ```bash
   nano /var/www/alca-financas/.env
   # Atualizar: SUPABASE_JWT_SECRET=<jwt-secret-correto>
   docker compose restart backend
   ```

### Cenário 2: Frontend Buildado com Projeto Errado

```bash
cd /var/www/alca-financas
./scripts/rebuild-frontend-on-server.sh
```

### Cenário 3: Dois Projetos Supabase (Dev + Prod)

**No servidor (prod):**
```bash
SUPABASE_URL=https://prod-project.supabase.co
SUPABASE_JWT_SECRET=<prod-jwt-secret>
VITE_SUPABASE_URL=https://prod-project.supabase.co
```

**No PC (dev local):**
```bash
SUPABASE_URL=https://dev-project.supabase.co
SUPABASE_JWT_SECRET=<dev-jwt-secret>
VITE_SUPABASE_URL=https://dev-project.supabase.co
```

## Validação Final

1. Limpar dados do site (DevTools → Application → Clear storage)
2. Fazer login novamente
3. Verificar dashboard carrega sem 401

## Referências

- `backend/utils/supabase_jwt.py` - Validação JWT
- `backend/debug_jwt.py` - Script de diagnóstico
- `DEPLOY.md` - Deploy workflow
