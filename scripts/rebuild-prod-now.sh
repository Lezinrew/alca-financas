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
      -e VITE_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg" \
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
echo "1. Acesse http://76.13.239.220:3000"
echo "2. Faça login"
echo "3. Faça logout"
echo "4. O erro 'Supabase não configurado' NÃO deve aparecer"
