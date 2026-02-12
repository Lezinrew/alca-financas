from flask import Blueprint, request, jsonify, current_app, Response
from utils.auth_utils import require_auth, admin_required, hash_password
from services.user_service import create_user, create_default_categories
from utils.admin_logger import log_admin_action, get_admin_logs
from datetime import datetime, timedelta
import uuid
import csv
import io

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@bp.route('/stats', methods=['GET'])
@require_auth
@admin_required
def get_stats():
    """Get system statistics with advanced metrics"""
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

    # Users active in last 24h (created/updated recently as proxy)
    last_24h = datetime.utcnow() - timedelta(days=1)
    active_24h = users_collection.count_documents({'created_at': {'$gte': last_24h}})

    # Calculate total financial volume
    total_volume = 0.0
    try:
        pipeline = [
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]
        result = list(transactions_collection.aggregate(pipeline))
        if result:
            total_volume = float(result[0].get('total', 0))
    except Exception as e:
        print(f"Error calculating volume: {e}")

    # Top categories by usage
    top_categories = []
    try:
        pipeline = [
            {'$group': {'_id': '$category_id', 'count': {'$sum': 1}, 'total': {'$sum': '$amount'}}},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]
        for cat in transactions_collection.aggregate(pipeline):
            category = categories_collection.find_one({'_id': cat['_id']})
            if category:
                top_categories.append({
                    'id': cat['_id'],
                    'name': category.get('name', 'Sem nome'),
                    'count': cat['count'],
                    'total': float(cat.get('total', 0))
                })
    except Exception as e:
        print(f"Error getting top categories: {e}")

    # Monthly growth (last 6 months)
    monthly_growth = []
    try:
        for i in range(5, -1, -1):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
            month_end = month_start.replace(day=28) + timedelta(days=4)
            month_end = month_end.replace(day=1)

            count = users_collection.count_documents({
                'created_at': {'$gte': month_start, '$lt': month_end}
            })
            monthly_growth.append({
                'month': month_start.strftime('%b'),
                'users': count
            })
    except Exception as e:
        print(f"Error calculating monthly growth: {e}")

    return jsonify({
        'users': {
            'total': total_users,
            'new_this_month': new_users_month,
            'active_24h': active_24h
        },
        'data': {
            'transactions': total_transactions,
            'categories': total_categories,
            'accounts': total_accounts
        },
        'financial': {
            'total_volume': total_volume,
            'top_categories': top_categories
        },
        'growth': {
            'monthly': monthly_growth
        },
        'system_status': 'healthy'
    })

@bp.route('/users/<user_id>/details', methods=['GET'])
@require_auth
@admin_required
def get_user_details(user_id):
    """Get detailed information about a specific user"""
    users_collection = current_app.config['USERS']
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    accounts_collection = current_app.config['ACCOUNTS']

    user = users_collection.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Get user statistics
    total_transactions = transactions_collection.count_documents({'user_id': user_id})
    total_categories = categories_collection.count_documents({'user_id': user_id})
    total_accounts = accounts_collection.count_documents({'user_id': user_id})

    # Calculate financial summary
    total_income = 0.0
    total_expense = 0.0
    try:
        pipeline_income = [
            {'$match': {'user_id': user_id, 'type': 'income'}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]
        result = list(transactions_collection.aggregate(pipeline_income))
        if result:
            total_income = float(result[0].get('total', 0))

        pipeline_expense = [
            {'$match': {'user_id': user_id, 'type': 'expense'}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]
        result = list(transactions_collection.aggregate(pipeline_expense))
        if result:
            total_expense = float(result[0].get('total', 0))
    except Exception as e:
        print(f"Error calculating financial summary: {e}")

    # Get recent transactions
    recent_transactions = []
    try:
        cursor = transactions_collection.find({'user_id': user_id}).sort('date', -1).limit(10)
        for trans in cursor:
            recent_transactions.append({
                'id': trans['_id'],
                'description': trans.get('description', ''),
                'amount': float(trans.get('amount', 0)),
                'type': trans.get('type', ''),
                'date': trans.get('date', ''),
                'category_id': trans.get('category_id', '')
            })
    except Exception as e:
        print(f"Error getting recent transactions: {e}")

    # Get accounts
    user_accounts = []
    try:
        cursor = accounts_collection.find({'user_id': user_id})
        for acc in cursor:
            user_accounts.append({
                'id': acc['_id'],
                'name': acc.get('name', ''),
                'balance': float(acc.get('balance', 0)),
                'type': acc.get('type', '')
            })
    except Exception as e:
        print(f"Error getting accounts: {e}")

    return jsonify({
        'user': {
            'id': user['_id'],
            'name': user.get('name'),
            'email': user.get('email'),
            'is_admin': user.get('is_admin', False),
            'is_blocked': user.get('is_blocked', False),
            'created_at': user.get('created_at'),
            'auth_provider': user.get('auth_providers', [{}])[0].get('provider', 'email') if user.get('auth_providers') else 'email'
        },
        'stats': {
            'transactions': total_transactions,
            'categories': total_categories,
            'accounts': total_accounts,
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': total_income - total_expense
        },
        'recent_transactions': recent_transactions,
        'accounts': user_accounts
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

    # Get user before update for logging
    user = users_collection.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    update_fields = {}
    action = None
    details = {'user_name': user.get('name'), 'user_email': user.get('email')}

    if 'is_blocked' in data:
        update_fields['is_blocked'] = data['is_blocked']
        action = 'block_user' if data['is_blocked'] else 'unblock_user'
        details['is_blocked'] = data['is_blocked']

    if 'is_admin' in data:
        update_fields['is_admin'] = data['is_admin']
        action = 'promote_admin' if data['is_admin'] else 'demote_admin'
        details['is_admin'] = data['is_admin']

    if not update_fields:
        return jsonify({'error': 'Nenhum campo para atualizar'}), 400

    result = users_collection.update_one({'_id': user_id}, {'$set': update_fields})

    if result.matched_count == 0:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Log the action
    if action:
        log_admin_action(
            admin_id=request.user_id,
            admin_email=request.user_email,
            action=action,
            target_id=user_id,
            details=details
        )

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

    # Log action before deleting
    log_admin_action(
        admin_id=request.user_id,
        admin_email=request.user_email,
        action='delete_user',
        target_id=user_id,
        details={'user_name': user.get('name'), 'user_email': user.get('email')}
    )

    # Delete everything
    users_collection.delete_one({'_id': user_id})
    categories_collection.delete_many({'user_id': user_id})
    transactions_collection.delete_many({'user_id': user_id})
    accounts_collection.delete_many({'user_id': user_id})

    return jsonify({'message': 'Usuário e dados deletados com sucesso'})

@bp.route('/logs', methods=['GET'])
@require_auth
@admin_required
def list_admin_logs():
    """List admin action logs with pagination"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    action_filter = request.args.get('action')
    admin_filter = request.args.get('admin_id')

    skip = (page - 1) * per_page
    logs = get_admin_logs(limit=per_page, skip=skip, action_filter=action_filter, admin_filter=admin_filter)

    return jsonify({
        'logs': logs,
        'page': page,
        'per_page': per_page
    })

@bp.route('/users/<user_id>/export', methods=['GET'])
@require_auth
@admin_required
def export_user_data(user_id):
    """Export all user data as CSV"""
    users_collection = current_app.config['USERS']
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    accounts_collection = current_app.config['ACCOUNTS']

    user = users_collection.find_one({'_id': user_id})
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['=== DADOS DO USUÁRIO ==='])
    writer.writerow(['Nome', user.get('name', '')])
    writer.writerow(['Email', user.get('email', '')])
    writer.writerow(['Cadastro', user.get('created_at', '')])
    writer.writerow([])

    # Accounts
    writer.writerow(['=== CONTAS ==='])
    writer.writerow(['Nome', 'Tipo', 'Saldo'])
    for account in accounts_collection.find({'user_id': user_id}):
        writer.writerow([
            account.get('name', ''),
            account.get('type', ''),
            account.get('balance', 0)
        ])
    writer.writerow([])

    # Categories
    writer.writerow(['=== CATEGORIAS ==='])
    writer.writerow(['Nome', 'Tipo', 'Cor'])
    for category in categories_collection.find({'user_id': user_id}):
        writer.writerow([
            category.get('name', ''),
            category.get('type', ''),
            category.get('color', '')
        ])
    writer.writerow([])

    # Transactions
    writer.writerow(['=== TRANSAÇÕES ==='])
    writer.writerow(['Data', 'Descrição', 'Tipo', 'Valor', 'Categoria', 'Conta'])

    # Get category and account names for better readability
    categories_map = {cat['_id']: cat.get('name', '') for cat in categories_collection.find({'user_id': user_id})}
    accounts_map = {acc['_id']: acc.get('name', '') for acc in accounts_collection.find({'user_id': user_id})}

    for trans in transactions_collection.find({'user_id': user_id}).sort('date', -1):
        writer.writerow([
            trans.get('date', ''),
            trans.get('description', ''),
            trans.get('type', ''),
            trans.get('amount', 0),
            categories_map.get(trans.get('category_id', ''), ''),
            accounts_map.get(trans.get('account_id', ''), '')
        ])

    # Log action
    log_admin_action(
        admin_id=request.user_id,
        admin_email=request.user_email,
        action='export_user_data',
        target_id=user_id,
        details={'user_name': user.get('name'), 'user_email': user.get('email')}
    )

    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=user_data_{user_id}_{datetime.now().strftime("%Y%m%d")}.csv'
        }
    )
