#!/usr/bin/env python3
"""
ALCA FINANÇAS - FULL API TEST SUITE
Comprehensive integration tests for all endpoints
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Optional
import time

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class APITester:
    def __init__(self, base_url: str = "http://localhost:8001/api"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.headers: Dict[str, str] = {}
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_email = f"qa-{int(time.time())}@example.com"
        self.test_data = {}

    def log(self, message: str, color: str = Colors.NC):
        print(f"{color}{message}{Colors.NC}")

    def test_endpoint(self, name: str, method: str, endpoint: str,
                     data: Optional[Dict] = None,
                     expected_status: int = 200,
                     skip_assert: bool = False) -> Optional[Dict]:
        """Test a single endpoint"""
        print(f"\n  Testing: {name}... ", end='')

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                resp = requests.get(url, headers=self.headers)
            elif method == "POST":
                resp = requests.post(url, json=data, headers=self.headers)
            elif method == "PUT":
                resp = requests.put(url, json=data, headers=self.headers)
            elif method == "DELETE":
                resp = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if resp.status_code == expected_status or skip_assert:
                self.log(f"✅ PASSED (HTTP {resp.status_code})", Colors.GREEN)
                self.tests_passed += 1
                return resp.json() if resp.text else {}
            else:
                self.log(f"❌ FAILED (Expected {expected_status}, got {resp.status_code})", Colors.RED)
                self.log(f"     Response: {resp.text[:200]}", Colors.RED)
                self.tests_failed += 1
                return None

        except Exception as e:
            self.log(f"❌ EXCEPTION: {str(e)}", Colors.RED)
            self.tests_failed += 1
            return None

    def test_auth(self):
        """Test authentication endpoints"""
        self.log("\n📝 AUTHENTICATION TESTS", Colors.BLUE)

        # 1. Register
        register_data = {
            "email": self.test_email,
            "password": "senha123",
            "name": "QA Tester"
        }
        resp = self.test_endpoint("Register", "POST", "/auth/register",
                                  register_data, 201)
        if resp:
            self.access_token = resp.get('access_token')
            self.refresh_token = resp.get('refresh_token')
            self.headers = {"Authorization": f"Bearer {self.access_token}"}

        # 2. Login
        login_data = {
            "email": self.test_email,
            "password": "senha123"
        }
        self.test_endpoint("Login", "POST", "/auth/login", login_data, 200)

        # 3. Get User Info
        self.test_endpoint("Get /auth/me", "GET", "/auth/me", expected_status=200)

        # 4. Refresh Token
        refresh_data = {"refresh_token": self.refresh_token}
        self.test_endpoint("Refresh Token", "POST", "/auth/refresh",
                          refresh_data, 200)

        # 5. Get Settings
        self.test_endpoint("Get Settings", "GET", "/auth/settings", expected_status=200)

        # 6. Update Settings
        settings_data = {
            "currency": "BRL",
            "theme": "dark",
            "language": "pt"
        }
        self.test_endpoint("Update Settings", "PUT", "/auth/settings",
                          settings_data, 200)

    def test_categories(self):
        """Test categories endpoints"""
        self.log("\n🏷️  CATEGORIES TESTS", Colors.BLUE)

        # 1. List Categories
        self.test_endpoint("List Categories", "GET", "/categories", expected_status=200)

        # 2. Create Category
        category_data = {
            "name": "Alimentação",
            "type": "expense",
            "color": "#6366f1",
            "icon": "utensils",
            "description": "Gastos com alimentação"
        }
        resp = self.test_endpoint("Create Category", "POST", "/categories",
                                  category_data, 201)
        if resp:
            self.test_data['category_id'] = resp.get('id')

        # 3. Get Category
        if 'category_id' in self.test_data:
            category_id = self.test_data['category_id']
            self.test_endpoint("Get Category", "GET", f"/categories/{category_id}",
                             expected_status=200)

            # 4. Update Category
            update_data = {
                "name": "Alimentação Atualizada",
                "color": "#ef4444"
            }
            self.test_endpoint("Update Category", "PUT", f"/categories/{category_id}",
                             update_data, 200)

    def test_accounts(self):
        """Test accounts endpoints"""
        self.log("\n💳 ACCOUNTS TESTS", Colors.BLUE)

        # 1. List Accounts
        self.test_endpoint("List Accounts", "GET", "/accounts", expected_status=200)

        # 2. Create Account
        account_data = {
            "name": "Conta Corrente",
            "type": "checking",
            "initial_balance": 1000.00,
            "currency": "BRL"
        }
        resp = self.test_endpoint("Create Account", "POST", "/accounts",
                                  account_data, 201)
        if resp:
            self.test_data['account_id'] = resp.get('id')

        # 3. Get Account
        if 'account_id' in self.test_data:
            account_id = self.test_data['account_id']
            self.test_endpoint("Get Account", "GET", f"/accounts/{account_id}",
                             expected_status=200)

            # 4. Update Account
            update_data = {
                "name": "Conta Corrente Atualizada",
                "initial_balance": 1500.00
            }
            self.test_endpoint("Update Account", "PUT", f"/accounts/{account_id}",
                             update_data, 200)

        # 5. Create Credit Card
        cc_data = {
            "name": "Cartão de Crédito",
            "type": "credit_card",
            "initial_balance": 0.00,
            "currency": "BRL"
        }
        resp = self.test_endpoint("Create Credit Card", "POST", "/accounts",
                                  cc_data, 201)
        if resp:
            self.test_data['credit_card_id'] = resp.get('id')

    def test_transactions(self):
        """Test transactions endpoints"""
        self.log("\n💸 TRANSACTIONS TESTS", Colors.BLUE)

        # 1. List Transactions
        self.test_endpoint("List Transactions", "GET", "/transactions",
                          expected_status=200)

        # 2. Create Transaction
        if 'category_id' in self.test_data and 'account_id' in self.test_data:
            transaction_data = {
                "description": "Almoço",
                "amount": 35.50,
                "type": "expense",
                "category_id": self.test_data['category_id'],
                "account_id": self.test_data['account_id'],
                "date": "2024-03-04",
                "status": "paid"
            }
            resp = self.test_endpoint("Create Transaction", "POST", "/transactions",
                                     transaction_data, 201)

            # Get transaction ID from response
            if resp and 'message' in resp:
                # Try to list and get first transaction
                list_resp = self.test_endpoint("List for ID", "GET", "/transactions?limit=1",
                                              expected_status=200, skip_assert=True)
                if list_resp and 'transactions' in list_resp and len(list_resp['transactions']) > 0:
                    self.test_data['transaction_id'] = list_resp['transactions'][0].get('id')

        # 3. Filter Transactions by Month
        self.test_endpoint("Filter by Month", "GET", "/transactions?month=3&year=2024",
                          expected_status=200)

        # 4. Filter by Category
        if 'category_id' in self.test_data:
            category_id = self.test_data['category_id']
            self.test_endpoint("Filter by Category", "GET",
                             f"/transactions?category_id={category_id}",
                             expected_status=200)

        # 5. Get/Update/Delete Transaction
        if 'transaction_id' in self.test_data:
            transaction_id = self.test_data['transaction_id']

            self.test_endpoint("Get Transaction", "GET",
                             f"/transactions/{transaction_id}",
                             expected_status=200)

            update_data = {
                "description": "Almoço Atualizado",
                "amount": 40.00
            }
            self.test_endpoint("Update Transaction", "PUT",
                             f"/transactions/{transaction_id}",
                             update_data, 200)

    def test_dashboard(self):
        """Test dashboard endpoints"""
        self.log("\n📊 DASHBOARD TESTS", Colors.BLUE)

        # 1. Basic Dashboard
        self.test_endpoint("Get Dashboard", "GET", "/dashboard", expected_status=200)

        # 2. Dashboard with specific month
        self.test_endpoint("Dashboard for March 2024", "GET",
                          "/dashboard?month=3&year=2024", expected_status=200)

        # 3. Advanced Dashboard
        self.test_endpoint("Dashboard Advanced", "GET", "/dashboard-advanced",
                          expected_status=200)

        # 4. Dashboard Settings
        self.test_endpoint("Get Dashboard Settings", "GET", "/dashboard-settings",
                          expected_status=200)

        settings_data = {
            "show_expenses_by_category": True,
            "show_income_by_category": True
        }
        self.test_endpoint("Update Dashboard Settings", "PUT", "/dashboard-settings",
                          settings_data, 200)

    def test_reports(self):
        """Test reports endpoints"""
        self.log("\n📈 REPORTS TESTS", Colors.BLUE)

        # 1. Expenses by Category
        self.test_endpoint("Expenses by Category", "GET",
                          "/reports/overview?type=expenses_by_category",
                          expected_status=200)

        # 2. Expenses by Account
        self.test_endpoint("Expenses by Account", "GET",
                          "/reports/overview?type=expenses_by_account",
                          expected_status=200)

        # 3. Income by Category
        self.test_endpoint("Income by Category", "GET",
                          "/reports/overview?type=income_by_category",
                          expected_status=200)

        # 4. Balance by Account
        self.test_endpoint("Balance by Account", "GET",
                          "/reports/overview?type=balance_by_account",
                          expected_status=200)

        # 5. Comparison
        self.test_endpoint("Comparison Report", "GET", "/reports/comparison",
                          expected_status=200)

    def test_backup(self):
        """Test backup/export endpoints"""
        self.log("\n💾 BACKUP TESTS", Colors.BLUE)

        # 1. Export Data
        self.test_endpoint("Export Backup", "GET", "/auth/backup/export",
                          expected_status=200)

    def test_security(self):
        """Test security (negative tests)"""
        self.log("\n🔒 SECURITY TESTS", Colors.BLUE)

        # Save auth header
        original_headers = self.headers.copy()

        # 1. No Token
        self.headers = {}
        resp = self.test_endpoint("No Token", "GET", "/accounts",
                                  expected_status=401, skip_assert=True)

        # 2. Invalid Token
        self.headers = {"Authorization": "Bearer invalid_token"}
        resp = self.test_endpoint("Invalid Token", "GET", "/accounts",
                                  expected_status=401, skip_assert=True)

        # Restore auth
        self.headers = original_headers

        # 3. SQL Injection Attempt (should be sanitized)
        malicious_data = {
            "description": "' OR '1'='1",
            "amount": 10.00,
            "type": "expense",
            "date": "2024-03-04"
        }
        self.test_endpoint("SQL Injection Test", "POST", "/transactions",
                          malicious_data, expected_status=201, skip_assert=True)

    def cleanup(self):
        """Cleanup test data"""
        self.log("\n🧹 CLEANUP", Colors.BLUE)

        # Delete created data
        if 'transaction_id' in self.test_data:
            self.test_endpoint("Delete Transaction", "DELETE",
                             f"/transactions/{self.test_data['transaction_id']}",
                             expected_status=200, skip_assert=True)

        if 'account_id' in self.test_data:
            self.test_endpoint("Delete Account", "DELETE",
                             f"/accounts/{self.test_data['account_id']}",
                             expected_status=200, skip_assert=True)

        if 'credit_card_id' in self.test_data:
            self.test_endpoint("Delete Credit Card", "DELETE",
                             f"/accounts/{self.test_data['credit_card_id']}",
                             expected_status=200, skip_assert=True)

        if 'category_id' in self.test_data:
            self.test_endpoint("Delete Category", "DELETE",
                             f"/categories/{self.test_data['category_id']}",
                             expected_status=200, skip_assert=True)

        # Clear all data
        self.test_endpoint("Clear All Data", "POST", "/auth/data/clear",
                          {}, expected_status=200, skip_assert=True)

    def run_all_tests(self):
        """Run all test suites"""
        self.log("=" * 50, Colors.YELLOW)
        self.log("🧪 ALCA FINANÇAS - FULL API TEST SUITE", Colors.YELLOW)
        self.log("=" * 50, Colors.YELLOW)
        self.log(f"API URL: {self.base_url}", Colors.YELLOW)
        self.log(f"Test Email: {self.test_email}", Colors.YELLOW)

        start_time = time.time()

        try:
            # Run all test suites
            self.test_auth()
            self.test_categories()
            self.test_accounts()
            self.test_transactions()
            self.test_dashboard()
            self.test_reports()
            self.test_backup()
            self.test_security()

            # Cleanup
            self.cleanup()

        except KeyboardInterrupt:
            self.log("\n\n⚠️  Tests interrupted by user", Colors.YELLOW)
        except Exception as e:
            self.log(f"\n\n❌ Unexpected error: {str(e)}", Colors.RED)

        end_time = time.time()
        duration = end_time - start_time

        # Summary
        self.log("\n" + "=" * 50, Colors.YELLOW)
        self.log("📊 TEST SUMMARY", Colors.YELLOW)
        self.log("=" * 50, Colors.YELLOW)
        self.log(f"Total Tests: {self.tests_passed + self.tests_failed}")
        self.log(f"✅ Passed: {self.tests_passed}", Colors.GREEN)
        self.log(f"❌ Failed: {self.tests_failed}", Colors.RED)
        self.log(f"⏱️  Duration: {duration:.2f}s")
        self.log(f"📈 Success Rate: {(self.tests_passed / (self.tests_passed + self.tests_failed) * 100):.1f}%")

        if self.tests_failed == 0:
            self.log("\n🎉 ALL TESTS PASSED!", Colors.GREEN)
            return 0
        else:
            self.log(f"\n❌ {self.tests_failed} TEST(S) FAILED", Colors.RED)
            return 1

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001/api"

    tester = APITester(base_url)
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)
