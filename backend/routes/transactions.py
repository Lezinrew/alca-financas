from flask import Blueprint, request, jsonify, current_app
import pandas as pd
from io import StringIO
import uuid
from datetime import datetime

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
        account_id = request.args.get('account_id')
        filter_query = build_filter(request.user_id, month, year, category_id, transaction_type, account_id)
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
    allowed_fields = ['description', 'amount', 'category_id', 'date', 'status', 'responsible_person']
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
    from services.import_service import parse_import_file
    
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    accounts_collection = current_app.config['ACCOUNTS']
    
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo é obrigatório'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    # Aceita CSV e OFX
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.csv') or filename_lower.endswith('.ofx')):
        return jsonify({'error': 'Apenas arquivos CSV e OFX são aceitos'}), 400
    
    # Lê o conteúdo do arquivo uma vez
    file_content = file.read()
    
    # Obtém account_id do formulário (opcional)
    account_id = request.form.get('account_id')
    account_created = False
    created_account_name = None
    
    # Se não forneceu account_id, tenta detectar/criar automaticamente
    if not account_id:
        from services.account_detector import (
            extract_account_info_from_ofx,
            extract_account_info_from_csv,
            find_or_create_account
        )
        
        try:
            account_info = None
            if filename_lower.endswith('.ofx'):
                account_info = extract_account_info_from_ofx(file_content)
            elif filename_lower.endswith('.csv'):
                account_info = extract_account_info_from_csv(file.filename, file_content)
            
            if account_info:
                account_id, account_created = find_or_create_account(
                    accounts_collection,
                    request.user_id,
                    account_info,
                    file.filename
                )
                if account_created and account_id:
                    account = accounts_collection.find_one({'_id': account_id})
                    created_account_name = account.get('name') if account else None
        except Exception as e:
            # Se falhar na detecção, continua sem account_id
            pass
    
    # Se account_id foi fornecido, valida se existe
    if account_id:
        account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
        if not account:
            return jsonify({'error': 'Conta não encontrada'}), 404
    
    try:
        
        # Detecta formato e parseia
        try:
            file_format, parsed_transactions = parse_import_file(file.filename, file_content)
        except Exception as e:
            return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 400
        
        if not parsed_transactions:
            return jsonify({'error': 'Nenhuma transação encontrada no arquivo'}), 400
        
        # Importa serviço de detecção de categorias
        from services.category_detector import detect_category_from_description, get_or_create_category
        
        # Busca categorias do usuário
        user_categories = {cat['name']: cat['_id'] for cat in categories_collection.find({'user_id': request.user_id})}
        
        # Busca categorias padrão
        default_income_category = categories_collection.find_one({'user_id': request.user_id, 'type': 'income'})
        default_expense_category = categories_collection.find_one({'user_id': request.user_id, 'type': 'expense'})
        
        imported_transactions = []
        errors = []
        created_categories = []  # Para rastrear categorias criadas
        
        for idx, tx in enumerate(parsed_transactions):
            try:
                category_id = None
                
                # Para CSV padrão, usa category_name se disponível
                if file_format == 'csv' and 'category_name' in tx and tx['category_name']:
                    category_id = user_categories.get(tx['category_name'])
                    if not category_id:
                        # Tenta criar a categoria se não existir
                        try:
                            category_id = get_or_create_category(
                                categories_collection,
                                request.user_id,
                                tx['category_name'],
                                tx['type']
                            )
                            # Atualiza o dicionário de categorias
                            user_categories[tx['category_name']] = category_id
                            created_categories.append(tx['category_name'])
                        except Exception as e:
                            errors.append(f'Linha {idx + 2}: Erro ao criar categoria "{tx["category_name"]}": {str(e)}')
                            continue
                else:
                    # Para Nubank/OFX, detecta categoria automaticamente pela descrição
                    detected = detect_category_from_description(tx['description'])
                    
                    if detected:
                        category_name, color, icon = detected
                        try:
                            category_id = get_or_create_category(
                                categories_collection,
                                request.user_id,
                                category_name,
                                tx['type'],
                                color,
                                icon
                            )
                            # Atualiza o dicionário de categorias
                            if category_name not in user_categories:
                                user_categories[category_name] = category_id
                                created_categories.append(category_name)
                        except Exception as e:
                            errors.append(f'Transação {idx + 1}: Erro ao criar categoria "{category_name}": {str(e)}')
                            # Usa categoria padrão como fallback
                            if tx['type'] == 'income' and default_income_category:
                                category_id = default_income_category['_id']
                            elif tx['type'] == 'expense' and default_expense_category:
                                category_id = default_expense_category['_id']
                            else:
                                errors.append(f'Transação {idx + 1}: Não foi possível determinar a categoria')
                                continue
                    
                    # Se não conseguiu detectar, usa categoria padrão
                    if not category_id:
                        if tx['type'] == 'income' and default_income_category:
                            category_id = default_income_category['_id']
                        elif tx['type'] == 'expense' and default_expense_category:
                            category_id = default_expense_category['_id']
                        else:
                            errors.append(f'Transação {idx + 1}: Nenhuma categoria padrão encontrada para tipo {tx["type"]}')
                            continue
                
                # Validações
                if tx['amount'] <= 0:
                    errors.append(f'Transação {idx + 1}: Valor deve ser positivo')
                    continue
                
                transaction_data = {
                    '_id': str(uuid.uuid4()),
                    'user_id': request.user_id,
                    'description': tx['description'],
                    'amount': tx['amount'],
                    'type': tx['type'],
                    'category_id': category_id,
                    'date': tx['date'],
                    'is_recurring': False,
                    'status': 'paid',  # Transações importadas geralmente são pagas
                    'responsible_person': 'Leandro',
                    'installment_info': None,
                    'imported': True,
                    'import_source': file_format,
                    'created_at': datetime.utcnow()
                }
                
                # Associa a conta se fornecida
                if account_id:
                    transaction_data['account_id'] = account_id
                
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Transação {idx + 1}: Erro inesperado - {str(e)}')
        
        if imported_transactions:
            transactions_collection.insert_many(imported_transactions)
            
            # Atualiza o saldo da conta se account_id foi fornecido
            if account_id:
                from services.transaction_service import apply_account_balance_updates
                apply_account_balance_updates(accounts_collection, account_id, imported_transactions)
        
        result = {
            'message': f'{len(imported_transactions)} transações importadas com sucesso',
            'imported_count': len(imported_transactions),
            'error_count': len(errors),
            'file_format': file_format,
            'categories_created': len(created_categories),
            'categories_created_list': list(set(created_categories)),  # Remove duplicatas
            'account_created': account_created,
            'account_name': created_account_name
        }
        if errors:
            result['errors'] = errors
        return jsonify(result), 201 if imported_transactions else 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


