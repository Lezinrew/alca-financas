# Deploy no Render.com - Passo a Passo

## BACKEND

### 1. Criar Web Service

1. Acesse: https://dashboard.render.com/
2. Clique: **New +** → **Web Service**
3. Conecte ao GitHub (autorize se necessário)
4. Selecione repositório: **alca-financas**

### 2. Configurações Básicas

```
Name: alca-financas-backend
Region: Oregon (US West) ou Ohio (US East)
Branch: main
Root Directory: backend
Runtime: Python 3
```

### 3. Build & Deploy

```
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app -c gunicorn.conf.py
```

### 4. Instance Type

```
Instance Type: Free
```

### 5. Environment Variables

Copie TODAS as variáveis de `RENDER_BACKEND_ENV.txt` e cole no Render:

1. Clique em **Advanced**
2. Clique em **Add Environment Variable**
3. Cole cada variável (ou use "Add from .env")

**IMPORTANTE**: Substitua `SUPABASE_SERVICE_ROLE_KEY` pelo valor real do Supabase.

### 6. Deploy

1. Clique: **Create Web Service**
2. Aguarde: ~3-5 minutos (build + deploy)
3. Status: Deve ficar "Live" (verde)

### 7. Testar

Após deploy completo, teste o health check:

```bash
curl https://alca-financas-backend.onrender.com/api/health
```

Esperado: `{"status": "ok"}`

### 8. Copiar URL

Anote a URL do backend para usar no frontend:
```
https://alca-financas-backend.onrender.com
```

---

## FRONTEND

### 1. Criar Static Site

1. Render Dashboard → **New +** → **Static Site**
2. Selecione: **alca-financas**

### 2. Configurações

```
Name: alca-financas-frontend
Region: Oregon (US West)
Branch: main
Root Directory: frontend
Build Command: npm install && npm run build
Publish Directory: dist
```

### 3. Environment Variables

```
VITE_API_URL=https://alca-financas-backend.onrender.com
VITE_SUPABASE_URL=https://blutjlzyvhdvnkvrzdcm.supabase.co
VITE_SUPABASE_ANON_KEY=VALOR_DA_ANON_KEY_DO_SUPABASE
```

### 4. Deploy

1. Clique: **Create Static Site**
2. Aguarde: ~2-3 minutos
3. Status: Deve ficar "Live"

### 5. Atualizar CORS no Backend

Após obter URL do frontend (ex: `https://alca-financas-frontend.onrender.com`):

1. Render → Backend Service → Environment
2. Atualizar variáveis:
   ```
   FRONTEND_URL=https://alca-financas-frontend.onrender.com
   CORS_ORIGINS=https://alca-financas-frontend.onrender.com
   ```
3. Save Changes (vai fazer redeploy automático)

---

## VALIDAÇÃO FINAL

1. Backend health: `curl https://alca-financas-backend.onrender.com/api/health`
2. Frontend abre no navegador
3. Login funciona
4. Dashboard mostra dados
5. HTTPS funcionando (cadeado verde)
6. Console do navegador sem erros CORS

---

## TROUBLESHOOTING

### Backend não inicia
- Render → Logs → Verificar erros
- Comum: "SECRET_KEY não configurado" → Verificar Environment Variables

### Frontend não conecta ao backend
- F12 → Console → Verificar erros CORS
- Solução: Atualizar CORS_ORIGINS no backend

### "Invalid API key" do Supabase
- Verificar se está usando SERVICE_ROLE_KEY no backend
- Verificar se está usando ANON_KEY no frontend
