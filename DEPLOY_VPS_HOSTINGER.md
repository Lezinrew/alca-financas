# Deploy no VPS Hostinger - alcahub.com.br

## Arquitetura do Deploy

```
Cliente → alcahub.com.br (Frontend - Nginx)
       ↓
       → api.alcahub.com.br (Backend - Gunicorn + Nginx)
       ↓
       → Supabase (Database)
```

## Pré-requisitos

- VPS Hostinger com acesso SSH
- Domínio alcahub.com.br configurado
- Ubuntu/Debian (assumido)

---

## PARTE 1: Preparação do VPS

### 1.1 Conectar ao VPS

```bash
# Obter IP do VPS no hPanel da Hostinger
# Conectar via SSH
ssh root@SEU_IP_VPS
```

### 1.2 Atualizar Sistema

```bash
apt update && apt upgrade -y
```

### 1.3 Instalar Dependências

```bash
# Python e pip
apt install -y python3 python3-pip python3-venv

# Nginx
apt install -y nginx

# Certbot (SSL)
apt install -y certbot python3-certbot-nginx

# Git
apt install -y git

# Node.js (para build do frontend)
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Supervisor (gerenciador de processos)
apt install -y supervisor
```

---

## PARTE 2: Deploy do Backend

### 2.1 Criar Usuário para Aplicação

```bash
# Criar usuário específico (segurança)
useradd -m -s /bin/bash alcaapp
su - alcaapp
```

### 2.2 Clonar Repositório

```bash
cd /home/alcaapp
git clone https://github.com/Lezinrew/alca-financas.git
cd alca-financas/backend
```

### 2.3 Criar Ambiente Virtual

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Configurar Environment Variables

```bash
# Criar arquivo .env
nano /home/alcaapp/alca-financas/backend/.env
```

Cole o conteúdo de `VPS_BACKEND_ENV.txt`:
```bash
FLASK_ENV=production
NODE_ENV=production
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_XXXXXXXXXXXXXXXXXXXXXXXX
SUPABASE_KEY=sb_secret_XXXXXXXXXXXXXXXXXXXXXXXX
SECRET_KEY=GERAR_COM_openssl_rand_hex_32
JWT_SECRET=GERAR_COM_openssl_rand_hex_32
JWT_EXPIRES_HOURS=24
FRONTEND_URL=https://alcahub.com.br
API_BASE_URL=https://api.alcahub.com.br
CORS_ORIGINS=https://alcahub.com.br,https://www.alcahub.com.br
HOST=0.0.0.0
PORT=8000
WEB_CONCURRENCY=2
WORKER_TIMEOUT=120
LOG_LEVEL=info
```

### 2.5 Testar Aplicação

```bash
# Testar se inicia sem erros
source venv/bin/activate
python app.py
# Ctrl+C para parar
```

### 2.6 Configurar Supervisor (mantém app rodando)

Sair do usuário alcaapp:
```bash
exit  # volta para root
```

Criar configuração:
```bash
nano /etc/supervisor/conf.d/alca-backend.conf
```

Cole:
```ini
[program:alca-backend]
command=/home/alcaapp/alca-financas/backend/venv/bin/gunicorn app:app -c gunicorn.conf.py
directory=/home/alcaapp/alca-financas/backend
user=alcaapp
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/alca-backend.log
environment=PATH="/home/alcaapp/alca-financas/backend/venv/bin"
```

Iniciar:
```bash
supervisorctl reread
supervisorctl update
supervisorctl start alca-backend
supervisorctl status
```

### 2.7 Configurar Nginx para API

```bash
nano /etc/nginx/sites-available/api.alcahub.com.br
```

Cole:
```nginx
server {
    listen 80;
    server_name api.alcahub.com.br;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ativar:
```bash
ln -s /etc/nginx/sites-available/api.alcahub.com.br /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## PARTE 3: Deploy do Frontend

### 3.1 Build Local (na sua máquina)

```bash
cd /Users/lezinrew/Projetos/alca-financas/frontend

# Criar .env.production
cat > .env.production << EOF
VITE_API_URL=https://api.alcahub.com.br
VITE_SUPABASE_URL=https://SEU_PROJETO.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_XXXXXXXXXXXXXXXXXXXXXXXX
EOF

# Build
npm install
npm run build

# Resultado estará em: dist/
```

### 3.2 Upload para VPS

```bash
# Na sua máquina local
cd /Users/lezinrew/Projetos/alca-financas/frontend
rsync -avz --delete dist/ root@SEU_IP_VPS:/var/www/alcahub.com.br/
```

### 3.3 Configurar Nginx para Frontend

No VPS:
```bash
mkdir -p /var/www/alcahub.com.br
nano /etc/nginx/sites-available/alcahub.com.br
```

Cole:
```nginx
server {
    listen 80;
    server_name alcahub.com.br www.alcahub.com.br;
    root /var/www/alcahub.com.br;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache estático
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Ativar:
```bash
ln -s /etc/nginx/sites-available/alcahub.com.br /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## PARTE 4: Configurar DNS

### 4.1 No hPanel da Hostinger

Acessar: https://hpanel.hostinger.com/domains/alcahub.com.br/dns

Adicionar registros:
```
Tipo: A
Nome: @
Valor: SEU_IP_VPS
TTL: 3600

Tipo: A
Nome: www
Valor: SEU_IP_VPS
TTL: 3600

Tipo: A
Nome: api
Valor: SEU_IP_VPS
TTL: 3600
```

Aguardar propagação: 5-30 minutos

---

## PARTE 5: Configurar SSL (HTTPS)

### 5.1 Instalar Certificados

```bash
# Backend API
certbot --nginx -d api.alcahub.com.br

# Frontend
certbot --nginx -d alcahub.com.br -d www.alcahub.com.br
```

Certbot vai:
- Obter certificados Let's Encrypt
- Configurar Nginx automaticamente para HTTPS
- Configurar renovação automática

---

## PARTE 6: Testes Finais

### 6.1 Testar Backend

```bash
curl https://api.alcahub.com.br/api/health
# Esperado: {"status": "ok"}
```

### 6.2 Testar Frontend

Abrir no navegador: https://alcahub.com.br

Verificar:
- ✅ Site carrega
- ✅ HTTPS funcionando (cadeado verde)
- ✅ Login funciona
- ✅ Dashboard mostra dados
- ✅ Console sem erros (F12)

---

## SCRIPTS ÚTEIS

### Atualizar Backend

```bash
ssh root@SEU_IP_VPS
su - alcaapp
cd alca-financas
git pull
cd backend
source venv/bin/activate
pip install -r requirements.txt
exit
supervisorctl restart alca-backend
```

### Atualizar Frontend

```bash
# Local
cd frontend
npm run build
rsync -avz --delete dist/ root@SEU_IP_VPS:/var/www/alcahub.com.br/
```

### Ver Logs

```bash
# Backend
tail -f /var/log/alca-backend.log

# Nginx
tail -f /var/log/nginx/error.log
```

---

## TROUBLESHOOTING

### Backend não inicia
```bash
supervisorctl tail -f alca-backend
# Verificar erros de configuração
```

### CORS errors
- Verificar CORS_ORIGINS no backend/.env
- Reiniciar: `supervisorctl restart alca-backend`

### SSL não funciona
```bash
certbot certificates
# Verificar status dos certificados
```

### DNS não propaga
```bash
# Verificar DNS
nslookup alcahub.com.br
nslookup api.alcahub.com.br
```
