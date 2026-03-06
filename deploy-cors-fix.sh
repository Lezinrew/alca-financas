#!/bin/bash
# Script para atualizar configurações de CORS no servidor VPS

set -e

SERVER="alcaapp@76.13.239.220"
PROJECT_DIR="/home/alcaapp/alca-financas"

echo "🔧 Corrigindo configuração de CORS no servidor..."

# Conectar ao servidor e atualizar o .env do backend
ssh $SERVER << 'ENDSSH'
cd /home/alcaapp/alca-financas/backend

# Backup do .env atual
echo "💾 Fazendo backup do .env atual..."
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Atualizar CORS_ORIGINS para incluir alcahub.cloud
echo "📝 Atualizando CORS_ORIGINS..."
if grep -q "^CORS_ORIGINS=" .env; then
    # Se a linha existe, atualiza
    sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud,http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://localhost:8001|' .env
else
    # Se não existe, adiciona
    echo "" >> .env
    echo "# CORS - CRITICAL: Must include production domain" >> .env
    echo "CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud,http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://localhost:8001" >> .env
fi

# Atualizar FRONTEND_URL se necessário
if grep -q "^FRONTEND_URL=" .env; then
    sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://alcahub.cloud|' .env
else
    echo "FRONTEND_URL=https://alcahub.cloud" >> .env
fi

echo "✅ Configurações atualizadas!"
echo ""
echo "📄 Verificando CORS_ORIGINS no .env:"
grep "^CORS_ORIGINS=" .env

echo ""
echo "🔄 Reiniciando backend..."
sudo supervisorctl restart alca-backend

echo ""
echo "✅ Backend reiniciado com sucesso!"
sudo supervisorctl status alca-backend
ENDSSH

echo ""
echo "✅ Configuração de CORS atualizada no servidor!"
echo "🧪 Teste o login novamente em: https://alcahub.cloud/login"
echo ""
echo "ℹ️  Se ainda não funcionar, verifique:"
echo "   1. Se o backend está rodando: sudo supervisorctl status alca-backend"
echo "   2. Os logs do backend: sudo supervisorctl tail -f alca-backend"
echo "   3. Os logs do nginx: sudo tail -f /var/log/nginx/error.log"
