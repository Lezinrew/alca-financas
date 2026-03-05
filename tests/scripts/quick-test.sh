#!/bin/bash
# Quick API Test Script
# Usage: ./quick-test.sh [API_URL]

set -e

API_URL="${1:-http://localhost:8001/api}"
TIMESTAMP=$(date +%s)
TEST_EMAIL="qa-${TIMESTAMP}@example.com"

echo "🧪 ALCA FINANÇAS - QUICK API TEST"
echo "=================================="
echo "API URL: $API_URL"
echo "Test Email: $TEST_EMAIL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test endpoint
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local headers="$6"

    echo -n "Testing $name... "

    if [ "$method" == "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET "$API_URL$endpoint" -H "$headers" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -H "$headers" \
            -d "$data" 2>&1)
    fi

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" == "$expected_status" ]; then
        echo -e "${GREEN}✅ PASSED${NC} (HTTP $http_code)"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC} (Expected $expected_status, got $http_code)"
        echo "  Response: $body"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 1. Health Check
echo "📍 HEALTH CHECK"
test_endpoint "Health Check" "GET" "/health" "" "200" ""

# 2. Register
echo -e "\n📝 AUTHENTICATION TESTS"
REGISTER_DATA="{\"email\":\"$TEST_EMAIL\",\"password\":\"senha123\",\"name\":\"QA Tester\"}"
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_DATA")

if echo "$REGISTER_RESPONSE" | grep -q "access_token"; then
    echo -e "Register... ${GREEN}✅ PASSED${NC}"
    ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | jq -r '.access_token // empty')
    ((TESTS_PASSED++))
else
    echo -e "Register... ${RED}❌ FAILED${NC}"
    echo "  Response: $REGISTER_RESPONSE"
    ((TESTS_FAILED++))
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"

# 3. Get User Info
test_endpoint "Get /auth/me" "GET" "/auth/me" "" "200" "$AUTH_HEADER"

# 4. Login
LOGIN_DATA="{\"email\":\"$TEST_EMAIL\",\"password\":\"senha123\"}"
test_endpoint "Login" "POST" "/auth/login" "$LOGIN_DATA" "200" ""

# 5. Accounts
echo -e "\n💳 ACCOUNTS TESTS"
test_endpoint "List Accounts" "GET" "/accounts" "" "200" "$AUTH_HEADER"

ACCOUNT_DATA="{\"name\":\"Conta Teste\",\"type\":\"checking\",\"initial_balance\":1000.00,\"currency\":\"BRL\"}"
ACCOUNT_RESPONSE=$(curl -s -X POST "$API_URL/accounts" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$ACCOUNT_DATA")

if echo "$ACCOUNT_RESPONSE" | grep -q "id"; then
    echo -e "Create Account... ${GREEN}✅ PASSED${NC}"
    ACCOUNT_ID=$(echo "$ACCOUNT_RESPONSE" | jq -r '.id // empty')
    ((TESTS_PASSED++))
else
    echo -e "Create Account... ${RED}❌ FAILED${NC}"
    ((TESTS_FAILED++))
fi

# 6. Categories
echo -e "\n🏷️  CATEGORIES TESTS"
test_endpoint "List Categories" "GET" "/categories" "" "200" "$AUTH_HEADER"

CATEGORY_DATA="{\"name\":\"Alimentação\",\"type\":\"expense\",\"color\":\"#6366f1\",\"icon\":\"utensils\"}"
CATEGORY_RESPONSE=$(curl -s -X POST "$API_URL/categories" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$CATEGORY_DATA")

if echo "$CATEGORY_RESPONSE" | grep -q "id"; then
    echo -e "Create Category... ${GREEN}✅ PASSED${NC}"
    CATEGORY_ID=$(echo "$CATEGORY_RESPONSE" | jq -r '.id // empty')
    ((TESTS_PASSED++))
else
    echo -e "Create Category... ${RED}❌ FAILED${NC}"
    ((TESTS_FAILED++))
fi

# 7. Transactions
echo -e "\n💸 TRANSACTIONS TESTS"
test_endpoint "List Transactions" "GET" "/transactions" "" "200" "$AUTH_HEADER"

if [ -n "$CATEGORY_ID" ] && [ -n "$ACCOUNT_ID" ]; then
    TRANSACTION_DATA="{\"description\":\"Teste\",\"amount\":50.00,\"type\":\"expense\",\"category_id\":\"$CATEGORY_ID\",\"account_id\":\"$ACCOUNT_ID\",\"date\":\"2024-03-04\",\"status\":\"paid\"}"
    test_endpoint "Create Transaction" "POST" "/transactions" "$TRANSACTION_DATA" "201" "$AUTH_HEADER"
fi

# 8. Dashboard
echo -e "\n📊 DASHBOARD TESTS"
test_endpoint "Get Dashboard" "GET" "/dashboard" "" "200" "$AUTH_HEADER"
test_endpoint "Get Dashboard Advanced" "GET" "/dashboard-advanced" "" "200" "$AUTH_HEADER"

# 9. Reports
echo -e "\n📈 REPORTS TESTS"
test_endpoint "Get Reports Overview" "GET" "/reports/overview?type=expenses_by_category" "" "200" "$AUTH_HEADER"

# Summary
echo ""
echo "=================================="
echo "📊 TEST SUMMARY"
echo "=================================="
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
fi
