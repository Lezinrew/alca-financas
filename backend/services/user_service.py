from datetime import datetime
import uuid
from typing import Dict, Any


def create_default_categories(categories_repo_or_collection, user_id: str):
    """
    Cria categorias padrão para um usuário.
    Aceita tanto repositório Supabase quanto collection MongoDB para compatibilidade.
    """
    default_categories = [
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Alimentação', 'type': 'expense', 'color': '#FF6B6B', 'icon': 'basket', 'active': True},
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Transporte', 'type': 'expense', 'color': '#4ECDC4', 'icon': 'car-front', 'active': True},
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Casa', 'type': 'expense', 'color': '#45B7D1', 'icon': 'house', 'active': True},
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Saúde', 'type': 'expense', 'color': '#96CEB4', 'icon': 'heart-pulse', 'active': True},
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Salário', 'type': 'income', 'color': '#52C41A', 'icon': 'currency-dollar', 'active': True},
        {'id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Freelance', 'type': 'income', 'color': '#1890FF', 'icon': 'briefcase', 'active': True}
    ]
    
    # Verificar se é repositório Supabase ou collection MongoDB
    if hasattr(categories_repo_or_collection, 'create'):
        # É um repositório Supabase
        for category in default_categories:
            categories_repo_or_collection.create(category)
    elif hasattr(categories_repo_or_collection, 'insert_many'):
        # É uma collection MongoDB (compatibilidade)
        # Converter 'id' para '_id' para MongoDB
        mongo_categories = []
        for cat in default_categories:
            mongo_cat = cat.copy()
            mongo_cat['_id'] = mongo_cat.pop('id')
            mongo_categories.append(mongo_cat)
        categories_repo_or_collection.insert_many(mongo_categories)
    else:
        raise ValueError("categories_repo_or_collection deve ser um repositório ou collection válido")


def create_user(users_repo_or_collection, data: Dict[str, Any], hash_password):
    """
    Cria usuário na tabela customizada.
    Aceita tanto repositório Supabase quanto collection MongoDB para compatibilidade.
    Nota: Para Supabase Auth, use SupabaseAuthService.sign_up() ao invés desta função.
    """
    user_id = data.get('id') or str(uuid.uuid4())
    user_data = {
        'id': user_id,
        'name': data['name'],
        'email': data['email'],
        'password': hash_password(data['password']) if hash_password else None,
        'settings': {
            'currency': 'BRL',
            'theme': 'light',
            'language': 'pt'
        },
        'auth_providers': [],
        'is_admin': False
    }
    
    # Verificar se é repositório Supabase ou collection MongoDB
    if hasattr(users_repo_or_collection, 'create'):
        # É um repositório Supabase
        users_repo_or_collection.create(user_data)
        user_data['_id'] = user_data['id']  # Para compatibilidade
    elif hasattr(users_repo_or_collection, 'insert_one'):
        # É uma collection MongoDB (compatibilidade)
        mongo_user = user_data.copy()
        mongo_user['_id'] = mongo_user.pop('id')
        users_repo_or_collection.insert_one(mongo_user)
        user_data = mongo_user
    else:
        raise ValueError("users_repo_or_collection deve ser um repositório ou collection válido")
    
    return user_data


def get_user_public(user: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai dados públicos do usuário (compatível com MongoDB e Supabase)"""
    # MongoDB usa '_id', Supabase usa 'id'
    user_id = user.get('id') or user.get('_id')
    return {
        'id': str(user_id) if user_id else None,
        'name': user.get('name'),
        'email': user.get('email')
    }


