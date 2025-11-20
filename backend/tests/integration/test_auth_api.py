"""
Integration tests for authentication API endpoints
"""
import pytest
import json


@pytest.mark.api
@pytest.mark.auth
class TestAuthAPI:
    """Test authentication endpoints"""

    def test_health_check(self, client):
        """Test API health endpoint"""
        response = client.get('/api/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'

    def test_register_success(self, client, db):
        """Test successful user registration"""
        payload = {
            'name': 'New User',
            'email': 'newuser@alcahub.com.br',
            'password': 'SecurePass123!'
        }

        response = client.post(
            '/api/auth/register',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'user' in data
        assert data['user']['email'] == payload['email']

    def test_register_duplicate_email(self, client, test_user):
        """Test registration with duplicate email"""
        payload = {
            'name': 'Another User',
            'email': test_user['email'],
            'password': 'SecurePass123!'
        }

        response = client.post(
            '/api/auth/register',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_register_missing_fields(self, client):
        """Test registration with missing required fields"""
        payload = {
            'email': 'incomplete@alcahub.com.br'
        }

        response = client.post(
            '/api/auth/register',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_login_success(self, client, test_user):
        """Test successful login"""
        payload = {
            'email': test_user['email'],
            'password': 'TestPassword123!'
        }

        response = client.post(
            '/api/auth/login',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'user' in data

    def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password"""
        payload = {
            'email': test_user['email'],
            'password': 'WrongPassword123!'
        }

        response = client.post(
            '/api/auth/login',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user"""
        payload = {
            'email': 'nonexistent@alcahub.com.br',
            'password': 'SomePassword123!'
        }

        response = client.post(
            '/api/auth/login',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_me_endpoint_authenticated(self, client, auth_headers, test_user):
        """Test /me endpoint with authentication"""
        response = client.get(
            '/api/auth/me',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['email'] == test_user['email']

    def test_me_endpoint_unauthenticated(self, client):
        """Test /me endpoint without authentication"""
        response = client.get('/api/auth/me')

        assert response.status_code == 401

    def test_settings_get(self, client, auth_headers):
        """Test get user settings"""
        response = client.get(
            '/api/auth/settings',
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_settings_update(self, client, auth_headers):
        """Test update user settings"""
        payload = {
            'language': 'en',
            'theme': 'dark'
        }

        response = client.put(
            '/api/auth/settings',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_forgot_password(self, client):
        """Test forgot password endpoint"""
        payload = {
            'email': 'test@alcahub.com.br'
        }

        response = client.post(
            '/api/auth/forgot-password',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data

    def test_forgot_password_missing_email(self, client):
        """Test forgot password without email"""
        response = client.post(
            '/api/auth/forgot-password',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 400

    def test_refresh_token_success(self, client, test_user):
        """Test refresh token flow"""
        # First login to get tokens
        login_payload = {
            'email': test_user['email'],
            'password': 'TestPassword123!'
        }
        
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps(login_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        login_data = json.loads(login_response.data)
        refresh_token = login_data['refresh_token']
        
        # Use refresh token to get new tokens
        refresh_payload = {
            'refresh_token': refresh_token
        }
        
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps(refresh_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'refresh_token' in data

    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token"""
        payload = {
            'refresh_token': 'invalid_token_12345'
        }
        
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        payload = {
            'email': 'test@alcahub.com.br'
            # Missing password
        }
        
        response = client.post(
            '/api/auth/login',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400


    def test_settings_update_invalid_fields(self, client, auth_headers):
        """Test updating settings with invalid/disallowed fields"""
        payload = {
            'language': 'en',
            'theme': 'dark',
            'disallowed_field': 'should_be_ignored'
        }
        
        response = client.put(
            '/api/auth/settings',
            data=json.dumps(payload),
            headers=auth_headers
        )
        
        # Should succeed but ignore disallowed fields
        assert response.status_code == 200

    def test_refresh_token_missing_field(self, client):
        """Test refresh with missing refresh_token field"""
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps({}),
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400

    def test_me_endpoint_deleted_user(self, client, db):
        """Test /me endpoint when user is deleted after token generation"""
        from utils.auth_utils import generate_jwt
        
        # Generate token for non-existent user
        fake_user_id = 'deleted-user-id-12345'
        tokens = generate_jwt(fake_user_id)
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {tokens["access_token"]}'
        }
        
        response = client.get(
            '/api/auth/me',
            headers=headers
        )
        
        assert response.status_code == 404

    def test_refresh_token_deleted_user(self, client, db):
        """Test refresh token when user is deleted"""
        from utils.auth_utils import generate_jwt
        
        # Generate token for non-existent user
        fake_user_id = 'deleted-user-id-67890'
        tokens = generate_jwt(fake_user_id)
        
        payload = {
            'refresh_token': tokens['refresh_token']
        }
        
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 401

    def test_settings_get_empty(self, client, auth_headers, db):
        """Test getting settings when user has no settings configured"""
        # The test_user fixture should have empty settings by default
        response = client.get(
            '/api/auth/settings',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should return empty dict or default settings
        assert isinstance(data, dict)

    def test_settings_update_empty_payload(self, client, auth_headers):
        """Test updating settings with empty payload"""
        response = client.put(
            '/api/auth/settings',
            data=json.dumps({}),
            headers=auth_headers
        )
        
        # Should succeed even with empty payload
        assert response.status_code == 200


