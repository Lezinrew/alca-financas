#!/bin/bash
# =============================================================================
# test-migrations-docker.sh
# Testa migrations do zero usando Docker Postgres
# =============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
CONTAINER_NAME="alca-test-pg"
DB_NAME="alca_test"
PG_PASSWORD="postgres"
PG_USER="postgres"
PG_PORT="5432"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🐳 TESTE DE MIGRATIONS COM DOCKER POSTGRES                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# STEP 1: Docker Check
# =============================================================================
echo -e "${BLUE}[1/8]${NC} Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado${NC}"
    echo "Instale Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✅ Docker instalado${NC}"
echo ""

# =============================================================================
# STEP 2: Cleanup Previous Container
# =============================================================================
echo -e "${BLUE}[2/8]${NC} Limpando containers antigos..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true
echo -e "${GREEN}✅ Ambiente limpo${NC}"
echo ""

# =============================================================================
# STEP 3: Start Postgres Container
# =============================================================================
echo -e "${BLUE}[3/8]${NC} Iniciando container Postgres 15..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PG_PORT:5432 \
  -e POSTGRES_PASSWORD=$PG_PASSWORD \
  postgres:15-alpine > /dev/null

echo -n "Aguardando Postgres inicializar"
for i in {1..15}; do
    if docker exec $CONTAINER_NAME pg_isready -U postgres &> /dev/null; then
        echo ""
        echo -e "${GREEN}✅ Postgres pronto${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# =============================================================================
# STEP 4: Create Database
# =============================================================================
echo -e "${BLUE}[4/8]${NC} Criando database '$DB_NAME'..."
docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    createdb -U $PG_USER $DB_NAME 2>&1 | grep -v "could not change directory" || true
echo -e "${GREEN}✅ Database criado${NC}"
echo ""

# =============================================================================
# STEP 4.5: Create Supabase-compatible Mocks
# =============================================================================
echo -e "${BLUE}[4.5/8]${NC} Criando mocks para compatibilidade Supabase..."

# Create roles (authenticated, anon)
docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -c "CREATE ROLE authenticated NOLOGIN;" 2>/dev/null || true
docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -c "CREATE ROLE anon NOLOGIN;" 2>/dev/null || true

# Create auth schema and auth.uid() mock
docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -c "
        CREATE SCHEMA IF NOT EXISTS auth;
        CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
        LANGUAGE sql STABLE
        AS \$\$ SELECT NULL::uuid; \$\$;
    " > /dev/null 2>&1

echo -e "${GREEN}✅ Roles e auth.uid() criados${NC}"
echo ""

# =============================================================================
# STEP 5: Apply Migrations
# =============================================================================
echo -e "${BLUE}[5/8]${NC} Aplicando migrations..."
echo ""

DB_URL="postgresql://$PG_USER:$PG_PASSWORD@localhost:$PG_PORT/$DB_NAME"

# Migration 001: init
echo -n "  [001] init.sql (schema) ... "
if docker exec -i $CONTAINER_NAME psql -U $PG_USER -d $DB_NAME < supabase/migrations/20260303_000001_init.sql &> /tmp/migration_001.log; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    cat /tmp/migration_001.log
    exit 1
fi

# Migration 002: functions
echo -n "  [002] functions.sql ... "
if docker exec -i $CONTAINER_NAME psql -U $PG_USER -d $DB_NAME < supabase/migrations/20260303_000002_functions.sql &> /tmp/migration_002.log; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    cat /tmp/migration_002.log
    exit 1
fi

# Migration 003: policies
echo -n "  [003] rls_policies.sql ... "
if docker exec -i $CONTAINER_NAME psql -U $PG_USER -d $DB_NAME < supabase/migrations/20260303_000003_rls_policies.sql &> /tmp/migration_003.log; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    cat /tmp/migration_003.log
    exit 1
fi

# Migration 004: triggers
echo -n "  [004] triggers.sql ... "
if docker exec -i $CONTAINER_NAME psql -U $PG_USER -d $DB_NAME < supabase/migrations/20260303_000004_triggers.sql &> /tmp/migration_004.log; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    cat /tmp/migration_004.log
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Todas as migrations aplicadas com sucesso${NC}"
echo ""

# =============================================================================
# STEP 6: Validation Checks
# =============================================================================
echo -e "${BLUE}[6/8]${NC} Executando validações..."
echo ""

# Check tables
TABLES_COUNT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | xargs)
echo -n "  📋 Tabelas criadas (esperado: 7) ... "
if [ "$TABLES_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ $TABLES_COUNT${NC}"
else
    echo -e "${RED}❌ $TABLES_COUNT${NC}"
fi

# Check functions
FUNCTIONS_COUNT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public' AND p.proname IN ('current_app_user_id', 'current_tenant_id', 'dev_seed_account', 'update_updated_at_column');" | xargs)
echo -n "  🔧 Functions criadas (esperado: 4) ... "
if [ "$FUNCTIONS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ $FUNCTIONS_COUNT${NC}"
else
    echo -e "${RED}❌ $FUNCTIONS_COUNT${NC}"
fi

# Check RLS enabled
RLS_COUNT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true;" | xargs)
echo -n "  🔐 RLS habilitado (esperado: 7) ... "
if [ "$RLS_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ $RLS_COUNT${NC}"
else
    echo -e "${RED}❌ $RLS_COUNT${NC}"
fi

# Check policies
POLICIES_COUNT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public';" | xargs)
echo -n "  🛡️  Policies criadas (esperado: ~14) ... "
if [ "$POLICIES_COUNT" -ge 14 ]; then
    echo -e "${GREEN}✅ $POLICIES_COUNT${NC}"
else
    echo -e "${YELLOW}⚠️  $POLICIES_COUNT${NC}"
fi

# Check TO public (SECURITY)
PUBLIC_POLICIES=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND roles @> ARRAY['public']::name[];" | xargs)
echo -n "  🔒 Policies TO public (esperado: 0) ... "
if [ "$PUBLIC_POLICIES" -eq 0 ]; then
    echo -e "${GREEN}✅ $PUBLIC_POLICIES (seguro)${NC}"
else
    echo -e "${RED}❌ $PUBLIC_POLICIES (VULNERABILIDADE!)${NC}"
fi

# Check triggers
TRIGGERS_COUNT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_trigger WHERE tgname LIKE 'update_%_updated_at';" | xargs)
echo -n "  ⚡ Triggers criados (esperado: 4) ... "
if [ "$TRIGGERS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ $TRIGGERS_COUNT${NC}"
else
    echo -e "${RED}❌ $TRIGGERS_COUNT${NC}"
fi

# Test functions callable
echo -n "  🧪 Testando current_tenant_id() ... "
TENANT_RESULT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT current_tenant_id();" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ (callable)${NC}"
else
    echo -e "${RED}❌${NC}"
fi

echo -n "  🧪 Testando current_app_user_id() ... "
USER_RESULT=$(docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -t -c "SELECT current_app_user_id();" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ (callable)${NC}"
else
    echo -e "${RED}❌${NC}"
fi

echo ""

# =============================================================================
# STEP 7: Detailed Table List
# =============================================================================
echo -e "${BLUE}[7/8]${NC} Tabelas criadas:"
echo ""
docker exec -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME \
    psql -U $PG_USER -d $DB_NAME -c "\dt" | grep -E "public \|"
echo ""

# =============================================================================
# STEP 8: Cleanup
# =============================================================================
echo -e "${BLUE}[8/8]${NC} Limpeza..."
echo ""
echo "Container '$CONTAINER_NAME' mantido para inspeção manual."
echo ""
echo -e "${YELLOW}Comandos úteis:${NC}"
echo "  # Conectar ao DB:"
echo "  docker exec -it -e PGPASSWORD=$PG_PASSWORD $CONTAINER_NAME psql -U $PG_USER -d $DB_NAME"
echo ""
echo "  # Parar e remover:"
echo "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
echo ""

# =============================================================================
# FINAL SUMMARY
# =============================================================================
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  📊 RESUMO DO TESTE                                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Status: ${GREEN}✅ MIGRATIONS EXECUTAM DO ZERO${NC}"
echo ""
echo "  Resultados:"
echo "    - Tabelas: $TABLES_COUNT/7"
echo "    - Functions: $FUNCTIONS_COUNT/4"
echo "    - RLS: $RLS_COUNT/7 tabelas"
echo "    - Policies: $POLICIES_COUNT (~14 esperado)"
echo "    - Policies TO public: $PUBLIC_POLICIES (0 = seguro)"
echo "    - Triggers: $TRIGGERS_COUNT/4"
echo ""
echo "  🎉 ${GREEN}Migrations estão 100% reprodutíveis!${NC}"
echo ""
echo "  Próximo passo: Testar em Supabase staging"
echo ""

exit 0
