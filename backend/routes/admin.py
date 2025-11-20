from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth, admin_required, hash_password
from services.user_service import create_user, create_default_categories
from datetime import datetime
import uuid

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@bp.route('/stats', methods=['GET'])
@require_auth
@admin_required
def get_stats():
    """Get system statistics"""
    users_collection = current_app.config['USERS']
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    accounts_collection = current_app.config['ACCOUNTS']

    total_users = users_collection.count_documents({})
    total_transactions = transactions_collection.count_documents({})
    total_categories = categories_collection.count_documents({})
    total_accounts = accounts_collection.count_documents({})

    # Active users (users with login in last 30 days - assuming we tracked it, 
    # but for now we can check users created recently or just total)
    # Since we don't track last_login yet, we'll return new users this month
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_users_month = users_collection.count_documents({'created_at': {'$gte': start_of_month}})

    return jsonify({
        'users': {
            'total': total_users,
            'new_this_month': new_users_month
        },
        'data': {
            'transactions': total_transactions,
            'categories': total_categories,
            'accounts': total_accounts
        },
        'system_status': 'healthy'
    })

@bp.route('/users', methods=['GET'])
@require_auth
@admin_required
def list_users():
    """List users with pagination and filtering"""
    users_collection = current_app.config['USERS']
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '')
    
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}}
        ]
    
    total = users_collection.count_documents(query)
    cursor = users_collection.find(query).skip((page - 1) * per_page).limit(per_page)
    
    users = []
    for user in cursor:
        users.append({
            'id': user['_id'],
            'name': user.get('name'),
            'email': user.get('email'),
            'is_admin': user.get('is_admin', False),
            'is_blocked': user.get('is_blocked', False),
            'created_at': user.get('created_at'),
            'auth_provider': user.get('auth_providers')[0]['provider'] if user.get('auth_providers') else 'email'
        })
        
    return jsonify({
        'users': users,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })

@bp.route('/users', methods=['POST'])
@require_auth
@admin_required
def create_user_admin():
    """Create a user manually by admin"""
    data = request.get_json()
    users_collection = current_app.config['USERS']
    categories_collection = current_app.config['CATEGORIES']

    if not data.get('email') or not data.get('password') or not data.get('name'):
        return jsonify({'error': 'Nome, email e senha são obrigatórios'}), 400

    if users_collection.find_one({'email': data['email']}):
        return jsonify({'error': 'Email já cadastrado'}), 400

    user_data = {
        'name': data['name'],
        'email': data['email'],
        'password': data['password'] # create_user handles hashing
    }
    
    # We need to adapt create_user signature or use it directly
    # user_service.create_user takes (collection, data, hash_function)
    # and data expects 'password' to be raw, it hashes it inside.
    
    try:
        user = create_user(users_collection, user_data, hash_password)
        create_default_categories(categories_collection, user['_id'])
        
        # If admin requested, set as admin
        if data.get('is_admin'):
            users_collection.update_one({'_id': user['_id']}, {'$set': {'is_admin': True}})
            user['is_admin'] = True
            
        return jsonify({
            'message': 'Usuário criado com sucesso',
            'user': {
                'id': user['_id'],
                'name': user['name'],
                'email': user['email'],
                'is_admin': user.get('is_admin', False)
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<user_id>', methods=['PUT'])
@require_auth
@admin_required
def update_user_status(user_id):
    """Update user status (block/unblock, promote/demote)"""
    data = request.get_json()
    users_collection = current_app.config['USERS']
    
    update_fields = {}
    if 'is_blocked' in data:
        update_fields['is_blocked'] = data['is_blocked']
    if 'is_admin' in data:
        update_fields['is_admin'] = data['is_admin']
        
    if not update_fields:
        return jsonify({'error': 'Nenhum campo para atualizar'}), 400
        
    result = users_collection.update_one({'_id': user_id}, {'$set': update_fields})
    
    if result.matched_count == 0:
        return jsonify({'error': 'Usuário não encontrado'}), 404
        
    return jsonify({'message': 'Usuário atualizado com sucesso'})

@bp.route('/users/<user_id>', methods=['DELETE'])
@require_auth
@admin_required
def delete_user(user_id):
    """Delete user and all their data"""
    # Prevent deleting self
    if user_id == request.user_id:
        return jsonify({'error': 'Não é possível deletar a si mesmo'}), 400

    users_collection = current_app.config['USERS']
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    accounts_collection = current_app.config['ACCOUNTS']
    
    user = users_collection.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
        
    # Delete everything
    users_collection.delete_one({'_id': user_id})
    categories_collection.delete_many({'user_id': user_id})
    transactions_collection.delete_many({'user_id': user_id})
    accounts_collection.delete_many({'user_id': user_id})
    
    return jsonify({'message': 'Usuário e dados deletados com sucesso'})
