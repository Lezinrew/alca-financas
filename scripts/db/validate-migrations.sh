#!/bin/bash
# =============================================================================
# validate-migrations.sh
# Valida estado do banco após aplicar migrations
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Database URL (from env or arg)
DATABASE_URL="${1:-$SUPABASE_DB_URL}"

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL not set${NC}"
    echo "Usage: $0 [DATABASE_URL]"
    echo "   or: export SUPABASE_DB_URL=postgresql://..."
    exit 1
fi

echo "🔍 Validating migrations against: ${DATABASE_URL}"
echo ""

# =============================================================================
# 1. Verificar Tabelas
# =============================================================================
echo "📋 Checking tables..."
EXPECTED_TABLES="users tenants tenant_members categories accounts transactions oauth_states"
TABLES_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")

if [ "$TABLES_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ Tables: $TABLES_COUNT/7${NC}"
else
    echo -e "${RED}❌ Tables: $TABLES_COUNT/7 (expected 7)${NC}"
    psql "$DATABASE_URL" -c "\dt public.*"
    exit 1
fi

# =============================================================================
# 2. Verificar Functions
# =============================================================================
echo "🔧 Checking functions..."
FUNCTIONS_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public' AND p.proname IN ('current_app_user_id', 'current_tenant_id', 'dev_seed_account', 'update_updated_at_column');")

if [ "$FUNCTIONS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ Functions: $FUNCTIONS_COUNT/4${NC}"
else
    echo -e "${RED}❌ Functions: $FUNCTIONS_COUNT/4 (expected 4)${NC}"
    psql "$DATABASE_URL" -c "\df public.*"
    exit 1
fi

# =============================================================================
# 3. Verificar RLS Ativo
# =============================================================================
echo "🔐 Checking RLS..."
RLS_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true;")

if [ "$RLS_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ RLS enabled: $RLS_COUNT/7 tables${NC}"
else
    echo -e "${RED}❌ RLS enabled: $RLS_COUNT/7 (expected 7)${NC}"
    psql "$DATABASE_URL" -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';"
    exit 1
fi

# =============================================================================
# 4. Verificar Policies
# =============================================================================
echo "🛡️  Checking policies..."
POLICIES_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public';")

if [ "$POLICIES_COUNT" -ge 14 ]; then
    echo -e "${GREEN}✅ Policies: $POLICIES_COUNT (expected ~14)${NC}"
else
    echo -e "${YELLOW}⚠️  Policies: $POLICIES_COUNT (expected ~14)${NC}"
fi

# Verificar se há policies com TO public (inseguro)
PUBLIC_POLICIES=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND roles @> ARRAY['public']::name[];")

if [ "$PUBLIC_POLICIES" -eq 0 ]; then
    echo -e "${GREEN}✅ No policies with TO public (secure)${NC}"
else
    echo -e "${RED}❌ Found $PUBLIC_POLICIES policies with TO public (SECURITY RISK!)${NC}"
    psql "$DATABASE_URL" -c "SELECT schemaname, tablename, policyname, roles FROM pg_policies WHERE schemaname = 'public' AND roles @> ARRAY['public']::name[];"
    exit 1
fi

# =============================================================================
# 5. Verificar Triggers
# =============================================================================
echo "⚡ Checking triggers..."
TRIGGERS_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_trigger WHERE tgname LIKE 'update_%_updated_at';")

if [ "$TRIGGERS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ Triggers: $TRIGGERS_COUNT/4${NC}"
else
    echo -e "${RED}❌ Triggers: $TRIGGERS_COUNT/4 (expected 4)${NC}"
    psql "$DATABASE_URL" -c "SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE tgname LIKE 'update_%';"
    exit 1
fi

# =============================================================================
# 6. Testar Functions
# =============================================================================
echo "🧪 Testing functions..."

# Test current_tenant_id() (should return NULL if no session)
TENANT_ID=$(psql "$DATABASE_URL" -t -c "SELECT public.current_tenant_id();")
echo -e "${GREEN}✅ current_tenant_id() callable (returned: $TENANT_ID)${NC}"

# Test current_app_user_id() (should return NULL if no session)
USER_ID=$(psql "$DATABASE_URL" -t -c "SELECT public.current_app_user_id();")
echo -e "${GREEN}✅ current_app_user_id() callable (returned: $USER_ID)${NC}"

# =============================================================================
# 7. Verificar Constraints
# =============================================================================
echo "🔗 Checking constraints..."
FK_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;")

if [ "$FK_COUNT" -ge 10 ]; then
    echo -e "${GREEN}✅ Foreign keys: $FK_COUNT (expected ~10)${NC}"
else
    echo -e "${YELLOW}⚠️  Foreign keys: $FK_COUNT (expected ~10)${NC}"
fi

CHECK_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'c' AND connamespace = 'public'::regnamespace;")

if [ "$CHECK_COUNT" -ge 5 ]; then
    echo -e "${GREEN}✅ Check constraints: $CHECK_COUNT (expected ~5)${NC}"
else
    echo -e "${YELLOW}⚠️  Check constraints: $CHECK_COUNT (expected ~5)${NC}"
fi

# =============================================================================
# 8. Verificar Indexes
# =============================================================================
echo "📊 Checking indexes..."
INDEXES_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';")

if [ "$INDEXES_COUNT" -ge 20 ]; then
    echo -e "${GREEN}✅ Indexes: $INDEXES_COUNT (expected ~20+)${NC}"
else
    echo -e "${YELLOW}⚠️  Indexes: $INDEXES_COUNT (expected ~20+)${NC}"
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "========================================="
echo -e "${GREEN}✅ VALIDATION PASSED${NC}"
echo "========================================="
echo "Database is ready for use!"
echo ""
echo "Next steps:"
echo "  - Apply seed data (if dev): psql \$DATABASE_URL -f supabase/seed.sql"
echo "  - Test backend connection: pytest tests/integration/test_db.py"
echo "  - Verify RLS: Try connecting with anon key (should block access)"
echo ""
exit 0
