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
        # Convert _id to id for frontend compatibility
        for category in user_categories:
            if '_id' in category:
                category['id'] = category['_id']
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

# Rota do Dashboard

@app.route('/api/dashboard', methods=['GET'])
@require_auth
def dashboard():
    """Dados do dashboard"""
    # Parâmetros de período (padrão: mês atual)
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    
    # Data inicial e final do período
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # Filtro base para o período
    period_filter = {
        'user_id': request.user_id,
        'date': {'$gte': start_date, '$lt': end_date}
    }
    
    # Busca todas as transações do período
    transactions_list = list(transactions_collection.find(period_filter))
    
    # Calcula totais
    total_income = sum(t['amount'] for t in transactions_list if t['type'] == 'income')
    total_expense = sum(t['amount'] for t in transactions_list if t['type'] == 'expense')
    balance = total_income - total_expense
    
    # Transações recentes (últimas 10)
    recent_transactions = list(transactions_collection.find(
        {'user_id': request.user_id}
    ).sort('date', -1).limit(10))
    
    # Inclui dados das categorias nas transações recentes
    for transaction in recent_transactions:
        category = categories_collection.find_one({'_id': transaction['category_id']})
        if category:
            transaction['category'] = {
                'name': category['name'],
                'color': category['color'],
                'icon': category['icon']
            }
        transaction.pop('_id', None)
    
    # Análise por categoria (despesas)
    expense_pipeline = [
        {'$match': {**period_filter, 'type': 'expense'}},
        {'$group': {
            '_id': '$category_id',
            'total': {'$sum': '$amount'},
            'count': {'$sum': 1}
        }},
        {'$sort': {'total': -1}}
    ]
    
    expense_by_category = []
    for item in transactions_collection.aggregate(expense_pipeline):
        category = categories_collection.find_one({'_id': item['_id']})
        if category:
            expense_by_category.append({
                'category_id': item['_id'],
                'category_name': category['name'],
                'category_color': category['color'],
                'category_icon': category['icon'],
                'total': item['total'],
                'count': item['count'],
                'percentage': (item['total'] / total_expense * 100) if total_expense > 0 else 0
            })
    
    # Análise por categoria (receitas)
    income_pipeline = [
        {'$match': {**period_filter, 'type': 'income'}},
        {'$group': {
            '_id': '$category_id',
            'total': {'$sum': '$amount'},
            'count': {'$sum': 1}
        }},
        {'$sort': {'total': -1}}
    ]
    
    income_by_category = []
    for item in transactions_collection.aggregate(income_pipeline):
        category = categories_collection.find_one({'_id': item['_id']})
        if category:
            income_by_category.append({
                'category_id': item['_id'],
                'category_name': category['name'],
                'category_color': category['color'],
                'category_icon': category['icon'],
                'total': item['total'],
                'count': item['count'],
                'percentage': (item['total'] / total_income * 100) if total_income > 0 else 0
            })
    
    return jsonify({
        'period': {
            'month': month,
            'year': year,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'summary': {
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': balance,
            'transactions_count': len(transactions_list)
        },
        'recent_transactions': recent_transactions,
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category
    })

# Rota de Importação CSV

@app.route('/api/transactions/import', methods=['POST'])
@require_auth
def import_transactions():
    """Importar transações via CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo CSV é obrigatório'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Apenas arquivos CSV são aceitos'}), 400
    
    try:
        # Lê arquivo CSV
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = pd.read_csv(stream)
        
        # Valida colunas obrigatórias
        required_columns = ['description', 'amount', 'type', 'category_name', 'date']
        missing_columns = [col for col in required_columns if col not in csv_input.columns]
        
        if missing_columns:
            return jsonify({
                'error': f'Colunas obrigatórias ausentes: {", ".join(missing_columns)}',
                'required_columns': required_columns,
                'found_columns': list(csv_input.columns)
            }), 400
        
        # Busca categorias do usuário para mapeamento
        user_categories = {cat['name']: cat['_id'] for cat in categories_collection.find({'user_id': request.user_id})}
        
        imported_transactions = []
        errors = []
        
        for index, row in csv_input.iterrows():
            try:
                # Valida tipo
                if row['type'] not in ['income', 'expense']:
                    errors.append(f'Linha {index + 2}: Tipo deve ser income ou expense')
                    continue
                
                # Mapeia categoria
                category_id = user_categories.get(row['category_name'])
                if not category_id:
                    errors.append(f'Linha {index + 2}: Categoria "{row["category_name"]}" não encontrada')
                    continue
                
                # Valida e converte data
                try:
                    transaction_date = pd.to_datetime(row['date']).to_pydatetime()
                except:
                    errors.append(f'Linha {index + 2}: Data inválida "{row["date"]}"')
                    continue
                
                # Valida e converte valor
                try:
                    amount = float(row['amount'])
                    if amount <= 0:
                        errors.append(f'Linha {index + 2}: Valor deve ser positivo')
                        continue
                except:
                    errors.append(f'Linha {index + 2}: Valor inválido "{row["amount"]}"')
                    continue
                
                # Cria transação
                transaction_data = {
                    '_id': str(uuid.uuid4()),
                    'user_id': request.user_id,
                    'description': str(row['description']).strip(),
                    'amount': amount,
                    'type': row['type'],
                    'category_id': category_id,
                    'date': transaction_date,
                    'is_recurring': False,
                    'installment_info': None,
                    'imported': True,
                    'created_at': datetime.utcnow()
                }
                
                imported_transactions.append(transaction_data)
                
            except Exception as e:
                errors.append(f'Linha {index + 2}: Erro inesperado - {str(e)}')
        
        # Insere transações válidas no banco
        if imported_transactions:
            transactions_collection.insert_many(imported_transactions)
        
        result = {
            'message': f'{len(imported_transactions)} transações importadas com sucesso',
            'imported_count': len(imported_transactions),
            'error_count': len(errors)
        }
        
        if errors:
            result['errors'] = errors
        
        return jsonify(result), 201 if imported_transactions else 400
        
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500

# Rotas de OAuth (Google, Microsoft, Apple)

@app.route('/api/auth/google/login', methods=['GET'])
def google_login():
    """Inicia processo de login com Google"""
    google = oauth.create_client('google')
    redirect_uri = request.url_root + 'api/auth/google/callback'
    return google.authorize_redirect(redirect_uri)

@app.route('/api/auth/google/callback', methods=['GET'])
def google_callback():
    """Callback do login com Google"""
    if GOOGLE_CLIENT_ID.startswith('placeholder'):
        return jsonify({
            'error': 'Configuração OAuth do Google não definida',
            'message': 'Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env'
        }), 400
    
    try:
        google = oauth.create_client('google')
        token = google.authorize_access_token()
        
        # Obtém dados do usuário do Google
        resp = google.parse_id_token(token)
        google_user = {
            'sub': resp['sub'],
            'email': resp['email'],
            'name': resp['name'],
            'picture': resp.get('picture'),
            'email_verified': resp.get('email_verified', False)
        }
        
        # Verifica se usuário já existe
        user = users_collection.find_one({
            '$or': [
                {'email': google_user['email']},
                {'auth_providers.provider': 'google', 'auth_providers.sub': google_user['sub']}
            ]
        })
        
        if user:
            # Usuário existente - atualiza dados do provedor
            provider_exists = any(p['provider'] == 'google' and p['sub'] == google_user['sub'] 
                                for p in user.get('auth_providers', []))
            
            if not provider_exists:
                users_collection.update_one(
                    {'_id': user['_id']},
                    {'$push': {
                        'auth_providers': {
                            'provider': 'google',
                            'sub': google_user['sub'],
                            'email_verified': google_user['email_verified']
                        }
                    }}
                )
        else:
            # Novo usuário via Google
            user_data = {
                '_id': str(uuid.uuid4()),
                'name': google_user['name'],
                'email': google_user['email'],
                'password': None,  # Não tem senha local
                'settings': {
                    'currency': 'BRL',
                    'theme': 'light',
                    'language': 'pt'
                },
                'auth_providers': [{
                    'provider': 'google',
                    'sub': google_user['sub'],
                    'email_verified': google_user['email_verified']
                }],
                'profile_picture': google_user.get('picture'),
                'created_at': datetime.utcnow()
            }
            
            users_collection.insert_one(user_data)
            user = user_data
            
            # Cria categorias padrão para novo usuário
            default_categories = [
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Alimentação', 'type': 'expense', 'color': '#FF6B6B', 'icon': 'basket'},
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Transporte', 'type': 'expense', 'color': '#4ECDC4', 'icon': 'car-front'},
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Casa', 'type': 'expense', 'color': '#45B7D1', 'icon': 'house'},
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Saúde', 'type': 'expense', 'color': '#96CEB4', 'icon': 'heart-pulse'},
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Salário', 'type': 'income', 'color': '#52C41A', 'icon': 'currency-dollar'},
                {'_id': str(uuid.uuid4()), 'user_id': user['_id'], 'name': 'Freelance', 'type': 'income', 'color': '#1890FF', 'icon': 'briefcase'}
            ]
            categories_collection.insert_many(default_categories)
        
        # Gera token JWT
        jwt_token = generate_jwt(user['_id'])
        
        # Em produção, redirecionar para frontend com token
        return jsonify({
            'success': True,
            'token': jwt_token,
            'user': {
                'id': user['_id'],
                'name': user['name'],
                'email': user['email']
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro no login com Google: {str(e)}'}), 500

@app.route('/api/auth/microsoft/login', methods=['GET'])
def microsoft_login():
    """Placeholder para login com Microsoft"""
    return jsonify({
        'error': 'Login com Microsoft não implementado ainda',
        'message': 'Configure as credenciais do Microsoft OAuth no arquivo .env'
    }), 501

@app.route('/api/auth/apple/login', methods=['GET'])
def apple_login():
    """Placeholder para login com Apple"""
    return jsonify({
        'error': 'Login com Apple não implementado ainda',
        'message': 'Configure as credenciais do Apple OAuth no arquivo .env'
    }), 501

# Configuração OAuth clients
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)