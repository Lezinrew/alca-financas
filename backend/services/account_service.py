from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
from utils.exceptions import ValidationException, NotFoundException
from utils.money_utils import parse_money_value

logger = logging.getLogger(__name__)

_ACCOUNT_TYPE_LABEL_PT = {
    "wallet": "carteira",
    "checking": "conta corrente",
    "savings": "poupança",
    "credit_card": "cartão de crédito",
    "investment": "investimento",
}


def _account_type_label_pt(account_type: str) -> str:
    return _ACCOUNT_TYPE_LABEL_PT.get(account_type, account_type or "conta")


def _parse_date(d):
    """Parse date from record (string or datetime)."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d.replace('Z', '+00:00'))
        except Exception:
            return None
    return None


class AccountService:
    def __init__(self, account_repo, transactions_repo):
        self.account_repo = account_repo
        self.transactions_repo = transactions_repo

    def list_accounts(self, user_id: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        accounts = self.account_repo.find_by_user(user_id, tenant_id=tenant_id)
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

    def create_account(self, user_id: str, data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        # Validação mais robusta
        name = data.get('name', '').strip() if data.get('name') else ''
        account_type = data.get('type', '').strip() if data.get('type') else ''
        
        if not name:
            raise ValidationException('Nome da conta é obrigatório')
        
        if not account_type:
            raise ValidationException('Tipo da conta é obrigatório')
        
        if account_type not in ['wallet', 'checking', 'savings', 'credit_card', 'investment']:
            raise ValidationException('Tipo de conta inválido. Tipos válidos: wallet, checking, savings, credit_card, investment')

        if hasattr(self.account_repo, "find_by_name_and_type"):
            existing = self.account_repo.find_by_name_and_type(
                user_id, name, account_type, tenant_id=tenant_id
            )
        else:
            existing = self.account_repo.find_by_name(user_id, name)
            if existing and existing.get("type") != account_type:
                existing = None
        if existing:
            raise ValidationException(
                f'Já existe um {_account_type_label_pt(account_type)} com o nome "{name}".'
            )

        # Trata initial_balance de diferentes formas (aceita string pt-BR ou número)
        # Para cartões de crédito, também aceita 'limit' como sinônimo de initial_balance
        initial_balance = 0.0
        if 'initial_balance' in data:
            initial_balance = parse_money_value(data['initial_balance'])
        elif account_type == 'credit_card' and 'limit' in data:
            initial_balance = parse_money_value(data['limit'])
        elif 'balance' in data:
            initial_balance = parse_money_value(data['balance'])
        
        # Para cartões de crédito, current_balance começa em 0 (sem gastos)
        # Para outras contas, current_balance = initial_balance
        starting_balance = 0.0 if account_type == 'credit_card' else initial_balance
        new_id = str(uuid.uuid4())
        account_data = {
            'id': new_id,
            'user_id': user_id,
            'tenant_id': tenant_id,
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
            # account_id só se for UUID válido (vinculação a conta corrente); vazio não envia
            aid = data.get('account_id')
            if aid and str(aid).strip():
                account_data['account_id'] = str(aid).strip()
        
        try:
            created_id = self.account_repo.create(account_data)
            if created_id:
                account_data['id'] = created_id
            logger.info(f'Conta criada: {name} (tipo: {account_type}) - user_id: {user_id}')
            return account_data
        except Exception as e:
            logger.error(f'Erro ao criar conta: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao salvar conta no banco de dados. Detalhe: {str(e)}')

    def update_account(self, user_id: str, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        account = self.account_repo.find_by_id(account_id)
        if not account or account['user_id'] != user_id:
            raise NotFoundException('Conta não encontrada')
        if not account.get('tenant_id'):
            raise ValidationException('Conta sem workspace. Recarregue a página.')

        update_data = {}

        # Valida e aplica nome (verifica duplicatas se nome mudou)
        if 'name' in data:
            new_name = data['name'].strip() if data['name'] else ''
            if not new_name:
                raise ValidationException('Nome da conta não pode ser vazio')
            if new_name != account.get('name'):
                tenant_id = account.get('tenant_id')
                acc_type = account.get('type') or ''
                if hasattr(self.account_repo, "find_by_name_and_type"):
                    existing = self.account_repo.find_by_name_and_type(
                        user_id, new_name, acc_type, tenant_id=tenant_id
                    )
                else:
                    existing = self.account_repo.find_by_name(user_id, new_name)
                    if existing and existing.get("type") != acc_type:
                        existing = None
                other_id = existing.get("id") or existing.get("_id") if existing else None
                if existing and str(other_id) != str(account_id):
                    raise ValidationException(
                        f'Já existe um {_account_type_label_pt(acc_type)} com o nome "{new_name}".'
                    )
            update_data['name'] = new_name

        # NÃO permite alterar tipo (evita inconsistência - ex: credit_card para checking)
        if 'type' in data and data['type'] != account.get('type'):
            raise ValidationException('Não é possível alterar o tipo da conta. Crie uma nova conta se necessário.')

        if 'color' in data:
            update_data['color'] = data['color']
        if 'institution' in data:
            update_data['institution'] = data['institution']
        if 'icon' in data:
            update_data['icon'] = data['icon']
        if 'is_active' in data:
            update_data['is_active'] = bool(data['is_active'])
        if 'initial_balance' in data:
            update_data['initial_balance'] = parse_money_value(data['initial_balance'])
        # Para cartão de crédito, aceita 'limit' como sinônimo de initial_balance
        if account.get('type') == 'credit_card' and 'limit' in data and 'initial_balance' not in data:
            update_data['initial_balance'] = parse_money_value(data['limit'])
        if 'current_balance' in data:
            update_data['current_balance'] = parse_money_value(data['current_balance'])
        # Campos de cartão de crédito no update
        if account.get('type') == 'credit_card':
            if 'closing_day' in data:
                update_data['closing_day'] = int(data['closing_day'])
            if 'due_day' in data:
                update_data['due_day'] = int(data['due_day'])
            if 'card_type' in data:
                update_data['card_type'] = data['card_type']
            if 'account_id' in data:
                aid = data.get('account_id')
                update_data['account_id'] = str(aid).strip() if aid and str(aid).strip() else None

        if update_data:
            try:
                self.account_repo.update(account_id, update_data)
                logger.info(f'Conta atualizada: {account_id} - user_id: {user_id}')
            except Exception as e:
                logger.error(f'Erro ao atualizar conta {account_id}: {str(e)}', exc_info=True)
                raise ValidationException(f'Erro ao atualizar conta no banco de dados. Detalhe: {str(e)}')

        # Return updated account
        updated_account = self.account_repo.find_by_id(account_id)
        updated_account['id'] = updated_account.get('id') or updated_account.get('_id')
        updated_account.pop('_id', None)
        return updated_account

    def update_balance(self, account_id: str, amount: float):
        if getattr(self.account_repo, 'collection', None) is not None:
            self.account_repo.collection.update_one(
                {'_id': account_id}, {'$inc': {'current_balance': amount}}
            )
        else:
            account = self.account_repo.find_by_id(account_id)
            if not account:
                return
            new_balance = (account.get('current_balance') or 0) + amount
            self.account_repo.update(account_id, {'current_balance': new_balance})

    def calculate_projected_balance(self, user_id: str, account_id: str, transactions_repo) -> float:
        """
        Calcula o saldo previsto considerando:
        - Saldo atual da conta (já inclui transações pagas)
        - Transações pendentes (status = 'pending') que ainda não foram aplicadas ao saldo
        - Transações futuras (data > hoje) que ainda não foram aplicadas ao saldo
        """
        account = self.account_repo.find_by_id(account_id)
        if not account or account.get('user_id') != user_id:
            return 0.0
        tenant_id = account.get('tenant_id')
        if not tenant_id:
            return 0.0
        
        current_balance = account.get('current_balance', 0) or 0
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if getattr(transactions_repo, 'find', None) is not None:
            pending_query = {
                'user_id': user_id,
                'account_id': account_id,
                'tenant_id': tenant_id,
                '$or': [
                    {'status': 'pending'},
                    {'date': {'$gt': today}, 'status': {'$ne': 'paid'}}
                ]
            }
            pending_transactions = list(transactions_repo.find(pending_query))
        else:
            all_txs = transactions_repo.find_all({'user_id': user_id, 'account_id': account_id, 'tenant_id': tenant_id})
            pending_transactions = []
            for tx in all_txs:
                status = tx.get('status') or 'paid'
                dt = _parse_date(tx.get('date'))
                if status == 'pending':
                    pending_transactions.append(tx)
                elif dt and dt.replace(tzinfo=None) > today and status != 'paid':
                    pending_transactions.append(tx)
        
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
        if not account or account.get('user_id') != user_id:
            raise NotFoundException('Conta não encontrada')
        tenant_id = account.get('tenant_id')
        if not tenant_id:
            raise ValidationException('Conta sem workspace. Recarregue a página.')

        try:
            # Verifica se há transações usando esta conta
            if getattr(self.transactions_repo, 'count_documents', None) is not None:
                count = self.transactions_repo.count_documents({'account_id': account_id, 'tenant_id': tenant_id})
            else:
                count = len(self.transactions_repo.find_all({'account_id': account_id, 'tenant_id': tenant_id}))
            if count > 0:
                raise ValidationException(f'Não é possível deletar. Existem {count} transações nesta conta')

            result = self.account_repo.delete(account_id)
            logger.info(f'Conta deletada: {account_id} ({account.get("name")}) - user_id: {user_id}')
            return result
        except ValidationException:
            # Re-raise ValidationException sem logar (já é esperada)
            raise
        except Exception as e:
            logger.error(f'Erro ao deletar conta {account_id}: {str(e)}', exc_info=True)
            raise ValidationException(f'Erro ao deletar conta no banco de dados. Detalhe: {str(e)}')
