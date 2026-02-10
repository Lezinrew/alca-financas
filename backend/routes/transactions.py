from flask import Blueprint, request, jsonify, current_app
import pandas as pd
from io import StringIO
import uuid
from datetime import datetime

from utils.auth_utils import require_auth
from services.transaction_service import TransactionService
from utils.exceptions import ValidationException, NotFoundException

bp = Blueprint('transactions', __name__, url_prefix='/api/transactions')

@bp.route('', methods=['GET', 'POST'])
@require_auth
def transactions():
    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)

    if request.method == 'GET':
        page = int(request.args.get('page', 1))
        # Aumenta o limite padrão para mostrar mais transações
        per_page = int(request.args.get('limit', 100))
        
        # Coleta filtros, removendo valores vazios
        filters = {}
        
        month = request.args.get('month')
        if month and month.strip():
            try:
                filters['month'] = int(month)
            except ValueError:
                pass
        
        year = request.args.get('year')
        if year and year.strip():
            try:
                filters['year'] = int(year)
            except ValueError:
                pass
        
        category_id = request.args.get('category_id')
        if category_id and category_id.strip():
            filters['category_id'] = category_id
        
        transaction_type = request.args.get('type')
        if transaction_type and transaction_type.strip():
            filters['type'] = transaction_type
        
        account_id = request.args.get('account_id')
        if account_id and account_id.strip():
            filters['account_id'] = account_id
        
        return jsonify(service.list_transactions(request.user_id, filters, page, per_page))

    try:
        data = request.get_json()
        result = service.create_transaction(request.user_id, data)
        return jsonify({'message': f"{result['count']} transação(ões) criada(s) com sucesso", 'count': result['count']}), 201
    except ValidationException as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route('/<transaction_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def transaction_detail(transaction_id: str):
    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)

    try:
        if request.method == 'GET':
            result = service.get_transaction(request.user_id, transaction_id)
            return jsonify(result)

        if request.method == 'DELETE':
            service.delete_transaction(request.user_id, transaction_id)
            return jsonify({'message': 'Transação deletada com sucesso'})

        data = request.get_json()
        result = service.update_transaction(request.user_id, transaction_id, data)
        return jsonify(result)
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route('/import', methods=['POST'])
@require_auth
def import_transactions():
    from services.import_service import parse_import_file
    from services.account_service import AccountService
    from services.category_service import CategoryService

    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    account_service = AccountService(accounts_repo, transaction_repo)
    category_service = CategoryService(categories_repo, transaction_repo)
    
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
                    accounts_repo,
                    request.user_id,
                    account_info,
                    file.filename,
                    account_service=account_service
                )
                if account_created and account_id:
                    account = accounts_repo.find_by_id(account_id) if hasattr(accounts_repo, 'find_by_id') else None
                    created_account_name = account.get('name') if account else None
        except Exception as e:
            # Se falhar na detecção, continua sem account_id
            # Mas registra o erro para informar ao usuário
            current_app.logger.warning(f'Falha ao detectar/criar conta automaticamente: {str(e)}')
            pass
    
    if account_id:
        account = accounts_repo.find_by_id(account_id) if hasattr(accounts_repo, 'find_by_id') else None
        if not account or account.get('user_id') != request.user_id:
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
        
        user_cats = categories_repo.find_by_user(request.user_id)
        user_categories = {cat['name']: (cat.get('id') or cat.get('_id')) for cat in user_cats}
        income_cats = categories_repo.find_by_type(request.user_id, 'income') if hasattr(categories_repo, 'find_by_type') else (categories_repo.find_all({'user_id': request.user_id, 'type': 'income'}) or [])
        expense_cats = categories_repo.find_by_type(request.user_id, 'expense') if hasattr(categories_repo, 'find_by_type') else (categories_repo.find_all({'user_id': request.user_id, 'type': 'expense'}) or [])
        default_income_category = income_cats[0] if income_cats else None
        default_expense_category = expense_cats[0] if expense_cats else None
        
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
                                category_service,
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
                                category_service,
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
                                category_id = default_income_category.get('id') or default_income_category.get('_id')
                            elif tx['type'] == 'expense' and default_expense_category:
                                category_id = default_expense_category.get('id') or default_expense_category.get('_id')
                            else:
                                errors.append(f'Transação {idx + 1}: Não foi possível determinar a categoria')
                                continue
                    
                    # Se não conseguiu detectar, usa categoria padrão
                    if not category_id:
                        if tx['type'] == 'income' and default_income_category:
                            category_id = default_income_category.get('id') or default_income_category.get('_id')
                        elif tx['type'] == 'expense' and default_expense_category:
                            category_id = default_expense_category.get('id') or default_expense_category.get('_id')
                        else:
                            errors.append(f'Transação {idx + 1}: Nenhuma categoria padrão encontrada para tipo {tx["type"]}')
                            continue
                
                # Validações
                if tx['amount'] <= 0:
                    errors.append(f'Transação {idx + 1}: Valor deve ser positivo')
                    continue
                
                date_val = tx['date']
                if hasattr(date_val, 'strftime'):
                    date_val = date_val.strftime('%Y-%m-%d')
                transaction_data = {
                    'id': str(uuid.uuid4()),
                    'user_id': request.user_id,
                    'description': tx['description'],
                    'amount': tx['amount'],
                    'type': tx['type'],
                    'category_id': category_id,
                    'date': date_val,
                    'is_recurring': False,
                    'status': 'paid',
                    'responsible_person': 'Leandro',
                    'installment_info': None,
                }
                
                # Associa a conta se fornecida
                if account_id:
                    transaction_data['account_id'] = account_id
                
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Transação {idx + 1}: Erro inesperado - {str(e)}')
        
        if imported_transactions:
            service.create_many_transactions(imported_transactions)
            
            # Atualiza o saldo da conta se account_id foi fornecido
            # Apenas transações com status 'paid' afetam o saldo atual
            if account_id:
                # Calcula o saldo a ser atualizado (apenas transações pagas)
                total_change = 0
                for tx in imported_transactions:
                    # Só atualiza saldo se a transação estiver paga
                    if tx.get('status') == 'paid':
                        amount = tx['amount']
                        if tx['type'] == 'expense':
                            amount = -amount
                        total_change += amount
                
                if total_change != 0:
                    account_service.update_balance(account_id, total_change)
        
        result = {
            'message': f'{len(imported_transactions)} transações importadas com sucesso',
            'imported_count': len(imported_transactions),
            'error_count': len(errors),
            'file_format': file_format,
            'categories_created': len(created_categories),
            'categories_created_list': list(set(created_categories)),  # Remove duplicatas
            'account_created': account_created,
            'account_name': created_account_name,
            'account_id': account_id if account_id else None,
            'warning': None
        }
        
        # Adiciona aviso se não conseguiu associar a uma conta
        if not account_id and imported_transactions:
            result['warning'] = 'As transações foram importadas sem associação a uma conta. Crie uma conta e associe as transações manualmente se necessário.'
        if errors:
            result['errors'] = errors
        return jsonify(result), 201 if imported_transactions else 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


