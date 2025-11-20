from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import bcrypt
import jwt
import os


JWT_SECRET = os.getenv('SECRET_KEY', 'dev-secret-key')
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', 24))


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def check_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


import uuid

def generate_jwt(user_id: str) -> dict:
    access_payload = {
        'user_id': str(user_id),
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(minutes=15),
        'jti': str(uuid.uuid4())
    }
    refresh_payload = {
        'user_id': str(user_id),
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(days=7),
        'jti': str(uuid.uuid4())
    }
    
    return {
        'access_token': jwt.encode(access_payload, JWT_SECRET, algorithm='HS256'),
        'refresh_token': jwt.encode(refresh_payload, JWT_SECRET, algorithm='HS256')
    }


def decode_token(token: str, type_required: str = 'access'):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        if payload.get('type') != type_required:
            return None
        return payload['user_id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def verify_jwt(token: str):
    return decode_token(token, 'access')


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


