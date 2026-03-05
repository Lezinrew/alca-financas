#!/bin/bash
# Automated Test Runner - Manages backend lifecycle and runs all tests
# Usage: ./run-all-tests.sh [quick|full|performance|all]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
TESTS_DIR="$PROJECT_ROOT/tests"
BACKEND_PID_FILE="/tmp/alca-backend-test.pid"
BACKEND_LOG_FILE="/tmp/alca-backend-test.log"
API_URL="http://localhost:8001/api"
WAIT_TIMEOUT=30

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         ALCA FINANÇAS - AUTOMATED TEST SUITE             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to cleanup
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"

    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo "Stopping backend (PID: $BACKEND_PID)..."
            kill "$BACKEND_PID" 2>/dev/null || true
            sleep 2
            # Force kill if still running
            kill -9 "$BACKEND_PID" 2>/dev/null || true
        fi
        rm -f "$BACKEND_PID_FILE"
    fi

    # Kill any python process on port 8001
    lsof -ti:8001 | xargs kill -9 2>/dev/null || true

    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Setup trap to cleanup on exit
trap cleanup EXIT INT TERM

# Function to check if backend is running
check_backend() {
    curl -s -f "$API_URL/health" > /dev/null 2>&1
    return $?
}

# Function to wait for backend
wait_for_backend() {
    echo -e "${YELLOW}⏳ Waiting for backend to be ready...${NC}"
    local count=0
    while [ $count -lt $WAIT_TIMEOUT ]; do
        if check_backend; then
            echo -e "${GREEN}✅ Backend is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        ((count++))
    done
    echo -e "\n${RED}❌ Backend failed to start within ${WAIT_TIMEOUT}s${NC}"
    echo -e "${YELLOW}📋 Backend logs:${NC}"
    tail -20 "$BACKEND_LOG_FILE"
    return 1
}

# Function to start backend
start_backend() {
    echo -e "${BLUE}🚀 Starting backend...${NC}"

    # Check if already running
    if check_backend; then
        echo -e "${YELLOW}⚠️  Backend already running on port 8001${NC}"
        read -p "Kill existing backend and restart? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            lsof -ti:8001 | xargs kill -9 2>/dev/null || true
            sleep 2
        else
            echo -e "${GREEN}✅ Using existing backend${NC}"
            return 0
        fi
    fi

    # Find Python executable
    PYTHON_CMD=""
    if [ -f "$BACKEND_DIR/.venv/bin/python" ]; then
        PYTHON_CMD="$BACKEND_DIR/.venv/bin/python"
        echo "Using venv Python: $PYTHON_CMD"
    elif [ -f "$BACKEND_DIR/venv/bin/python" ]; then
        PYTHON_CMD="$BACKEND_DIR/venv/bin/python"
        echo "Using venv Python: $PYTHON_CMD"
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        echo "Using system Python: $PYTHON_CMD"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
        echo "Using system Python: $PYTHON_CMD"
    else
        echo -e "${RED}❌ Python not found!${NC}"
        exit 1
    fi

    # Check if requirements are installed
    echo "Checking dependencies..."
    if ! $PYTHON_CMD -c "import flask" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Flask not installed. Installing dependencies...${NC}"
        cd "$BACKEND_DIR"
        $PYTHON_CMD -m pip install -q -r requirements.txt || {
            echo -e "${RED}❌ Failed to install dependencies${NC}"
            exit 1
        }
    fi

    # Start backend
    echo "Starting backend server..."
    cd "$BACKEND_DIR"
    nohup $PYTHON_CMD app.py > "$BACKEND_LOG_FILE" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    echo "Backend PID: $BACKEND_PID"

    # Wait for backend to be ready
    if ! wait_for_backend; then
        echo -e "${RED}❌ Failed to start backend${NC}"
        exit 1
    fi
}

# Function to run quick tests
run_quick_tests() {
    echo -e "\n${BLUE}⚡ Running Quick Tests...${NC}"
    cd "$PROJECT_ROOT"
    if [ -x "$TESTS_DIR/scripts/quick-test.sh" ]; then
        "$TESTS_DIR/scripts/quick-test.sh" "$API_URL"
        return $?
    else
        echo -e "${RED}❌ quick-test.sh not found or not executable${NC}"
        return 1
    fi
}

# Function to run full tests
run_full_tests() {
    echo -e "\n${BLUE}🧪 Running Full Test Suite...${NC}"
    cd "$PROJECT_ROOT"

    # Check if Python is available
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}❌ Python not found!${NC}"
        return 1
    fi

    # Check if requests is installed
    if ! $PYTHON_CMD -c "import requests" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  'requests' module not installed. Installing...${NC}"
        $PYTHON_CMD -m pip install -q requests || {
            echo -e "${RED}❌ Failed to install requests${NC}"
            return 1
        }
    fi

    if [ -x "$TESTS_DIR/scripts/full-test.py" ]; then
        $PYTHON_CMD "$TESTS_DIR/scripts/full-test.py" "$API_URL"
        return $?
    else
        echo -e "${RED}❌ full-test.py not found or not executable${NC}"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    echo -e "\n${BLUE}📈 Running Performance Tests...${NC}"

    # Check if k6 is installed
    if ! command -v k6 &> /dev/null; then
        echo -e "${RED}❌ k6 is not installed${NC}"
        echo -e "${YELLOW}Install k6:${NC}"
        echo "  macOS: brew install k6"
        echo "  Linux: https://k6.io/docs/getting-started/installation/"
        return 1
    fi

    cd "$TESTS_DIR/performance"
    if [ -f "load-test.js" ]; then
        API_URL="$API_URL" k6 run load-test.js
        return $?
    else
        echo -e "${RED}❌ load-test.js not found${NC}"
        return 1
    fi
}

# Main execution
TEST_TYPE="${1:-quick}"

echo "Project Root: $PROJECT_ROOT"
echo "Backend Dir: $BACKEND_DIR"
echo "Tests Dir: $TESTS_DIR"
echo "API URL: $API_URL"
echo ""

# Start backend
start_backend

# Run tests based on argument
case "$TEST_TYPE" in
    quick)
        run_quick_tests
        TEST_EXIT_CODE=$?
        ;;
    full)
        run_full_tests
        TEST_EXIT_CODE=$?
        ;;
    performance|perf)
        run_performance_tests
        TEST_EXIT_CODE=$?
        ;;
    all)
        echo -e "${BLUE}🎯 Running ALL test suites...${NC}"

        run_quick_tests
        QUICK_EXIT=$?

        run_full_tests
        FULL_EXIT=$?

        run_performance_tests
        PERF_EXIT=$?

        # Summary
        echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║                    FINAL SUMMARY                          ║${NC}"
        echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

        if [ $QUICK_EXIT -eq 0 ]; then
            echo -e "Quick Tests:       ${GREEN}✅ PASSED${NC}"
        else
            echo -e "Quick Tests:       ${RED}❌ FAILED${NC}"
        fi

        if [ $FULL_EXIT -eq 0 ]; then
            echo -e "Full Tests:        ${GREEN}✅ PASSED${NC}"
        else
            echo -e "Full Tests:        ${RED}❌ FAILED${NC}"
        fi

        if [ $PERF_EXIT -eq 0 ]; then
            echo -e "Performance Tests: ${GREEN}✅ PASSED${NC}"
        else
            echo -e "Performance Tests: ${YELLOW}⚠️  SKIPPED/FAILED${NC}"
        fi

        # Set exit code (fail if any test failed)
        TEST_EXIT_CODE=$((QUICK_EXIT + FULL_EXIT + PERF_EXIT))
        ;;
    *)
        echo -e "${RED}❌ Invalid test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [quick|full|performance|all]"
        echo ""
        echo "Options:"
        echo "  quick       - Fast smoke tests (~30s)"
        echo "  full        - Complete integration tests (~2-3min)"
        echo "  performance - Load tests with k6 (~5min)"
        echo "  all         - Run all test suites"
        exit 1
        ;;
esac

# Cleanup is handled by trap
echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${BLUE}║${GREEN}                 🎉 ALL TESTS PASSED! 🎉                   ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${RED}                  ❌ SOME TESTS FAILED                     ${BLUE}║${NC}"
fi
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

exit $TEST_EXIT_CODE
