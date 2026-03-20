# 🚀 Deploy Rápido - Checklist Simplificado

**Use este guia para deploy rápido. Ver DEPLOY_PRODUCTION_GUIDE.md para detalhes completos.**

---

## ⚡ INÍCIO RÁPIDO (30 minutos)

### 1️⃣ Supabase (5 min)

```bash
# 1. Abrir Supabase SQL Editor
https://app.supabase.com/project/SEU_PROJETO/sql

# 2. Copiar e executar migration
cat backend/database/migrations/002_fix_rls_policies.sql
# Colar no SQL Editor e clicar RUN

# 3. Anotar credenciais de produção
# Project Settings > API:
# - SUPABASE_URL
# - service_role key (SERVICE_ROLE_KEY)
# - anon key (ANON_KEY)
```

✅ **Validar:** 15 policies criadas

---

### 2️⃣ Secrets de Produção (1 min)

```bash
# Copie estes valores:
SECRET_KEY=7be987749f78065916208fcdc892a9a67d75e980b8ff352796def22fc3d1b114
JWT_SECRET=d64e4a0d67f2c9a3e854cd8cd9284c3f226df8d30fa727b3771d07e5b91e8d0a
```

---

### 3️⃣ Deploy Backend - Render.com (10 min)

**A. Criar Web Service**
1. https://dashboard.render.com/create
2. Connect GitHub → alca-financas
3. Name: `alca-financas-backend`
4. Root Directory: `backend`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `gunicorn app:app`

**B. Environment Variables** (copiar tudo)
```bash
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ... (do Supabase)
SECRET_KEY=7be987749f78065916208fcdc892a9a67d75e980b8ff352796def22fc3d1b114
JWT_SECRET=d64e4a0d67f2c9a3e854cd8cd9284c3f226df8d30fa727b3771d07e5b91e8d0a
FLASK_ENV=production
FRONTEND_URL=https://alcahub.com.br
CORS_ORIGINS=https://alcahub.com.br,https://www.alcahub.com.br
```

**C. Deploy**
- Clicar: Create Web Service
- Aguardar: ~3 min
- Testar: https://alca-financas-backend.onrender.com/api/health

✅ **Validar:** `{"status": "ok"}`

---

### 4️⃣ Deploy Frontend - Render.com (10 min)

**A. Criar Static Site**
1. https://dashboard.render.com/create
2. Select Static Site
3. Connect GitHub → alca-financas
4. Name: `alca-financas-frontend`
5. Root Directory: `frontend`
6. Build Command: `npm install && npm run build`
7. Publish Directory: `dist`

**B. Environment Variables**
```bash
VITE_API_URL=https://alca-financas-backend.onrender.com
VITE_SUPABASE_URL=https://seu-projeto.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ... (anon key do Supabase)
```

**C. Deploy**
- Clicar: Create Static Site
- Aguardar: ~2 min
- Testar: Abrir URL no navegador

✅ **Validar:** Site carrega

---

### 5️⃣ Testes Básicos (5 min)

```bash
# 1. Health check
curl https://alca-financas-backend.onrender.com/api/health

# 2. Frontend carrega
# Abrir no navegador

# 3. Login funciona
# Fazer login no site

# 4. Dados aparecem
# Verificar dashboard
```

---

## 🌐 DOMÍNIO PERSONALIZADO (Opcional - 10 min)

### Backend (api.alcahub.com.br)

**Render:**
- Settings > Custom Domain
- Add: `api.alcahub.com.br`
- Copiar CNAME

**DNS Provider:**
```
Tipo: CNAME
Nome: api
Valor: alca-financas-backend.onrender.com
```

### Frontend (alcahub.com.br)

**Render:**
- Settings > Custom Domain
- Add: `alcahub.com.br`
- Copiar valores

**DNS Provider:**
```
Tipo: A
Nome: @
Valor: <IP do Render>
```

---

## ✅ CHECKLIST FINAL

- [ ] Backend rodando (health check OK)
- [ ] Frontend rodando (site abre)
- [ ] Login funciona
- [ ] Dashboard mostra dados
- [ ] RLS validado (só meus dados aparecem)
- [ ] HTTPS funcionando

---

## 🚨 SE ALGO DER ERRADO

### Backend não inicia
```bash
# Render > Logs
# Procurar por:
# - "SECRET_KEY não configurado"
# - "SUPABASE_URL não configurado"
# - Outros erros
```

**Solução:** Verificar Environment Variables

### Frontend não conecta
```bash
# Console do navegador (F12)
# Procurar por:
# - CORS errors
# - Network errors
```

**Solução:**
- Verificar VITE_API_URL
- Verificar CORS_ORIGINS no backend

### RLS bloqueando
- Backend DEVE usar SERVICE_ROLE_KEY
- Frontend DEVE usar ANON_KEY

---

## 📞 SUPORTE RÁPIDO

| Problema | Solução |
|----------|---------|
| "Secret not configured" | Adicionar SECRET_KEY e JWT_SECRET |
| "CORS error" | Adicionar domínio ao CORS_ORIGINS |
| "Database connection failed" | Verificar SUPABASE_URL e KEY |
| "502 Bad Gateway" | Backend ainda está fazendo build |

---

## 🎯 PRÓXIMO

Após deploy estável:
1. ✅ Monitorar logs (24h)
2. ✅ Configurar domínio personalizado
3. ✅ Adicionar monitoramento (Sentry)
4. ⏳ Implementar FASE 2 (rate limiting)

---

**Ver detalhes completos:** `DEPLOY_PRODUCTION_GUIDE.md`
