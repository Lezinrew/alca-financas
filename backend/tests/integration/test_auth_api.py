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
        assert 'token' in data
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
        assert 'token' in data
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
