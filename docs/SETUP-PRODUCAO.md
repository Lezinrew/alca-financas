# 🚀 Setup de Produção - alcahub.com.br

Guia completo para configurar o ambiente de produção.

---

## 📋 Checklist de Produção

- [ ] 1. Servidor configurado
- [ ] 2. Domínio configurado
- [ ] 3. SSL/TLS instalado
- [ ] 4. Docker instalado
- [ ] 5. Secrets GitHub configurados
- [ ] 6. Variáveis de ambiente configuradas
- [ ] 7. Primeiro deploy realizado
- [ ] 8. Monitoramento configurado

---

## 1️⃣ Configuração do Servidor

### Requisitos Mínimos

- **OS:** Ubuntu 20.04+ / Debian 11+
- **CPU:** 2 cores
- **RAM:** 4GB
- **Disk:** 20GB SSD
- **Providers:** AWS, DigitalOcean, Vultr, etc.

### Instalação Base

```bash
# Conecte ao servidor
ssh root@alcahub.com.br

# Atualize o sistema
sudo apt update && sudo apt upgrade -y

# Instale dependências
sudo apt install -y \
    curl \
    git \
    nginx \
    certbot \
    python3-certbot-nginx
```

### Instalar Docker

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar instalação
docker --version
docker-compose --version
```

### Criar Usuário Deploy

```bash
# Criar usuário
sudo adduser deploy
sudo usermod -aG docker deploy
sudo usermod -aG sudo deploy

# Configurar SSH
sudo mkdir -p /home/deploy/.ssh
sudo cp ~/.ssh/authorized_keys /home/deploy/.ssh/
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys

# Testar login
ssh deploy@alcahub.com.br
```

### Criar Estrutura de Diretórios

```bash
# Como usuário deploy
sudo mkdir -p /var/www/alcahub
sudo chown -R deploy:deploy /var/www/alcahub

cd /var/www/alcahub
mkdir -p {frontend/dist,backend,logs,backups}
```

---

## 2️⃣ Configuração do Domínio

### DNS Records

Configure no seu provedor de DNS:

```
# A Records
alcahub.com.br          A       <IP_DO_SERVIDOR>
www.alcahub.com.br      A       <IP_DO_SERVIDOR>
api.alcahub.com.br      A       <IP_DO_SERVIDOR>

# CNAME (opcional)
*.alcahub.com.br        CNAME   alcahub.com.br
```

### Testar DNS

```bash
# Local
dig alcahub.com.br
dig api.alcahub.com.br

# Ou
nslookup alcahub.com.br
```

---

## 3️⃣ Configuração SSL/TLS (Let's Encrypt)

### Instalar Certificado

```bash
# Para alcahub.com.br
sudo certbot --nginx -d alcahub.com.br -d www.alcahub.com.br

# Para api.alcahub.com.br
sudo certbot --nginx -d api.alcahub.com.br

# Renovação automática
sudo certbot renew --dry-run
```

### Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/alcahub
```

Adicione a configuração:

```nginx
# Frontend - alcahub.com.br
server {
    listen 80;
    listen [::]:80;
    server_name alcahub.com.br www.alcahub.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name alcahub.com.br www.alcahub.com.br;

    ssl_certificate /etc/letsencrypt/live/alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/alcahub.com.br/privkey.pem;

    root /var/www/alcahub/frontend/dist;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

# Backend API - api.alcahub.com.br
server {
    listen 80;
    listen [::]:80;
    server_name api.alcahub.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.alcahub.com.br;

    ssl_certificate /etc/letsencrypt/live/api.alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.alcahub.com.br/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to Flask
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Ative e teste:

```bash
sudo ln -s /etc/nginx/sites-available/alcahub /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4️⃣ MongoDB em Produção

### Opção A: MongoDB Atlas (Recomendado)

1. Acesse https://www.mongodb.com/cloud/atlas
2. Crie uma conta/cluster gratuito
3. Configure network access (IP do servidor)
4. Crie database user
5. Copie connection string

```
mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas
```

### Opção B: MongoDB Local

```bash
# Instalar MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y mongodb-org

# Iniciar
sudo systemctl start mongod
sudo systemctl enable mongod

# Configurar autenticação
mongo
use admin
db.createUser({
  user: "alcaadmin",
  pwd: "senha-super-segura",
  roles: ["root"]
})
exit

# Editar config
sudo nano /etc/mongod.conf
```

```yaml
# mongod.conf
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1
  port: 27017
```

```bash
sudo systemctl restart mongod
```

---

## 5️⃣ Secrets GitHub

### Gerar SSH Key para Deploy

```bash
# No servidor
ssh-keygen -t ed25519 -C "deploy@alcahub.com.br" -f ~/.ssh/deploy_key -N ""

# Ver chave pública (adicione ao authorized_keys)
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# Ver chave privada (adicione ao GitHub)
cat ~/.ssh/deploy_key
```

### Configurar no GitHub

Vá para: `Settings → Secrets and variables → Actions → New repository secret`

Adicione os seguintes secrets:

```yaml
# Docker Registry (se usar)
DOCKER_REGISTRY: registry.hub.docker.com
DOCKER_USERNAME: seu-usuario-docker
DOCKER_PASSWORD: sua-senha-docker

# Servidor
PROD_HOST: alcahub.com.br
PROD_USER: deploy
PROD_SSH_KEY: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  [conteúdo da chave privada]
  -----END OPENSSH PRIVATE KEY-----

# Notificações (opcional)
TELEGRAM_CHAT_ID: seu-chat-id
TELEGRAM_BOT_TOKEN: seu-bot-token
```

### Como Obter Token Telegram (Opcional)

1. Abra Telegram e procure por @BotFather
2. Envie `/newbot`
3. Siga as instruções
4. Copie o token fornecido
5. Para obter chat_id:
   - Envie uma mensagem para seu bot
   - Acesse: https://api.telegram.org/bot<TOKEN>/getUpdates
   - Copie o chat id

---

## 6️⃣ Variáveis de Ambiente Produção

### No Servidor

```bash
ssh deploy@alcahub.com.br
cd /var/www/alcahub

# Criar .env
nano .env
```

Adicione:

```bash
# Ambiente
NODE_ENV=production

# URLs
PROD_API_URL=https://api.alcahub.com.br
PROD_WEB_URL=https://alcahub.com.br

# MongoDB
MONGO_URI=mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas
MONGO_DB=alca_financas

# JWT
JWT_SECRET=gere-uma-chave-super-segura-aqui-min-32-caracteres
JWT_EXPIRATION=7d

# OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# SMTP (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=

# Deploy
DEPLOY_USER=deploy
DEPLOY_HOST=alcahub.com.br
DEPLOY_PATH=/var/www/alcahub
```

### Gerar JWT Secret Seguro

```bash
# Gerar chave aleatória
openssl rand -base64 32
```

---

## 7️⃣ Docker Compose Produção

```bash
cd /var/www/alcahub
nano docker-compose.yml
```

```yaml
version: '3.8'

services:
  backend:
    image: alcahub/backend:latest
    container_name: alcahub-backend
    restart: always
    ports:
      - "5000:5000"
    env_file:
      - .env
    environment:
      - MONGO_URI=${MONGO_URI}
      - JWT_SECRET=${JWT_SECRET}
    networks:
      - alcahub-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  alcahub-network:
    driver: bridge
```

---

## 8️⃣ Primeiro Deploy Manual

### Preparar Repositório Local

```bash
# No seu computador
cd alca-financas

# Commitar tudo
git add .
git commit -m "feat: setup de produção completo"
git push origin main
```

### Deploy Manual (Primeira Vez)

```bash
# 1. Build Backend
cd backend
docker build -t alcahub/backend:latest .

# 2. Build Frontend
cd ../frontend
npm install
VITE_API_URL=https://api.alcahub.com.br npm run build

# 3. Enviar para servidor
rsync -avz --delete dist/ deploy@alcahub.com.br:/var/www/alcahub/frontend/dist/

# 4. Docker backend
docker save alcahub/backend:latest | ssh deploy@alcahub.com.br "docker load"
ssh deploy@alcahub.com.br "cd /var/www/alcahub && docker-compose up -d"

# 5. Verificar
curl https://api.alcahub.com.br/api/health
curl https://alcahub.com.br
```

---

## 9️⃣ Deploy Automático (GitHub Actions)

Após configurar os secrets, todo push para `main` vai:

1. ✅ Executar todos os testes
2. ✅ Build Docker images
3. ✅ Deploy automático
4. ✅ Health checks
5. ✅ Smoke tests
6. ✅ Notificar resultado

### Testar Pipeline

```bash
git add .
git commit -m "test: primeiro deploy automático"
git push origin main

# Acompanhar no GitHub
# https://github.com/seu-usuario/alca-financas/actions
```

---

## 🔟 Configurar Backup Automático

### Cron Job no Servidor

```bash
ssh deploy@alcahub.com.br

# Editar crontab
crontab -e
```

Adicione:

```cron
# Backup diário às 3am
0 3 * * * /var/www/alcahub/scripts/backup.sh >> /var/www/alcahub/logs/backup.log 2>&1

# Limpar logs antigos toda segunda às 2am
0 2 * * 1 find /var/www/alcahub/logs -name "*.log" -mtime +30 -delete
```

---

## 1️⃣1️⃣ Monitoramento (Opcional)

### Logs

```bash
# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Backend
docker-compose logs -f backend

# Sistema
sudo journalctl -u nginx -f
```

### Uptime Monitoring (Recomendado)

- [UptimeRobot](https://uptimerobot.com/) - Gratuito
- [Pingdom](https://www.pingdom.com/)
- [StatusCake](https://www.statuscake.com/)

Configure para monitorar:
- https://alcahub.com.br
- https://api.alcahub.com.br/api/health

---

## ✅ Checklist Final

Antes de fazer o primeiro deploy, verifique:

- [ ] Servidor configurado e acessível via SSH
- [ ] Docker e Docker Compose instalados
- [ ] Nginx configurado e rodando
- [ ] DNS apontando para servidor
- [ ] SSL/TLS instalado (Let's Encrypt)
- [ ] MongoDB configurado (Atlas ou local)
- [ ] .env produção configurado
- [ ] Secrets GitHub configurados
- [ ] Deploy manual testado e funcionando
- [ ] Backup configurado
- [ ] Monitoramento configurado

---

## 🆘 Troubleshooting

### Nginx não inicia

```bash
sudo nginx -t
sudo journalctl -xe
```

### SSL não funciona

```bash
sudo certbot certificates
sudo certbot renew --dry-run
```

### Docker sem permissão

```bash
sudo usermod -aG docker $USER
# Logout e login novamente
```

### MongoDB não conecta

```bash
# Testar conexão
mongosh "mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas"
```

### Frontend 404

```bash
# Verificar arquivos
ls -la /var/www/alcahub/frontend/dist/

# Verificar permissões
sudo chown -R deploy:deploy /var/www/alcahub
```

---

## 📚 Próximos Passos

1. Configure monitoramento de erros (Sentry)
2. Configure analytics (Google Analytics)
3. Configure CDN (Cloudflare)
4. Configure rate limiting
5. Configure WAF (Web Application Firewall)

---

**Sucesso no deploy! 🚀**
