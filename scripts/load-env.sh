#!/usr/bin/env bash
###############################################################################
# Load Environment Variables
# Carrega variáveis do .env para usar em scripts de deploy
# Uso: source scripts/load-env.sh
###############################################################################

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  Arquivo .env não encontrado na raiz do projeto"
    echo "Crie um arquivo .env com suas credenciais Supabase"
    return 1 2>/dev/null || exit 1
fi

# Carregar variáveis
echo "📦 Carregando variáveis do .env..."
set -a
source .env
set +a

# Verificar e normalizar variáveis Supabase
# Se VITE_SUPABASE_URL existe mas SUPABASE_URL não, copiar
if [ -z "$SUPABASE_URL" ] && [ -n "$VITE_SUPABASE_URL" ]; then
    export SUPABASE_URL="$VITE_SUPABASE_URL"
    echo "ℹ️  Usando VITE_SUPABASE_URL como SUPABASE_URL"
fi

if [ -z "$SUPABASE_ANON_KEY" ] && [ -n "$VITE_SUPABASE_ANON_KEY" ]; then
    export SUPABASE_ANON_KEY="$VITE_SUPABASE_ANON_KEY"
    echo "ℹ️  Usando VITE_SUPABASE_ANON_KEY como SUPABASE_ANON_KEY"
fi

# Verificar variáveis importantes
if [ -n "$SUPABASE_URL" ]; then
    echo "✅ SUPABASE_URL carregado: $SUPABASE_URL"
else
    echo "⚠️  SUPABASE_URL não encontrado no .env"
    echo "   Procure por: SUPABASE_URL ou VITE_SUPABASE_URL"
fi

if [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "✅ SUPABASE_SERVICE_ROLE_KEY carregado (${#SUPABASE_SERVICE_ROLE_KEY} caracteres)"
else
    echo "⚠️  SUPABASE_SERVICE_ROLE_KEY não encontrado no .env"
    echo "   Esta é a chave 'service_role' do Supabase (começa com eyJ...)"
fi

if [ -n "$SUPABASE_ANON_KEY" ] || [ -n "$VITE_SUPABASE_ANON_KEY" ]; then
    echo "✅ SUPABASE_ANON_KEY carregado (${#SUPABASE_ANON_KEY} caracteres)"
else
    echo "⚠️  SUPABASE_ANON_KEY não encontrado no .env"
    echo "   Procure por: SUPABASE_ANON_KEY ou VITE_SUPABASE_ANON_KEY"
fi

echo ""
echo "✨ Variáveis carregadas! Agora você pode rodar os scripts de deploy."
echo ""
echo "Exemplo:"
echo "  export SERVER_HOST='76.13.239.220'"
echo "  export SERVER_USER='root'"
echo "  export DOMAIN='alcahub.cloud'"
echo "  ./scripts/deploy-docker-remote.sh"
