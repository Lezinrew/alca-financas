from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from utils.exceptions import ValidationException, NotFoundException
from utils.money_utils import parse_money_value
from utils.date_utils import parse_date_value


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

    def list_transactions(
        self,
        user_id: str,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 20,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self.transaction_repo.find_by_filter(user_id, filters, page, per_page, tenant_id=tenant_id)
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

    def create_transaction(self, user_id: str, data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        if not tenant_id:
            raise ValidationException('Workspace não identificado. Recarregue a página ou faça login novamente.')

        if not data.get('description') or not data.get('amount') or not data.get('date'):
            raise ValidationException('Descrição, valor e data são obrigatórios')

        if data.get('type') and data['type'] not in ['income', 'expense']:
            raise ValidationException('Tipo de transação inválido. Use "income" ou "expense"')
        
        date = parse_date_value(data['date'])

        # Schema: account_tenant_id e category_tenant_id são NOT NULL e CHECK (= tenant_id).
        # Sempre enviar tenant_id nesses campos para satisfazer constraint.
        account_id = data.get('account_id')
        if account_id:
            account = _account_for(self.accounts_repo, account_id, user_id)
            if not account:
                raise ValidationException('Conta não encontrada')
        account_tenant_id = tenant_id  # obrigatório; CHECK (account_tenant_id = tenant_id)
        category_id = data.get('category_id')
        if category_id:
            category = _category_for(self.categories_repo, category_id)
            if not category:
                raise ValidationException('Categoria não encontrada')
        category_tenant_id = tenant_id  # obrigatório; CHECK (category_tenant_id = tenant_id)

        # Handle installments
        if data.get('installments') and int(data['installments']) > 1:
            return self._create_installments(data, user_id, tenant_id, date, account_id)

        new_id = str(uuid.uuid4())
        date_val = date.strftime('%Y-%m-%d') if isinstance(date, datetime) else date
        amount_val = parse_money_value(data.get('amount'))
        transaction_data = {
            'id': new_id,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'description': data['description'],
            'amount': amount_val,
            'type': data.get('type', 'expense'),
            'category_id': data.get('category_id') or None,
            'category_tenant_id': category_tenant_id,
            'account_id': account_id or None,
            'account_tenant_id': account_tenant_id,
            'date': date_val,
            'is_recurring': data.get('is_recurring', False),
            'status': data.get('status', 'pending'),
            'responsible_person': data.get('responsible_person'),
            'installment_info': None,
        }
        try:
            created_id = self.transaction_repo.create(transaction_data)
            if created_id:
                transaction_data['id'] = created_id
        except Exception as e:
            raise ValidationException(f'Erro ao salvar no banco de dados. Detalhe: {str(e)}')
        
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

        # Valores antigos para reconciliação de saldo
        old_account_id = transaction.get('account_id')
        old_amount = float(transaction.get('amount', 0) or 0)
        old_type = transaction.get('type', 'expense')
        old_status = transaction.get('status', 'pending')

        update_data: Dict[str, Any] = {}
        # Inclui 'type' para permitir correções, mantendo mesma validação de create_transaction
        allowed_fields = ['description', 'amount', 'category_id', 'date', 'status', 'responsible_person', 'account_id', 'type']

        for field in allowed_fields:
            if field in data:
                if field == 'date':
                    parsed_date = parse_date_value(data[field])
                    update_data[field] = parsed_date.strftime('%Y-%m-%d')
                elif field == 'amount':
                    update_data[field] = parse_money_value(data[field])
                elif field == 'type':
                    if data['type'] not in ['income', 'expense']:
                        raise ValidationException('Tipo de transação inválido. Use "income" ou "expense"')
                    update_data[field] = data['type']
                else:
                    update_data[field] = data[field]

        if not update_data:
            return {'message': 'Nenhum dado para atualizar'}

        # Calcula novos valores efetivos (após update) para reconciliação
        new_status = update_data.get('status', old_status)
        new_type = update_data.get('type', old_type)
        new_amount = float(update_data.get('amount', old_amount) or old_amount)
        new_account_id = update_data.get('account_id', old_account_id)

        # Valida conta, se tiver sido alterada
        if 'account_id' in update_data and new_account_id:
            account = _account_for(self.accounts_repo, new_account_id, user_id)
            if not account:
                raise ValidationException('Conta não encontrada')

        # Valida categoria, se tiver sido alterada
        if 'category_id' in update_data and update_data.get('category_id'):
            category = _category_for(self.categories_repo, update_data['category_id'])
            if not category:
                raise ValidationException('Categoria não encontrada')

        # Reconciliação de saldo:
        # 1) Reverte impacto antigo (se transação antiga era paga e tinha conta)
        # 2) Aplica impacto novo (se transação nova é paga e tem conta)
        try:
            # Passo 1: reverter saldo antigo
            if old_account_id and old_status == 'paid' and old_amount:
                # Usa amount negativo com o mesmo tipo para inverter o sinal
                self._update_account_balance(old_account_id, -old_amount, old_type)

            # Atualiza transação no repositório
            self.transaction_repo.update(transaction_id, update_data)

            # Passo 2: aplicar saldo novo
            if new_account_id and new_status == 'paid' and new_amount:
                self._update_account_balance(new_account_id, new_amount, new_type)
        except Exception as e:
            raise ValidationException(f'Erro ao atualizar no banco de dados. Detalhe: {str(e)}')

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

    def _create_installments(self, data: Dict[str, Any], user_id: str, tenant_id: str, base_date: datetime, account_id: Optional[str]) -> Dict[str, Any]:
        installments = int(data.get('installments', 1))
        status = data.get('status', 'pending')
        total_amount = parse_money_value(data.get('amount'))
        installment_amount = total_amount / installments

        to_create = []
        from dateutil.relativedelta import relativedelta

        group_id = str(uuid.uuid4())
        for i in range(installments):
            d = base_date + relativedelta(months=i)
            date_str = d.strftime('%Y-%m-%d') if isinstance(d, datetime) else d
            tx = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'tenant_id': tenant_id,
                'description': f"{data['description']} ({i+1}/{installments})",
                'amount': installment_amount,
                'type': data.get('type', 'expense'),
                'category_id': data.get('category_id') or None,
                'category_tenant_id': tenant_id,
                'account_id': account_id or None,
                'account_tenant_id': tenant_id,
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

        try:
            self.transaction_repo.create_many(to_create)
        except Exception as e:
            raise ValidationException(f'Erro ao salvar parcelamentos no banco de dados. Detalhe: {str(e)}')
        
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
