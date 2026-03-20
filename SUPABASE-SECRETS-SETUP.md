# Configuração dos Secrets do Supabase no GitHub

## Problema
O frontend de produção não tem acesso às credenciais do Supabase durante o build, causando o erro:
```
Supabase não configurado. Defina VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY no ambiente do frontend.
```

## Solução
Adicionar os secrets do Supabase no GitHub Actions para que sejam injetados durante o build do frontend.

### Rebuild manual no VPS (imediato)

Se o site já está no ar mas o bundle foi gerado **sem** as variáveis, o erro continua até **voltar a fazer o build** com `VITE_SUPABASE_*` definidas.

1. No servidor, garanta `/var/www/alca-financas/.env` com **pelo menos**:
   - `VITE_SUPABASE_URL=https://SEU_PROJETO.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=` (chave **anon** do dashboard)

2. Execute na raiz do projeto:
   ```bash
   chmod +x scripts/rebuild-frontend-prod-on-server.sh
   ./scripts/rebuild-frontend-prod-on-server.sh
   ```

3. Confirme que a URL do Supabase entrou no JS: `grep -r supabase.co build/frontend/assets/ | head -1`

---

## 📋 Passo a Passo

### 1. Obter as credenciais do Supabase

Você já tem essas informações no arquivo `frontend/.env` local:
```env
VITE_SUPABASE_URL=https://blutjlzyvhdvnkvrzdcm.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. Adicionar secrets no GitHub

**Via CLI (RECOMENDADO - mais rápido):**
```bash
# Na raiz do repositório local, execute:

gh secret set VITE_SUPABASE_URL --body "https://blutjlzyvhdvnkvrzdcm.supabase.co"

gh secret set VITE_SUPABASE_ANON_KEY --body "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg"
```

**Via Interface Web (alternativa):**
1. Acesse https://github.com/Lezinrew/alca-financas/settings/secrets/actions
2. Clique em "New repository secret"
3. Adicione os dois secrets:
   - Nome: `VITE_SUPABASE_URL`
     Valor: `https://blutjlzyvhdvnkvrzdcm.supabase.co`

   - Nome: `VITE_SUPABASE_ANON_KEY`
     Valor: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg`

### 3. Verificar secrets configurados
```bash
gh secret list
```

Você deve ver:
```
PROD_HOST              2026-03-14
PROD_PASSWORD          2026-03-14
PROD_USER              2026-03-14
VITE_SUPABASE_ANON_KEY 2026-03-XX  (NOVO)
VITE_SUPABASE_URL      2026-03-XX  (NOVO)
```

---

## 🚀 Deploy Imediato (FIX URGENTE)

### Opção 1: Trigger deploy via push (commit vazio)
```bash
git commit --allow-empty -m "fix(prod): add supabase env vars to frontend build"
git push origin main
```

Isso vai:
1. Disparar CI/CD Pipeline - Supabase
2. Após CI passar, disparar `deploy-production.yml`
3. Fazer build do frontend **COM** as variáveis do Supabase
4. Deploy em produção
5. Executar smoke tests

### Opção 2: Deploy manual via SSH (mais rápido, sem CI/CD)
```bash
ssh lezinrew@$PROD_HOST

# No servidor:
cd /var/www/alca-financas

# Rebuild do frontend com variáveis corretas
docker run --rm \
  -e VITE_SUPABASE_URL="https://blutjlzyvhdvnkvrzdcm.supabase.co" \
  -e VITE_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg" \
  -e VITE_API_URL="http://localhost:8001" \
  -v /var/www/alca-financas/frontend:/app \
  -w /app \
  node:22-alpine \
  sh -c "npm ci && npm run build"

# Copiar build para nginx
rm -rf build/frontend
mkdir -p build/frontend
cp -a frontend/dist/. build/frontend/

# Reiniciar frontend
docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

# Verificar logs
docker compose -f docker-compose.prod.yml logs -f frontend
```

---

## 🧪 Validação

### 1. Verificar build do frontend
```bash
# No servidor, após deploy:
ls -lah /var/www/alca-financas/build/frontend/

# Deve conter:
# - index.html
# - assets/*.js
# - assets/*.css
```

### 2. Verificar variáveis no bundle JavaScript
```bash
# No servidor:
grep -r "blutjlzyvhdvnkvrzdcm" /var/www/alca-financas/build/frontend/assets/*.js

# Deve retornar match - significa que a URL do Supabase está "baked" no bundle
```

### 3. Testar no navegador
1. Acesse http://$PROD_HOST:3000
2. Abra o DevTools Console (F12)
3. Faça login
4. Faça logout
5. **NÃO deve aparecer erro de "Supabase não configurado"**

---

## 📝 O que foi alterado?

### `.github/workflows/deploy-production.yml`
```yaml
# ANTES (SEM variáveis):
docker run --rm \
  -v /var/www/alca-financas/frontend:/app \
  -w /app \
  node:22-alpine \
  sh -c "npm ci && npm run build"

# DEPOIS (COM variáveis do Supabase):
docker run --rm \
  -e VITE_SUPABASE_URL="$VITE_SUPABASE_URL" \
  -e VITE_SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY" \
  -e VITE_API_URL="http://localhost:8001" \
  -v /var/www/alca-financas/frontend:/app \
  -w /app \
  node:22-alpine \
  sh -c "npm ci && npm run build"
```

### `frontend/Dockerfile`
```dockerfile
# Adicionados ARG e ENV para aceitar variáveis durante build
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_URL=http://localhost:8001

ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_API_URL=$VITE_API_URL
```

---

## ⚠️ Importante

**NUNCA commitar o arquivo `frontend/.env` no repositório!**

- ✅ Ambiente local: usa `frontend/.env` (gitignored)
- ✅ Produção: usa GitHub Secrets → injetados via `-e` no docker run
- ❌ NUNCA adicionar `.env` ao git (contém credenciais públicas, mas ainda assim deve ser protegido)

---

## 🔍 Troubleshooting

### "Secret not found" durante deploy
- Verifique que os secrets foram criados no repositório correto
- Execute `gh secret list` para confirmar

### Build bem-sucedido mas erro persiste no navegador
- Limpe o cache do navegador (Ctrl+Shift+Delete)
- Faça hard refresh (Ctrl+F5)
- Verifique se o nginx está servindo o novo build: `docker compose -f docker-compose.prod.yml logs frontend`

### Erro 500 ao acessar a aplicação
- Verifique logs do backend: `docker compose -f docker-compose.prod.yml logs backend`
- Verifique health do backend: `curl http://localhost:8001/api/health`
