from typing import List, Dict, Any, Optional
import uuid
from repositories.account_repository import AccountRepository
from utils.exceptions import ValidationException, NotFoundException

class AccountService:
    def __init__(self, account_repo: AccountRepository, transactions_collection):
        self.account_repo = account_repo
        self.transactions_collection = transactions_collection

    def list_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        accounts = self.account_repo.find_by_user(user_id)
        for acc in accounts:
            if '_id' in acc:
                acc['id'] = acc['_id']
                acc.pop('_id', None)
        return accounts

    def create_account(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('name') or not data.get('type'):
            raise ValidationException('Nome e tipo da conta são obrigatórios')
        
        if data['type'] not in ['wallet', 'checking', 'savings', 'credit_card', 'investment']:
            raise ValidationException('Tipo de conta inválido')

        existing = self.account_repo.find_by_name(user_id, data['name'])
        if existing:
            raise ValidationException(f'Conta "{data["name"]}" já existe')

        initial_balance = float(data.get('initial_balance', data.get('balance', 0)))
        account_data = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': data['name'],
            'type': data['type'],
            'balance': initial_balance,
            'initial_balance': initial_balance,
            'color': data.get('color', '#2196F3'),
            'current_balance': initial_balance
        }
        
        self.account_repo.create(account_data)
        
        account_data['id'] = account_data['_id']
        account_data.pop('_id', None)
        return account_data

    def update_account(self, user_id: str, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        account = self.account_repo.find_by_id(account_id)
        if not account or account['user_id'] != user_id:
            raise NotFoundException('Conta não encontrada')

        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'color' in data:
            update_data['color'] = data['color']
        if 'type' in data:
             if data['type'] not in ['wallet', 'checking', 'savings', 'credit_card', 'investment']:
                raise ValidationException('Tipo de conta inválido')
             update_data['type'] = data['type']

        if update_data:
            self.account_repo.update(account_id, update_data)
            
        # Return updated account
        updated_account = self.account_repo.find_by_id(account_id)
        updated_account['id'] = updated_account['_id']
        updated_account.pop('_id', None)
        return updated_account

    def update_balance(self, account_id: str, amount: float):
        self.account_repo.collection.update_one(
            {'_id': account_id}, 
            {'$inc': {'current_balance': amount}}
        )

    def delete_account(self, user_id: str, account_id: str) -> bool:
        account = self.account_repo.find_by_id(account_id)
        if not account or account['user_id'] != user_id:
            raise NotFoundException('Conta não encontrada')

        # Check for transactions
        count = self.transactions_collection.count_documents({'account_id': account_id})
        if count > 0:
            raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta conta')

        return self.account_repo.delete(account_id)
