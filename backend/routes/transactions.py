from flask import Blueprint, request, jsonify, current_app
import pandas as pd
from io import StringIO
import uuid

from utils.auth_utils import require_auth
from services.transaction_service import build_filter, list_transactions, create_installments, apply_account_balance_updates


bp = Blueprint('transactions', __name__, url_prefix='/api/transactions')


@bp.route('', methods=['GET', 'POST'])
@require_auth
def transactions():
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    accounts_collection = current_app.config['ACCOUNTS']

    if request.method == 'GET':
        month = request.args.get('month')
        year = request.args.get('year')
        category_id = request.args.get('category_id')
        transaction_type = request.args.get('type')
        filter_query = build_filter(request.user_id, month, year, category_id, transaction_type)
        return jsonify(list_transactions(transactions_collection, categories_collection, filter_query))

    data = request.get_json()
    required_fields = ['description', 'amount', 'type', 'category_id', 'date']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Campo {field} é obrigatório'}), 400
    if data['type'] not in ['income', 'expense']:
        return jsonify({'error': 'Tipo deve ser income ou expense'}), 400

    category = categories_collection.find_one({'_id': data['category_id'], 'user_id': request.user_id})
    if not category:
        return jsonify({'error': 'Categoria não encontrada'}), 404
    if data['type'] != category['type']:
        return jsonify({'error': 'Tipo da transação não combina com tipo da categoria'}), 400

    account_id = data.get('account_id')
    if account_id:
        account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
        if not account:
            return jsonify({'error': 'Conta não encontrada'}), 404

    base_date = pd.to_datetime(data['date']).to_pydatetime()
    to_create = create_installments(data, request.user_id, base_date, account_id)
    if to_create:
        transactions_collection.insert_many(to_create)
        if account_id:
            apply_account_balance_updates(accounts_collection, account_id, to_create)
    return jsonify({'message': f'{len(to_create)} transação(ões) criada(s) com sucesso', 'count': len(to_create)}), 201


@bp.route('/<transaction_id>', methods=['PUT', 'DELETE'])
@require_auth
def transaction_detail(transaction_id: str):
    transactions_collection = current_app.config['TRANSACTIONS']
    transaction = transactions_collection.find_one({'_id': transaction_id, 'user_id': request.user_id})
    if not transaction:
        return jsonify({'error': 'Transação não encontrada'}), 404
    if request.method == 'DELETE':
        transactions_collection.delete_one({'_id': transaction_id})
        return jsonify({'message': 'Transação deletada com sucesso'})

    data = request.get_json()
    allowed_fields = ['description', 'amount', 'category_id', 'date']
    update_data = {}
    for field in allowed_fields:
        if field in data:
            if field == 'date':
                update_data[field] = pd.to_datetime(data[field]).to_pydatetime()
            elif field == 'amount':
                update_data[field] = float(data[field])
            else:
                update_data[field] = data[field]
    if update_data:
        transactions_collection.update_one({'_id': transaction_id, 'user_id': request.user_id}, {'$set': update_data})
    return jsonify({'message': 'Transação atualizada com sucesso'})


@bp.route('/import', methods=['POST'])
@require_auth
def import_transactions():
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo CSV é obrigatório'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Apenas arquivos CSV são aceitos'}), 400
    try:
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = pd.read_csv(stream)
        required_columns = ['description', 'amount', 'type', 'category_name', 'date']
        missing_columns = [col for col in required_columns if col not in csv_input.columns]
        if missing_columns:
            return jsonify({'error': f'Colunas obrigatórias ausentes: {", ".join(missing_columns)}', 'required_columns': required_columns, 'found_columns': list(csv_input.columns)}), 400
        user_categories = {cat['name']: cat['_id'] for cat in categories_collection.find({'user_id': request.user_id})}
        imported_transactions = []
        errors = []
        for index, row in csv_input.iterrows():
            try:
                if row['type'] not in ['income', 'expense']:
                    errors.append(f'Linha {index + 2}: Tipo deve ser income ou expense')
                    continue
                category_id = user_categories.get(row['category_name'])
                if not category_id:
                    errors.append(f'Linha {index + 2}: Categoria "{row["category_name"]}" não encontrada')
                    continue
                try:
                    transaction_date = pd.to_datetime(row['date']).to_pydatetime()
                except Exception:
                    errors.append(f'Linha {index + 2}: Data inválida "{row["date"]}"')
                    continue
                try:
                    amount = float(row['amount'])
                    if amount <= 0:
                        errors.append(f'Linha {index + 2}: Valor deve ser positivo')
                        continue
                except Exception:
                    errors.append(f'Linha {index + 2}: Valor inválido "{row["amount"]}"')
                    continue
                transaction_data = {
                    '_id': str(uuid.uuid4()),
                    'user_id': request.user_id,
                    'description': str(row['description']).strip(),
                    'amount': amount,
                    'type': row['type'],
                    'category_id': category_id,
                    'date': transaction_date,
                    'is_recurring': False,
                    'installment_info': None,
                    'imported': True,
                    'created_at': pd.Timestamp.now().to_pydatetime()
                }
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Linha {index + 2}: Erro inesperado - {str(e)}')
        if imported_transactions:
            transactions_collection.insert_many(imported_transactions)
        result = {'message': f'{len(imported_transactions)} transações importadas com sucesso', 'imported_count': len(imported_transactions), 'error_count': len(errors)}
        if errors:
            result['errors'] = errors
        return jsonify(result), 201 if imported_transactions else 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


