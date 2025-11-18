# backend/routes/auth.py

from flask import Blueprint, request, jsonify, current_app, session
from authlib.integrations.flask_client import OAuth
from datetime import datetime
import uuid

from utils.auth_utils import hash_password, check_password, generate_jwt, require_auth
from services.user_service import create_user, create_default_categories, get_user_public


# Remova o 'url_prefix' daqui. Ele será definido em app.py
bp = Blueprint('auth', __name__)


# Adicione '/auth' a todas as rotas de autenticação para agrupar logicamente os endpoints.
@bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data.get('name') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Nome, email e senha são obrigatórios'}), 400

    users_collection = current_app.config['USERS']
    categories_collection = current_app.config['CATEGORIES']

    if users_collection.find_one({'email': data['email']}):
        return jsonify({'error': 'Email já cadastrado'}), 400

    user = create_user(users_collection, data, hash_password)
    create_default_categories(categories_collection, user['_id'])

    token = generate_jwt(user['_id'])
    return jsonify({'message': 'Usuário criado com sucesso', 'token': token, 'user': get_user_public(user)}), 201


@bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400
    users_collection = current_app.config['USERS']
    user = users_collection.find_one({'email': data['email']})
    if not user or not check_password(data['password'], user['password']):
        return jsonify({'error': 'Email ou senha incorretos'}), 401
    token = generate_jwt(user['_id'])
    return jsonify({'message': 'Login realizado com sucesso', 'token': token, 'user': get_user_public(user)})


@bp.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    if not data.get('email'):
        return jsonify({'error': 'Email é obrigatório'}), 400
    return jsonify({'message': 'Se o email existir, um link de reset será enviado'})


@bp.route('/auth/me', methods=['GET'])
@require_auth
def get_user():
    users_collection = current_app.config['USERS']
    user = users_collection.find_one({'_id': request.user_id})
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    return jsonify({
        'id': user['_id'],
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
        user = users_collection.find_one({'_id': request.user_id})
        return jsonify(user.get('settings', {}))
    data = request.get_json()
    allowed_settings = ['currency', 'theme', 'language']
    update_data = {f'settings.{k}': data[k] for k in allowed_settings if k in data}
    if update_data:
        users_collection.update_one({'_id': request.user_id}, {'$set': update_data})
    return jsonify({'message': 'Configurações atualizadas com sucesso'})


# OAuth Google endpoints (kept similar)
@bp.route('/auth/google/login', methods=['GET'])
def google_login():
    oauth: OAuth = current_app.config['OAUTH']
    google = oauth.create_client('google')
    redirect_uri = request.url_root + 'api/auth/google/callback'
    import secrets
    nonce = secrets.token_urlsafe(16)
    session["__google_oidc_nonce__"] = nonce
    return google.authorize_redirect(redirect_uri, nonce=nonce)


@bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
    GOOGLE_CLIENT_ID = current_app.config['GOOGLE_CLIENT_ID']
    if str(GOOGLE_CLIENT_ID).startswith('placeholder'):
        return jsonify({'error': 'Configuração OAuth do Google não definida', 'message': 'Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env'}), 400
    try:
        oauth: OAuth = current_app.config['OAUTH']
        google = oauth.create_client('google')
        token = google.authorize_access_token()
        resp = google.parse_id_token(token, nonce=session.get("__google_oidc_nonce__"))
        session.pop("__google_oidc_nonce__", None)
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
        return jsonify({'success': True, 'token': jwt_token, 'user': get_user_public(user)})
    except Exception as e:
        return jsonify({'error': f'Erro no login com Google: {str(e)}'}), 500


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