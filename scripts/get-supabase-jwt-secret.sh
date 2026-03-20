#!/bin/bash
# Script para obter o JWT Secret do Supabase

set -e

SUPABASE_URL="https://blutjlzyvhdvnkvrzdcm.supabase.co"
PROJECT_REF=$(echo $SUPABASE_URL | sed 's/https:\/\///' | cut -d'.' -f1)

echo "🔐 Obtendo JWT Secret do Supabase..."
echo "Project: $PROJECT_REF"
echo ""

# Tentar obter via API (requer anon key)
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdXRqbHp5dmhkdm5rdnJ6ZGNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTEyNzAsImV4cCI6MjA3OTkyNzI3MH0.38YCSHtl6oeScAxgvK8b4O-ahWCPP63vl3uVOe7WXhg"

# Decodificar o anon key para extrair informações
echo "📋 Decodificando Anon Key..."
echo "$ANON_KEY" | cut -d'.' -f2 | base64 -d 2>/dev/null | jq -r '.' || echo "(não é JSON válido)"

echo ""
echo "⚠️  O JWT Secret não está exposto via API pública."
echo ""
echo "🔍 Para obter manualmente:"
echo "1. Acesse: https://app.supabase.com/project/$PROJECT_REF/settings/api"
echo "2. Role até a seção 'JWT Settings'"
echo "3. Copie o valor de 'JWT Secret'"
echo ""
echo "💡 Dica: O JWT Secret geralmente é uma string longa (tipo chave secreta)"
echo ""
read -p "Cole o JWT Secret aqui: " JWT_SECRET

if [ -z "$JWT_SECRET" ]; then
    echo "❌ JWT Secret não informado"
    exit 1
fi

echo ""
echo "✅ JWT Secret obtido!"
echo ""
echo "📝 Atualizando arquivos .env..."

# Atualizar .env na raiz
if grep -q "SUPABASE_JWT_SECRET" .env 2>/dev/null; then
    sed -i.bak "s/^SUPABASE_JWT_SECRET=.*/SUPABASE_JWT_SECRET=$JWT_SECRET/" .env
    echo "✓ Atualizado .env (raiz)"
else
    echo "SUPABASE_JWT_SECRET=$JWT_SECRET" >> .env
    echo "✓ Adicionado a .env (raiz)"
fi

# Atualizar backend/.env se existir
if [ -f backend/.env ]; then
    if grep -q "SUPABASE_JWT_SECRET" backend/.env; then
        sed -i.bak "s/^SUPABASE_JWT_SECRET=.*/SUPABASE_JWT_SECRET=$JWT_SECRET/" backend/.env
        echo "✓ Atualizado backend/.env"
    else
        echo "SUPABASE_JWT_SECRET=$JWT_SECRET" >> backend/.env
        echo "✓ Adicionado a backend/.env"
    fi
fi

echo ""
echo "🔄 Reiniciando backend para carregar nova variável..."
docker compose restart backend

echo ""
echo "⏳ Aguardando backend inicializar..."
sleep 5

echo ""
echo "✅ Configuração concluída!"
echo ""
echo "🧪 Teste agora:"
echo "1. Acesse http://localhost:3000"
echo "2. Faça login"
echo "3. O dashboard deve carregar sem erro 401"
