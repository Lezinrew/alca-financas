#!/usr/bin/env python3
"""
Mobills Pro Backend API Testing Suite
Tests all API endpoints for the financial control application
"""

import requests
import sys
import json
from datetime import datetime, timedelta
import uuid
import os

class MobillsAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_user_email = f"test_{uuid.uuid4().hex[:8]}@mobills.com"
        self.test_user_password = "TestPass123!"
        self.test_user_name = "Test User"
        self.created_category_id = None
        self.created_transaction_id = None

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")

    def make_request(self, method, endpoint, data=None, files=None, expected_status=200):
        """Make HTTP request with proper headers"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if files:
            headers.pop('Content-Type')  # Let requests handle multipart
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                return False, f"Unsupported method: {method}"

            success = response.status_code == expected_status
            
            if success:
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                try:
                    error_data = response.json()
                    return False, f"Status {response.status_code}: {error_data.get('error', 'Unknown error')}"
                except:
                    return False, f"Status {response.status_code}: {response.text}"
                    
        except Exception as e:
            return False, f"Request failed: {str(e)}"

    def test_user_registration(self):
        """Test user registration"""
        print("\n🔍 Testing User Registration...")
        
        data = {
            "name": self.test_user_name,
            "email": self.test_user_email,
            "password": self.test_user_password
        }
        
        success, response = self.make_request('POST', 'register', data, expected_status=201)
        
        if success and isinstance(response, dict):
            if 'token' in response and 'user' in response:
                self.token = response['token']
                self.user_id = response['user']['id']
                self.log_test("User Registration", True)
                return True
            else:
                self.log_test("User Registration", False, "Missing token or user in response")
                return False
        else:
            self.log_test("User Registration", False, str(response))
            return False

    def test_user_login(self):
        """Test user login"""
        print("\n🔍 Testing User Login...")
        
        data = {
            "email": self.test_user_email,
            "password": self.test_user_password
        }
        
        success, response = self.make_request('POST', 'login', data)
        
        if success and isinstance(response, dict):
            if 'token' in response and 'user' in response:
                self.token = response['token']
                self.user_id = response['user']['id']
                self.log_test("User Login", True)
                return True
            else:
                self.log_test("User Login", False, "Missing token or user in response")
                return False
        else:
            self.log_test("User Login", False, str(response))
            return False

    def test_get_user_profile(self):
        """Test getting user profile"""
        print("\n🔍 Testing Get User Profile...")
        
        success, response = self.make_request('GET', 'me')
        
        if success and isinstance(response, dict):
            if 'id' in response and 'name' in response and 'email' in response:
                self.log_test("Get User Profile", True)
                return True
            else:
                self.log_test("Get User Profile", False, "Missing required fields in response")
                return False
        else:
            self.log_test("Get User Profile", False, str(response))
            return False

    def test_user_settings(self):
        """Test user settings GET and PUT"""
        print("\n🔍 Testing User Settings...")
        
        # Test GET settings
        success, response = self.make_request('GET', 'settings')
        
        if not success:
            self.log_test("Get User Settings", False, str(response))
            return False
        
        self.log_test("Get User Settings", True)
        
        # Test PUT settings
        update_data = {
            "currency": "USD",
            "theme": "dark",
            "language": "en"
        }
        
        success, response = self.make_request('PUT', 'settings', update_data)
        
        if success:
            self.log_test("Update User Settings", True)
            return True
        else:
            self.log_test("Update User Settings", False, str(response))
            return False

    def test_categories_crud(self):
        """Test categories CRUD operations"""
        print("\n🔍 Testing Categories CRUD...")
        
        # Test GET categories (should have default categories)
        success, response = self.make_request('GET', 'categories')
        
        if not success:
            self.log_test("Get Categories", False, str(response))
            return False
        
        if isinstance(response, list) and len(response) > 0:
            self.log_test("Get Categories", True)
        else:
            self.log_test("Get Categories", False, "No default categories found")
            return False
        
        # Test POST - Create new category
        category_data = {
            "name": "Test Category",
            "type": "expense",
            "color": "#FF0000",
            "icon": "test-icon"
        }
        
        success, response = self.make_request('POST', 'categories', category_data, expected_status=201)
        
        if success and isinstance(response, dict):
            if 'name' in response and response['name'] == category_data['name']:
                # Store the category ID for later tests (it should be in the response)
                # Since we're using UUID, we need to get it from the response
                self.log_test("Create Category", True)
                
                # Get categories again to find our created category
                success, categories = self.make_request('GET', 'categories')
                if success:
                    for cat in categories:
                        if cat.get('name') == 'Test Category':
                            self.created_category_id = cat.get('id') or cat.get('_id')
                            break
                
            else:
                self.log_test("Create Category", False, "Category not created properly")
                return False
        else:
            self.log_test("Create Category", False, str(response))
            return False
        
        return True

    def test_transactions_crud(self):
        """Test transactions CRUD operations"""
        print("\n🔍 Testing Transactions CRUD...")
        
        # First get categories to use one for transaction
        success, categories = self.make_request('GET', 'categories')
        
        if not success or not categories:
            self.log_test("Get Categories for Transaction", False, "No categories available")
            return False
        
        # Use first expense category
        expense_category = None
        for cat in categories:
            if cat.get('type') == 'expense':
                expense_category = cat
                break
        
        if not expense_category:
            self.log_test("Find Expense Category", False, "No expense category found")
            return False
        
        # Debug: print category structure
        print(f"   Category structure: {expense_category}")
        
        # Try different possible ID fields
        category_id = expense_category.get('id') or expense_category.get('_id')
        
        if not category_id:
            # If no ID found, try to find it by looking for any field that looks like an ID
            for key, value in expense_category.items():
                if 'id' in key.lower() and isinstance(value, str):
                    category_id = value
                    break
        
        if not category_id:
            self.log_test("Find Category ID", False, f"No ID found in category: {expense_category}")
            return False
        
        # Test POST - Create transaction
        transaction_data = {
            "description": "Test Transaction",
            "amount": 100.50,
            "type": "expense",
            "category_id": category_id,
            "date": datetime.now().isoformat()
        }
        
        success, response = self.make_request('POST', 'transactions', transaction_data, expected_status=201)
        
        if success:
            self.log_test("Create Transaction", True)
        else:
            self.log_test("Create Transaction", False, str(response))
            return False
        
        # Test GET transactions
        success, response = self.make_request('GET', 'transactions')
        
        if success and isinstance(response, list):
            self.log_test("Get Transactions", True)
            
            # Find our created transaction
            for trans in response:
                if trans.get('description') == 'Test Transaction':
                    self.created_transaction_id = trans.get('id') or trans.get('_id')
                    break
        else:
            self.log_test("Get Transactions", False, str(response))
            return False
        
        return True

    def test_dashboard(self):
        """Test dashboard endpoint"""
        print("\n🔍 Testing Dashboard...")
        
        success, response = self.make_request('GET', 'dashboard')
        
        if success and isinstance(response, dict):
            required_keys = ['period', 'summary', 'recent_transactions', 'expense_by_category', 'income_by_category']
            missing_keys = [key for key in required_keys if key not in response]
            
            if not missing_keys:
                self.log_test("Dashboard Data", True)
                return True
            else:
                self.log_test("Dashboard Data", False, f"Missing keys: {missing_keys}")
                return False
        else:
            self.log_test("Dashboard Data", False, str(response))
            return False

    def test_forgot_password(self):
        """Test forgot password endpoint"""
        print("\n🔍 Testing Forgot Password...")
        
        data = {"email": self.test_user_email}
        success, response = self.make_request('POST', 'forgot-password', data)
        
        if success:
            self.log_test("Forgot Password", True)
            return True
        else:
            self.log_test("Forgot Password", False, str(response))
            return False

    def test_oauth_endpoints(self):
        """Test OAuth endpoints (should return proper error messages)"""
        print("\n🔍 Testing OAuth Endpoints...")
        
        # Test Google OAuth callback (should return configuration error)
        success, response = self.make_request('GET', 'auth/google/callback', expected_status=400)
        
        if success:
            self.log_test("Google OAuth Configuration Check", True)
        else:
            self.log_test("Google OAuth Configuration Check", False, str(response))
        
        # Test Microsoft OAuth (should return not implemented)
        success, response = self.make_request('GET', 'auth/microsoft/login', expected_status=501)
        
        if success:
            self.log_test("Microsoft OAuth Not Implemented Check", True)
        else:
            self.log_test("Microsoft OAuth Not Implemented Check", False, str(response))
        
        # Test Apple OAuth (should return not implemented)
        success, response = self.make_request('GET', 'auth/apple/login', expected_status=501)
        
        if success:
            self.log_test("Apple OAuth Not Implemented Check", True)
        else:
            self.log_test("Apple OAuth Not Implemented Check", False, str(response))

    def test_invalid_endpoints(self):
        """Test invalid endpoints and authentication"""
        print("\n🔍 Testing Invalid Endpoints and Auth...")
        
        # Test invalid endpoint
        success, response = self.make_request('GET', 'invalid-endpoint', expected_status=404)
        
        # Flask returns 404 for invalid endpoints, so success=False with 404 status is correct
        if not success and "404" in str(response):
            self.log_test("Invalid Endpoint 404", True)
        else:
            # Check if we actually got a 404 response
            try:
                url = f"{self.base_url}/api/invalid-endpoint"
                headers = {'Content-Type': 'application/json'}
                if self.token:
                    headers['Authorization'] = f'Bearer {self.token}'
                resp = requests.get(url, headers=headers)
                if resp.status_code == 404:
                    self.log_test("Invalid Endpoint 404", True)
                else:
                    self.log_test("Invalid Endpoint 404", False, f"Got status {resp.status_code} instead of 404")
            except Exception as e:
                self.log_test("Invalid Endpoint 404", False, f"Exception: {str(e)}")
        
        # Test protected endpoint without token
        old_token = self.token
        self.token = None
        
        success, response = self.make_request('GET', 'me', expected_status=401)
        
        # Similar logic for 401
        if not success and "401" in str(response):
            self.log_test("Protected Endpoint Without Token", True)
        else:
            # Check if we actually got a 401 response
            try:
                url = f"{self.base_url}/api/me"
                headers = {'Content-Type': 'application/json'}
                resp = requests.get(url, headers=headers)
                if resp.status_code == 401:
                    self.log_test("Protected Endpoint Without Token", True)
                else:
                    self.log_test("Protected Endpoint Without Token", False, f"Got status {resp.status_code} instead of 401")
            except Exception as e:
                self.log_test("Protected Endpoint Without Token", False, f"Exception: {str(e)}")
        
        # Restore token
        self.token = old_token

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Mobills Pro API Tests...")
        print(f"📍 Testing against: {self.base_url}")
        print(f"👤 Test user: {self.test_user_email}")
        
        # Test sequence
        tests = [
            self.test_user_registration,
            self.test_get_user_profile,
            self.test_user_settings,
            self.test_categories_crud,
            self.test_transactions_crud,
            self.test_dashboard,
            self.test_forgot_password,
            self.test_oauth_endpoints,
            self.test_invalid_endpoints,
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                print(f"❌ {test.__name__} - EXCEPTION: {str(e)}")
        
        # Print summary
        print(f"\n📊 Test Summary:")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        print(f"   Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test function"""
    # Use environment variable or default
    backend_url = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
    
    print(f"🔧 Backend URL: {backend_url}")
    
    tester = MobillsAPITester(backend_url)
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Backend API is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the backend implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())