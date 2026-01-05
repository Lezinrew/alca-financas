"""
Rotas de autenticação usando Supabase Auth
"""
from flask import Blueprint, request, jsonify, current_app
from services.supabase_auth_service import SupabaseAuthService
from services.user_service import create_default_categories
from schemas.auth_schemas import UserRegisterSchema, UserLoginSchema
from extensions import limiter
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('auth_supabase', __name__)


@bp.route('/auth/register', methods=['POST'])
@limiter.limit("3 per hour")
def register():
    """Registra novo usuário usando Supabase Auth"""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        data = UserRegisterSchema(**request_data)
    except ValidationError as e:
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar registro: {str(e)}'}), 400
    
    try:
        auth_service = SupabaseAuthService()
        result = auth_service.sign_up(
            email=data.email,
            password=data.password,
            name=data.name
        )
        
        # Criar categorias padrão
        category_repo = current_app.config['CATEGORY_REPO']
        create_default_categories(category_repo, result['user']['id'])
        
        return jsonify({
            'message': 'Usuário criado com sucesso',
            'access_token': result['access_token'],
            'refresh_token': result['refresh_token'],
            'user': result['user']
        }), 201
    except Exception as e:
        error_msg = str(e)
        if 'already registered' in error_msg.lower() or 'user already exists' in error_msg.lower():
            return jsonify({'error': 'Email já cadastrado'}), 400
        logger.error(f"Erro ao registrar usuário: {e}")
        return jsonify({'error': f'Erro ao criar usuário: {error_msg}'}), 500


@bp.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login usando Supabase Auth"""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        data = UserLoginSchema(**request_data)
    except ValidationError as e:
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar login: {str(e)}'}), 400
    
    try:
        auth_service = SupabaseAuthService()
        result = auth_service.sign_in(
            email=data.email,
            password=data.password
        )
        
        return jsonify({
            'message': 'Login realizado com sucesso',
            'access_token': result['access_token'],
            'refresh_token': result['refresh_token'],
            'user': result['user']
        })
    except Exception as e:
        error_msg = str(e)
        if 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
            return jsonify({'error': 'Email ou senha incorretos'}), 401
        logger.error(f"Erro no login: {e}")
        return jsonify({'error': f'Erro no login: {error_msg}'}), 500


@bp.route('/auth/refresh', methods=['POST'])
@limiter.limit("10 per minute")
def refresh():
    """Renova o token de acesso usando refresh token"""
    try:
        request_data = request.get_json()
        if not request_data or not request_data.get('refresh_token'):
            return jsonify({'error': 'refresh_token é obrigatório'}), 400
        
        auth_service = SupabaseAuthService()
        result = auth_service.refresh_session(request_data['refresh_token'])
        
        if not result:
            return jsonify({'error': 'Token inválido ou expirado'}), 401
        
        return jsonify({
            'access_token': result['access_token'],
            'refresh_token': result['refresh_token']
        })
    except Exception as e:
        logger.error(f"Erro ao renovar token: {e}")
        return jsonify({'error': 'Erro ao renovar token'}), 500


@bp.route('/auth/me', methods=['GET'])
def get_user():
    """Obtém dados do usuário autenticado"""
    try:
        # Obter token do header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autorização necessário'}), 401
        
        access_token = auth_header[7:]  # Remove 'Bearer '
        
        auth_service = SupabaseAuthService()
        user = auth_service.get_user(access_token)
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado ou token inválido'}), 401
        
        return jsonify(user)
    except Exception as e:
        logger.error(f"Erro ao obter usuário: {e}")
        return jsonify({'error': 'Erro ao obter dados do usuário'}), 500


@bp.route('/auth/logout', methods=['POST'])
def logout():
    """Faz logout do usuário"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autorização necessário'}), 401
        
        access_token = auth_header[7:]
        
        auth_service = SupabaseAuthService()
        auth_service.sign_out(access_token)
        
        return jsonify({'message': 'Logout realizado com sucesso'})
    except Exception as e:
        logger.error(f"Erro ao fazer logout: {e}")
        return jsonify({'error': 'Erro ao fazer logout'}), 500



