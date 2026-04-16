"""
Utilitários de autenticação para Supabase Auth.

Fluxo principal: access_token do Supabase Auth (sessão do cliente).
Validação de rotas protegidas com @require_auth (auth_utils) usa verify_supabase_jwt.
"""
from functools import wraps
from flask import request, jsonify, current_app
from services.supabase_auth_service import SupabaseAuthService
import logging

logger = logging.getLogger(__name__)


def _get_authenticated_user(access_token: str):
    """
    Resolve o usuário a partir do token Supabase Auth (único caminho ativo aqui).
    """
    auth_service = SupabaseAuthService()
    return auth_service.get_user(access_token)


def require_auth_supabase(f):
    """
    Decorator para rotas que requerem autenticação via token Supabase Auth.
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
    Decorator para rotas que requerem autenticação (ex.: chatbot) via token Supabase Auth.
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


