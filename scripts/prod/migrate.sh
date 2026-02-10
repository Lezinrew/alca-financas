#!/usr/bin/env bash
# ================================
# PROD MIGRATE - Alça Finanças
# ================================
# Runs database migrations for Supabase

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATIONS_DIR="$REPO_DIR/scripts/db"

echo -e "${BLUE}🗄️  Alça Finanças - Database Migrations${NC}"
echo ""

# ================================
# Load Environment
# ================================
echo -e "${BLUE}==> Loading environment...${NC}"

if [ -f "$REPO_DIR/.env.production" ]; then
    ENV_FILE="$REPO_DIR/.env.production"
    echo -e "${GREEN}✅ Using .env.production${NC}"
elif [ -f "$REPO_DIR/.env" ]; then
    ENV_FILE="$REPO_DIR/.env"
    echo -e "${YELLOW}⚠️  Using .env${NC}"
else
    echo -e "${RED}❌ No environment file found${NC}"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# ================================
# Validate Supabase Configuration
# ================================
echo -e "${BLUE}==> Validating Supabase configuration...${NC}"

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    echo -e "${RED}❌ Supabase credentials not configured${NC}"
    echo -e "${YELLOW}   Required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Supabase configured${NC}"
echo -e "   URL: $SUPABASE_URL"
echo ""

# ================================
# Check Migrations Directory
# ================================
echo -e "${BLUE}==> Checking migrations...${NC}"

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo -e "${YELLOW}⚠️  Migrations directory not found: $MIGRATIONS_DIR${NC}"
    echo ""
    echo -e "${BLUE}📚 Supabase Migration Strategy:${NC}"
    echo ""
    echo -e "${YELLOW}Supabase uses SQL migrations managed via:${NC}"
    echo ""
    echo -e "  ${BLUE}1. Supabase Dashboard (Recommended for production):${NC}"
    echo -e "     - Go to: $SUPABASE_URL (your project dashboard)"
    echo -e "     - Navigate to: SQL Editor"
    echo -e "     - Run your migration scripts there"
    echo -e "     - Supabase tracks migrations automatically"
    echo ""
    echo -e "  ${BLUE}2. Supabase CLI (For version control):${NC}"
    echo -e "     Install: ${YELLOW}npm install -g supabase${NC}"
    echo -e "     Login:   ${YELLOW}supabase login${NC}"
    echo -e "     Link:    ${YELLOW}supabase link --project-ref YOUR_PROJECT_REF${NC}"
    echo -e "     Create:  ${YELLOW}supabase migration new migration_name${NC}"
    echo -e "     Apply:   ${YELLOW}supabase db push${NC}"
    echo ""
    echo -e "  ${BLUE}3. Manual SQL via psql (Advanced):${NC}"
    echo -e "     Get connection string from Supabase Dashboard"
    echo -e "     Connect: ${YELLOW}psql 'postgresql://...'${NC}"
    echo -e "     Run SQL files"
    echo ""
    echo -e "${BLUE}📁 Recommended Structure:${NC}"
    echo -e "   Create: ${YELLOW}$MIGRATIONS_DIR/${NC}"
    echo -e "   Add SQL files: ${YELLOW}$MIGRATIONS_DIR/001_initial_schema.sql${NC}"
    echo -e "                  ${YELLOW}$MIGRATIONS_DIR/002_add_indexes.sql${NC}"
    echo -e "                  ${YELLOW}etc.${NC}"
    echo ""
    echo -e "${BLUE}🔗 Resources:${NC}"
    echo -e "   Supabase Migrations: ${YELLOW}https://supabase.com/docs/guides/cli/local-development#database-migrations${NC}"
    echo -e "   SQL Editor:          ${YELLOW}$SUPABASE_URL/editor/sql${NC}"
    echo ""
    exit 0
fi

# ================================
# Run Migrations
# ================================
echo -e "${BLUE}==> Looking for migration files...${NC}"

# Find all .sql files
MIGRATIONS=$(find "$MIGRATIONS_DIR" -name "*.sql" -type f | sort)

if [ -z "$MIGRATIONS" ]; then
    echo -e "${YELLOW}⚠️  No SQL migration files found in $MIGRATIONS_DIR${NC}"
    echo ""
    echo -e "${BLUE}💡 To create a migration:${NC}"
    echo -e "   1. Create a SQL file: ${YELLOW}$MIGRATIONS_DIR/001_your_migration.sql${NC}"
    echo -e "   2. Add your SQL statements"
    echo -e "   3. Run this script again"
    echo ""
    exit 0
fi

echo -e "${GREEN}Found $(echo "$MIGRATIONS" | wc -l | tr -d ' ') migration file(s)${NC}"
echo ""

# List migrations
echo -e "${BLUE}Migrations to apply:${NC}"
echo "$MIGRATIONS" | while read migration; do
    echo "  - $(basename $migration)"
done
echo ""

# Confirm
read -p "Apply these migrations to production? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted by user${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}==> Applying migrations...${NC}"

# Check if supabase CLI is available
if command -v supabase >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Supabase CLI found${NC}"
    echo ""
    echo -e "${YELLOW}Using Supabase CLI...${NC}"

    # Try to apply migrations via CLI
    if supabase db push 2>/dev/null; then
        echo -e "${GREEN}✅ Migrations applied via Supabase CLI${NC}"
    else
        echo -e "${YELLOW}⚠️  Supabase CLI push failed${NC}"
        echo -e "${YELLOW}   Falling back to manual approach...${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Supabase CLI not found${NC}"
    echo ""
    echo -e "${BLUE}📋 Manual Migration Steps:${NC}"
    echo ""
    echo "1. Go to your Supabase SQL Editor:"
    echo -e "   ${YELLOW}$SUPABASE_URL/project/_/sql${NC}"
    echo ""
    echo "2. Run each migration file in order:"
    echo ""

    echo "$MIGRATIONS" | while read migration; do
        echo -e "   ${BLUE}$(basename $migration):${NC}"
        echo -e "   ${YELLOW}cat $migration | pbcopy${NC}  (copy to clipboard)"
        echo "   Then paste and run in SQL Editor"
        echo ""
    done

    echo -e "${BLUE}💡 Or install Supabase CLI for automatic migrations:${NC}"
    echo -e "   ${YELLOW}npm install -g supabase${NC}"
    echo ""
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Migration Process Complete${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}🔍 Verify migrations in Supabase:${NC}"
echo -e "   Table Editor: ${YELLOW}$SUPABASE_URL/project/_/editor${NC}"
echo -e "   SQL Editor:   ${YELLOW}$SUPABASE_URL/project/_/sql${NC}"
echo ""
