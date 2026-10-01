# 🚀 Guia de Deploy em Produção

**Data:** 2026-02-10
**Versão:** FASE 1 - Security Fixes

---

## ⚠️ PRÉ-REQUISITOS

### ✅ Antes de Fazer Deploy

- [ ] FASE 1 completa e testada localmente
- [ ] Secrets de produção gerados
- [ ] Backup do banco Supabase criado
- [ ] Migration RLS executada no Supabase de produção
- [ ] Domínio configurado (alcahub.com.br)
- [ ] SSL/HTTPS configurado

---

## 🔐 SECRETS DE PRODUÇÃO

**CRÍTICO:** Use secrets DIFERENTES de desenvolvimento!

```bash
# ⚠️  NÃO commitar ao git!
# Copie manualmente para o servidor

SECRET_KEY=<gerar com: openssl rand -hex 32>
JWT_SECRET=<gerar com: openssl rand -hex 32>
```

---

## 📋 CHECKLIST DE DEPLOY

### 1️⃣ Supabase (Produção)

#### a) Criar Projeto de Produção (se não existe)
- [ ] Acessar: https://app.supabase.com
- [ ] Criar novo projeto: "alca-financas-prod"
- [ ] Região: South America (São Paulo) ou mais próxima
- [ ] Anotar: URL e Keys

#### b) Executar Migration RLS
- [ ] Abrir: SQL Editor no Supabase
- [ ] Copiar: `backend/database/migrations/002_fix_rls_policies.sql`
- [ ] Executar: RUN
- [ ] Validar: 15 policies criadas

```sql
-- Validação
SELECT COUNT(*) FROM pg_policies
WHERE tablename IN ('users', 'categories', 'accounts', 'transactions');
-- Deve retornar 15
```

#### c) Configurar Email (Password Recovery)
- [ ] Supabase Dashboard > Authentication > Email Templates
- [ ] Configurar "Reset Password" template
- [ ] Testar envio de email

---

### 2️⃣ Servidor/Hosting

**Opções de Hosting:**
- Render.com (Recomendado - fácil)
- Railway.app (Simples)
- DigitalOcean App Platform
- Heroku
- VPS (AWS, DigitalOcean, Vultr)

---

## 🌐 DEPLOY NO RENDER.COM (Recomendado)

### Backend

1. **Criar Web Service**
   - [ ] Acessar: https://dashboard.render.com
   - [ ] New > Web Service
   - [ ] Connect Repository: alca-financas
   - [ ] Branch: main

2. **Configurações**
   ```
   Name: alca-financas-backend
   Region: São Paulo (ou Oregon)
   Branch: main
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```

3. **Environment Variables** (CRÍTICO)
   ```bash
   # Database
   SUPABASE_URL=https://seu-projeto-prod.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJ... (do Supabase prod)

   # Security (usar valores gerados acima)
   SECRET_KEY=<gerar com: openssl rand -hex 32>
   JWT_SECRET=<gerar com: openssl rand -hex 32>
   JWT_EXPIRES_HOURS=24

   # URLs
   FRONTEND_URL=https://alcahub.com.br
   API_BASE_URL=https://api.alcahub.com.br

   # CORS
   CORS_ORIGINS=https://alcahub.com.br,https://www.alcahub.com.br

   # Environment
   FLASK_ENV=production
   NODE_ENV=production

   # Optional: OAuth
   GOOGLE_CLIENT_ID=seu-client-id
   GOOGLE_CLIENT_SECRET=seu-client-secret
   ```

4. **Deploy**
   - [ ] Clicar: Create Web Service
   - [ ] Aguardar build (~3-5 min)
   - [ ] Anotar URL: https://alca-financas-backend.onrender.com

### Frontend

1. **Criar Static Site**
   - [ ] New > Static Site
   - [ ] Connect Repository: alca-financas
   - [ ] Branch: main

2. **Configurações**
   ```
   Name: alca-financas-frontend
   Root Directory: frontend
   Build Command: npm install && npm run build
   Publish Directory: dist
   ```

3. **Environment Variables**
   ```bash
   VITE_API_URL=https://api.alcahub.com.br
   VITE_SUPABASE_URL=https://seu-projeto-prod.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJ... (anon key do Supabase)
   ```

4. **Deploy**
   - [ ] Create Static Site
   - [ ] Aguardar build (~2-3 min)

---

## 🌐 DOMÍNIO PERSONALIZADO

### Backend (api.alcahub.com.br)

1. **No Render.com**
   - [ ] Settings > Custom Domain
   - [ ] Add: api.alcahub.com.br
   - [ ] Copiar CNAME

2. **No seu DNS Provider**
   - [ ] Criar registro CNAME:
   ```
   Tipo: CNAME
   Nome: api
   Valor: alca-financas-backend.onrender.com
   TTL: 3600
   ```

### Frontend (alcahub.com.br)

1. **No Render.com**
   - [ ] Settings > Custom Domain
   - [ ] Add: alcahub.com.br
   - [ ] Add: www.alcahub.com.br
   - [ ] Copiar valores

2. **No seu DNS Provider**
   - [ ] Criar registros:
   ```
   # Root domain
   Tipo: A
   Nome: @
   Valor: <IP do Render>

   # WWW
   Tipo: CNAME
   Nome: www
   Valor: alca-financas-frontend.onrender.com
   ```

---

## 🔒 SSL/HTTPS

### Render.com (Automático)
- [ ] SSL configurado automaticamente
- [ ] Let's Encrypt gratuito
- [ ] Renovação automática

### Verificar
```bash
# Testar HTTPS
curl -I https://api.alcahub.com.br/api/health
curl -I https://alcahub.com.br
```

---

## 🧪 TESTES PÓS-DEPLOY

### 1. Backend Health Check
```bash
curl https://api.alcahub.com.br/api/health
# Esperado: {"status": "ok"}
```

### 2. Testar Login
- [ ] Abrir: https://alcahub.com.br
- [ ] Fazer login com usuário de teste
- [ ] Verificar que dados aparecem
- [ ] Criar transação teste
- [ ] Logout

### 3. Testar RLS (CRÍTICO)
- [ ] Criar 2 usuários diferentes
- [ ] Login como usuário A
- [ ] Verificar que SÓ aparecem dados do usuário A
- [ ] Login como usuário B
- [ ] Verificar que SÓ aparecem dados do usuário B

### 4. Testar OAuth (se configurado)
- [ ] Testar "Login com Google"
- [ ] Verificar que funciona
- [ ] Verificar redirecionamento

### 5. Testar Password Recovery
- [ ] Clicar "Esqueci minha senha"
- [ ] Verificar que email é enviado
- [ ] Testar reset de senha

---

## 📊 MONITORAMENTO

### Logs

**Render.com:**
- Logs > View Logs
- Filtrar por "error", "warning"

**Supabase:**
- Logs > API Logs
- Verificar queries suspeitas

### Métricas

Monitorar:
- [ ] Taxa de erro (deve ser <1%)
- [ ] Tempo de resposta (<500ms)
- [ ] Uso de memória
- [ ] Uso de CPU

---

## 🚨 ROLLBACK (Se Algo Der Errado)

### Opção 1: Rollback no Git
```bash
# Voltar ao commit anterior
git revert HEAD
git push origin main

# Render fará deploy automático
```

### Opção 2: Rollback no Render
- Dashboard > Deploys
- Selecionar deploy anterior
- "Rollback to this version"

### Opção 3: Rollback RLS no Supabase
- Database > Backups
- Restore backup anterior

---

## 📝 CONFIGURAÇÕES ADICIONAIS

### Gunicorn (Backend)

Criar `backend/gunicorn.conf.py`:
```python
bind = "0.0.0.0:8001"
workers = 2
worker_class = "sync"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

### Procfile (Render/Heroku)

Criar `backend/Procfile`:
```
web: gunicorn app:app
```

### Requirements (Produção)

Adicionar ao `backend/requirements.txt`:
```
gunicorn==21.2.0
```

---

## ✅ CHECKLIST FINAL

Antes de considerar deploy completo:

- [ ] Backend rodando em produção
- [ ] Frontend rodando em produção
- [ ] HTTPS funcionando (ambos)
- [ ] Domínio personalizado configurado
- [ ] RLS validado (isolamento de dados)
- [ ] Secrets de produção configurados
- [ ] OAuth funcionando (se aplicável)
- [ ] Email funcionando (password recovery)
- [ ] Testes manuais completos
- [ ] Logs sem erros críticos
- [ ] Monitoramento configurado
- [ ] Backup agendado (Supabase)

---

## 🎯 PRÓXIMOS PASSOS

Após deploy estável:
1. Monitorar logs primeiras 24h
2. Configurar alertas (Sentry, Uptime Robot)
3. Implementar FASE 2 (rate limiting, audit logs)
4. Adicionar analytics (opcional)
5. Configurar CI/CD (GitHub Actions)

---

## 📞 SUPORTE

### Problemas Comuns

**Backend não inicia:**
- Verificar secrets configurados
- Verificar SUPABASE_URL e KEY
- Ver logs: render.com > logs

**Frontend não conecta:**
- Verificar VITE_API_URL correto
- Verificar CORS no backend
- Verificar HTTPS

**RLS bloqueando queries:**
- Verificar que backend usa SERVICE_ROLE_KEY
- Frontend usa ANON_KEY
- Policies corretas no Supabase

---

## 🎉 CONCLUSÃO

Deploy completo de aplicação segura!

**Status:**
- ✅ Sistema seguro (FASE 1 completa)
- ✅ RLS protegendo dados
- ✅ OAuth seguro
- ✅ Secrets fortes obrigatórios

**Próximo:** Monitorar e implementar melhorias (FASE 2)

---

**Última atualização:** 2026-02-10
**Responsável:** Lezinrew
**Ambiente:** Produção
