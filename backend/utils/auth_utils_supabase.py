"""
Utilitários de autenticação para Supabase Auth
"""
from functools import wraps
from flask import request, jsonify, current_app
from services.supabase_auth_service import SupabaseAuthService
import logging

logger = logging.getLogger(__name__)


def require_auth_supabase(f):
    """
    Decorator para rotas que requerem autenticação via Supabase Auth
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autorização necessário'}), 401
        
        access_token = auth_header[7:]  # Remove 'Bearer '
        
        try:
            auth_service = SupabaseAuthService()
            user = auth_service.get_user(access_token)
            
            if not user:
                return jsonify({'error': 'Token inválido ou expirado'}), 401
            
            # Adicionar user_id ao request para uso na rota
            request.user_id = user['id']
            request.user = user
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao verificar autenticação: {e}")
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



