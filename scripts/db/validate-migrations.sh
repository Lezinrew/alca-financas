#!/usr/bin/env bash
# =============================================================================
# validate-migrations.sh
# Valida estado do banco após aplicar migrations
# =============================================================================
# IDEMPOTENTE: Pode rodar múltiplas vezes sem efeitos colaterais
# PORTÁVEL: bash/zsh, macOS/Linux
# SEGURO: Não expõe senhas/secrets nos logs
# =============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if command exists
require_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ Required command not found: $1${NC}" >&2
        echo "Please install $1 and try again." >&2
        exit 1
    fi
}

# Execute psql query silently and reliably
# Assumes connection was already tested
psqlq() {
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -qAt -c "$1" 2>&1
}

# Trim whitespace from string
trim() {
    local var="$*"
    # Remove leading whitespace
    var="${var#"${var%%[![:space:]]*}"}"
    # Remove trailing whitespace
    var="${var%"${var##*[![:space:]]}"}"
    echo -n "$var"
}

# Sanitize database URL (remove user/pass)
sanitize_url() {
    local url="$1"
    # Replace user:pass@ with ***:***@
    echo "$url" | sed -E 's|(postgresql://[^:]*):([^@]*)@|\1:***@|'
}

# =============================================================================
# CONFIGURATION
# =============================================================================

# Check dependencies
require_cmd psql

# Database URL (priority order: $1, DATABASE_URL, SUPABASE_DB_URL, SUPABASE_STAGING_DB_URL)
DATABASE_URL="${1:-${DATABASE_URL:-${SUPABASE_DB_URL:-${SUPABASE_STAGING_DB_URL:-}}}}"

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL not set${NC}" >&2
    echo "" >&2
    echo "Usage: $0 [DATABASE_URL]" >&2
    echo "   or: export DATABASE_URL=postgresql://..." >&2
    echo "   or: export SUPABASE_DB_URL=postgresql://..." >&2
    echo "   or: export SUPABASE_STAGING_DB_URL=postgresql://..." >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  $0 'postgresql://user:pass@host:5432/db'" >&2
    echo "  DATABASE_URL='postgresql://...' $0" >&2
    exit 1
fi

# Sanitize URL for display
SAFE_URL=$(sanitize_url "$DATABASE_URL")

echo "🔍 Validating migrations against: ${SAFE_URL}"
echo ""

# =============================================================================
# CONNECTION TEST
# =============================================================================
echo "🔌 Testing database connection..."
if ! psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -qAt -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${RED}❌ Database connection failed${NC}" >&2
    echo "" >&2
    echo "Could not connect to: ${SAFE_URL}" >&2
    echo "" >&2
    echo "Possible causes:" >&2
    echo "  - Invalid credentials" >&2
    echo "  - Host unreachable" >&2
    echo "  - Database does not exist" >&2
    echo "  - Firewall blocking connection" >&2
    echo "" >&2
    exit 1
fi
echo -e "${GREEN}✅ Connection successful${NC}"
echo ""

# =============================================================================
# VALIDATION TRACKING
# =============================================================================

FAILED=0

check_failed() {
    FAILED=1
}

# =============================================================================
# 1. Verificar Tabelas
# =============================================================================
echo "📋 Checking tables..."
TABLES_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")")

if [ "$TABLES_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ Tables:      $TABLES_COUNT/7${NC}"
else
    echo -e "${RED}❌ Tables:      $TABLES_COUNT/7 (expected 7)${NC}"
    psql "$DATABASE_URL" -c "\dt public.*" || true
    check_failed
fi

# =============================================================================
# 2. Verificar Functions
# =============================================================================
echo "🔧 Checking functions..."
FUNCTIONS_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public' AND p.proname IN ('current_app_user_id', 'current_tenant_id', 'dev_seed_account', 'update_updated_at_column');")")

if [ "$FUNCTIONS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ Functions:   $FUNCTIONS_COUNT/4${NC}"
else
    echo -e "${RED}❌ Functions:   $FUNCTIONS_COUNT/4 (expected 4)${NC}"
    psql "$DATABASE_URL" -c "\df public.*" || true
    check_failed
fi

# =============================================================================
# 3. Verificar RLS Ativo
# =============================================================================
echo "🔐 Checking RLS..."
RLS_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true;")")

if [ "$RLS_COUNT" -eq 7 ]; then
    echo -e "${GREEN}✅ RLS enabled: $RLS_COUNT/7 tables${NC}"
else
    echo -e "${RED}❌ RLS enabled: $RLS_COUNT/7 (expected 7)${NC}"
    psql "$DATABASE_URL" -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';" || true
    check_failed
fi

# =============================================================================
# 4. Verificar Policies
# =============================================================================
echo "🛡️  Checking policies..."
POLICIES_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public';")")

if [ "$POLICIES_COUNT" -ge 14 ]; then
    echo -e "${GREEN}✅ Policies:    $POLICIES_COUNT (expected ~14)${NC}"
else
    echo -e "${YELLOW}⚠️  Policies:    $POLICIES_COUNT (expected ~14)${NC}"
fi

# Verificar se há policies com TO public (inseguro)
PUBLIC_POLICIES=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND roles @> ARRAY['public']::name[];")")

if [ "$PUBLIC_POLICIES" -eq 0 ]; then
    echo -e "${GREEN}✅ No policies with TO public (secure)${NC}"
else
    echo -e "${RED}❌ Found $PUBLIC_POLICIES policies with TO public (SECURITY RISK!)${NC}"
    psql "$DATABASE_URL" -c "SELECT schemaname, tablename, policyname, roles FROM pg_policies WHERE schemaname = 'public' AND roles @> ARRAY['public']::name[];" || true
    check_failed
fi

# =============================================================================
# 5. Verificar Triggers
# =============================================================================
echo "⚡ Checking triggers..."
TRIGGERS_COUNT=$(trim "$(psqlq "
    SELECT COUNT(*)
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE t.tgname LIKE 'update_%_updated_at'
    AND n.nspname = 'public'
    AND NOT t.tgisinternal;
")")

if [ "$TRIGGERS_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✅ Triggers:    $TRIGGERS_COUNT/4${NC}"
else
    echo -e "${RED}❌ Triggers:    $TRIGGERS_COUNT/4 (expected 4)${NC}"
    psql "$DATABASE_URL" -c "
        SELECT t.tgname, c.relnamespace::regnamespace || '.' || c.relname AS table_name
        FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE t.tgname LIKE 'update_%_updated_at'
        AND n.nspname = 'public'
        AND NOT t.tgisinternal
        ORDER BY table_name;
    " || true
    check_failed
fi

# =============================================================================
# 6. Testar Functions
# =============================================================================
echo "🧪 Testing functions..."

# Test current_tenant_id() (should return NULL if no session)
TENANT_ID=$(trim "$(psqlq "SELECT public.current_tenant_id();")" || echo "ERROR")
if [ "$TENANT_ID" != "ERROR" ]; then
    echo -e "${GREEN}✅ current_tenant_id() callable (returned: $TENANT_ID)${NC}"
else
    echo -e "${RED}❌ current_tenant_id() failed${NC}"
    check_failed
fi

# Test current_app_user_id() (should return NULL if no session)
USER_ID=$(trim "$(psqlq "SELECT public.current_app_user_id();")" || echo "ERROR")
if [ "$USER_ID" != "ERROR" ]; then
    echo -e "${GREEN}✅ current_app_user_id() callable (returned: $USER_ID)${NC}"
else
    echo -e "${RED}❌ current_app_user_id() failed${NC}"
    check_failed
fi

# =============================================================================
# 7. Verificar Constraints
# =============================================================================
echo "🔗 Checking constraints..."
FK_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;")")

if [ "$FK_COUNT" -ge 10 ]; then
    echo -e "${GREEN}✅ Foreign keys: $FK_COUNT (expected ~10)${NC}"
else
    echo -e "${YELLOW}⚠️  Foreign keys: $FK_COUNT (expected ~10)${NC}"
fi

CHECK_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'c' AND connamespace = 'public'::regnamespace;")")

if [ "$CHECK_COUNT" -ge 5 ]; then
    echo -e "${GREEN}✅ Check constraints: $CHECK_COUNT (expected ~5)${NC}"
else
    echo -e "${YELLOW}⚠️  Check constraints: $CHECK_COUNT (expected ~5)${NC}"
fi

# =============================================================================
# 8. Verificar Indexes
# =============================================================================
echo "📊 Checking indexes..."
INDEXES_COUNT=$(trim "$(psqlq "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';")")

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
if [ "$FAILED" -eq 0 ]; then
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
else
    echo -e "${RED}❌ VALIDATION FAILED${NC}"
    echo "========================================="
    echo "Some checks failed. Review the errors above."
    echo ""
    exit 1
fi
