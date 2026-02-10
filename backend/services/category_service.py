from typing import List, Dict, Any, Optional
import uuid
from utils.exceptions import ValidationException, NotFoundException


class CategoryService:
    def __init__(self, category_repo, transactions_repo):
        self.category_repo = category_repo
        self.transactions_repo = transactions_repo

    def list_categories(self, user_id: str) -> List[Dict[str, Any]]:
        categories = self.category_repo.find_by_user(user_id)
        for cat in categories:
            cat['id'] = cat.get('id') or cat.get('_id')
            cat.pop('_id', None)
        return categories

    def create_category(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
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

        new_id = str(uuid.uuid4())
        category_data = {
            'id': new_id,
            'user_id': user_id,
            'name': name,
            'type': category_type,
            'color': data.get('color', '#6366f1'),
            'icon': data.get('icon', 'circle'),
            'description': data.get('description', '')
        }
        created_id = self.category_repo.create(category_data)
        if created_id:
            category_data['id'] = created_id
        return category_data

    def get_category(self, user_id: str, category_id: str) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
            raise NotFoundException('Categoria não encontrada')
        category['id'] = category.get('id') or category.get('_id')
        category.pop('_id', None)
        return category

    def update_category(self, user_id: str, category_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
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

        updated_category = self.category_repo.find_by_id(category_id)
        updated_category['id'] = updated_category.get('id') or updated_category.get('_id')
        updated_category.pop('_id', None)
        return updated_category

    def delete_category(self, user_id: str, category_id: str) -> bool:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
            raise NotFoundException('Categoria não encontrada')

        if getattr(self.transactions_repo, 'count_documents', None) is not None:
            count = self.transactions_repo.count_documents({'category_id': category_id})
        else:
            count = len(self.transactions_repo.find_all({'category_id': category_id}))
        if count > 0:
            raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta categoria')

        return self.category_repo.delete(category_id)
