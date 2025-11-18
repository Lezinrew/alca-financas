# 🚀 Guia de Deploy - Alça Finanças na Hostinger

Este guia fornece instruções passo a passo para fazer o deploy da aplicação Alça Finanças em um servidor da Hostinger.

## 📋 Pré-requisitos

- Conta na Hostinger (VPS ou Cloud Hosting recomendado)
- Acesso SSH ao servidor
- Domínio configurado (opcional, mas recomendado)
- MongoDB Atlas (recomendado) ou MongoDB instalado no servidor
- Git instalado no servidor

## 🎯 Opções de Hospedagem na Hostinger

### Opção 1: VPS (Recomendado) ⭐
- **Vantagens**: Controle total, melhor performance, suporta MongoDB local
- **Recomendado para**: Produção com muitos usuários
- **Preço**: A partir de R$ 29,90/mês

### Opção 2: Cloud Hosting
- **Vantagens**: Escalável, fácil gerenciamento
- **Recomendado para**: Produção com crescimento esperado
- **Preço**: A partir de R$ 19,90/mês

### Opção 3: Shared Hosting (Não recomendado)
- **Limitações**: Não suporta MongoDB local, recursos limitados
- **Alternativa**: Usar MongoDB Atlas + build estático do frontend

---

## 📦 Passo 1: Preparação do Servidor

### 1.1 Conectar via SSH

```bash
ssh root@seu-ip-ou-dominio
# ou
ssh usuario@seu-ip-ou-dominio
```

### 1.2 Atualizar o Sistema

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### 1.3 Instalar Dependências Básicas

```bash
# Ubuntu/Debian
sudo apt install -y git curl wget build-essential python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Node.js (para build do frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 1.4 Verificar Instalações

```bash
python3 --version  # Deve ser 3.9+
node --version     # Deve ser 20.x
npm --version
nginx -v
```

---

## 🗄️ Passo 2: Configurar MongoDB

### Opção A: MongoDB Atlas (Recomendado) ⭐

1. Acesse [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Crie uma conta gratuita
3. Crie um cluster (Free tier disponível)
4. Configure usuário e senha
5. Adicione seu IP do servidor na whitelist (ou `0.0.0.0/0` para desenvolvimento)
6. Copie a connection string (ex: `mongodb+srv://user:pass@cluster.mongodb.net/alca_financas`)

### Opção B: MongoDB Local (Apenas VPS)

```bash
# Instalar MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org

# Iniciar MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verificar status
sudo systemctl status mongod
```

---

## 📁 Passo 3: Clonar e Configurar o Projeto

### 3.1 Criar Diretório de Aplicação

```bash
sudo mkdir -p /var/www/alca-financas
sudo chown $USER:$USER /var/www/alca-financas
cd /var/www/alca-financas
```

### 3.2 Clonar Repositório

```bash
# Se usar HTTPS
git clone https://github.com/seu-usuario/alca-financas.git .

# Se usar SSH (recomendado)
git clone git@github.com:seu-usuario/alca-financas.git .
```

### 3.3 Configurar Backend

```bash
cd backend

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Criar arquivo .env
nano .env
```

**Conteúdo do `.env` do backend:**

```env
# Ambiente
FLASK_ENV=production
NODE_ENV=production

# MongoDB
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/alca_financas
# ou para MongoDB local:
# MONGO_URI=mongodb://localhost:27017/alca_financas
MONGO_DB=alca_financas

# JWT
SECRET_KEY=SUA_CHAVE_SECRETA_SUPER_SEGURA_AQUI_GERE_UMA_ALEATORIA
JWT_EXPIRES_HOURS=24

# CORS (ajuste com seu domínio)
CORS_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br

# OAuth (opcional)
GOOGLE_CLIENT_ID=seu-google-client-id
GOOGLE_CLIENT_SECRET=seu-google-client-secret
```

**Gerar SECRET_KEY segura:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.4 Configurar Frontend

```bash
cd ../frontend

# Instalar dependências
npm install

# Criar arquivo .env.production
nano .env.production
```

**Conteúdo do `.env.production`:**

```env
VITE_API_URL=https://api.seudominio.com.br
# ou se API e frontend no mesmo domínio:
# VITE_API_URL=https://seudominio.com.br/api
```

**Build do Frontend:**

```bash
npm run build
```

O build será gerado em `frontend/dist/`

---

## 🔧 Passo 4: Configurar Nginx

### 4.1 Criar Configuração do Nginx

```bash
sudo nano /etc/nginx/sites-available/alca-financas
```

**Configuração para API e Frontend no mesmo domínio:**

```nginx
# Redirecionar HTTP para HTTPS
server {
    listen 80;
    server_name seudominio.com.br www.seudominio.com.br;
    return 301 https://$server_name$request_uri;
}

# Servidor HTTPS
server {
    listen 443 ssl http2;
    server_name seudominio.com.br www.seudominio.com.br;

    # Certificados SSL (serão gerados pelo Certbot)
    ssl_certificate /etc/letsencrypt/live/seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seudominio.com.br/privkey.pem;

    # Configurações SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Frontend (React SPA)
    location / {
        root /var/www/alca-financas/frontend/dist;
        try_files $uri $uri/ /index.html;
        index index.html;
        
        # Cache para assets estáticos
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API Backend
    location /api {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Logs
    access_log /var/log/nginx/alca-financas-access.log;
    error_log /var/log/nginx/alca-financas-error.log;
}
```

**Configuração alternativa: API em subdomínio separado:**

```nginx
# Frontend
server {
    listen 443 ssl http2;
    server_name seudominio.com.br www.seudominio.com.br;
    
    ssl_certificate /etc/letsencrypt/live/seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seudominio.com.br/privkey.pem;

    root /var/www/alca-financas/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}

# API Backend
server {
    listen 443 ssl http2;
    server_name api.seudominio.com.br;
    
    ssl_certificate /etc/letsencrypt/live/api.seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.seudominio.com.br/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4.2 Ativar Site

```bash
# Criar link simbólico
sudo ln -s /etc/nginx/sites-available/alca-financas /etc/nginx/sites-enabled/

# Remover site padrão (opcional)
sudo rm /etc/nginx/sites-enabled/default

# Testar configuração
sudo nginx -t

# Recarregar Nginx
sudo systemctl reload nginx
```

---

## 🔒 Passo 5: Configurar SSL com Let's Encrypt

```bash
# Instalar Certbot (se ainda não instalado)
sudo apt install certbot python3-certbot-nginx

# Gerar certificado SSL
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br

# Se usar subdomínio separado para API:
sudo certbot --nginx -d api.seudominio.com.br

# Renovação automática (já configurado automaticamente)
sudo certbot renew --dry-run
```

---

## 🚀 Passo 6: Configurar Gunicorn (Backend)

### 6.1 Criar Arquivo de Configuração do Gunicorn

```bash
cd /var/www/alca-financas/backend
nano gunicorn_config.py
```

**Conteúdo:**

```python
import multiprocessing

bind = "127.0.0.1:8001"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/var/log/gunicorn/alca-financas-access.log"
errorlog = "/var/log/gunicorn/alca-financas-error.log"
loglevel = "info"
```

### 6.2 Criar Diretório de Logs

```bash
sudo mkdir -p /var/log/gunicorn
sudo chown $USER:$USER /var/log/gunicorn
```

### 6.3 Criar Service do Systemd

```bash
sudo nano /etc/systemd/system/alca-financas.service
```

**Conteúdo:**

```ini
[Unit]
Description=Alca Financas Backend API
After=network.target

[Service]
User=seu-usuario
Group=seu-usuario
WorkingDirectory=/var/www/alca-financas/backend
Environment="PATH=/var/www/alca-financas/backend/venv/bin"
ExecStart=/var/www/alca-financas/backend/venv/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Substitua `seu-usuario` pelo seu usuário do sistema.**

### 6.4 Iniciar Serviço

```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Iniciar serviço
sudo systemctl start alca-financas

# Habilitar início automático
sudo systemctl enable alca-financas

# Verificar status
sudo systemctl status alca-financas

# Ver logs
sudo journalctl -u alca-financas -f
```

---

## 🔄 Passo 7: Script de Deploy Automatizado

### 7.1 Criar Script de Deploy

```bash
cd /var/www/alca-financas
nano deploy.sh
```

**Conteúdo:**

```bash
#!/bin/bash

set -e

echo "🚀 Iniciando deploy do Alça Finanças..."

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Atualizar código
echo -e "${BLUE}📥 Atualizando código...${NC}"
git pull origin main

# Backend
echo -e "${BLUE}🔧 Atualizando backend...${NC}"
cd backend
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate
cd ..

# Frontend
echo -e "${BLUE}🎨 Buildando frontend...${NC}"
cd frontend
npm install --silent
npm run build
cd ..

# Reiniciar serviços
echo -e "${BLUE}🔄 Reiniciando serviços...${NC}"
sudo systemctl restart alca-financas
sudo systemctl reload nginx

echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
```

### 7.2 Tornar Executável

```bash
chmod +x deploy.sh
```

### 7.3 Usar o Script

```bash
./deploy.sh
```

---

## 📊 Passo 8: Monitoramento e Logs

### 8.1 Ver Logs do Backend

```bash
# Logs do systemd
sudo journalctl -u alca-financas -f

# Logs do Gunicorn
tail -f /var/log/gunicorn/alca-financas-error.log
tail -f /var/log/gunicorn/alca-financas-access.log
```

### 8.2 Ver Logs do Nginx

```bash
# Logs de acesso
sudo tail -f /var/log/nginx/alca-financas-access.log

# Logs de erro
sudo tail -f /var/log/nginx/alca-financas-error.log
```

### 8.3 Verificar Status dos Serviços

```bash
# Status do backend
sudo systemctl status alca-financas

# Status do Nginx
sudo systemctl status nginx

# Status do MongoDB (se local)
sudo systemctl status mongod
```

---

## 🔍 Passo 9: Testes Pós-Deploy

### 9.1 Testar API

```bash
# Testar endpoint de saúde (se existir)
curl https://api.seudominio.com.br/api/health

# Testar autenticação
curl -X POST https://api.seudominio.com.br/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@teste.com","password":"senha123"}'
```

### 9.2 Testar Frontend

1. Acesse `https://seudominio.com.br` no navegador
2. Verifique se a página carrega corretamente
3. Teste o login
4. Verifique se as requisições à API funcionam (F12 > Network)

---

## 🛠️ Troubleshooting

### Problema: Backend não inicia

```bash
# Verificar logs
sudo journalctl -u alca-financas -n 50

# Verificar se a porta está em uso
sudo netstat -tulpn | grep 8001

# Verificar permissões
ls -la /var/www/alca-financas/backend
```

### Problema: Nginx retorna 502 Bad Gateway

```bash
# Verificar se backend está rodando
sudo systemctl status alca-financas

# Verificar configuração do Nginx
sudo nginx -t

# Verificar logs do Nginx
sudo tail -f /var/log/nginx/alca-financas-error.log
```

### Problema: Frontend não carrega

```bash
# Verificar se build foi gerado
ls -la /var/www/alca-financas/frontend/dist

# Verificar permissões
sudo chown -R www-data:www-data /var/www/alca-financas/frontend/dist

# Verificar configuração do Nginx
sudo nginx -t
```

### Problema: Erro de conexão com MongoDB

```bash
# Testar conexão MongoDB Atlas
mongosh "mongodb+srv://user:pass@cluster.mongodb.net/alca_financas"

# Verificar variáveis de ambiente
cd /var/www/alca-financas/backend
source venv/bin/activate
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('MONGO_URI'))"
```

---

## 🔐 Segurança Adicional

### Firewall (UFW)

```bash
# Instalar UFW
sudo apt install ufw

# Permitir SSH
sudo ufw allow 22/tcp

# Permitir HTTP e HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Ativar firewall
sudo ufw enable

# Verificar status
sudo ufw status
```

### Atualizações Automáticas

```bash
# Instalar unattended-upgrades
sudo apt install unattended-upgrades

# Configurar
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 📝 Checklist Final

- [ ] Servidor configurado e atualizado
- [ ] MongoDB configurado (Atlas ou local)
- [ ] Código clonado e configurado
- [ ] Variáveis de ambiente configuradas
- [ ] Frontend buildado
- [ ] Nginx configurado e rodando
- [ ] SSL configurado (Let's Encrypt)
- [ ] Gunicorn configurado e rodando
- [ ] Serviços iniciados e habilitados
- [ ] Testes realizados
- [ ] Firewall configurado
- [ ] Logs monitorados

---

## 🆘 Suporte

Se encontrar problemas:

1. Verifique os logs (Passo 8)
2. Consulte a seção Troubleshooting
3. Verifique a documentação da Hostinger
4. Abra uma issue no GitHub do projeto

---

## 📚 Recursos Adicionais

- [Documentação Nginx](https://nginx.org/en/docs/)
- [Documentação Gunicorn](https://docs.gunicorn.org/)
- [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
- [Let's Encrypt](https://letsencrypt.org/)
- [Hostinger Knowledge Base](https://www.hostinger.com.br/tutoriais)

---

**Última atualização**: Dezembro 2024

