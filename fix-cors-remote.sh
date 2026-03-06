#!/bin/bash
# Script para ser executado DIRETAMENTE no servidor VPS
# Copie este script para o servidor e execute lá

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

echo ""
echo "✅ Correção aplicada! Teste o login em: https://alcahub.cloud/login"
