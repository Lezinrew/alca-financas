from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid
import logging
from utils.exceptions import ValidationException, NotFoundException
from utils.money_utils import parse_money_value
from utils.date_utils import parse_date_value

logger = logging.getLogger(__name__)


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


def _resolve_transaction_tenant_ids(
    tenant_id: str,
    account_id: Optional[str],
    category_id: Optional[str],
    user_id: str,
    accounts_repo,
    categories_repo,
) -> Tuple[str, str]:
    """
    Resolve account_tenant_id e category_tenant_id a partir dos registros reais de
    accounts e categories. Garante consistência com tenant_id e FK do schema.
    Retorna (account_tenant_id, category_tenant_id); ambos nunca null (schema NOT NULL).
    """
    account_tenant_id = tenant_id
    category_tenant_id = tenant_id
    if account_id:
        account = _account_for(accounts_repo, account_id, user_id)
        if not account:
            raise ValidationException('Conta não encontrada')
        acc_tenant = account.get('tenant_id')
        if acc_tenant is not None and acc_tenant != tenant_id:
            raise ValidationException('Conta não pertence ao workspace atual.')
        account_tenant_id = acc_tenant if acc_tenant else tenant_id
    if category_id:
        category = _category_for(categories_repo, category_id)
        if not category:
            raise ValidationException('Categoria não encontrada')
        cat_tenant = category.get('tenant_id')
        if cat_tenant is not None and cat_tenant != tenant_id:
            raise ValidationException('Categoria não pertence ao workspace atual.')
        category_tenant_id = cat_tenant if cat_tenant else tenant_id
    return (account_tenant_id, category_tenant_id)


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
        # Garante que paginação sempre esteja presente nos filtros para o repositório avançado
        filters = dict(filters or {})
        filters.setdefault("page", page)
        filters.setdefault("limit", per_page)

        result = self.transaction_repo.find_advanced(
            user_id,
            filters,
            tenant_id=tenant_id,
        )
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
        account_id = data.get('account_id')
        category_id = data.get('category_id')

        account_tenant_id, category_tenant_id = _resolve_transaction_tenant_ids(
            tenant_id, account_id, category_id, user_id,
            self.accounts_repo, self.categories_repo,
        )
        if category_id and not category_tenant_id:
            raise ValidationException('Categoria não pertence ao workspace. Escolha outra categoria ou recarregue a página.')
        if account_id and not account_tenant_id:
            raise ValidationException('Conta não pertence ao workspace. Escolha outra conta ou recarregue a página.')

        if data.get('installments') and int(data['installments']) > 1:
            return self._create_installments(
                data, user_id, tenant_id, date, account_id,
                account_tenant_id, category_tenant_id,
            )

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
            'category_id': category_id or None,
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
            logger.info(f'Transação criada: {transaction_data["description"]} - R$ {amount_val} - user_id: {user_id}')
        except Exception as e:
            logger.error(f'Erro ao criar transação: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao salvar no banco de dados. Detalhe: {str(e)}')

        if account_id and transaction_data['status'] == 'paid':
            self._update_account_balance(account_id, transaction_data['amount'], transaction_data['type'])

        return {'count': 1, 'transaction': transaction_data}

    def create_many_transactions(self, transactions: List[Dict[str, Any]]) -> List[str]:
        try:
            return self.transaction_repo.create_many(transactions)
        except ValueError as e:
            raise ValidationException(f'Dados inválidos para transações. {str(e)}')

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

        current_tenant_id = transaction.get('tenant_id')
        if not current_tenant_id:
            raise ValidationException('Transação sem workspace. Recarregue a página.')
        new_category_id = update_data.get('category_id', transaction.get('category_id'))
        account_tenant_id, category_tenant_id = _resolve_transaction_tenant_ids(
            current_tenant_id,
            new_account_id,
            new_category_id,
            user_id,
            self.accounts_repo,
            self.categories_repo,
        )
        update_data['account_tenant_id'] = account_tenant_id
        update_data['category_tenant_id'] = category_tenant_id

        # Reconciliação de saldo:
        # 1) Reverte impacto antigo (se transação antiga era paga e tinha conta)
        # 2) Aplica impacto novo (se transação nova é paga e tem conta)
        try:
            # Passo 1: reverter saldo antigo
            # Para reverter: aplica o tipo oposto com mesmo amount
            if old_account_id and old_status == 'paid' and old_amount:
                opposite_type = self._get_opposite_type(old_type)
                self._update_account_balance(old_account_id, old_amount, opposite_type)

            # Atualiza transação no repositório
            self.transaction_repo.update(transaction_id, update_data)
            logger.info(f'Transação atualizada: {transaction_id} - user_id: {user_id}')

            # Passo 2: aplicar saldo novo
            if new_account_id and new_status == 'paid' and new_amount:
                self._update_account_balance(new_account_id, new_amount, new_type)
        except Exception as e:
            logger.error(f'Erro ao atualizar transação {transaction_id}: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao atualizar no banco de dados. Detalhe: {str(e)}')

        return {'message': 'Transação atualizada com sucesso'}

    def delete_transaction(self, user_id: str, transaction_id: str) -> bool:
        transaction = self.transaction_repo.find_by_id(transaction_id)
        if not transaction or transaction.get('user_id') != user_id:
            raise NotFoundException('Transação não encontrada')

        try:
            # Reverter impacto no saldo (se transação era paga)
            # Usa mesma lógica de update_transaction para consistência
            if transaction.get('account_id') and transaction.get('status') == 'paid':
                amount = float(transaction.get('amount', 0))
                tx_type = transaction.get('type', 'expense')
                opposite_type = self._get_opposite_type(tx_type)
                self._update_account_balance(transaction['account_id'], amount, opposite_type)

            result = self.transaction_repo.delete(transaction_id)
            logger.info(f'Transação deletada: {transaction_id} ({transaction.get("description")}) - user_id: {user_id}')
            return result
        except Exception as e:
            logger.error(f'Erro ao deletar transação {transaction_id}: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao deletar transação no banco de dados. Detalhe: {str(e)}')

    def _create_installments(
        self,
        data: Dict[str, Any],
        user_id: str,
        tenant_id: str,
        base_date: datetime,
        account_id: Optional[str],
        account_tenant_id: str,
        category_tenant_id: str,
    ) -> Dict[str, Any]:
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
                'category_tenant_id': category_tenant_id,
                'account_id': account_id or None,
                'account_tenant_id': account_tenant_id,
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
            logger.info(f'Parcelamento criado: {installments}x de {data["description"]} - user_id: {user_id}')
        except Exception as e:
            logger.error(f'Erro ao criar parcelamento: {str(e)}', exc_info=True)
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

    def _get_opposite_type(self, type: str) -> str:
        """
        Retorna o tipo oposto para reversão de impacto.
        Usar para reverter transações: aplica o tipo oposto com mesmo amount.
        """
        return 'expense' if type == 'income' else 'income'

    def _update_account_balance(self, account_id: str, amount: float, type: str):
        """
        Aplica impacto de transação no saldo da conta.
        - income: aumenta saldo (+amount)
        - expense: diminui saldo (-amount)

        Para REVERTER uma transação, use _get_opposite_type:
        self._update_account_balance(account_id, amount, self._get_opposite_type(old_type))
        """
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
