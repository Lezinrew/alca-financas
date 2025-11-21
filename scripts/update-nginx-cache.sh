#!/bin/bash
# Script para atualizar configuração do Nginx com cache para assets estáticos

set -e

SERVER_HOST="alcahub.com.br"
SERVER_USER="root"

echo "⚡ Configurando cache para assets estáticos no Nginx..."

sshpass -p "4203434@Mudar" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SERVER_USER@$SERVER_HOST" bash <<'EOF'
    cat > /etc/nginx/sites-available/app.alcahub.com.br <<NGINXEOF
server {
    listen 80;
    server_name app.alcahub.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.alcahub.com.br;
    ssl_certificate /etc/letsencrypt/live/app.alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.alcahub.com.br/privkey.pem;
    include snippets/ssl-params.conf;

    root /var/www/alca-financas/frontend/dist;
    index index.html;

    # Cache para assets estáticos
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|webp|avif)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
        access_log off;
    }

    # Cache para HTML (menor tempo)
    location ~* \.html$ {
        expires 1h;
        add_header Cache-Control "public, must-revalidate";
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json application/xml;
    gzip_comp_level 6;
}
NGINXEOF

    nginx -t && systemctl reload nginx
    echo "✅ Cache configurado com sucesso"
EOF

echo "✅ Configuração de cache aplicada!"

