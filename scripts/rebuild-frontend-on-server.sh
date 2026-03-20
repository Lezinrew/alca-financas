#!/bin/bash
# Script para executar DIRETAMENTE no servidor de produção
# Uso: ./rebuild-frontend-on-server.sh

set -e

echo "🔧 Rebuild Frontend em Produção"
echo "================================"
echo ""

# Verificar se está no servidor
if [ ! -d "/var/www/alca-financas" ]; then
    echo "❌ Este script deve ser executado NO SERVIDOR!"
    echo "Execute:"
    echo "  ssh root@76.13.239.220"
    echo "  cd /var/www/alca-financas"
    echo "  ./scripts/rebuild-frontend-on-server.sh"
    exit 1
fi

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
if grep -r "blutjlzyvhdvnkvrzdcm" build/frontend/assets/ > /dev/null 2>&1; then
    echo "✅ Supabase URL encontrada no bundle"
else
    echo "⚠️  Supabase URL NÃO encontrada no bundle!"
fi

echo "🔄 Reiniciando container do frontend..."
docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

echo ""
echo "✅ Rebuild concluído!"
echo ""
echo "📊 Status dos containers:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "🧪 Teste agora:"
echo "  http://76.13.239.220:3000"
echo "  ou"
echo "  https://alcahub.cloud"
