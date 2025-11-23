from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from repositories.account_repository import AccountRepository
from utils.exceptions import ValidationException, NotFoundException

class AccountService:
    def __init__(self, account_repo: AccountRepository, transactions_collection):
        self.account_repo = account_repo
        self.transactions_collection = transactions_collection

    def list_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        accounts = self.account_repo.find_by_user(user_id)
        # Garante que todas as contas pertencem ao usuário (segurança extra)
        filtered_accounts = []
        for acc in accounts:
            # Verifica se a conta pertence ao usuário
            if acc.get('user_id') == user_id:
                if '_id' in acc:
                    acc['id'] = acc['_id']
                    acc.pop('_id', None)
                filtered_accounts.append(acc)
        return filtered_accounts

    def create_account(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        # Validação mais robusta
        name = data.get('name', '').strip() if data.get('name') else ''
        account_type = data.get('type', '').strip() if data.get('type') else ''
        
        if not name:
            raise ValidationException('Nome da conta é obrigatório')
        
        if not account_type:
            raise ValidationException('Tipo da conta é obrigatório')
        
        if account_type not in ['wallet', 'checking', 'savings', 'credit_card', 'investment']:
            raise ValidationException('Tipo de conta inválido. Tipos válidos: wallet, checking, savings, credit_card, investment')

        existing = self.account_repo.find_by_name(user_id, name)
        if existing:
            raise ValidationException(f'Conta "{name}" já existe')

        # Trata initial_balance de diferentes formas
        # Para cartões de crédito, também aceita 'limit' como sinônimo de initial_balance
        initial_balance = 0.0
        if 'initial_balance' in data:
            try:
                initial_balance = float(data['initial_balance'])
            except (ValueError, TypeError):
                # Tenta converter string com formatação de moeda
                balance_str = str(data['initial_balance']).replace('R$', '').replace(' ', '').replace(',', '.').strip()
                try:
                    initial_balance = float(balance_str)
                except ValueError:
                    initial_balance = 0.0
        elif account_type == 'credit_card' and 'limit' in data:
            # Para cartões de crédito, usa 'limit' como initial_balance
            try:
                initial_balance = float(data['limit'])
            except (ValueError, TypeError):
                # Tenta converter string com formatação de moeda
                limit_str = str(data['limit']).replace('R$', '').replace(' ', '').replace(',', '.').strip()
                try:
                    initial_balance = float(limit_str)
                except ValueError:
                    initial_balance = 0.0
        elif 'balance' in data:
            try:
                initial_balance = float(data['balance'])
            except (ValueError, TypeError):
                initial_balance = 0.0
        
        # Para cartões de crédito, current_balance começa em 0 (sem gastos)
        # Para outras contas, current_balance = initial_balance
        starting_balance = 0.0 if account_type == 'credit_card' else initial_balance
        
        account_data = {
            '_id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': name,
            'type': account_type,
            'balance': initial_balance,
            'initial_balance': initial_balance,
            'color': data.get('color', '#2196F3'),
            'current_balance': starting_balance
        }
        
        # Adiciona campos opcionais se fornecidos
        if 'institution' in data:
            account_data['institution'] = data['institution']
        if 'icon' in data:
            account_data['icon'] = data['icon']
        if 'is_active' in data:
            account_data['is_active'] = bool(data['is_active'])
        
        # Campos específicos para cartões de crédito
        if account_type == 'credit_card':
            if 'closing_day' in data:
                account_data['closing_day'] = int(data['closing_day'])
            if 'due_day' in data:
                account_data['due_day'] = int(data['due_day'])
            if 'card_type' in data:
                account_data['card_type'] = data['card_type']
            if 'account_id' in data:
                account_data['account_id'] = data['account_id']
        
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
        if 'institution' in data:
            update_data['institution'] = data['institution']
        if 'icon' in data:
            update_data['icon'] = data['icon']
        if 'is_active' in data:
            update_data['is_active'] = bool(data['is_active'])
        if 'initial_balance' in data:
            update_data['initial_balance'] = float(data['initial_balance'])
        if 'current_balance' in data:
            # Permite editar o saldo atual manualmente
            update_data['current_balance'] = float(data['current_balance'])

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

    def calculate_projected_balance(self, user_id: str, account_id: str, transactions_collection) -> float:
        """
        Calcula o saldo previsto considerando:
        - Saldo atual da conta (já inclui transações pagas)
        - Transações pendentes (status = 'pending') que ainda não foram aplicadas ao saldo
        - Transações futuras (data > hoje) que ainda não foram aplicadas ao saldo
        """
        account = self.account_repo.find_by_id(account_id)
        if not account or account.get('user_id') != user_id:
            return 0.0
        
        current_balance = account.get('current_balance', 0) or 0
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Busca transações que ainda não foram aplicadas ao saldo:
        # 1. Transações pendentes (status = 'pending') - independente da data
        # 2. Transações futuras (data > hoje) - independente do status (exceto se já pagas no futuro)
        pending_query = {
            'user_id': user_id,
            'account_id': account_id,
            '$or': [
                {'status': 'pending'},  # Transações pendentes
                {
                    'date': {'$gt': today},
                    'status': {'$ne': 'paid'}  # Transações futuras que ainda não foram pagas
                }
            ]
        }
        
        pending_transactions = list(transactions_collection.find(pending_query))
        
        # Calcula o impacto das transações pendentes/futuras
        # Essas transações ainda não foram aplicadas ao current_balance
        projected_adjustment = 0.0
        for tx in pending_transactions:
            amount = tx.get('amount', 0)
            tx_type = tx.get('type', 'expense')
            
            if tx_type == 'income':
                projected_adjustment += amount
            elif tx_type == 'expense':
                projected_adjustment -= amount
        
        return current_balance + projected_adjustment

    def delete_account(self, user_id: str, account_id: str) -> bool:
        account = self.account_repo.find_by_id(account_id)
        if not account or account['user_id'] != user_id:
            raise NotFoundException('Conta não encontrada')

        # Check for transactions
        count = self.transactions_collection.count_documents({'account_id': account_id})
        if count > 0:
            raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta conta')

        return self.account_repo.delete(account_id)
