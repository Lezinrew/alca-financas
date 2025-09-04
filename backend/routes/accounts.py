from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from services.account_service import list_accounts, create_account, update_account, delete_account


bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')


@bp.route('', methods=['GET', 'POST'])
@require_auth
def accounts():
    accounts_collection = current_app.config['ACCOUNTS']
    if request.method == 'GET':
        return jsonify(list_accounts(accounts_collection, request.user_id))
    data = request.get_json()
    if not data.get('name') or not data.get('type'):
        return jsonify({'error': 'Nome e tipo da conta são obrigatórios'}), 400
    if data['type'] not in ['wallet', 'checking', 'savings', 'credit_card', 'investment']:
        return jsonify({'error': 'Tipo de conta inválido'}), 400
    account = create_account(accounts_collection, request.user_id, data)
    return jsonify(account), 201


@bp.route('/<account_id>', methods=['PUT', 'DELETE'])
@require_auth
def account_detail(account_id: str):
    accounts_collection = current_app.config['ACCOUNTS']
    transactions_collection = current_app.config['TRANSACTIONS']
    account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
    if not account:
        return jsonify({'error': 'Conta não encontrada'}), 404
    if request.method == 'DELETE':
        ok = delete_account(accounts_collection, transactions_collection, request.user_id, account_id)
        if not ok:
            count = transactions_collection.count_documents({'account_id': account_id})
            return jsonify({'error': f'Não é possível deletar. Existem {count} transações nesta conta'}), 400
        return jsonify({'message': 'Conta deletada com sucesso'})
    data = request.get_json()
    update_account(accounts_collection, request.user_id, account_id, data)
    return jsonify({'message': 'Conta atualizada com sucesso'})


