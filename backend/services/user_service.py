from datetime import datetime
import uuid
from typing import Dict, Any


def create_default_categories(categories_collection, user_id: str):
    default_categories = [
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Alimentação', 'type': 'expense', 'color': '#FF6B6B', 'icon': 'basket'},
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Transporte', 'type': 'expense', 'color': '#4ECDC4', 'icon': 'car-front'},
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Casa', 'type': 'expense', 'color': '#45B7D1', 'icon': 'house'},
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Saúde', 'type': 'expense', 'color': '#96CEB4', 'icon': 'heart-pulse'},
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Salário', 'type': 'income', 'color': '#52C41A', 'icon': 'currency-dollar'},
        {'_id': str(uuid.uuid4()), 'user_id': user_id, 'name': 'Freelance', 'type': 'income', 'color': '#1890FF', 'icon': 'briefcase'}
    ]
    categories_collection.insert_many(default_categories)


def create_user(users_collection, data: Dict[str, Any], hash_password):
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
    return user_data


def get_user_public(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': user['_id'],
        'name': user.get('name'),
        'email': user.get('email')
    }


