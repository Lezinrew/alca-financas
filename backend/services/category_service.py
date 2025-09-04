from datetime import datetime
import uuid
from typing import Dict, Any, List


def list_categories(categories_collection, user_id: str) -> List[Dict[str, Any]]:
    user_categories = list(categories_collection.find({'user_id': user_id}))
    for category in user_categories:
        if '_id' in category:
            category['id'] = category['_id']
            category.pop('_id', None)
    return user_categories


def create_category(categories_collection, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    category_data = {
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'name': data['name'],
        'type': data['type'],
        'color': data.get('color', '#6C757D'),
        'icon': data.get('icon', 'circle'),
        'created_at': datetime.utcnow()
    }
    categories_collection.insert_one(category_data)
    category_data['id'] = category_data['_id']
    category_data.pop('_id')
    return category_data


def update_category(categories_collection, user_id: str, category_id: str, data: Dict[str, Any]):
    allowed_fields = ['name', 'color', 'icon']
    update_data = {field: data[field] for field in allowed_fields if field in data}
    if update_data:
        categories_collection.update_one(
            {'_id': category_id, 'user_id': user_id},
            {'$set': update_data}
        )


def delete_category(categories_collection, transactions_collection, user_id: str, category_id: str) -> bool:
    transaction_count = transactions_collection.count_documents({'category_id': category_id})
    if transaction_count > 0:
        return False
    categories_collection.delete_one({'_id': category_id})
    return True


