# backend/routes/auth.py

from flask import Blueprint, request, jsonify, current_app, session
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError
from datetime import datetime
import uuid
import os
import base64
import json
import jwt
import requests

from utils.auth_utils import (
    hash_password,
    check_password,
    generate_jwt,
    require_auth,
    decode_token,
    generate_reset_token,
    decode_reset_token,
)
from services.user_service import create_user, create_default_categories, get_user_public
from services.email_service import send_reset_link
from schemas.auth_schemas import UserRegisterSchema, UserLoginSchema, RefreshTokenSchema
from extensions import limiter
from pydantic import ValidationError


# Remova o 'url_prefix' daqui. Ele será definido em app.py
bp = Blueprint('auth', __name__)


def _user_id(user):
    """ID do usuário (Supabase usa 'id', MongoDB usa '_id')."""
    return user.get('_id') or user.get('id')


def _user_id_filter(user_id):
    """Filtro para buscar usuário por ID (Supabase: id, MongoDB: _id)."""
    if current_app.config.get('DB_TYPE') == 'supabase':
        return {'id': user_id}
    return {'_id': user_id}


# Adicione '/auth' a todas as rotas de autenticação para agrupar logicamente os endpoints.
@bp.route('/auth/register', methods=['POST'])
@limiter.limit("3 per hour")
def register():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        data = UserRegisterSchema(**request_data)
    except ValidationError as e:
        # Formata erros do Pydantic em mensagens mais amigáveis
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação nos dados fornecidos'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar registro: {str(e)}'}), 400

    users_collection = current_app.config['USERS']
    categories_collection = current_app.config['CATEGORIES']

    email_norm = data.email.strip().lower()
    if users_collection.find_by_email(email_norm):
        return jsonify({'error': 'Email já cadastrado'}), 400

    try:
        user_data = data.model_dump()
        user_data['email'] = email_norm
        user = create_user(users_collection, user_data, hash_password)
        create_default_categories(categories_collection, _user_id(user))

        tokens = generate_jwt(_user_id(user))
        return jsonify({
            'message': 'Usuário criado com sucesso',
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'user': get_user_public(user)
        }), 201
    except Exception as e:
        import traceback
        print(f"Erro ao criar usuário: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erro ao criar usuário: {str(e)}'}), 500


@bp.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        data = UserLoginSchema(**request_data)
    except ValidationError as e:
        # Formata erros do Pydantic em mensagens mais amigáveis
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação nos dados fornecidos'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar login: {str(e)}'}), 400

    users_collection = current_app.config['USERS']
    email = data.email.strip().lower()
    if current_app.config.get('DB_TYPE') == 'supabase':
        user = users_collection.find_by_email(email)
    else:
        user = users_collection.find_one({'email': {'$regex': f'^{email}$', '$options': 'i'}})
    
    if not user:
        current_app.logger.warning(f"Login falhou: usuário não encontrado para email: {email}")
        return jsonify({'error': 'Email ou senha incorretos'}), 401

    if user.get('password') is None:
        return jsonify({'error': 'Este email está vinculado ao Google. Por favor, faça login via Google.'}), 400
    
    # Debug: log do tipo da senha (sem mostrar o valor)
    password_type = type(user['password']).__name__
    current_app.logger.debug(f"Tentativa de login para {email}: tipo da senha no banco: {password_type}")
    
    password_check_result = check_password(data.password, user['password'])
    current_app.logger.debug(f"Resultado da verificação de senha: {password_check_result}")
    
    if not password_check_result:
        current_app.logger.warning(f"Login falhou: senha incorreta para email: {email}")
        return jsonify({'error': 'Email ou senha incorretos'}), 401
        
    tokens = generate_jwt(_user_id(user))
    return jsonify({
        'message': 'Login realizado com sucesso',
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token'],
        'user': get_user_public(user)
    })


@bp.route('/auth/refresh', methods=['POST'])
@limiter.limit("10 per minute")
def refresh():
    try:
        data = RefreshTokenSchema(**request.get_json())
    except ValidationError as e:
        return jsonify({'error': e.errors()}), 400
        
    user_id = decode_token(data.refresh_token, 'refresh')
    if not user_id:
        return jsonify({'error': 'Refresh token inválido ou expirado'}), 401
        
    users_collection = current_app.config['USERS']
    user = users_collection.find_one(_user_id_filter(user_id))
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 401
        
    tokens = generate_jwt(user_id)
    return jsonify({
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token']
    })


@bp.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email é obrigatório'}), 400

    users_collection = current_app.config['USERS']
    if current_app.config.get('DB_TYPE') == 'supabase':
        user = users_collection.find_by_email(email)
    else:
        user = users_collection.find_one({'email': {'$regex': f'^{email}$', '$options': 'i'}})
    if user and user.get('password') is not None:
        reset_token = generate_reset_token(_user_id(user))
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"
        send_reset_link(user['email'], reset_url)

    return jsonify({'message': 'Se existir uma conta com esse e-mail, você receberá um link para redefinir sua senha.'}), 200


@bp.route('/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    token = data.get('token') or ''
    new_password = data.get('new_password') or ''
    if not token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'A senha deve ter pelo menos 6 caracteres'}), 400

    user_id = decode_reset_token(token)
    if not user_id:
        return jsonify({'error': 'Link inválido ou expirado. Solicite um novo.'}), 400

    users_collection = current_app.config['USERS']
    user = users_collection.find_one(_user_id_filter(user_id))
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 400

    hashed = hash_password(new_password)
    users_collection.update(user_id, {'password': hashed})

    return jsonify({'message': 'Senha redefinida com sucesso. Faça login com a nova senha.'}), 200


@bp.route('/auth/me', methods=['GET'])
@require_auth
def get_user():
    users_collection = current_app.config['USERS']
    user = users_collection.find_one(_user_id_filter(request.user_id))
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    return jsonify({
        'id': _user_id(user),
        'name': user['name'],
        'email': user['email'],
        'settings': user.get('settings', {}),
        'auth_providers': user.get('auth_providers', [])
    })


@bp.route('/auth/settings', methods=['GET', 'PUT'])
@require_auth
def user_settings():
    users_collection = current_app.config['USERS']
    if request.method == 'GET':
        user = users_collection.find_one(_user_id_filter(request.user_id))
        return jsonify(user.get('settings', {}) if user else {})
    data = request.get_json() or {}
    allowed_settings = ['currency', 'theme', 'language']
    update_data = {k: data[k] for k in allowed_settings if k in data}
    if update_data:
        if hasattr(users_collection, 'update_settings'):
            users_collection.update_settings(request.user_id, update_data)
        else:
            users_collection.update_one({'_id': request.user_id}, {'$set': {f'settings.{k}': v for k, v in update_data.items()}})
    return jsonify({'message': 'Configurações atualizadas com sucesso'})


# OAuth Google endpoints (kept similar)
@bp.route('/auth/google/login', methods=['GET'])
def google_login():
    oauth: OAuth = current_app.config['OAUTH']
    google = oauth.create_client('google')
    
    # Usa a URL base da API (api.alcahub.com.br) para o callback
    # Isso garante que o redirect_uri corresponda ao configurado no Google
    api_base_url = os.getenv('API_BASE_URL', 'https://api.alcahub.com.br')
    redirect_uri = f"{api_base_url}/api/auth/google/callback"
    
    import secrets
    nonce = secrets.token_urlsafe(16)
    session["__google_oidc_nonce__"] = nonce
    session.permanent = True  # Torna a sessão permanente
    session.modified = True  # Força o salvamento da sessão antes do redirect
    return google.authorize_redirect(redirect_uri, nonce=nonce)


@bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
    GOOGLE_CLIENT_ID = current_app.config['GOOGLE_CLIENT_ID']
    frontend_url = os.getenv('FRONTEND_URL', 'https://alcahub.com.br')
    
    if str(GOOGLE_CLIENT_ID).startswith('placeholder') or not GOOGLE_CLIENT_ID:
        error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Erro de Configuração</title>
    <meta charset="UTF-8">
</head>
<body>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
        Erro: Configuração OAuth do Google não definida. Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env
    </p>
    <script>
        setTimeout(function() {{
            window.location.href = {json.dumps(frontend_url + '/login?error=oauth_not_configured')};
        }}, 3000);
    </script>
</body>
</html>"""
        return error_html, 400, {'Content-Type': 'text/html; charset=utf-8'}
    
    try:
        oauth: OAuth = current_app.config['OAUTH']
        google = oauth.create_client('google')
        api_base_url = os.getenv('API_BASE_URL', 'https://api.alcahub.com.br')
        
        # Verifica se há erro na requisição
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', error)
            error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Erro de Autenticação</title>
    <meta charset="UTF-8">
</head>
<body>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
        Erro na autenticação: {error_description}
    </p>
    <script>
        setTimeout(function() {{
            window.location.href = {json.dumps(frontend_url + '/login?error=' + error)};
        }}, 3000);
    </script>
</body>
</html>"""
            return error_html, 400, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Tenta obter o token com verificação segura de state
        token = None
        nonce = None
        try:
            token = google.authorize_access_token()
            nonce = session.get("__google_oidc_nonce__")
        except MismatchingStateError as e:
            # SEGURANÇA: NÃO fazer fallback - sessão OAuth expirou
            error_msg = "Sessão OAuth expirou. Por favor, tente fazer login novamente."
            current_app.logger.warning(f"OAuth state mismatch (security): {e}")

            error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Erro de Autenticação</title>
    <meta charset="UTF-8">
</head>
<body>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
        {error_msg}
    </p>
    <script>
        setTimeout(function() {{
            window.location.href = {json.dumps(frontend_url + '/login?error=session_expired')};
        }}, 3000);
    </script>
</body>
</html>"""
            return error_html, 401, {'Content-Type': 'text/html; charset=utf-8'}
        
        if not token:
            raise Exception('Token de acesso não recebido do Google')

        # SEGURANÇA: Sempre validar nonce e assinatura
        if not nonce:
            raise Exception('Nonce inválido - sessão OAuth expirada')

        # Parse do ID token com verificação de assinatura (SEMPRE)
        resp = google.parse_id_token(token, nonce=nonce)
        session.pop("__google_oidc_nonce__", None)

        # Validações adicionais de segurança
        if resp.get('iss') not in ['https://accounts.google.com', 'accounts.google.com']:
            raise Exception('Token issuer inválido')

        GOOGLE_CLIENT_ID = current_app.config['GOOGLE_CLIENT_ID']
        if resp.get('aud') != GOOGLE_CLIENT_ID:
            raise Exception('Token audience inválido')
        google_user = {
            'sub': resp['sub'],
            'email': resp['email'],
            'name': resp['name'],
            'picture': resp.get('picture'),
            'email_verified': resp.get('email_verified', False)
        }
        users_collection = current_app.config['USERS']
        categories_collection = current_app.config['CATEGORIES']
        user = users_collection.find_one({'$or': [
            {'email': google_user['email']},
            {'auth_providers.provider': 'google', 'auth_providers.sub': google_user['sub']}
        ]})
        if user:
            provider_exists = any(p['provider'] == 'google' and p['sub'] == google_user['sub'] for p in user.get('auth_providers', []))
            if not provider_exists:
                users_collection.update_one({'_id': user['_id']}, {'$push': {'auth_providers': {'provider': 'google', 'sub': google_user['sub'], 'email_verified': google_user['email_verified']}}})
        else:
            user_data = {
                '_id': str(uuid.uuid4()),
                'name': google_user['name'],
                'email': google_user['email'],
                'password': None,
                'settings': {'currency': 'BRL', 'theme': 'light', 'language': 'pt'},
                'auth_providers': [{'provider': 'google', 'sub': google_user['sub'], 'email_verified': google_user['email_verified']}],
                'profile_picture': google_user.get('picture'),
                'created_at': datetime.utcnow()
            }
            users_collection.insert_one(user_data)
            user = user_data
            create_default_categories(categories_collection, user['_id'])
        jwt_token = generate_jwt(user['_id'])
        user_data = get_user_public(user)
        
        # Redireciona para o frontend com o token e dados do usuário
        # Usa uma página HTML intermediária que processa o token e redireciona
        frontend_url = os.getenv('FRONTEND_URL', 'https://app.alcahub.com.br')
        
        # Prepara dados para o frontend
        access_token = jwt_token['access_token']
        refresh_token = jwt_token['refresh_token']
        user_json_str = json.dumps(user_data)
        
        # Retorna HTML que processa o token e redireciona
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Autenticando...</title>
    <meta charset="UTF-8">
</head>
<body>
    <script>
        // Salva token e dados do usuário no localStorage
        try {{
            localStorage.setItem('auth_token', {json.dumps(access_token)});
            localStorage.setItem('refresh_token', {json.dumps(refresh_token)});
            localStorage.setItem('user_data', {json.dumps(user_json_str)});
            
            // Redireciona para o dashboard
            window.location.href = {json.dumps(frontend_url + '/dashboard')};
        }} catch (e) {{
            console.error('Erro ao salvar dados:', e);
            window.location.href = {json.dumps(frontend_url + '/login?error=storage_error')};
        }}
    </script>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
        Autenticando... Aguarde.
    </p>
</body>
</html>"""
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except MismatchingStateError as e:
        # Erro específico de state mismatch (sessão expirada ou múltiplas tentativas)
        error_msg = str(e)
        print(f"Erro MismatchingStateError no callback OAuth: {error_msg}")
        
        user_message = "A sessão expirou. Por favor, tente fazer login novamente."
        error_code = "session_expired"
        
        error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Erro de Autenticação</title>
    <meta charset="UTF-8">
</head>
<body>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
        {user_message}
    </p>
    <script>
        setTimeout(function() {{
            window.location.href = {json.dumps(frontend_url + '/login?error=' + error_code)};
        }}, 3000);
    </script>
</body>
</html>"""
        return error_html, 400, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        import traceback
        
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"Erro no callback OAuth: {error_msg}")
        print(error_trace)
        
        user_message = f"Erro no login com Google: {error_msg}"
        error_code = "oauth_failed"
        
        error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Erro de Autenticação</title>
    <meta charset="UTF-8">
</head>
<body>
    <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
        {user_message}
    </p>
    <script>
        setTimeout(function() {{
            window.location.href = {json.dumps(frontend_url + '/login?error=' + error_code)};
        }}, 3000);
    </script>
</body>
</html>"""
        return error_html, 500, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/auth/microsoft/login', methods=['GET'])
def microsoft_login():
    return jsonify({'error': 'Login com Microsoft não implementado ainda', 'message': 'Configure as credenciais do Microsoft OAuth no arquivo .env'}), 501


@bp.route('/auth/apple/login', methods=['GET'])
def apple_login():
    return jsonify({'error': 'Login com Apple não implementado ainda', 'message': 'Configure as credenciais do Apple OAuth no arquivo .env'}), 501


@bp.route('/auth/backup/export', methods=['GET'])
@require_auth
def export_backup():
    """Exporta todos os dados do usuário em formato JSON"""
    try:
        user_id = request.user_id
        categories_collection = current_app.config['CATEGORIES']
        transactions_collection = current_app.config['TRANSACTIONS']
        accounts_collection = current_app.config['ACCOUNTS']
        
        # Busca todos os dados do usuário
        categories = list(categories_collection.find({'user_id': user_id}))
        transactions = list(transactions_collection.find({'user_id': user_id}))
        accounts = list(accounts_collection.find({'user_id': user_id}))
        
        # Remove _id do MongoDB e converte para string
        backup_data = {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'categories': [dict(cat, _id=str(cat['_id'])) for cat in categories],
            'transactions': [dict(tx, _id=str(tx['_id'])) for tx in transactions],
            'accounts': [dict(acc, _id=str(acc['_id'])) for acc in accounts]
        }
        
        return jsonify(backup_data)
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar backup: {str(e)}'}), 500


@bp.route('/auth/backup/import', methods=['POST'])
@require_auth
def import_backup():
    """Importa backup de dados do usuário"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados do backup são obrigatórios'}), 400
        
        categories_collection = current_app.config['CATEGORIES']
        transactions_collection = current_app.config['TRANSACTIONS']
        accounts_collection = current_app.config['ACCOUNTS']
        
        imported_counts = {
            'categories': 0,
            'transactions': 0,
            'accounts': 0
        }
        
        # Importa categorias
        if 'categories' in data and isinstance(data['categories'], list):
            for cat in data['categories']:
                cat['user_id'] = user_id
                cat.pop('_id', None)  # Remove _id para criar novo
                # Verifica se já existe pelo nome e tipo
                existing = categories_collection.find_one({
                    'user_id': user_id,
                    'name': cat.get('name'),
                    'type': cat.get('type')
                })
                if not existing:
                    categories_collection.insert_one(cat)
                    imported_counts['categories'] += 1
        
        # Importa contas
        if 'accounts' in data and isinstance(data['accounts'], list):
            for acc in data['accounts']:
                acc['user_id'] = user_id
                acc.pop('_id', None)
                # Verifica se já existe pelo nome
                existing = accounts_collection.find_one({
                    'user_id': user_id,
                    'name': acc.get('name')
                })
                if not existing:
                    accounts_collection.insert_one(acc)
                    imported_counts['accounts'] += 1
        
        # Importa transações
        if 'transactions' in data and isinstance(data['transactions'], list):
            for tx in data['transactions']:
                tx['user_id'] = user_id
                tx.pop('_id', None)
                # Atualiza category_id e account_id se necessário
                if 'category_id' in tx:
                    # Tenta encontrar categoria pelo nome se ID não existir
                    pass
                transactions_collection.insert_one(tx)
                imported_counts['transactions'] += 1
        
        return jsonify({
            'message': 'Backup importado com sucesso',
            'imported': imported_counts
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao importar backup: {str(e)}'}), 500


@bp.route('/auth/data/clear', methods=['POST'])
@require_auth
def clear_all_data():
    """Limpa todos os dados do usuário (exceto a conta)"""
    try:
        user_id = request.user_id
        categories_collection = current_app.config['CATEGORIES']
        transactions_collection = current_app.config['TRANSACTIONS']
        accounts_collection = current_app.config['ACCOUNTS']
        
        # Deleta todos os dados do usuário
        categories_deleted = categories_collection.delete_many({'user_id': user_id}).deleted_count
        transactions_deleted = transactions_collection.delete_many({'user_id': user_id}).deleted_count
        accounts_deleted = accounts_collection.delete_many({'user_id': user_id}).deleted_count
        
        return jsonify({
            'message': 'Todos os dados foram limpos com sucesso',
            'deleted': {
                'categories': categories_deleted,
                'transactions': transactions_deleted,
                'accounts': accounts_deleted
            }
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao limpar dados: {str(e)}'}), 500