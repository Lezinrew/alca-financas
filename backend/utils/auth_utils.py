from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import bcrypt
import jwt
import os


JWT_SECRET = os.getenv('SECRET_KEY')
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', 24))


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def check_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def generate_jwt(user_id: str) -> str:
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def verify_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token de autorização necessário'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        user_id = verify_jwt(token)
        if not user_id:
            return jsonify({'error': 'Token inválido ou expirado'}), 401

        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


