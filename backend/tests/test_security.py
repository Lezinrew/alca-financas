import pytest
import time
from flask import url_for

def test_register_validation(client):
    """Test input validation for registration"""
    # Missing fields
    response = client.post('/api/auth/register', json={}, environ_base={'REMOTE_ADDR': '127.0.0.101'})
    assert response.status_code == 400
    assert 'error' in response.json

    # Invalid email
    data = {
        'name': 'Test User',
        'email': 'invalid-email',
        'password': 'password123'
    }
    response = client.post('/api/auth/register', json=data, environ_base={'REMOTE_ADDR': '127.0.0.102'})
    assert response.status_code == 400

    # Short password
    response = client.post('/api/auth/register', json={
        'name': 'Test User',
        'email': 'test@example.com',
        'password': '123'
    }, environ_base={'REMOTE_ADDR': '127.0.0.103'})
    assert response.status_code == 400

def test_login_rate_limit(client, db):
    """Test rate limiting on login endpoint"""
    # Create user first
    client.post('/api/auth/register', json={
        'name': 'Rate Limit User',
        'email': 'ratelimit@example.com',
        'password': 'password123'
    }, environ_base={'REMOTE_ADDR': '10.0.0.1'})

    # Attempt login 10 times (limit is 5 per minute)
    for i in range(10):
        response = client.post('/api/auth/login', json={
            'email': 'ratelimit@example.com',
            'password': 'wrongpassword'
        }, environ_base={'REMOTE_ADDR': '10.0.0.1'})
        print(f"Request {i+1}: {response.status_code}")
        if i < 5:
            # First 5 should be allowed (401 because wrong password, but allowed by limiter)
            assert response.status_code == 401
        else:
            # 6th onwards should be blocked
            assert response.status_code == 429
            assert '429 TOO MANY REQUESTS' in response.status

def test_refresh_token_flow(client, db):
    """Test full refresh token flow"""
    # Register with unique IP to avoid rate limits
    resp = client.post('/api/auth/register', json={
        'name': 'Refresh User',
        'email': 'refresh_new@example.com',
        'password': 'password123'
    }, environ_base={'REMOTE_ADDR': '10.0.0.2'})
    assert resp.status_code == 201
    data = resp.json
    refresh_token = data['refresh_token']
    access_token = data['access_token']

    # Use access token
    headers = {'Authorization': f'Bearer {access_token}'}
    resp = client.get('/api/auth/me', headers=headers)
    assert resp.status_code == 200

    # Refresh token
    resp = client.post('/api/auth/refresh', json={
        'refresh_token': refresh_token
    })
    assert resp.status_code == 200
    new_tokens = resp.json
    assert 'access_token' in new_tokens
    assert 'refresh_token' in new_tokens
    assert new_tokens['access_token'] != access_token

    # Use new access token
    headers = {'Authorization': f'Bearer {new_tokens["access_token"]}'}
    resp = client.get('/api/auth/me', headers=headers)
    assert resp.status_code == 200

def test_invalid_refresh_token(client):
    """Test invalid refresh token"""
    response = client.post('/api/auth/refresh', json={
        'refresh_token': 'invalid.token.here'
    })
    assert response.status_code == 401
