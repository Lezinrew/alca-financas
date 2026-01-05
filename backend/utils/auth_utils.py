from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import bcrypt
import jwt
import os


JWT_SECRET = os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'dev-secret-key'))
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', 24))


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def check_password(password: str, hashed) -> bool:
    """
    Verifica se a senha corresponde ao hash.
    Aceita tanto bytes quanto string (MongoDB pode retornar como string ou Binary).
    """
    if not hashed:
        return False
    
    # Se for Binary do MongoDB, extrai os bytes
    try:
        from bson import Binary
        if isinstance(hashed, Binary):
            hashed = hashed.as_bytes()
    except ImportError:
        pass
    
    # Se for string, converte para bytes
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    elif not isinstance(hashed, bytes):
        # Tenta converter para bytes se for outro tipo
        try:
            hashed = bytes(hashed)
        except (TypeError, ValueError):
            # Se não conseguir converter, tenta como string primeiro
            if hasattr(hashed, '__str__'):
                hashed = str(hashed).encode('utf-8')
            else:
                import logging
                logging.error(f"Erro ao verificar senha: tipo do hash não suportado: {type(hashed)}")
                return False
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except (TypeError, ValueError) as e:
        # Log do erro para debug
        import logging
        logging.error(f"Erro ao verificar senha: {e}, tipo do hash: {type(hashed)}")
        return False


import uuid

def generate_jwt(user_id: str) -> dict:
    access_payload = {
        'user_id': str(user_id),
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS),
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
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Assumes @require_auth is used before this or request.user_id is set
        if not hasattr(request, 'user_id'):
            return jsonify({'error': 'Autenticação necessária'}), 401

        from flask import current_app
        users_collection = current_app.config['USERS']
        user = users_collection.find_one({'_id': request.user_id})
        
        if not user or not user.get('is_admin'):
            return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403
            
        return f(*args, **kwargs)
    return decorated

