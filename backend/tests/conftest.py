"""
Pytest configuration and fixtures for all tests
"""
import os
import pytest
from app import app as flask_app
import jwt
from datetime import datetime, timedelta


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    flask_app.config.update({
        'TESTING': True,
        'JWT_SECRET': os.getenv('JWT_SECRET', 'test-secret-key'),
        'RATELIMIT_ENABLED': True,
        'RATELIMIT_STORAGE_URI': 'memory://'
    })
    yield flask_app


@pytest.fixture(scope='session')
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_user():
    """Usuário fictício em memória (não é gravado em banco)."""
    import uuid
    return {
        '_id': str(uuid.uuid4()),
        'name': 'Test User',
        'email': 'test@alcahub.com.br',
        'created_at': datetime.utcnow()
    }


@pytest.fixture
def auth_token(app, test_user):
    """Generate JWT token for test user"""
    secret = app.config['JWT_SECRET']
    token = jwt.encode(
        {
            'user_id': test_user['_id'],
            'exp': datetime.utcnow() + timedelta(hours=1)
        },
        secret,
        algorithm='HS256'
    )
    return token


@pytest.fixture
def api_base_url():
    """Get API base URL based on environment"""
    env = os.getenv('NODE_ENV', 'local')
    if env == 'production':
        return os.getenv('PROD_API_URL', 'https://alcahub.cloud/api')
    return os.getenv('LOCAL_API_URL', 'http://localhost:5000')
