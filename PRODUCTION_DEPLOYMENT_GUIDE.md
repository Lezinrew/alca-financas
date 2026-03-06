# 🚀 Guia de Deploy Profissional - Produção

Deploy completo e profissional do Alça Finanças em produção com Docker.

## 📋 Pré-requisitos

- ✅ Servidor VPS com Ubuntu 24.04
- ✅ Docker e Docker Compose instalados
- ✅ Domínio configurado (alcahub.cloud)
- ✅ Acesso SSH ao servidor
- ✅ Conta Supabase com banco configurado

---

## 🎯 Arquitetura de Produção

```
Internet
   ↓
Nginx Reverse Proxy (SSL/TLS)
   ├─→ Frontend Container (React + Nginx) - alcahub.cloud
   └─→ Backend Container (Flask + Gunicorn) - api.alcahub.cloud
          ↓
       Supabase PostgreSQL (externo)
```

---

## 📦 Passo 1: Preparar o Servidor

### 1.1 Conectar ao servidor

```bash
ssh root@76.13.239.220
```

### 1.2 Atualizar sistema

```bash
apt update && apt upgrade -y
```

### 1.3 Instalar Docker

```bash
# Remover versões antigas
apt remove docker docker-engine docker.io containerd runc

# Instalar dependências
apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Adicionar chave GPG oficial do Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Configurar repositório
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verificar instalação
docker --version
docker compose version
```

### 1.4 Configurar Docker

```bash
# Habilitar Docker na inicialização
systemctl enable docker
systemctl start docker

# Adicionar usuário ao grupo docker (opcional)
usermod -aG docker alcaapp
```

### 1.5 Instalar ferramentas úteis

```bash
apt install -y git curl wget nano htop ufw fail2ban
```

### 1.6 Configurar Firewall

```bash
# Configurar UFW
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status
```

---

## 📦 Passo 2: Clonar e Configurar o Projeto

### 2.1 Criar estrutura de diretórios

```bash
mkdir -p /var/www/alca-financas
cd /var/www/alca-financas
```

### 2.2 Clonar repositório

```bash
git clone https://github.com/Lezinrew/alca-financas.git .
```

### 2.3 Configurar variáveis de ambiente

```bash
# Backend
cp .env.production.example backend/.env.production
nano backend/.env.production
```

**Preencha com seus valores reais:**

```env
# SECURITY (gere com: openssl rand -hex 32)
SECRET_KEY=<valor-gerado>
JWT_SECRET=<valor-gerado>

# SUPABASE
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_secret_YOUR_SUPABASE_SERVICE_ROLE_KEY

# CORS
CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# OPENCLAW (opcional)
OPENCLAW_GATEWAY_TOKEN=<seu-token>
OPENCLAW_URL=https://openclaw-qi3v-openclaw.srv1353242.hstgr.cloud
```

### 2.4 Configurar variáveis do Docker Compose

```bash
cp .env.production.example .env
nano .env
```

```env
DOMAIN=alcahub.cloud
SSL_EMAIL=seu-email@example.com
VITE_API_URL=https://api.alcahub.cloud
```

---

## 📦 Passo 3: Configurar SSL com Let's Encrypt

### 3.1 Configuração inicial do Nginx (sem SSL)

```bash
# Criar diretório para certbot
mkdir -p nginx/ssl certbot-data certbot-conf

# Iniciar apenas nginx temporariamente
docker compose -f docker-compose.production.yml up -d nginx
```

### 3.2 Obter certificados SSL

```bash
# Executar Certbot
docker compose -f docker-compose.production.yml run --rm certbot

# Ou manualmente:
docker run --rm \
  -v /var/www/alca-financas/certbot-conf:/etc/letsencrypt \
  -v /var/www/alca-financas/certbot-data:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email seu-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d alcahub.cloud \
  -d www.alcahub.cloud \
  -d api.alcahub.cloud
```

### 3.3 Configurar renovação automática

```bash
# Criar cron job para renovação
crontab -e

# Adicionar linha (roda todo dia às 3h):
0 3 * * * docker compose -f /var/www/alca-financas/docker-compose.production.yml run --rm certbot renew --quiet && docker compose -f /var/www/alca-financas/docker-compose.production.yml restart nginx
```

---

## 📦 Passo 4: Build e Deploy

### 4.1 Build das imagens Docker

```bash
cd /var/www/alca-financas

# Build das imagens
docker compose -f docker-compose.production.yml build --no-cache

# Verificar imagens criadas
docker images | grep alca
```

### 4.2 Iniciar todos os serviços

```bash
# Iniciar em modo detached
docker compose -f docker-compose.production.yml up -d

# Verificar status
docker compose -f docker-compose.production.yml ps

# Ver logs
docker compose -f docker-compose.production.yml logs -f
```

### 4.3 Verificar health checks

```bash
# Backend
curl http://localhost:8001/api/health

# Frontend
curl http://localhost:3000/

# Nginx (HTTPS)
curl -k https://alcahub.cloud
curl -k https://api.alcahub.cloud/api/health
```

---

## 📦 Passo 5: Executar Migrações do Banco

### 5.1 Migração do Chatbot

```bash
# Conectar ao Supabase Dashboard
# https://supabase.com/dashboard

# SQL Editor → Executar:
# backend/migrations/add_chatbot_conversations.sql
```

### 5.2 Verificar migrações

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

---

## 📦 Passo 6: Configurar Monitoramento e Logs

### 6.1 Ver logs em tempo real

```bash
# Todos os serviços
docker compose -f docker-compose.production.yml logs -f

# Apenas backend
docker compose -f docker-compose.production.yml logs -f backend

# Apenas frontend
docker compose -f docker-compose.production.yml logs -f frontend

# Apenas nginx
docker compose -f docker-compose.production.yml logs -f nginx
```

### 6.2 Configurar log rotation

```bash
# Criar configuração de logrotate
cat > /etc/logrotate.d/alca-financas <<EOF
/var/www/alca-financas/nginx/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        docker exec alca-nginx nginx -s reload > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 6.3 Monitoramento de recursos

```bash
# Uso de CPU e memória dos containers
docker stats

# Informações detalhadas
docker compose -f docker-compose.production.yml top
```

---

## 📦 Passo 7: Backup e Recuperação

### 7.1 Backup automático dos volumes

```bash
# Criar script de backup
cat > /usr/local/bin/backup-alca.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/alca-financas"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup de volumes Docker
docker run --rm \
  -v alca-financas_backend-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/backend-data-$DATE.tar.gz /data

# Backup de configurações
tar czf $BACKUP_DIR/configs-$DATE.tar.gz \
  /var/www/alca-financas/docker-compose.production.yml \
  /var/www/alca-financas/.env \
  /var/www/alca-financas/nginx/

# Manter apenas últimos 7 backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

# Tornar executável
chmod +x /usr/local/bin/backup-alca.sh

# Agendar backup diário
echo "0 2 * * * /usr/local/bin/backup-alca.sh >> /var/log/alca-backup.log 2>&1" | crontab -
```

### 7.2 Backup de imagens Docker

```bash
# Salvar imagens
docker save alca-backend:latest | gzip > /var/backups/alca-backend-image.tar.gz
docker save alca-frontend:latest | gzip > /var/backups/alca-frontend-image.tar.gz
```

### 7.3 Restauração

```bash
# Restaurar volumes
tar xzf /var/backups/alca-financas/backend-data-XXXXXXXX.tar.gz -C /

# Restaurar imagens
docker load < /var/backups/alca-backend-image.tar.gz
docker load < /var/backups/alca-frontend-image.tar.gz

# Reiniciar serviços
docker compose -f docker-compose.production.yml up -d
```

---

## 📦 Passo 8: Testes de Produção

### 8.1 Teste de SSL

```bash
# Verificar certificado
openssl s_client -connect alcahub.cloud:443 -servername alcahub.cloud < /dev/null | grep "Verify return code"

# Teste com SSLLabs (recomendado)
# https://www.ssllabs.com/ssltest/analyze.html?d=alcahub.cloud
```

### 8.2 Teste de Performance

```bash
# Teste de carga no backend
ab -n 1000 -c 10 https://api.alcahub.cloud/api/health

# Teste de carga no frontend
ab -n 1000 -c 10 https://alcahub.cloud/
```

### 8.3 Teste de Segurança

```bash
# Verificar headers de segurança
curl -I https://alcahub.cloud

# Teste de vulnerabilidades (opcional)
docker run --rm -it secfigo/terrascan scan -t docker -f docker-compose.production.yml
```

---

## 📦 Passo 9: Manutenção e Atualizações

### 9.1 Atualizar código

```bash
cd /var/www/alca-financas

# Pull das mudanças
git pull origin main

# Rebuild e restart
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d --force-recreate

# Ver logs de atualização
docker compose -f docker-compose.production.yml logs -f
```

### 9.2 Limpeza de recursos

```bash
# Remover containers parados
docker container prune -f

# Remover imagens não utilizadas
docker image prune -a -f

# Remover volumes não utilizados (CUIDADO!)
docker volume prune -f

# Limpeza completa do sistema
docker system prune -a --volumes -f
```

---

## 🔧 Troubleshooting

### Backend não inicia

```bash
# Ver logs detalhados
docker compose -f docker-compose.production.yml logs backend

# Verificar health check
docker inspect alca-backend | grep -A 10 Health

# Entrar no container
docker exec -it alca-backend /bin/bash
curl http://localhost:8001/api/health
```

### Frontend não carrega

```bash
# Ver logs
docker compose -f docker-compose.production.yml logs frontend

# Verificar nginx interno
docker exec -it alca-frontend cat /etc/nginx/conf.d/default.conf

# Testar diretamente
curl http://localhost:3000
```

### SSL não funciona

```bash
# Verificar certificados
docker exec -it alca-nginx ls -la /etc/letsencrypt/live/alcahub.cloud/

# Renovar manualmente
docker compose -f docker-compose.production.yml run --rm certbot renew

# Ver logs do nginx
docker compose -f docker-compose.production.yml logs nginx
```

### CORS errors

```bash
# Verificar headers CORS
curl -I -X OPTIONS https://api.alcahub.cloud/api/health \
  -H "Origin: https://alcahub.cloud" \
  -H "Access-Control-Request-Method: POST"

# Verificar configuração do backend
docker exec -it alca-backend env | grep CORS
```

---

## ✅ Checklist Pós-Deploy

- [ ] Servidor atualizado e configurado
- [ ] Docker e Docker Compose instalados
- [ ] Firewall (UFW) configurado
- [ ] Projeto clonado
- [ ] Variáveis de ambiente configuradas
- [ ] SSL/TLS configurado com Let's Encrypt
- [ ] Build das imagens concluído
- [ ] Containers rodando (docker ps)
- [ ] Health checks passando
- [ ] Migrações do banco executadas
- [ ] Logs configurados
- [ ] Backup automático agendado
- [ ] Testes de SSL, performance e segurança executados
- [ ] Monitoramento configurado
- [ ] Documentação atualizada

---

## 📊 Monitoramento Contínuo

### Comandos úteis

```bash
# Status geral
docker compose -f docker-compose.production.yml ps

# Uso de recursos
docker stats --no-stream

# Logs recentes
docker compose -f docker-compose.production.yml logs --tail=100

# Restart específico
docker compose -f docker-compose.production.yml restart backend

# Stop/Start todos
docker compose -f docker-compose.production.yml stop
docker compose -f docker-compose.production.yml start
```

---

## 🎉 Deploy Concluído!

Seu sistema está rodando em produção de forma profissional!

**URLs:**
- Frontend: https://alcahub.cloud
- API: https://api.alcahub.cloud
- Health Check: https://api.alcahub.cloud/api/health

**Próximos passos:**
1. Configurar monitoramento avançado (opcional)
2. Configurar CI/CD (opcional)
3. Otimizar performance conforme uso
4. Revisar logs regularmente

---

**Documentação**: Este guia
**Suporte**: GitHub Issues
**Versão**: 1.0.0
**Data**: 2026-03-06
