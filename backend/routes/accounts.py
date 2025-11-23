from flask import Blueprint, request, jsonify, current_app
import uuid
import pandas as pd
from datetime import datetime
from utils.auth_utils import require_auth
from repositories.account_repository import AccountRepository
from repositories.transaction_repository import TransactionRepository
from repositories.category_repository import CategoryRepository
from services.account_service import AccountService
from services.transaction_service import TransactionService
from services.category_service import CategoryService
from utils.exceptions import ValidationException, NotFoundException
from extensions import limiter

bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

@bp.route('', methods=['GET', 'POST'])
@require_auth
@limiter.limit("200 per hour")  # Aumenta limite para GET de contas (muitos componentes precisam)
def accounts():
    accounts_collection = current_app.config['ACCOUNTS']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    repo = AccountRepository(accounts_collection)
    service = AccountService(repo, transactions_collection)

    if request.method == 'GET':
        accounts = service.list_accounts(request.user_id)
        # Garante que todas as contas pertencem ao usuário
        filtered_accounts = [acc for acc in accounts if acc.get('user_id') == request.user_id]
        
        # Calcula saldo previsto para cada conta e adiciona campos específicos
        transactions_collection = current_app.config['TRANSACTIONS']
        for acc in filtered_accounts:
            if acc.get('id'):
                projected = service.calculate_projected_balance(
                    request.user_id, 
                    acc['id'], 
                    transactions_collection
                )
                acc['projected_balance'] = projected
                
                # Para cartões de crédito, adiciona o limite total (initial_balance)
                if acc.get('type') == 'credit_card':
                    acc['limit'] = acc.get('initial_balance', 0)
        
        return jsonify(filtered_accounts)
    
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        print(f"DEBUG: Criando conta - user_id={request.user_id}, data={request_data}")
        account = service.create_account(request.user_id, request_data)
        return jsonify(account), 201
    except ValidationException as e:
        print(f"DEBUG: ValidationException: {e.to_dict()}")
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception ao criar conta: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Erro ao criar conta: {str(e)}'}), 500

@bp.route('/<account_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def account_detail(account_id: str):
    accounts_collection = current_app.config['ACCOUNTS']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    repo = AccountRepository(accounts_collection)
    service = AccountService(repo, transactions_collection)

    try:
        if request.method == 'GET':
            account = repo.find_by_id(account_id)
            if not account or account['user_id'] != request.user_id:
                return jsonify({'error': 'Conta não encontrada'}), 404
            account['id'] = account['_id']
            account.pop('_id', None)
            return jsonify(account)
        
        if request.method == 'DELETE':
            service.delete_account(request.user_id, account_id)
            return jsonify({'message': 'Conta deletada com sucesso'})
        
        data = request.get_json()
        result = service.update_account(request.user_id, account_id, data)
        return jsonify(result)
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code

@bp.route('/<account_id>/import', methods=['POST'])
@require_auth
def import_credit_card_statement(account_id: str):
    """Importa fatura de cartão de crédito via PDF, OFX ou CSV"""
    from services.import_service import parse_import_file
    
    accounts_collection = current_app.config['ACCOUNTS']
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    account_repo = AccountRepository(accounts_collection)
    account_service = AccountService(account_repo, transactions_collection)
    
    category_repo = CategoryRepository(categories_collection)
    category_service = CategoryService(category_repo, transactions_collection)
    
    transaction_repo = TransactionRepository(transactions_collection)
    transaction_service = TransactionService(transaction_repo, categories_collection, accounts_collection)
    
    # Verifica se a conta existe e é um cartão de crédito
    account = account_repo.find_by_id(account_id)
    if not account or account['user_id'] != request.user_id:
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
                                category_service,
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
                                category_service,
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
                    'created_at': datetime.utcnow()
                }
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Transação {idx + 1}: Erro inesperado - {str(e)}')
        
        if imported_transactions:
            transaction_service.create_many_transactions(imported_transactions)
            
            # Atualiza o saldo do cartão (diminui o current_balance)
            # Calcula o total
            total_amount = sum(t['amount'] for t in imported_transactions)
            # Como são despesas, subtrai
            account_service.update_balance(account_id, -total_amount)
        
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


