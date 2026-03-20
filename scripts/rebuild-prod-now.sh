#!/bin/bash
# Rebuild frontend de produção COM Supabase config

ssh root@76.13.239.220 << 'EOF'
    set -e
    cd /var/www/alca-financas

    echo "🧹 Limpando builds antigos..."
    rm -rf frontend/dist build/frontend
    mkdir -p build/frontend

    echo "📦 Rebuilding frontend com Supabase config..."
    docker run --rm \
      -e VITE_SUPABASE_URL="https://blutjlzyvhdvnkvrzdcm.supabase.co" \
      -e VITE_SUPABASE_ANON_KEY="***REMOVED_SUPABASE_ANON_KEY***" \
      -v /var/www/alca-financas/frontend:/app \
      -w /app \
      node:22-alpine \
      sh -c "npm ci && npm run build"

    echo "📋 Copiando build para nginx..."
    cp -a frontend/dist/. build/frontend/
    chmod -R a+rX build/frontend

    echo "🔍 Verificando se Supabase está no bundle..."
    grep -r "blutjlzyvhdvnkvrzdcm" build/frontend/assets/ | head -1 || echo "⚠️  Supabase URL não encontrada no bundle"

    echo "🔄 Reiniciando frontend..."
    docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

    echo ""
    echo "✅ Frontend reconstruído e reiniciado!"
    echo ""
    docker compose -f docker-compose.prod.yml ps frontend
EOF

echo ""
echo "=========================================="
echo "✅ Rebuild concluído!"
echo ""
echo "🧪 Teste agora:"
echo "   🌐 https://alcahub.cloud"
echo ""
echo "Checklist:"
echo "  ✓ Fazer login"
echo "  ✓ Fazer logout (NÃO deve dar erro 'Supabase não configurado')"
echo "  ✓ Testar recuperação de senha (deve redirecionar para alcahub.cloud)"
