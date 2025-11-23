from typing import List, Dict, Any, Optional
import uuid
from repositories.category_repository import CategoryRepository
from utils.exceptions import ValidationException, NotFoundException

class CategoryService:
    def __init__(self, category_repo: CategoryRepository, transactions_collection):
        self.category_repo = category_repo
        self.transactions_collection = transactions_collection

    def list_categories(self, user_id: str) -> List[Dict[str, Any]]:
        categories = self.category_repo.find_by_user(user_id)
        for cat in categories:
            if '_id' in cat:
                cat['id'] = cat['_id']
                cat.pop('_id', None)
        return categories

    def create_category(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        # Validação mais robusta
        name = data.get('name', '').strip() if data.get('name') else ''
        category_type = data.get('type', '').strip() if data.get('type') else ''
        
        if not name:
            raise ValidationException('Nome da categoria é obrigatório')
        
        if not category_type:
            raise ValidationException('Tipo da categoria é obrigatório')
        
        if category_type not in ['income', 'expense']:
            raise ValidationException('Tipo deve ser income ou expense')

        existing = self.category_repo.find_by_name_and_type(user_id, name, category_type)
        if existing:
            raise ValidationException(f'Categoria "{name}" já existe para este tipo')

        category_data = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': name,
            'type': category_type,
            'color': data.get('color', '#6366f1'),
            'icon': data.get('icon', 'circle'),
            'description': data.get('description', '')
        }
        
        self.category_repo.create(category_data)
        
        category_data['id'] = category_data['_id']
        category_data.pop('_id', None)
        return category_data

    def get_category(self, user_id: str, category_id: str) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category['user_id'] != user_id:
            raise NotFoundException('Categoria não encontrada')
        
        category['id'] = category['_id']
        category.pop('_id', None)
        return category

    def update_category(self, user_id: str, category_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category['user_id'] != user_id:
            raise NotFoundException('Categoria não encontrada')

        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'color' in data:
            update_data['color'] = data['color']
        if 'icon' in data:
            update_data['icon'] = data['icon']
        if 'description' in data:
            update_data['description'] = data['description']

        if update_data:
            self.category_repo.update(category_id, update_data)
            
        # Return updated category
        updated_category = self.category_repo.find_by_id(category_id)
        updated_category['id'] = updated_category['_id']
        updated_category.pop('_id', None)
        return updated_category

    def delete_category(self, user_id: str, category_id: str) -> bool:
        category = self.category_repo.find_by_id(category_id)
        if not category or category['user_id'] != user_id:
            raise NotFoundException('Categoria não encontrada')

        # Check for transactions
        count = self.transactions_collection.count_documents({'category_id': category_id})
        if count > 0:
            raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta categoria')

        return self.category_repo.delete(category_id)
