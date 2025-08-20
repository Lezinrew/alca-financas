"""
Aplicação Mobills Pro - API Backend
Sistema de controle financeiro pessoal inspirado no Mobills
Desenvolvido com Flask 3, MongoDB, JWT e OAuth 2.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import bcrypt
import jwt
import os
import pandas as pd
from io import StringIO
import requests
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import uuid

# Carrega variáveis de ambiente
load_dotenv()

# Configuração da aplicação Flask
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configuração CORS
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))

# Configuração OAuth
oauth = OAuth(app)

# Conexão MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client[os.getenv('MONGO_DB')]

# Coleções do banco
users_collection = db.users
categories_collection = db.categories
transactions_collection = db.transactions

# Configurações JWT
JWT_SECRET = os.getenv('SECRET_KEY')
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', 24))

# Configurações OAuth
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Utilitários de autenticação
def hash_password(password):
    """Gera hash da senha usando bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    """Verifica se a senha corresponde ao hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def generate_jwt(user_id):
    """Gera token JWT para o usuário"""
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_jwt(token):
    """Verifica e decodifica token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator para rotas que requerem autenticação"""
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
    decorated.__name__ = f.__name__
    return decorated

# Rotas de Autenticação

@app.route('/api/register', methods=['POST'])
def register():
    """Registro de novo usuário"""
    data = request.get_json()
    
    # Validação de dados
    if not data.get('name') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Nome, email e senha são obrigatórios'}), 400
    
    # Verifica se email já existe
    if users_collection.find_one({'email': data['email']}):
        return jsonify({'error': 'Email já cadastrado'}), 400
    
    # Cria novo usuário
    user_data = {
        '_id': str(uuid.uuid4()),
        'name': data['name'],
        'email': data['email'],
        'password': hash_password(data['password']),
        'settings': {
            'currency': 'BRL',
            'theme': 'light',
            'language': 'pt'
        },
        'auth_providers': [],
        'created_at': datetime.utcnow()
    }
    
    users_collection.insert_one(user_data)
    
    # Cria categorias padrão
    default_categories = [
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Alimentação', 'type': 'expense', 'color': '#FF6B6B', 'icon': 'basket'},
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Transporte', 'type': 'expense', 'color': '#4ECDC4', 'icon': 'car-front'},
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Casa', 'type': 'expense', 'color': '#45B7D1', 'icon': 'house'},
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Saúde', 'type': 'expense', 'color': '#96CEB4', 'icon': 'heart-pulse'},
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Salário', 'type': 'income', 'color': '#52C41A', 'icon': 'currency-dollar'},
        {'_id': str(uuid.uuid4()), 'user_id': user_data['_id'], 'name': 'Freelance', 'type': 'income', 'color': '#1890FF', 'icon': 'briefcase'}
    ]
    
    categories_collection.insert_many(default_categories)
    
    # Gera token JWT
    token = generate_jwt(user_data['_id'])
    
    return jsonify({
        'message': 'Usuário criado com sucesso',
        'token': token,
        'user': {
            'id': user_data['_id'],
            'name': user_data['name'],
            'email': user_data['email']
        }
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Login do usuário"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400
    
    user = users_collection.find_one({'email': data['email']})
    if not user or not check_password(data['password'], user['password']):
        return jsonify({'error': 'Email ou senha incorretos'}), 401
    
    token = generate_jwt(user['_id'])
    
    return jsonify({
        'message': 'Login realizado com sucesso',
        'token': token,
        'user': {
            'id': user['_id'],
            'name': user['name'],
            'email': user['email']
        }
    })

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Reset de senha (placeholder)"""
    data = request.get_json()
    
    if not data.get('email'):
        return jsonify({'error': 'Email é obrigatório'}), 400
    
    # Em produção, implementar envio de email
    return jsonify({'message': 'Se o email existir, um link de reset será enviado'})

@app.route('/api/me', methods=['GET'])
@require_auth
def get_user():
    """Dados do usuário autenticado"""
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

# Rota de configurações
@app.route('/api/settings', methods=['GET', 'PUT'])
@require_auth
def user_settings():
    """Configurações do usuário"""
    if request.method == 'GET':
        user = users_collection.find_one({'_id': request.user_id})
        return jsonify(user.get('settings', {}))
    
    # PUT - Atualizar configurações
    data = request.get_json()
    allowed_settings = ['currency', 'theme', 'language']
    
    update_data = {}
    for key in allowed_settings:
        if key in data:
            update_data[f'settings.{key}'] = data[key]
    
    if update_data:
        users_collection.update_one(
            {'_id': request.user_id},
            {'$set': update_data}
        )
    
    return jsonify({'message': 'Configurações atualizadas com sucesso'})

# Rotas de Categorias

@app.route('/api/categories', methods=['GET', 'POST'])
@require_auth
def categories():
    """Gerenciamento de categorias"""
    if request.method == 'GET':
        user_categories = list(categories_collection.find({'user_id': request.user_id}))
        # Remove _id do MongoDB para evitar problemas de serialização
        for category in user_categories:
            category.pop('_id', None)
        return jsonify(user_categories)
    
    # POST - Criar nova categoria
    data = request.get_json()
    
    if not data.get('name') or not data.get('type'):
        return jsonify({'error': 'Nome e tipo da categoria são obrigatórios'}), 400
    
    if data['type'] not in ['income', 'expense']:
        return jsonify({'error': 'Tipo deve ser income ou expense'}), 400
    
    category_data = {
        '_id': str(uuid.uuid4()),
        'user_id': request.user_id,
        'name': data['name'],
        'type': data['type'],
        'color': data.get('color', '#6C757D'),
        'icon': data.get('icon', 'circle'),
        'created_at': datetime.utcnow()
    }
    
    categories_collection.insert_one(category_data)
    category_data.pop('_id')  # Remove _id para retorno
    
    return jsonify(category_data), 201

@app.route('/api/categories/<category_id>', methods=['PUT', 'DELETE'])
@require_auth
def category_detail(category_id):
    """Atualizar ou deletar categoria"""
    category = categories_collection.find_one({'_id': category_id, 'user_id': request.user_id})
    if not category:
        return jsonify({'error': 'Categoria não encontrada'}), 404
    
    if request.method == 'DELETE':
        # Verifica se há transações usando esta categoria
        transaction_count = transactions_collection.count_documents({'category_id': category_id})
        if transaction_count > 0:
            return jsonify({'error': f'Não é possível deletar. Existem {transaction_count} transações nesta categoria'}), 400
        
        categories_collection.delete_one({'_id': category_id})
        return jsonify({'message': 'Categoria deletada com sucesso'})
    
    # PUT - Atualizar categoria
    data = request.get_json()
    update_data = {}
    
    allowed_fields = ['name', 'color', 'icon']
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    if update_data:
        categories_collection.update_one(
            {'_id': category_id, 'user_id': request.user_id},
            {'$set': update_data}
        )
    
    return jsonify({'message': 'Categoria atualizada com sucesso'})

# Rotas de Transações

@app.route('/api/transactions', methods=['GET', 'POST'])
@require_auth
def transactions():
    """Gerenciamento de transações"""
    if request.method == 'GET':
        # Parâmetros de filtro opcionais
        month = request.args.get('month')
        year = request.args.get('year')
        category_id = request.args.get('category_id')
        transaction_type = request.args.get('type')
        
        # Constrói filtro
        filter_query = {'user_id': request.user_id}
        
        if month and year:
            start_date = datetime(int(year), int(month), 1)
            if int(month) == 12:
                end_date = datetime(int(year) + 1, 1, 1)
            else:
                end_date = datetime(int(year), int(month) + 1, 1)
            
            filter_query['date'] = {'$gte': start_date, '$lt': end_date}
        
        if category_id:
            filter_query['category_id'] = category_id
        
        if transaction_type:
            filter_query['type'] = transaction_type
        
        # Busca transações
        transactions_list = list(transactions_collection.find(filter_query).sort('date', -1))
        
        # Busca dados das categorias para incluir na resposta
        for transaction in transactions_list:
            category = categories_collection.find_one({'_id': transaction['category_id']})
            if category:
                transaction['category'] = {
                    'name': category['name'],
                    'color': category['color'],
                    'icon': category['icon']
                }
            transaction.pop('_id', None)  # Remove _id do MongoDB
        
        return jsonify(transactions_list)
    
    # POST - Criar nova transação
    data = request.get_json()
    
    # Validação de dados obrigatórios
    required_fields = ['description', 'amount', 'type', 'category_id', 'date']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    
    if data['type'] not in ['income', 'expense']:
        return jsonify({'error': 'Tipo deve ser income ou expense'}), 400
    
    # Verifica se a categoria existe e pertence ao usuário
    category = categories_collection.find_one({
        '_id': data['category_id'], 
        'user_id': request.user_id
    })
    if not category:
        return jsonify({'error': 'Categoria não encontrada'}), 404
    
    # Verifica se o tipo da transação combina com o tipo da categoria
    if data['type'] != category['type']:
        return jsonify({'error': 'Tipo da transação não combina com tipo da categoria'}), 400
    
    # Processa recorrência/parcelamento
    installments = data.get('installments', 1)
    is_recurring = data.get('is_recurring', False)
    
    transactions_to_create = []
    base_date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
    
    if installments > 1:
        # Parcelamento
        installment_amount = float(data['amount']) / installments
        
        for i in range(installments):
            transaction_date = base_date.replace(month=base_date.month + i) if base_date.month + i <= 12 else base_date.replace(year=base_date.year + 1, month=(base_date.month + i) - 12)
            
            transaction_data = {
                '_id': str(uuid.uuid4()),
                'user_id': request.user_id,
                'description': f"{data['description']} ({i+1}/{installments})",
                'amount': installment_amount,
                'type': data['type'],
                'category_id': data['category_id'],
                'date': transaction_date,
                'is_recurring': False,
                'installment_info': {
                    'current': i + 1,
                    'total': installments,
                    'parent_id': str(uuid.uuid4()) if i == 0 else transactions_to_create[0]['installment_info']['parent_id']
                },
                'created_at': datetime.utcnow()
            }
            
            if i == 0:
                transaction_data['installment_info']['parent_id'] = transaction_data['_id']
            
            transactions_to_create.append(transaction_data)
    
    else:
        # Transação única ou recorrente
        transaction_data = {
            '_id': str(uuid.uuid4()),
            'user_id': request.user_id,
            'description': data['description'],
            'amount': float(data['amount']),
            'type': data['type'],
            'category_id': data['category_id'],
            'date': base_date,
            'is_recurring': is_recurring,
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        
        transactions_to_create.append(transaction_data)
    
    # Insere transações no banco
    if transactions_to_create:
        transactions_collection.insert_many(transactions_to_create)
    
    return jsonify({
        'message': f'{len(transactions_to_create)} transação(ões) criada(s) com sucesso',
        'count': len(transactions_to_create)
    }), 201

@app.route('/api/transactions/<transaction_id>', methods=['PUT', 'DELETE'])
@require_auth
def transaction_detail(transaction_id):
    """Atualizar ou deletar transação"""
    transaction = transactions_collection.find_one({
        '_id': transaction_id, 
        'user_id': request.user_id
    })
    
    if not transaction:
        return jsonify({'error': 'Transação não encontrada'}), 404
    
    if request.method == 'DELETE':
        transactions_collection.delete_one({'_id': transaction_id})
        return jsonify({'message': 'Transação deletada com sucesso'})
    
    # PUT - Atualizar transação
    data = request.get_json()
    update_data = {}
    
    allowed_fields = ['description', 'amount', 'category_id', 'date']
    for field in allowed_fields:
        if field in data:
            if field == 'date':
                update_data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
            elif field == 'amount':
                update_data[field] = float(data[field])
            else:
                update_data[field] = data[field]
    
    if update_data:
        transactions_collection.update_one(
            {'_id': transaction_id, 'user_id': request.user_id},
            {'$set': update_data}
        )
    
    return jsonify({'message': 'Transação atualizada com sucesso'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)