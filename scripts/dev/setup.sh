#!/usr/bin/env bash
# ================================
# DEV SETUP - Alça Finanças
# ================================
# Installs dependencies and prepares the development environment

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
MOBILE_DIR="$REPO_DIR/mobile"

echo -e "${BLUE}🔧 Alça Finanças - Development Setup${NC}"
echo ""

# ================================
# Check Required Tools
# ================================
echo -e "${BLUE}==> Checking required tools...${NC}"

check_tool() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo -e "${RED}❌ $1 not found${NC}"
        echo -e "${YELLOW}   Install it from: $2${NC}"
        return 1
    else
        echo -e "${GREEN}✅ $1 found${NC}"
        return 0
    fi
}

ALL_TOOLS_OK=true

check_tool "python3" "https://www.python.org/downloads/" || ALL_TOOLS_OK=false
check_tool "pip3" "https://pip.pypa.io/en/stable/installation/" || ALL_TOOLS_OK=false
check_tool "node" "https://nodejs.org/" || ALL_TOOLS_OK=false
check_tool "npm" "https://www.npmjs.com/" || ALL_TOOLS_OK=false

if [ "$ALL_TOOLS_OK" = false ]; then
    echo ""
    echo -e "${RED}❌ Missing required tools. Please install them and try again.${NC}"
    exit 1
fi

echo ""

# ================================
# Check Environment File
# ================================
echo -e "${BLUE}==> Checking environment configuration...${NC}"

if [ ! -f "$REPO_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo -e "${YELLOW}   Creating from .env.example...${NC}"
    if [ -f "$REPO_DIR/.env.example" ]; then
        cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
        echo -e "${GREEN}✅ Created .env file${NC}"
        echo -e "${YELLOW}   ⚠️  IMPORTANT: Edit .env with your Supabase credentials!${NC}"
        echo -e "${YELLOW}   Required variables:${NC}"
        echo -e "      - SUPABASE_URL"
        echo -e "      - SUPABASE_ANON_KEY"
        echo -e "      - SUPABASE_SERVICE_ROLE_KEY"
        echo ""
        read -p "Press ENTER after updating .env, or CTRL+C to exit..."
    else
        echo -e "${RED}❌ .env.example not found. Cannot create .env${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env file found${NC}"
fi

echo ""

# ================================
# Backend Setup
# ================================
echo -e "${BLUE}==> Setting up backend (Python)...${NC}"

cd "$BACKEND_DIR"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv .venv
    echo -e "  ${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "  ${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate and install dependencies
echo "  Installing Python dependencies..."
source .venv/bin/activate
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Verify critical dependencies
echo "  Verifying critical dependencies..."
python -c "import flask, supabase, bcrypt, jwt" 2>/dev/null || {
    echo -e "  ${RED}❌ Failed to import critical dependencies${NC}"
    exit 1
}

echo -e "  ${GREEN}✅ Backend setup complete${NC}"
echo ""

# ================================
# Frontend Setup
# ================================
echo -e "${BLUE}==> Setting up frontend (Node.js)...${NC}"

cd "$FRONTEND_DIR"

if [ -f "package-lock.json" ]; then
    echo "  Installing frontend dependencies (npm ci)..."
    npm ci --silent
else
    echo "  Installing frontend dependencies (npm install)..."
    npm install --silent
fi

echo -e "  ${GREEN}✅ Frontend setup complete${NC}"
echo ""

# ================================
# Mobile Setup (Optional)
# ================================
if [ -d "$MOBILE_DIR" ] && [ -f "$MOBILE_DIR/package.json" ]; then
    echo -e "${BLUE}==> Setting up mobile (Expo)...${NC}"

    read -p "Do you want to install mobile dependencies? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$MOBILE_DIR"
        if [ -f "package-lock.json" ]; then
            npm ci --silent
        else
            npm install --silent
        fi
        echo -e "  ${GREEN}✅ Mobile setup complete${NC}"
    else
        echo -e "  ${YELLOW}⏭️  Skipped mobile setup${NC}"
    fi
    echo ""
fi

# ================================
# Final Checks
# ================================
echo -e "${BLUE}==> Running final checks...${NC}"

# Check if .env has required Supabase variables
cd "$REPO_DIR"
set +u  # Temporarily allow undefined variables
if [ -f ".env" ]; then
    source .env
    if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
        echo -e "${YELLOW}⚠️  Supabase variables not configured in .env${NC}"
        echo -e "${YELLOW}   The application may not start without them.${NC}"
        echo -e "${YELLOW}   See: docs/ENVIRONMENTS.md${NC}"
    else
        echo -e "${GREEN}✅ Supabase variables configured${NC}"
    fi
fi
set -u

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo -e "   1. Ensure .env is configured with Supabase credentials"
echo -e "   2. Start the development environment:"
echo -e "      ${YELLOW}./scripts/dev/up.sh${NC}"
echo -e "   3. Check application health:"
echo -e "      ${YELLOW}./scripts/dev/doctor.sh${NC}"
echo ""
echo -e "${BLUE}📚 Documentation:${NC}"
echo -e "   Environment guide: ${YELLOW}docs/ENVIRONMENTS.md${NC}"
echo -e "   README:            ${YELLOW}README.md${NC}"
echo ""
