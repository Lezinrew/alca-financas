from datetime import datetime
import uuid
from typing import Dict, Any, List, Optional


def build_filter(user_id: str, month: Optional[str], year: Optional[str], category_id: Optional[str], transaction_type: Optional[str], account_id: Optional[str] = None):
    filter_query = {'user_id': user_id}
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
    if account_id:
        filter_query['account_id'] = account_id
    return filter_query


def list_transactions(transactions_collection, categories_collection, filter_query) -> List[Dict[str, Any]]:
    transactions_list = list(transactions_collection.find(filter_query).sort('date', -1))
    for transaction in transactions_list:
        category = categories_collection.find_one({'_id': transaction['category_id']})
        if category:
            transaction['category'] = {
                'name': category['name'],
                'color': category['color'],
                'icon': category['icon']
            }
        if '_id' in transaction:
            transaction['id'] = transaction['_id']
            transaction.pop('_id', None)
    return transactions_list


def create_installments(data: Dict[str, Any], request_user_id: str, base_date: datetime, account_id: Optional[str]) -> List[Dict[str, Any]]:
    installments = data.get('installments', 1)
    status = data.get('status', 'pending')
    responsible_person = data.get('responsible_person', 'Leandro')
    transactions_to_create = []
    if installments > 1:
        installment_amount = float(data['amount']) / installments
        for i in range(installments):
            transaction_date = base_date.replace(month=base_date.month + i) if base_date.month + i <= 12 else base_date.replace(year=base_date.year + 1, month=(base_date.month + i) - 12)
            transaction_data = {
                '_id': str(uuid.uuid4()),
                'user_id': request_user_id,
                'description': f"{data['description']} ({i+1}/{installments})",
                'amount': installment_amount,
                'type': data['type'],
                'category_id': data['category_id'],
                'account_id': account_id,
                'date': transaction_date,
                'is_recurring': False,
                'status': status,
                'responsible_person': responsible_person,
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
        transaction_data = {
            '_id': str(uuid.uuid4()),
            'user_id': request_user_id,
            'description': data['description'],
            'amount': float(data['amount']),
            'type': data['type'],
            'category_id': data['category_id'],
            'account_id': account_id,
            'date': base_date,
            'is_recurring': data.get('is_recurring', False),
            'status': status,
            'responsible_person': responsible_person,
            'installment_info': None,
            'created_at': datetime.utcnow()
        }
        transactions_to_create.append(transaction_data)
    return transactions_to_create


def apply_account_balance_updates(accounts_collection, account_id: Optional[str], transactions_to_create: List[Dict[str, Any]]):
    if not account_id:
        return
    for transaction in transactions_to_create:
        amount_change = transaction['amount']
        if transaction['type'] == 'expense':
            amount_change = -amount_change
        accounts_collection.update_one(
            {'_id': account_id},
            {'$inc': {'current_balance': amount_change}}
        )


