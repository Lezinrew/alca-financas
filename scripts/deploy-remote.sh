#!/bin/bash

###############################################################################
# Deploy Remoto - Alça Finanças para Hostinger
# Script para fazer deploy completo via SSH
###############################################################################

set -e

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configurações do servidor
SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
SERVER_PASS="4203434@Mudar"
PROJECT_DIR="/var/www/alca-financas"
DOMAIN="alcahub.com.br"

# Gerar SECRET_KEY
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)

echo -e "${BLUE}🚀 Iniciando deploy remoto do Alça Finanças...${NC}"
echo -e "${BLUE}Servidor: ${SERVER_USER}@${SERVER_HOST}${NC}"
echo ""

# Instalar sshpass se não estiver instalado (para autenticação por senha)
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass não encontrado. Instalando...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass 2>/dev/null || echo -e "${RED}❌ Instale sshpass manualmente: brew install hudochenkov/sshpass/sshpass${NC}"
    else
        sudo apt-get update && sudo apt-get install -y sshpass
    fi
fi

# Função para executar comandos remotos
execute_remote() {
    sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no \
        -o IdentitiesOnly=yes -o NumberOfPasswordPrompts=1 \
        "${SERVER_USER}@${SERVER_HOST}" "$1"
}

# Função para copiar arquivos
copy_file() {
    sshpass -p "$SERVER_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "$1" "${SERVER_USER}@${SERVER_HOST}:$2"
}

echo -e "${BLUE}📡 Conectando ao servidor...${NC}"

# Testar conexão
if ! execute_remote "echo 'Conexão OK'"; then
    echo -e "${RED}❌ Erro ao conectar ao servidor${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Conectado ao servidor${NC}"
echo ""

# 1. Atualizar sistema e instalar dependências
echo -e "${BLUE}📦 Atualizando sistema e instalando dependências...${NC}"
execute_remote "
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq git curl wget build-essential python3 python3-pip python3-venv nginx certbot python3-certbot-nginx
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs
"

echo -e "${GREEN}✅ Dependências instaladas${NC}"
echo ""

# 2. Criar diretório do projeto
echo -e "${BLUE}📁 Criando diretório do projeto...${NC}"
execute_remote "
    mkdir -p ${PROJECT_DIR}
    chown -R ${SERVER_USER}:${SERVER_USER} ${PROJECT_DIR}
"

echo -e "${GREEN}✅ Diretório criado${NC}"
echo ""

# 3. Clonar ou atualizar repositório
echo -e "${BLUE}📥 Clonando/atualizando repositório...${NC}"
execute_remote "
    cd ${PROJECT_DIR}
    if [ -d '.git' ]; then
        git fetch origin
        git reset --hard origin/main || git reset --hard origin/master
    else
        git clone https://github.com/Lezinrew/alca-financas.git .
    fi
"

echo -e "${GREEN}✅ Repositório atualizado${NC}"
echo ""

# 4. Configurar backend
echo -e "${BLUE}🔧 Configurando backend...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/backend
    if [ ! -d 'venv' ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    pip install gunicorn --quiet
    deactivate
"

# Criar arquivo .env do backend
echo -e "${BLUE}📝 Criando arquivo .env do backend...${NC}"
execute_remote "cat > ${PROJECT_DIR}/backend/.env << 'EOF'
# Ambiente
FLASK_ENV=production
NODE_ENV=production

# MongoDB (ATUALIZE COM SUA CONNECTION STRING)
MONGO_URI=mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas
MONGO_DB=alca_financas

# JWT
SECRET_KEY=${SECRET_KEY}
JWT_EXPIRES_HOURS=24

# CORS
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN},https://app.${DOMAIN}

# OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
EOF
"

echo -e "${YELLOW}⚠️  IMPORTANTE: Atualize o MONGO_URI no arquivo ${PROJECT_DIR}/backend/.env${NC}"
echo ""

# 5. Configurar frontend
echo -e "${BLUE}🎨 Configurando frontend...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/frontend
    npm install --silent
"

# Criar arquivo .env.production do frontend
echo -e "${BLUE}📝 Criando arquivo .env.production do frontend...${NC}"
execute_remote "cat > ${PROJECT_DIR}/frontend/.env.production << 'EOF'
VITE_API_URL=https://api.${DOMAIN}
EOF
"

# Build do frontend
echo -e "${BLUE}🏗️  Buildando frontend...${NC}"
execute_remote "
    cd ${PROJECT_DIR}/frontend
    npm run build
"

echo -e "${GREEN}✅ Frontend buildado${NC}"
echo ""

# 6. Configurar Nginx
echo -e "${BLUE}🌐 Configurando Nginx...${NC}"
execute_remote "cat > /etc/nginx/sites-available/alca-financas << 'NGINX_EOF'
# Redirecionar HTTP para HTTPS
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

# Servidor HTTPS
server {
    listen 443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};

    # Certificados SSL (serão gerados pelo Certbot)
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # Configurações SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Frontend (React SPA)
    location / {
        root ${PROJECT_DIR}/frontend/dist;
        try_files \$uri \$uri/ /index.html;
        index index.html;
        
        # Cache para assets estáticos
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control \"public, immutable\";
        }
    }

    # API Backend
    location /api {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Logs
    access_log /var/log/nginx/alca-financas-access.log;
    error_log /var/log/nginx/alca-financas-error.log;
}
NGINX_EOF
"

# Ativar site
execute_remote "
    ln -sf /etc/nginx/sites-available/alca-financas /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
"

echo -e "${GREEN}✅ Nginx configurado${NC}"
echo ""

# 7. Configurar Gunicorn
echo -e "${BLUE}⚙️  Configurando Gunicorn...${NC}"
execute_remote "cat > ${PROJECT_DIR}/backend/gunicorn_config.py << 'EOF'
import multiprocessing

bind = \"127.0.0.1:8001\"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = \"sync\"
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = \"/var/log/gunicorn/alca-financas-access.log\"
errorlog = \"/var/log/gunicorn/alca-financas-error.log\"
loglevel = \"info\"
EOF
"

# Criar diretório de logs
execute_remote "
    mkdir -p /var/log/gunicorn
    chown -R ${SERVER_USER}:${SERVER_USER} /var/log/gunicorn
"

echo -e "${GREEN}✅ Gunicorn configurado${NC}"
echo ""

# 8. Configurar Systemd Service
echo -e "${BLUE}🔧 Configurando serviço systemd...${NC}"
execute_remote "cat > /etc/systemd/system/alca-financas.service << 'EOF'
[Unit]
Description=Alca Financas Backend API
After=network.target

[Service]
User=${SERVER_USER}
Group=${SERVER_USER}
WorkingDirectory=${PROJECT_DIR}/backend
Environment=\"PATH=${PROJECT_DIR}/backend/venv/bin\"
ExecStart=${PROJECT_DIR}/backend/venv/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
"

execute_remote "
    systemctl daemon-reload
    systemctl enable alca-financas
    systemctl start alca-financas
"

echo -e "${GREEN}✅ Serviço systemd configurado${NC}"
echo ""

# 9. Configurar SSL (Let's Encrypt)
echo -e "${BLUE}🔒 Configurando SSL com Let's Encrypt...${NC}"
echo -e "${YELLOW}⚠️  Isso pode pedir um email. Use um email válido para notificações.${NC}"
execute_remote "
    certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --non-interactive --agree-tos --email admin@${DOMAIN} --redirect || echo 'Certbot pode precisar de configuração manual'
"

echo -e "${GREEN}✅ SSL configurado${NC}"
echo ""

# 10. Reiniciar serviços
echo -e "${BLUE}🔄 Reiniciando serviços...${NC}"
execute_remote "
    systemctl restart alca-financas
    systemctl reload nginx
"

echo -e "${GREEN}✅ Serviços reiniciados${NC}"
echo ""

# 11. Status final
echo -e "${GREEN}✅ Deploy concluído!${NC}"
echo ""
echo -e "${BLUE}📊 Status dos serviços:${NC}"
execute_remote "
    echo '  Backend:  ' \$(systemctl is-active alca-financas 2>/dev/null || echo 'não configurado')
    echo '  Nginx:    ' \$(systemctl is-active nginx 2>/dev/null || echo 'não configurado')
"

echo ""
echo -e "${BLUE}📝 Próximos passos:${NC}"
echo "  1. Atualize o MONGO_URI em ${PROJECT_DIR}/backend/.env"
echo "  2. Reinicie o serviço: ssh ${SERVER_USER}@${SERVER_HOST} 'systemctl restart alca-financas'"
echo "  3. Acesse: https://${DOMAIN}"
echo "  4. Verifique os logs: ssh ${SERVER_USER}@${SERVER_HOST} 'journalctl -u alca-financas -f'"
echo ""

