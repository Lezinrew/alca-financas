#!/bin/bash
# Setup Nginx Reverse Proxy para alcahub.cloud
# Executar NO SERVIDOR como root

set -e

echo "🔧 Configurando Nginx Reverse Proxy"
echo "===================================="
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Execute como root: sudo ./setup-nginx-proxy.sh"
    exit 1
fi

# 1. Instalar nginx se não estiver instalado
if ! command -v nginx &> /dev/null; then
    echo "📦 Instalando nginx..."
    apt update
    apt install -y nginx
else
    echo "✅ Nginx já instalado"
fi

# 2. Copiar configuração
echo "📝 Criando configuração do nginx..."
cat > /etc/nginx/sites-available/alcahub.cloud << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name alcahub.cloud www.alcahub.cloud;

    # Frontend (arquivos estáticos)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeout aumentado para operações longas
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logs
    access_log /var/log/nginx/alcahub.cloud.access.log;
    error_log /var/log/nginx/alcahub.cloud.error.log;
}
EOF

# 3. Criar symlink
echo "🔗 Habilitando site..."
ln -sf /etc/nginx/sites-available/alcahub.cloud /etc/nginx/sites-enabled/

# 4. Remover default se existir
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "🗑️  Removendo configuração default..."
    rm -f /etc/nginx/sites-enabled/default
fi

# 5. Testar configuração
echo "🧪 Testando configuração do nginx..."
nginx -t

# 6. Recarregar nginx
echo "🔄 Recarregando nginx..."
systemctl reload nginx
systemctl enable nginx

echo ""
echo "✅ Nginx configurado com sucesso!"
echo ""
echo "📊 Status:"
systemctl status nginx --no-pager | head -10

echo ""
echo "🧪 Teste agora:"
echo "   http://alcahub.cloud (será redirecionado para HTTPS depois do certbot)"
echo ""
echo "🔒 Próximo passo: Instalar SSL com certbot"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d alcahub.cloud -d www.alcahub.cloud"
echo ""
