from datetime import datetime
import uuid
from typing import Dict, Any, List


def list_accounts(accounts_collection, user_id: str) -> List[Dict[str, Any]]:
    user_accounts = list(accounts_collection.find({'user_id': user_id}))
    for account in user_accounts:
        if '_id' in account:
            account['id'] = account['_id']
            account.pop('_id', None)
    return user_accounts


def create_account(accounts_collection, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    account_data = {
        '_id': str(uuid.uuid4()),
        'user_id': user_id,
        'name': data['name'],
        'type': data['type'],
        'institution': data.get('institution', ''),
        'initial_balance': float(data.get('initial_balance', 0)),
        'current_balance': float(data.get('initial_balance', 0)),
        'color': data.get('color', '#6366f1'),
        'icon': data.get('icon', 'wallet2'),
        'is_active': True,
        'created_at': datetime.utcnow()
    }
    accounts_collection.insert_one(account_data)
    account_data['id'] = account_data['_id']
    account_data.pop('_id')
    return account_data


def update_account(accounts_collection, user_id: str, account_id: str, data: Dict[str, Any]):
    # Busca a conta atual para calcular a diferença do saldo inicial
    current_account = accounts_collection.find_one({'_id': account_id, 'user_id': user_id})
    if not current_account:
        return
    
    allowed_fields = ['name', 'type', 'institution', 'color', 'icon', 'is_active', 'initial_balance']
    update_data = {}
    
    for field in allowed_fields:
        if field in data:
            if field == 'initial_balance':
                # Converte para float
                new_initial_balance = float(data[field])
                old_initial_balance = float(current_account.get('initial_balance', 0))
                
                # Calcula a diferença
                balance_diff = new_initial_balance - old_initial_balance
                
                # Atualiza o saldo inicial
                update_data['initial_balance'] = new_initial_balance
                
                # Atualiza o saldo atual pela diferença
                current_balance = float(current_account.get('current_balance', 0))
                update_data['current_balance'] = current_balance + balance_diff
            else:
                update_data[field] = data[field]
    
    if update_data:
        accounts_collection.update_one(
            {'_id': account_id, 'user_id': user_id},
            {'$set': update_data}
        )


def delete_account(accounts_collection, transactions_collection, user_id: str, account_id: str) -> bool:
    transaction_count = transactions_collection.count_documents({'account_id': account_id})
    if transaction_count > 0:
        return False
    accounts_collection.delete_one({'_id': account_id})
    return True


