#!/bin/bash
# Hotfix: Rebuild frontend de produção com variáveis do Supabase
# Uso: ./scripts/hotfix-supabase-prod.sh

set -e

echo "🔧 Hotfix: Rebuild frontend com Supabase config"
echo "=============================================="

# Carregar .env se existir
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Validar variáveis necessárias
if [ -z "$PROD_HOST" ]; then
    echo "❌ Erro: PROD_HOST não definido no .env"
    exit 1
fi

if [ -z "$PROD_USER" ]; then
    echo "❌ Erro: PROD_USER não definido no .env"
    exit 1
fi

# Obter credenciais do Supabase do frontend/.env local
if [ -f frontend/.env ]; then
    VITE_SUPABASE_URL=$(grep VITE_SUPABASE_URL frontend/.env | cut -d '=' -f2)
    VITE_SUPABASE_ANON_KEY=$(grep VITE_SUPABASE_ANON_KEY frontend/.env | cut -d '=' -f2)
else
    echo "❌ Erro: frontend/.env não encontrado"
    exit 1
fi

echo "📡 Conectando ao servidor: $PROD_USER@$PROD_HOST"
echo ""

ssh $PROD_USER@$PROD_HOST << EOF
    set -e
    cd /var/www/alca-financas

    echo "🧹 Limpando builds antigos..."
    rm -rf frontend/dist build/frontend
    mkdir -p build/frontend

    echo "📦 Rebuilding frontend com Supabase config..."
    docker run --rm \
      -e VITE_SUPABASE_URL="$VITE_SUPABASE_URL" \
      -e VITE_SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY" \
      -e VITE_API_URL="http://localhost:8001" \
      -v /var/www/alca-financas/frontend:/app \
      -w /app \
      node:22-alpine \
      sh -c "npm ci && npm run build"

    echo "📋 Copiando build para nginx..."
    cp -a frontend/dist/. build/frontend/

    echo "🔄 Reiniciando container do frontend..."
    docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

    echo ""
    echo "✅ Frontend reconstruído e reiniciado"
    echo ""
    echo "🔍 Verificando status..."
    docker compose -f docker-compose.prod.yml ps frontend

    echo ""
    echo "📊 Logs recentes do frontend:"
    docker compose -f docker-compose.prod.yml logs --tail=20 frontend
EOF

echo ""
echo "=============================================="
echo "✅ Hotfix concluído!"
echo ""
echo "🧪 Validação:"
echo "1. Acesse http://$PROD_HOST:3000"
echo "2. Faça login"
echo "3. Faça logout"
echo "4. O erro 'Supabase não configurado' NÃO deve aparecer"
echo ""
