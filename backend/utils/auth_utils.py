from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from typing import Optional
import bcrypt
import jwt
import os

from utils.supabase_jwt import verify_supabase_jwt


JWT_SECRET = os.getenv("JWT_SECRET", "").strip()  # legado (não usado no Supabase-only)
JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", 24))


def hash_password(password: str) -> str:
    """Hash password and return as string (UTF-8 decoded) for JSON serialization."""
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')


def _normalize_password_hash(hashed):
    """Converte hash de senha para bytes (MongoDB Binary, Supabase BYTEA hex, ou bytes)."""
    if not hashed:
        return None
    # MongoDB Binary
    try:
        from bson import Binary
        if isinstance(hashed, Binary):
            return hashed.as_bytes()
    except ImportError:
        pass
    if isinstance(hashed, bytes):
        return hashed
    if isinstance(hashed, str):
        # Supabase/PostgREST retorna BYTEA como string hex com prefixo \x (ex: "\\x24326224...")
        s = hashed.strip()
        if s.startswith('\\x') or (len(s) > 2 and s[0] == '\\' and s[1] == 'x'):
            s = s[2:]
        try:
            return bytes.fromhex(s)
        except (ValueError, TypeError):
            pass
        # Fallback: tratar como UTF-8 (ex.: MongoDB que gravou como string)
        return hashed.encode('utf-8')
    if hasattr(hashed, 'tobytes'):
        return bytes(hashed)
    # memoryview ou outro buffer (Supabase/PostgreSQL BYTEA)
    try:
        if hasattr(hashed, '__iter__') and not isinstance(hashed, (str, dict)):
            return bytes(hashed)
    except Exception:
        pass
    return None


def check_password(password: str, hashed) -> bool:
    """
    Verifica se a senha corresponde ao hash.
    Aceita bytes (MongoDB), string hex BYTEA (Supabase/PostgREST) ou Binary.
    """
    hashed = _normalize_password_hash(hashed)
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except (TypeError, ValueError) as e:
        # Log do erro para debug
        import logging
        logging.error(f"Erro ao verificar senha: {e}, tipo do hash: {type(hashed)}")
        return False


import uuid

def generate_jwt(user_id: str, tenant_id: Optional[str] = None) -> dict:
    access_payload = {
        'user_id': str(user_id),
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS),
        'jti': str(uuid.uuid4())
    }
    if tenant_id:
        access_payload['tenant_id'] = str(tenant_id)
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


RESET_TOKEN_EXPIRES_HOURS = 1


def generate_reset_token(user_id: str) -> str:
    payload = {
        'user_id': str(user_id),
        'type': 'reset',
        'exp': datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRES_HOURS),
        'jti': str(uuid.uuid4()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token.decode('utf-8') if isinstance(token, bytes) else token


def decode_reset_token(token: str):
    """Returns user_id if token is valid, else None."""
    return decode_token(token, 'reset')


def verify_jwt(token: str):
    return decode_token(token, 'access')


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({'error': 'Token de autorização necessário'}), 401

        token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header

        try:
            payload = verify_supabase_jwt(token)
        except Exception as e:
            current_app.logger.debug(f"Auth inválida (Supabase JWT): {e}")
            return jsonify({"error": "Token inválido ou expirado"}), 401

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        request.user_id = user_id
        # Disponibiliza claims para resolução de tenant (se houver tenant_id em claims)
        setattr(request, "jwt_payload", payload)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Assumes @require_auth is used before this or request.user_id is set
        if not hasattr(request, 'user_id'):
            return jsonify({'error': 'Autenticação necessária'}), 401

        users_repo = current_app.config.get("USERS")
        user = None
        if users_repo:
            if hasattr(users_repo, "find_by_id"):
                user = users_repo.find_by_id(request.user_id)
            else:
                user = users_repo.find_one({"id": request.user_id})
        
        if not user or not user.get('is_admin'):
            return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403
            
        return f(*args, **kwargs)
    return decorated

