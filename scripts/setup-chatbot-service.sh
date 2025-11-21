#!/bin/bash
# Script para configurar o serviço de chatbot no servidor

set -e

SERVER_HOST="alcahub.com.br"
SERVER_USER="root"
PROJECT_DIR="/var/www/alca-financas"
CHATBOT_DIR="${PROJECT_DIR}/services/chatbot"
CHATBOT_PORT=8100

echo "🤖 Configurando serviço de Chatbot..."

# Instalar dependências do chatbot
echo "📦 Instalando dependências do chatbot..."
sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<EOF
    cd ${CHATBOT_DIR}
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    deactivate
    echo "✅ Dependências instaladas"
EOF

# Criar serviço systemd
echo "⚙️  Criando serviço systemd..."
sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<EOF
    cat > /etc/systemd/system/alca-chatbot.service <<SERVICEEOF
[Unit]
Description=Alca Financas Chatbot Service
After=network.target

[Service]
User=${SERVER_USER}
Group=${SERVER_USER}
WorkingDirectory=${CHATBOT_DIR}
Environment="PATH=${CHATBOT_DIR}/venv/bin"
Environment="CHATBOT_PORT=${CHATBOT_PORT}"
ExecStart=${CHATBOT_DIR}/venv/bin/uvicorn app:app --host 127.0.0.1 --port ${CHATBOT_PORT}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
    systemctl enable alca-chatbot
    systemctl start alca-chatbot
    echo "✅ Serviço criado e iniciado"
EOF

# Atualizar Nginx
echo "🌐 Atualizando configuração do Nginx..."
sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<EOF
    cat > /etc/nginx/sites-available/chat.alcahub.com.br <<NGINXEOF
server {
    listen 80;
    server_name chat.alcahub.com.br;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name chat.alcahub.com.br;
    ssl_certificate /etc/letsencrypt/live/chat.alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.alcahub.com.br/privkey.pem;
    include snippets/ssl-params.conf;

    location / {
        proxy_pass http://127.0.0.1:${CHATBOT_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
NGINXEOF

    nginx -t && systemctl reload nginx
    echo "✅ Nginx atualizado"
EOF

echo ""
echo "✅ Chatbot configurado com sucesso!"
echo ""
echo "📊 Status:"
sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" 'systemctl status alca-chatbot --no-pager -l | head -10'

