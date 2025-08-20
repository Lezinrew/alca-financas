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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)