#!/bin/bash
# Hotfix SSH: Rebuild frontend com Supabase config
# Uso: PROD_HOST=xxx PROD_USER=yyy ./scripts/hotfix-supabase-prod-simple.sh

set -e

# Verificar variáveis
if [ -z "$PROD_HOST" ]; then
    read -p "Digite o host de produção (IP ou domínio): " PROD_HOST
fi

if [ -z "$PROD_USER" ]; then
    read -p "Digite o usuário SSH (ex: lezinrew): " PROD_USER
fi

echo "🔧 Hotfix: Rebuild frontend com Supabase"
echo "Host: $PROD_USER@$PROD_HOST"
echo "=========================================="
echo ""

# Credenciais do Supabase (do frontend/.env local)
SUPABASE_URL="https://blutjlzyvhdvnkvrzdcm.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg"

ssh $PROD_USER@$PROD_HOST << EOF
    set -e
    cd /var/www/alca-financas

    echo "🧹 Limpando builds antigos..."
    rm -rf frontend/dist build/frontend
    mkdir -p build/frontend

    echo "📦 Rebuilding frontend com Supabase config..."
    docker run --rm \
      -e VITE_SUPABASE_URL="$SUPABASE_URL" \
      -e VITE_SUPABASE_ANON_KEY="$SUPABASE_KEY" \
      -e VITE_API_URL="http://localhost:8001" \
      -v /var/www/alca-financas/frontend:/app \
      -w /app \
      node:22-alpine \
      sh -c "npm ci && npm run build"

    echo "📋 Copiando build para nginx..."
    cp -a frontend/dist/. build/frontend/

    echo "🔄 Reiniciando frontend..."
    docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

    echo ""
    echo "✅ Concluído!"
    echo ""
    docker compose -f docker-compose.prod.yml ps frontend
EOF

echo ""
echo "=========================================="
echo "✅ Hotfix aplicado com sucesso!"
echo ""
echo "🧪 Teste agora:"
echo "1. Acesse http://$PROD_HOST:3000"
echo "2. Faça login"
echo "3. Faça logout"
echo "4. Não deve aparecer erro de Supabase"
