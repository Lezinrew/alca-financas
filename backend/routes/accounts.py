from flask import Blueprint, request, jsonify, current_app
import uuid
import pandas as pd
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


@bp.route('/<account_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def account_detail(account_id: str):
    accounts_collection = current_app.config['ACCOUNTS']
    transactions_collection = current_app.config['TRANSACTIONS']
    account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
    if not account:
        return jsonify({'error': 'Conta não encontrada'}), 404
    
    if request.method == 'GET':
        account['id'] = account['_id']
        account.pop('_id', None)
        return jsonify(account)
    
    if request.method == 'DELETE':
        ok = delete_account(accounts_collection, transactions_collection, request.user_id, account_id)
        if not ok:
            count = transactions_collection.count_documents({'account_id': account_id})
            return jsonify({'error': f'Não é possível deletar. Existem {count} transações nesta conta'}), 400
        return jsonify({'message': 'Conta deletada com sucesso'})
    data = request.get_json()
    update_account(accounts_collection, request.user_id, account_id, data)
    return jsonify({'message': 'Conta atualizada com sucesso'})


@bp.route('/<account_id>/import', methods=['POST'])
@require_auth
def import_credit_card_statement(account_id: str):
    """Importa fatura de cartão de crédito via PDF, OFX ou CSV"""
    from services.import_service import parse_import_file
    
    accounts_collection = current_app.config['ACCOUNTS']
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    # Verifica se a conta existe e é um cartão de crédito
    account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
    if not account:
        return jsonify({'error': 'Conta não encontrada'}), 404
    
    if account.get('type') != 'credit_card':
        return jsonify({'error': 'Esta rota é apenas para cartões de crédito'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo é obrigatório'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    # Aceita PDF, OFX e CSV
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.ofx') or filename_lower.endswith('.csv')):
        return jsonify({'error': 'Apenas arquivos PDF, OFX e CSV são aceitos'}), 400
    
    try:
        file_content = file.read()
        
        # Para PDF, retorna erro informando que ainda não é suportado
        if filename_lower.endswith('.pdf'):
            return jsonify({'error': 'Importação de PDF ainda não está implementada. Use OFX ou CSV.'}), 400
        
        # Para OFX e CSV, usa o serviço de importação existente
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
        
        imported_transactions = []
        errors = []
        created_categories = []  # Para rastrear categorias criadas
        
        for idx, tx in enumerate(parsed_transactions):
            try:
                # Para cartões de crédito, todas as transações são despesas
                if tx['type'] != 'expense':
                    continue
                
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
                                'expense'
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
                                'expense',
                                color,
                                icon
                            )
                            # Atualiza o dicionário de categorias
                            if category_name not in user_categories:
                                user_categories[category_name] = category_id
                                created_categories.append(category_name)
                        except Exception as e:
                            errors.append(f'Transação {idx + 1}: Erro ao criar categoria "{category_name}": {str(e)}')
                            continue
                    
                    # Se não conseguiu detectar, usa categoria padrão
                    if not category_id:
                        default_expense_category = categories_collection.find_one({
                            'user_id': request.user_id,
                            'type': 'expense'
                        })
                        if default_expense_category:
                            category_id = default_expense_category['_id']
                        else:
                            errors.append(f'Transação {idx + 1}: Não foi possível determinar a categoria')
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
                    'type': 'expense',
                    'category_id': category_id,
                    'account_id': account_id,
                    'date': tx['date'],
                    'is_recurring': False,
                    'status': 'paid',  # Transações importadas de fatura geralmente são pagas
                    'responsible_person': 'Leandro',
                    'installment_info': None,
                    'imported': True,
                    'import_source': file_format,
                    'created_at': pd.Timestamp.now().to_pydatetime()
                }
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Transação {idx + 1}: Erro inesperado - {str(e)}')
        
        if imported_transactions:
            transactions_collection.insert_many(imported_transactions)
            
            # Atualiza o saldo do cartão (diminui o current_balance)
            from services.transaction_service import apply_account_balance_updates
            apply_account_balance_updates(accounts_collection, account_id, imported_transactions)
        
        result = {
            'message': f'{len(imported_transactions)} transações importadas com sucesso',
            'imported_count': len(imported_transactions),
            'error_count': len(errors),
            'file_format': file_format,
            'categories_created': len(created_categories),
            'categories_created_list': list(set(created_categories))  # Remove duplicatas
        }
        if errors:
            result['errors'] = errors
        return jsonify(result), 201 if imported_transactions else 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


