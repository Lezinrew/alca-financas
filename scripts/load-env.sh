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
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Verificar variáveis importantes
if [ -n "$SUPABASE_URL" ]; then
    echo "✅ SUPABASE_URL carregado: $SUPABASE_URL"
else
    echo "⚠️  SUPABASE_URL não encontrado no .env"
fi

if [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "✅ SUPABASE_SERVICE_ROLE_KEY carregado"
else
    echo "⚠️  SUPABASE_SERVICE_ROLE_KEY não encontrado no .env"
fi

if [ -n "$SUPABASE_ANON_KEY" ]; then
    echo "✅ SUPABASE_ANON_KEY carregado"
else
    echo "⚠️  SUPABASE_ANON_KEY não encontrado no .env"
fi

echo ""
echo "✨ Variáveis carregadas! Agora você pode rodar os scripts de deploy."
echo ""
echo "Exemplo:"
echo "  export SERVER_HOST='76.13.239.220'"
echo "  export SERVER_USER='root'"
echo "  export DOMAIN='alcahub.cloud'"
echo "  ./scripts/deploy-docker-remote.sh"
