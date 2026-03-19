"""
Utilitários de autenticação para Supabase Auth e JWT da aplicação.

Aceita, nesta ordem:
1. JWT customizado da app (login retorna access_token com user_id, type: access) — mesmo token usado no restante da API.
2. Token Supabase Auth (fallback para fluxos que usam Supabase Auth diretamente).
"""
from functools import wraps
from flask import request, jsonify, current_app
from services.supabase_auth_service import SupabaseAuthService
import logging

logger = logging.getLogger(__name__)


def _user_from_app_jwt(access_token: str):
    """
    Valida o JWT da aplicação (JWT_SECRET, payload user_id, type: access) e retorna
    o usuário da base (dict com id, email, name, ...) ou None.
    """
    try:
        from utils.auth_utils import verify_jwt
        user_id = verify_jwt(access_token)
        if not user_id:
            return None
        users_repo = current_app.config.get('USERS')
        if not users_repo:
            return None
        user_doc = users_repo.find_by_id(user_id)
        if not user_doc:
            return None
        uid = user_doc.get('id') or user_doc.get('_id') or user_id
        return {
            'id': uid,
            'email': user_doc.get('email'),
            'name': user_doc.get('name'),
            'settings': user_doc.get('settings', {}),
            'is_admin': user_doc.get('is_admin', False),
            'email_verified': user_doc.get('email_verified', True),
        }
    except Exception as e:
        logger.debug(f"App JWT validation failed: {e}")
        return None


def _get_authenticated_user(access_token: str):
    """
    Tenta primeiro JWT da app; se falhar, tenta Supabase Auth.
    Retorna dict user ou None.
    """
    user = _user_from_app_jwt(access_token)
    if user:
        return user
    auth_service = SupabaseAuthService()
    return auth_service.get_user(access_token)


def require_auth_supabase(f):
    """
    Decorator para rotas que requerem autenticação.
    Aceita JWT da aplicação (login atual) ou token Supabase Auth.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning(f"Tentativa de acesso sem token - Path: {request.path} - IP: {request.remote_addr}")
            return jsonify({'error': 'Token de autorização necessário'}), 401

        access_token = auth_header[7:]  # Remove 'Bearer '

        try:
            user = _get_authenticated_user(access_token)

            if not user:
                logger.warning(f"Token inválido ou expirado - Path: {request.path} - IP: {request.remote_addr}")
                return jsonify({'error': 'Token inválido ou expirado'}), 401

            request.user_id = user['id']
            request.user = user
            logger.debug(f"Autenticação bem-sucedida - User: {user['id']} - Path: {request.path}")

            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao verificar autenticação - Path: {request.path} - IP: {request.remote_addr} - Erro: {e}", exc_info=True)
            return jsonify({'error': 'Erro ao verificar autenticação'}), 401

    return decorated


def admin_required_supabase(f):
    """
    Decorator para rotas que requerem privilégios de administrador
    Deve ser usado após @require_auth_supabase
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'user'):
            return jsonify({'error': 'Autenticação necessária'}), 401

        if not request.user.get('is_admin', False):
            return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403

        return f(*args, **kwargs)

    return decorated


def token_required(f):
    """
    Decorator para rotas que requerem autenticação (ex.: chatbot).
    Aceita JWT da aplicação (login atual) ou token Supabase Auth.
    Passa current_user como primeiro argumento para a função decorada.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning(f"token_required: Tentativa de acesso sem token - Path: {request.path} - IP: {request.remote_addr}")
            return jsonify({'error': 'Token de autorização necessário'}), 401

        access_token = auth_header[7:]  # Remove 'Bearer '

        try:
            user = _get_authenticated_user(access_token)

            if not user:
                logger.warning(f"token_required: Token inválido ou expirado - Path: {request.path} - IP: {request.remote_addr}")
                return jsonify({'error': 'Token inválido ou expirado'}), 401

            request.user_id = user['id']
            request.user = user
            logger.debug(f"token_required: Autenticação bem-sucedida - User: {user['id']} - Path: {request.path}")

            return f(user, *args, **kwargs)
        except Exception as e:
            logger.error(f"token_required: Erro ao verificar autenticação - Path: {request.path} - IP: {request.remote_addr} - Erro: {e}", exc_info=True)
            return jsonify({'error': 'Erro ao verificar autenticação'}), 401

    return decorated



