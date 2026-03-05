# 📜 Scripts de Deploy - Alça Finanças

Guia completo sobre os scripts de deploy disponíveis e quando usar cada um.

---

## 🎯 Qual Script Usar?

### 🏠 Desenvolvimento Local

**Script:** `deploy-local.sh`

```bash
./scripts/deploy-local.sh
```

**Quando usar:**
- Iniciar ambiente de desenvolvimento
- Testar mudanças localmente
- Desenvolvimento com hot-reload

**O que faz:**
- Verifica Docker e Docker Compose
- Valida arquivo .env
- Inicia containers (backend + frontend)
- Verifica health checks

---

### 🚀 Deploy Remoto (Primeira Vez)

**Script:** `deploy-docker-remote.sh`

```bash
export SERVER_HOST="76.13.239.220"
export SERVER_USER="root"
export DOMAIN="alcahub.cloud"

./scripts/deploy-docker-remote.sh
```

**Quando usar:**
- **Primeira instalação** no servidor
- Mudanças na infraestrutura Docker
- Rebuild completo necessário
- Configuração de novo servidor

**O que faz:**
- Instala Docker + Docker Compose
- Clona repositório
- Cria .env template
- Build frontend + backend
- Inicia containers
- Healthcheck completo

**Tempo:** ~10-15 minutos

---

### ⚡ Update Rápido

**Script:** `deploy-quick-update.sh`

```bash
export SERVER_HOST="76.13.239.220"
./scripts/deploy-quick-update.sh
```

**Quando usar:**
- Mudanças simples no código
- Hotfixes
- Ajustes em Python/JavaScript/CSS
- **Não requer rebuild**

**O que faz:**
- Git pull origin main
- Restart containers
- Verifica status

**Tempo:** ~30 segundos

⚠️ **NÃO use para:**
- Mudanças em Dockerfile
- Novas dependências (requirements.txt, package.json)
- Mudanças em docker-compose.yml
- Mudanças em nginx.conf

---

### 🏢 Deploy Hostinger/VPS

**Script:** `deploy-hostinger.sh`

```bash
# Execute diretamente no servidor via SSH
ssh root@76.13.239.220
cd /var/www/alca-financas
./scripts/deploy-hostinger.sh
```

**Quando usar:**
- Deploy em servidor já configurado
- Update completo com rebuild
- Após mudanças em dependências

**O que faz:**
- Git pull
- Build frontend
- Build imagens Docker
- Down + Up containers
- Healthcheck

**Tempo:** ~5-8 minutos

---

### 🎨 Deploy Frontend Only

**Script:** `deploy-frontend-only.sh`

```bash
export SERVER_HOST="76.13.239.220"
export SERVER_USER="root"
export DOMAIN="alcahub.cloud"

./scripts/deploy-frontend-only.sh
```

**Quando usar:**
- Mudanças **apenas** no frontend
- CSS/JavaScript/Componentes React
- Não alterou backend
- Deploy mais rápido

**O que faz:**
- Git pull
- Build frontend no servidor
- Restart container frontend
- Teste HTTP

**Tempo:** ~2-3 minutos

---

### 🏭 Deploy Production (Completo)

**Script:** `deploy-production.sh`

```bash
# Criar .env.deploy primeiro
cat > .env.deploy << EOF
DEPLOY_HOST=76.13.239.220
DEPLOY_USER=root
DEPLOY_PATH=/var/www/alca-financas
DOMAIN=alcahub.cloud
EOF

./scripts/deploy-production.sh
```

**Quando usar:**
- Deploy crítico para produção
- Requer testes antes do deploy
- Rollback automático em caso de falha
- Notificações (Slack opcional)

**O que faz:**
- Valida branch (main/master)
- Roda testes locais
- Git push
- Cria backup
- Build + Deploy
- Healthcheck extensivo
- Rollback automático se falhar
- Notificação Slack (opcional)

**Tempo:** ~10-15 minutos

---

## 📋 Comparação Rápida

| Script | Tempo | Uso | Rollback | Testes |
|--------|-------|-----|----------|--------|
| `deploy-local.sh` | 30s | Dev local | N/A | Não |
| `deploy-docker-remote.sh` | 10-15min | Setup inicial | Não | Não |
| `deploy-quick-update.sh` | 30s | Hotfix rápido | Manual | Não |
| `deploy-hostinger.sh` | 5-8min | Update VPS | Manual | Não |
| `deploy-frontend-only.sh` | 2-3min | Frontend only | Manual | Não |
| `deploy-production.sh` | 10-15min | Produção crítica | **Automático** | **Sim** |

---

## 🗂️ Scripts Auxiliares

### `prod/deploy.sh`

Script genérico que chama build.sh, migrate.sh e run.sh.

```bash
./scripts/prod/deploy.sh
```

Idempotente e modular.

---

## 🔧 Configuração Necessária

### Variáveis de Ambiente

Todos os scripts remotos usam variáveis de ambiente (não hardcoded):

```bash
# Servidor
export SERVER_HOST="76.13.239.220"  # IP do VPS
export SERVER_USER="root"            # Usuário SSH
export SERVER_SSH_KEY="~/.ssh/id_rsa"  # Chave SSH (opcional)

# Projeto
export PROJECT_DIR="/var/www/alca-financas"
export DOMAIN="alcahub.cloud"
```

### Arquivo .env no Servidor

Obrigatório em `/var/www/alca-financas/.env`:

```env
# Supabase
SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend
SECRET_KEY=<random_32_chars>
JWT_SECRET=<random_32_chars>
BACKEND_PORT=8001
FLASK_ENV=production

# CORS
CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# Frontend Build
VITE_API_URL=https://alcahub.cloud
VITE_SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 🚨 Scripts Removidos (Não Usar)

Estes scripts foram **REMOVIDOS** por segurança:

- ❌ `deploy-remote.sh` - Senha hardcoded
- ❌ `deploy-remote.py` - Senha hardcoded
- ❌ `deploy-remote-expect.sh` - Senha hardcoded
- ❌ `deploy-vps.sh` - MongoDB obsoleto

**Nunca coloque credenciais no código!**

---

## 📖 Documentação Completa

Para guia detalhado, veja: **[docs/DEPLOY-GUIDE.md](../docs/DEPLOY-GUIDE.md)**

- Troubleshooting
- Health checks
- Logs
- Rollback manual
- SSL/HTTPS setup

---

## 🆘 Ajuda Rápida

### Ver Logs

```bash
# Via SSH
ssh root@76.13.239.220
cd /var/www/alca-financas

# Ver todos os logs
docker-compose -f docker-compose.prod.yml logs -f

# Apenas backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Apenas frontend
docker-compose -f docker-compose.prod.yml logs -f frontend
```

### Restart Manual

```bash
ssh root@76.13.239.220
cd /var/www/alca-financas
docker-compose -f docker-compose.prod.yml restart
```

### Rollback Manual

```bash
ssh root@76.13.239.220
cd /var/www/alca-financas
git reset --hard HEAD@{1}
docker-compose -f docker-compose.prod.yml restart
```

---

## ✅ Checklist de Deploy

- [ ] Código testado localmente
- [ ] Commit e push feitos
- [ ] Variáveis de ambiente configuradas
- [ ] .env configurado no servidor
- [ ] Backup recente disponível
- [ ] Script apropriado selecionado
- [ ] Deploy executado
- [ ] Healthcheck passou
- [ ] Smoke test manual
- [ ] Logs monitorados

---

**🎉 Pronto para deploy!**
