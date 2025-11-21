#!/bin/bash
# Script para atualizar o redirecionamento do domínio principal para app.alcahub.com.br

set -e

SERVER_HOST="alcahub.com.br"
SERVER_USER="root"

echo "🔄 Atualizando redirecionamento do domínio principal..."

sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<'EOF'
    cat > /etc/nginx/sites-available/alca-financas <<NGINXEOF
# Redireciona domínio principal para app.alcahub.com.br
server {
    listen 80;
    server_name alcahub.com.br www.alcahub.com.br;
    return 301 https://app.alcahub.com.br$request_uri;
}

server {
    listen 443 ssl http2;
    server_name alcahub.com.br www.alcahub.com.br;
    ssl_certificate /etc/letsencrypt/live/alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/alcahub.com.br/privkey.pem;
    include snippets/ssl-params.conf;
    return 301 https://app.alcahub.com.br$request_uri;
}
NGINXEOF

    nginx -t && systemctl reload nginx
    echo "✅ Redirecionamento atualizado"
EOF

echo "✅ Domínio principal agora redireciona para app.alcahub.com.br"

