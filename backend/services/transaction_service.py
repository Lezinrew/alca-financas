from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from utils.exceptions import ValidationException, NotFoundException


def _category_for(categories_repo, category_id):
    if not category_id:
        return None
    if hasattr(categories_repo, 'find_by_id'):
        return categories_repo.find_by_id(category_id)
    if hasattr(categories_repo, 'find_one'):
        return categories_repo.find_one({'_id': category_id})
    return None


def _account_for(accounts_repo, account_id, user_id):
    if not account_id:
        return None
    acc = accounts_repo.find_by_id(account_id) if hasattr(accounts_repo, 'find_by_id') else None
    if not acc:
        return None
    if acc.get('user_id') != user_id:
        return None
    return acc


class TransactionService:
    def __init__(self, transaction_repo, categories_repo, accounts_repo):
        self.transaction_repo = transaction_repo
        self.categories_repo = categories_repo
        self.accounts_repo = accounts_repo

    def list_transactions(self, user_id: str, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        result = self.transaction_repo.find_by_filter(user_id, filters, page, per_page)
        data = result.get('data') or []
        for transaction in data:
            cat_id = transaction.get('category_id')
            category = _category_for(self.categories_repo, cat_id)
            if category:
                transaction['category'] = {
                    'name': category.get('name', ''),
                    'color': category.get('color', '#6b7280'),
                    'icon': category.get('icon', 'circle')
                }
            transaction['id'] = transaction.get('id') or transaction.get('_id')
            transaction.pop('_id', None)
        result['data'] = data
        return result

    def create_transaction(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('description') or not data.get('amount') or not data.get('date'):
            raise ValidationException('Descrição, valor e data são obrigatórios')

        if data.get('type') and data['type'] not in ['income', 'expense']:
            raise ValidationException('Tipo de transação inválido. Use "income" ou "expense"')
        
        try:
            date = datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            raise ValidationException('Data inválida. Use o formato YYYY-MM-DD')

        account_id = data.get('account_id')
        if account_id:
            if not _account_for(self.accounts_repo, account_id, user_id):
                raise ValidationException('Conta não encontrada')

        # Handle installments
        if data.get('installments') and int(data['installments']) > 1:
            return self._create_installments(data, user_id, date, account_id)

        new_id = str(uuid.uuid4())
        date_val = date.strftime('%Y-%m-%d') if isinstance(date, datetime) else date
        transaction_data = {
            'id': new_id,
            'user_id': user_id,
            'description': data['description'],
            'amount': float(data['amount']),
            'type': data.get('type', 'expense'),
            'category_id': data.get('category_id'),
            'account_id': account_id,
            'date': date_val,
            'is_recurring': data.get('is_recurring', False),
            'status': data.get('status', 'pending'),
            'responsible_person': data.get('responsible_person'),
            'installment_info': None,
        }
        created_id = self.transaction_repo.create(transaction_data)
        if created_id:
            transaction_data['id'] = created_id
        
        if account_id and transaction_data['status'] == 'paid':
            self._update_account_balance(account_id, transaction_data['amount'], transaction_data['type'])

        return {'count': 1, 'transaction': transaction_data}

    def create_many_transactions(self, transactions: List[Dict[str, Any]]) -> List[str]:
        return self.transaction_repo.create_many(transactions)

    def get_transaction(self, user_id: str, transaction_id: str) -> Dict[str, Any]:
        transaction = self.transaction_repo.find_by_id(transaction_id)
        if not transaction or transaction.get('user_id') != user_id:
            raise NotFoundException('Transação não encontrada')
        cat_id = transaction.get('category_id')
        category = _category_for(self.categories_repo, cat_id)
        if category:
            transaction['category'] = {
                'name': category.get('name', ''),
                'color': category.get('color', '#6b7280'),
                'icon': category.get('icon', 'circle')
            }
        transaction['id'] = transaction.get('id') or transaction.get('_id')
        transaction.pop('_id', None)
        return transaction

    def update_transaction(self, user_id: str, transaction_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        transaction = self.transaction_repo.find_by_id(transaction_id)
        if not transaction or transaction.get('user_id') != user_id:
            raise NotFoundException('Transação não encontrada')

        update_data = {}
        allowed_fields = ['description', 'amount', 'category_id', 'date', 'status', 'responsible_person', 'account_id']
        
        for field in allowed_fields:
            if field in data:
                if field == 'date':
                    try:
                        if isinstance(data[field], str):
                            update_data[field] = data[field]  # keep as YYYY-MM-DD for Supabase
                        elif isinstance(data[field], datetime):
                            update_data[field] = data[field].strftime('%Y-%m-%d')
                        else:
                            update_data[field] = data[field]
                    except (ValueError, TypeError):
                        raise ValidationException('Data inválida')
                elif field == 'amount':
                    update_data[field] = float(data[field])
                else:
                    update_data[field] = data[field]

        if not update_data:
            return {'message': 'Nenhum dado para atualizar'}

        # Handle balance update if amount or status changed
        # This is complex because we need to revert old balance and apply new
        # For now, let's keep it simple and just update the transaction
        # TODO: Implement balance reconciliation on update
        
        self.transaction_repo.update(transaction_id, update_data)
        return {'message': 'Transação atualizada com sucesso'}

    def delete_transaction(self, user_id: str, transaction_id: str) -> bool:
        transaction = self.transaction_repo.find_by_id(transaction_id)
        if not transaction or transaction.get('user_id') != user_id:
            raise NotFoundException('Transação não encontrada')

        if transaction.get('account_id') and transaction.get('status') == 'paid':
            reverse_amount = -float(transaction['amount']) if transaction.get('type') == 'income' else float(transaction['amount'])
            if getattr(self.accounts_repo, 'update_one', None) is not None:
                self.accounts_repo.update_one(
                    {'_id': transaction['account_id']},
                    {'$inc': {'current_balance': reverse_amount}}
                )
            elif hasattr(self.accounts_repo, 'find_by_id') and hasattr(self.accounts_repo, 'update'):
                acc = self.accounts_repo.find_by_id(transaction['account_id'])
                if acc:
                    new_balance = (acc.get('current_balance') or 0) + reverse_amount
                    self.accounts_repo.update(transaction['account_id'], {'current_balance': new_balance})

        return self.transaction_repo.delete(transaction_id)

    def _create_installments(self, data: Dict[str, Any], user_id: str, base_date: datetime, account_id: Optional[str]) -> Dict[str, Any]:
        installments = int(data.get('installments', 1))
        status = data.get('status', 'pending')
        total_amount = float(data['amount'])
        installment_amount = total_amount / installments
        
        to_create = []
        import pandas as pd
        from dateutil.relativedelta import relativedelta

        group_id = str(uuid.uuid4())
        for i in range(installments):
            d = base_date + relativedelta(months=i)
            date_str = d.strftime('%Y-%m-%d') if isinstance(d, datetime) else d
            tx = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'description': f"{data['description']} ({i+1}/{installments})",
                'amount': installment_amount,
                'type': data.get('type', 'expense'),
                'category_id': data.get('category_id'),
                'account_id': account_id,
                'date': date_str,
                'is_recurring': False,
                'status': status,
                'responsible_person': data.get('responsible_person'),
                'installment_info': {
                    'current': i + 1,
                    'total': installments,
                    'group_id': group_id
                },
            }
            to_create.append(tx)

        self.transaction_repo.create_many(to_create)
        
        # Update balance for paid installments (usually only the first one if status is paid, or all? 
        # Usually installments are future, so maybe only first is paid? 
        # Let's assume if status is paid, all are paid? Or user sets status.
        # For safety, let's iterate and check status
        if account_id:
             for tx in to_create:
                 if tx['status'] == 'paid':
                     self._update_account_balance(account_id, tx['amount'], tx['type'])
                
        return {'count': len(to_create), 'transactions': to_create}

    def _update_account_balance(self, account_id: str, amount: float, type: str):
        balance_change = amount if type == 'income' else -amount
        if getattr(self.accounts_repo, 'update_one', None) is not None:
            self.accounts_repo.update_one(
                {'_id': account_id},
                {'$inc': {'current_balance': balance_change}}
            )
        elif hasattr(self.accounts_repo, 'find_by_id') and hasattr(self.accounts_repo, 'update'):
            acc = self.accounts_repo.find_by_id(account_id)
            if acc:
                new_balance = (acc.get('current_balance') or 0) + balance_change
                self.accounts_repo.update(account_id, {'current_balance': new_balance})
