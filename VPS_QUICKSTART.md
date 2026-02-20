# VPS Hostinger - Deploy Rápido (45 minutos)

## Resumo Executivo

Deploy da aplicação no seu VPS Hostinger usando o domínio alcahub.com.br.

**URLs finais:**
- Frontend: https://alcahub.com.br (Principal)
- Frontend: https://alcahub.cloud (Novo)
- Backend API: https://api.alcahub.com.br
- Backend API: https://api.alcahub.cloud

---

## OPÇÃO 1: Setup Automático (Recomendado)

### Passo 1: Executar setup no VPS

Conecte ao VPS e execute:
```bash
ssh alcaapp@76.13.239.220
bash <(curl -s https://raw.githubusercontent.com/Lezinrew/alca-financas/main/scripts/setup-vps.sh)
```

### Passo 2: Configurar .env do backend

```bash
nano /home/alcaapp/alca-financas/backend/.env
```

Cole o conteúdo de `VPS_BACKEND_ENV.txt` (no seu projeto local).

### Passo 3: Configurar Nginx

**API (backend):**
```bash
sudo nano /etc/nginx/sites-available/api.alcahub.com.br
```
```nginx
server_name api.alcahub.com.br api.alcahub.cloud;
```

**Frontend:**
```bash
sudo nano /etc/nginx/sites-available/alcahub.com.br
```
```nginx
server_name alcahub.com.br www.alcahub.com.br alcahub.cloud www.alcahub.cloud;
```

Ativar:
```bash
sudo ln -s /etc/nginx/sites-available/api.alcahub.com.br /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/alcahub.com.br /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Passo 4: Configurar DNS (No Hostinger hPanel para AMBOS os domínios)

Adicionar registros A em `alcahub.com.br` e `alcahub.cloud`:
```
@ -> 76.13.239.220
www -> 76.13.239.220
api -> 76.13.239.220
```

### Passo 5: Fazer build e upload do frontend

Na sua máquina local:
```bash
cd frontend

# Criar .env.production
# Use api.alcahub.cloud (novo) ou api.alcahub.com.br (antigo)
cat > .env.production << EOF
VITE_API_URL=https://api.alcahub.cloud
VITE_SUPABASE_URL=https://SEU_PROJETO.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_XXXXXXXXXXXXXXXXXXXXXXXX
EOF

# Build
npm install
npm run build

# Upload
rsync -avz --delete dist/ alcaapp@76.13.239.220:/var/www/alcahub.com.br/
```

### Passo 6: Iniciar backend

No VPS:
```bash
sudo supervisorctl start alca-backend
sudo supervisorctl status
```

### Passo 7: Instalar/Expandir SSL

```bash
# Frontend (Todos os domínios)
sudo certbot --nginx -d alcahub.com.br -d www.alcahub.com.br -d alcahub.cloud -d www.alcahub.cloud

# API (Todos os domínios)
sudo certbot --nginx -d api.alcahub.com.br -d api.alcahub.cloud
```

### Passo 8: Testar

```bash
# Backend
curl https://api.alcahub.com.br/api/health

# Frontend
# Abrir no navegador: https://alcahub.com.br
```

---

## OPÇÃO 2: Deploys Futuros (Automatizado)

Após o setup inicial, use o script de deploy:

```bash
# Deploy completo (backend + frontend)
VPS_IP=76.13.239.220 ./scripts/deploy-vps.sh

# Ou apenas backend
VPS_IP=76.13.239.220 ./scripts/deploy-vps.sh backend

# Ou apenas frontend
VPS_IP=76.13.239.220 ./scripts/deploy-vps.sh frontend
```

---

## Checklist de Validação

- [ ] Backend health check OK: `curl https://api.alcahub.com.br/api/health`
- [ ] Frontend carrega: https://alcahub.com.br
- [ ] HTTPS funcionando (cadeado verde)
- [ ] Login funciona
- [ ] Dashboard mostra dados
- [ ] Console sem erros CORS (F12)
- [ ] SSL válido (certbot certificates)

---

## Troubleshooting Rápido

**Backend não inicia:**
```bash
tail -f /var/log/alca-backend.log
```

**Erro CORS:**
- Verificar CORS_ORIGINS no backend/.env
- Reiniciar: `supervisorctl restart alca-backend`

**DNS não propaga:**
```bash
nslookup alcahub.com.br
nslookup api.alcahub.com.br
```

**Nginx erro:**
```bash
nginx -t
tail -f /var/log/nginx/error.log
```

---

## Arquivos de Referência

- `DEPLOY_VPS_HOSTINGER.md` - Guia completo detalhado
- `VPS_BACKEND_ENV.txt` - Variáveis de ambiente do backend
- `VPS_FRONTEND_ENV.txt` - Variáveis de ambiente do frontend
- `scripts/setup-vps.sh` - Script de setup automático
- `scripts/deploy-vps.sh` - Script de deploy automático

---

## Suporte

Ver logs:
```bash
# Backend
tail -f /var/log/alca-backend.log

# Nginx
tail -f /var/log/nginx/error.log

# Supervisor
supervisorctl tail -f alca-backend
```

Reiniciar serviços:
```bash
supervisorctl restart alca-backend
systemctl reload nginx
```
