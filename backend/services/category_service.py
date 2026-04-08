from typing import List, Dict, Any, Optional
import uuid
import logging
from utils.exceptions import ValidationException, NotFoundException

logger = logging.getLogger(__name__)


class CategoryService:
    def __init__(self, category_repo, transactions_repo):
        self.category_repo = category_repo
        self.transactions_repo = transactions_repo

    def list_categories(self, user_id: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        categories = self.category_repo.find_by_user(user_id, tenant_id=tenant_id)
        for cat in categories:
            cat['id'] = cat.get('id') or cat.get('_id')
            cat.pop('_id', None)
        return categories

    def create_category(self, user_id: str, data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        name = data.get('name', '').strip() if data.get('name') else ''
        category_type = data.get('type', '').strip() if data.get('type') else ''

        if not name:
            raise ValidationException('Nome da categoria é obrigatório')
        if not category_type:
            raise ValidationException('Tipo da categoria é obrigatório')
        if category_type not in ['income', 'expense']:
            raise ValidationException('Tipo deve ser income ou expense')
        if not tenant_id:
            raise ValidationException('Workspace não identificado. Por favor, recarregue a página ou faça login novamente.')

        existing = self.category_repo.find_by_name_and_type(user_id, name, category_type, tenant_id=tenant_id)
        if existing:
            raise ValidationException(f'Categoria "{name}" já existe para este tipo')

        new_id = str(uuid.uuid4())
        category_data = {
            'id': new_id,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'name': name,
            'type': category_type,
            'color': data.get('color', '#6366f1'),
            'icon': data.get('icon', 'circle'),
            'description': data.get('description', '')
        }

        try:
            created_id = self.category_repo.create(category_data)
            if created_id:
                category_data['id'] = created_id
            logger.info(f'Categoria criada: {name} ({category_type}) - user_id: {user_id}')
            return category_data
        except Exception as e:
            logger.error(f'Erro ao criar categoria: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao salvar categoria no banco de dados. Detalhe: {str(e)}')

    def get_category(self, user_id: str, category_id: str) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
            raise NotFoundException('Categoria não encontrada')
        if not category.get('tenant_id'):
            raise ValidationException('Categoria sem workspace. Recarregue a página.')
        category['id'] = category.get('id') or category.get('_id')
        category.pop('_id', None)
        return category

    def update_category(self, user_id: str, category_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
            raise NotFoundException('Categoria não encontrada')
        if not category.get('tenant_id'):
            raise ValidationException('Categoria sem workspace. Recarregue a página.')

        update_data = {}

        # Valida e aplica nome (verifica duplicatas se nome mudou)
        if 'name' in data:
            new_name = data['name'].strip() if data['name'] else ''
            if not new_name:
                raise ValidationException('Nome da categoria não pode ser vazio')
            if new_name != category.get('name'):
                # Verifica se já existe outra categoria com mesmo nome e tipo
                tenant_id = category.get('tenant_id')
                category_type = category.get('type')
                existing = self.category_repo.find_by_name_and_type(user_id, new_name, category_type, tenant_id=tenant_id)
                if existing and (existing.get('id') or existing.get('_id')) != category_id:
                    raise ValidationException(f'Categoria "{new_name}" já existe para este tipo')
            update_data['name'] = new_name

        # NÃO permite alterar tipo (evita inconsistência com transações existentes)
        if 'type' in data and data['type'] != category.get('type'):
            raise ValidationException('Não é possível alterar o tipo da categoria. Crie uma nova categoria se necessário.')

        if 'color' in data:
            update_data['color'] = data['color']
        if 'icon' in data:
            update_data['icon'] = data['icon']
        if 'description' in data:
            update_data['description'] = data['description']

        if update_data:
            try:
                self.category_repo.update(category_id, update_data)
                logger.info(f'Categoria atualizada: {category_id} - user_id: {user_id}')
            except Exception as e:
                logger.error(f'Erro ao atualizar categoria {category_id}: {str(e)}', exc_info=True)
                raise ValidationException(f'Erro ao atualizar categoria no banco de dados. Detalhe: {str(e)}')

        updated_category = self.category_repo.find_by_id(category_id)
        updated_category['id'] = updated_category.get('id') or updated_category.get('_id')
        updated_category.pop('_id', None)
        return updated_category

    def delete_category(self, user_id: str, category_id: str) -> bool:
        category = self.category_repo.find_by_id(category_id)
        if not category or category.get('user_id') != user_id:
            raise NotFoundException('Categoria não encontrada')
        tenant_id = category.get('tenant_id')
        if not tenant_id:
            raise ValidationException('Categoria sem workspace. Recarregue a página.')

        try:
            # Verifica se há transações usando esta categoria
            if getattr(self.transactions_repo, 'count_documents', None) is not None:
                count = self.transactions_repo.count_documents({'category_id': category_id, 'tenant_id': tenant_id})
            else:
                count = len(self.transactions_repo.find_all({'category_id': category_id, 'tenant_id': tenant_id}))
            if count > 0:
                raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta categoria')

            result = self.category_repo.delete(category_id)
            logger.info(f'Categoria deletada: {category_id} ({category.get("name")}) - user_id: {user_id}')
            return result
        except ValidationException:
            # Re-raise ValidationException sem logar (já é esperada)
            raise
        except Exception as e:
            logger.error(f'Erro ao deletar categoria {category_id}: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao deletar categoria no banco de dados. Detalhe: {str(e)}')
