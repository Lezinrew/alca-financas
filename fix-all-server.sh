#!/bin/bash
# Script para corrigir TODOS os problemas do servidor
# Execute este script DIRETAMENTE no servidor VPS com sudo

set -e

echo "🔧 Corrigindo problemas do servidor - Alça Finanças"
echo "===================================================="
echo ""

# Verificar se está como root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Este script deve ser executado com sudo"
    echo "Execute: sudo bash fix-all-server.sh"
    exit 1
fi

# 1. Corrigir CORS no backend
echo "1️⃣  Corrigindo CORS no backend..."
cd /home/alcaapp/alca-financas/backend

# Backup
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Atualizar CORS_ORIGINS
if grep -q "^CORS_ORIGINS=" .env; then
    sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud,http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://localhost:8001|' .env
else
    echo "" >> .env
    echo "# CORS - CRITICAL" >> .env
    echo "CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud,http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://localhost:8001" >> .env
fi

# Atualizar FRONTEND_URL
if grep -q "^FRONTEND_URL=" .env; then
    sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://alcahub.cloud|' .env
else
    echo "FRONTEND_URL=https://alcahub.cloud" >> .env
fi

echo "✅ CORS configurado!"
echo ""

# 2. Verificar e corrigir configuração do Nginx
echo "2️⃣  Verificando configuração do Nginx..."
if [ ! -f /etc/nginx/sites-available/alcahub.cloud ]; then
    echo "Copiando configuração do Nginx..."
    cp /home/alcaapp/alca-financas/nginx-vps.conf /etc/nginx/sites-available/alcahub.cloud
    ln -sf /etc/nginx/sites-available/alcahub.cloud /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
fi

# Testar configuração
if nginx -t; then
    echo "✅ Configuração Nginx válida!"
    systemctl reload nginx
else
    echo "❌ Erro na configuração Nginx!"
    exit 1
fi
echo ""

# 3. Verificar SSL
echo "3️⃣  Verificando certificados SSL..."
if ! grep -q "listen 443" /etc/nginx/sites-enabled/alcahub.cloud; then
    echo "⚠️  SSL não está configurado!"
    echo ""
    echo "Para configurar SSL, você precisa:"
    echo "  1. Editar o arquivo: /home/alcaapp/alca-financas/scripts/setup-ssl-production.sh"
    echo "  2. Alterar o EMAIL na linha 20"
    echo "  3. Executar: sudo bash /home/alcaapp/alca-financas/scripts/setup-ssl-production.sh"
    echo ""
    echo "OU, se já tiver certificados Let's Encrypt configurados:"
    echo "  sudo certbot --nginx -d alcahub.cloud -d www.alcahub.cloud -d api.alcahub.cloud"
    echo ""
    read -p "Deseja configurar SSL agora? (s/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "Por favor, forneça seu email para Let's Encrypt:"
        read -p "Email: " EMAIL
        certbot --nginx \
            -d alcahub.cloud \
            -d www.alcahub.cloud \
            -d api.alcahub.cloud \
            --email "$EMAIL" \
            --agree-tos \
            --no-eff-email \
            --redirect
    fi
else
    echo "✅ SSL já está configurado!"
fi
echo ""

# 4. Reiniciar serviços
echo "4️⃣  Reiniciando serviços..."
supervisorctl restart alca-backend
supervisorctl restart alca-frontend
echo "✅ Serviços reiniciados!"
echo ""

# 5. Verificar status
echo "5️⃣  Verificando status dos serviços..."
supervisorctl status
echo ""

# 6. Teste final
echo "6️⃣  Teste de conectividade..."
sleep 3  # Aguardar serviços iniciarem

if curl -s http://localhost:8001/api/health > /dev/null; then
    echo "✅ Backend está respondendo"
else
    echo "❌ Backend não está respondendo"
fi

if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend está respondendo"
else
    echo "❌ Frontend não está respondendo"
fi
echo ""

echo "===================================================="
echo "✅ Correções aplicadas!"
echo ""
echo "📋 Verificações finais:"
echo "  CORS_ORIGINS: $(grep "^CORS_ORIGINS=" /home/alcaapp/alca-financas/backend/.env)"
echo "  FRONTEND_URL: $(grep "^FRONTEND_URL=" /home/alcaapp/alca-financas/backend/.env)"
echo ""
echo "🧪 Teste o login em: https://alcahub.cloud/login"
echo ""
echo "📝 Para ver logs em tempo real:"
echo "  sudo supervisorctl tail -f alca-backend"
echo "  sudo tail -f /var/log/nginx/error.log"
