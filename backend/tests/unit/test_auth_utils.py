"""
Unit tests for authentication utilities
"""
import pytest
import jwt
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash


class TestAuthUtils:
    """Test authentication utility functions"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        from werkzeug.security import generate_password_hash

        password = "SecurePassword123!"
        hashed = generate_password_hash(password)

        assert hashed != password
        assert check_password_hash(hashed, password)
        assert not check_password_hash(hashed, "WrongPassword")

    def test_jwt_token_generation(self, app):
        """Test JWT token generation"""
        secret = app.config['JWT_SECRET']
        user_id = "test-user-123"

        token = jwt.encode(
            {
                'user_id': user_id,
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            secret,
            algorithm='HS256'
        )

        assert token is not None
        assert isinstance(token, str)

    def test_jwt_token_decode(self, app, auth_token, test_user):
        """Test JWT token decoding"""
        secret = app.config['JWT_SECRET']

        decoded = jwt.decode(auth_token, secret, algorithms=['HS256'])

        assert decoded['user_id'] == test_user['_id']
        assert 'exp' in decoded

    def test_jwt_token_expired(self, app):
        """Test expired JWT token"""
        secret = app.config['JWT_SECRET']

        token = jwt.encode(
            {
                'user_id': 'test-user',
                'exp': datetime.utcnow() - timedelta(hours=1)
            },
            secret,
            algorithm='HS256'
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, secret, algorithms=['HS256'])

    def test_jwt_invalid_token(self, app):
        """Test invalid JWT token"""
        secret = app.config['JWT_SECRET']

        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode('invalid.token.here', secret, algorithms=['HS256'])
