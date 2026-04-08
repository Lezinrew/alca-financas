from flask import Blueprint, request, jsonify, current_app
import pandas as pd
from io import StringIO
import uuid
from datetime import datetime

from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from services.transaction_service import TransactionService
from utils.exceptions import ValidationException, NotFoundException

bp = Blueprint('transactions', __name__, url_prefix='/api/transactions')

@bp.route('', methods=['GET', 'POST'])
@require_auth
@require_tenant
def transactions():
    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)

    if request.method == 'GET':
        page = int(request.args.get('page', 1))
        # Limite padrão mais profissional
        per_page = int(request.args.get('limit', 50))
        
        # Coleta filtros em formato avançado
        filters = {
            'page': page,
            'limit': per_page,
            'month': request.args.get('month'),
            'year': request.args.get('year'),
            'date_from': request.args.get('date_from'),
            'date_to': request.args.get('date_to'),
            'type': request.args.get('type'),
            'account_id': request.args.get('account_id'),
            'account_ids': request.args.get('account_ids'),
            'category_id': request.args.get('category_id'),
            'category_ids': request.args.get('category_ids'),
            'min_amount': request.args.get('min_amount'),
            'max_amount': request.args.get('max_amount'),
            'search': request.args.get('search'),
            'status': request.args.get('status'),
            'sort': request.args.get('sort'),
        }
        
        # Remove chaves com valores vazios para não poluir o repositório
        filters = {k: v for k, v in filters.items() if v not in (None, '', [])}
        
        return jsonify(
            service.list_transactions(
                request.user_id,
                filters,
                page,
                per_page,
                tenant_id=request.tenant_id,
            )
        )

    try:
        data = request.get_json() or {}
        # tenant_id é garantido pelo decorator @require_tenant
        result = service.create_transaction(
            request.user_id,
            data,
            tenant_id=request.tenant_id,
        )
        return jsonify({'message': f"{result['count']} transação(ões) criada(s) com sucesso", 'count': result['count']}), 201
    except ValidationException as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route('/<transaction_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
@require_tenant
def transaction_detail(transaction_id: str):
    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)

    try:
        transaction = transaction_repo.find_by_id(transaction_id) if hasattr(transaction_repo, 'find_by_id') else None
        if (
            not transaction
            or transaction.get('user_id') != request.user_id
            or transaction.get('tenant_id') != request.tenant_id
        ):
            return jsonify({'error': 'Transação não encontrada'}), 404

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
@require_tenant
def import_transactions():
    from services.import_service import parse_import_file
    from services.account_service import AccountService
    from services.category_service import CategoryService
    from services.merchant_alias_service import MerchantAliasService

    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    service = TransactionService(transaction_repo, categories_repo, accounts_repo)
    account_service = AccountService(accounts_repo, transaction_repo)
    category_service = CategoryService(categories_repo, transaction_repo)
    alias_repo = current_app.config.get('MERCHANT_ALIAS_REPO')
    alias_service = MerchantAliasService(alias_repo) if alias_repo else None
    
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
    
    # Obtém account_id do formulário (opcional, mas obrigatório ao final do fluxo)
    account_id = request.form.get('account_id')
    account_created = False
    created_account_name = None
    
    # Se não forneceu account_id explicitamente, tenta detectar/criar automaticamente
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
                    account_service=account_service,
                    tenant_id=request.tenant_id,
                )
                if account_created and account_id:
                    account = accounts_repo.find_by_id(account_id) if hasattr(accounts_repo, 'find_by_id') else None
                    created_account_name = account.get('name') if account else None
        except Exception as e:
            # Se falhar na detecção, registra log e segue para validação abaixo
            current_app.logger.warning(f'Falha ao detectar/criar conta automaticamente: {str(e)}')
    
    # Política profissional: não permitimos mais importação de transações sem conta associada.
    # Se, após tentativa de detecção/criação, ainda não houver account_id, abortamos com erro claro.
    if not account_id:
        return jsonify({
            'error': 'Não foi possível identificar a conta de destino para este arquivo. '
                     'Selecione uma conta antes de importar ou tente novamente com um arquivo compatível.'
        }), 400
    
    # Validação da conta escolhida/detectada
    account = accounts_repo.find_by_id(account_id) if hasattr(accounts_repo, 'find_by_id') else None
    if (
        not account
        or account.get('user_id') != request.user_id
        or account.get('tenant_id') != request.tenant_id
    ):
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
        
        user_cats = categories_repo.find_by_user(request.user_id, tenant_id=request.tenant_id)
        user_categories = {cat['name']: (cat.get('id') or cat.get('_id')) for cat in user_cats}
        income_cats = (
            categories_repo.find_by_type(request.user_id, 'income', tenant_id=request.tenant_id)
            if hasattr(categories_repo, 'find_by_type')
            else (categories_repo.find_all({'user_id': request.user_id, 'type': 'income', 'tenant_id': request.tenant_id}) or [])
        )
        expense_cats = (
            categories_repo.find_by_type(request.user_id, 'expense', tenant_id=request.tenant_id)
            if hasattr(categories_repo, 'find_by_type')
            else (categories_repo.find_all({'user_id': request.user_id, 'type': 'expense', 'tenant_id': request.tenant_id}) or [])
        )
        default_income_category = income_cats[0] if income_cats else None
        default_expense_category = expense_cats[0] if expense_cats else None
        
        imported_transactions = []
        errors = []
        created_categories = []  # Para rastrear categorias criadas
        
        tenant_id = getattr(request, 'tenant_id', None)

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
                                tx['type'],
                                tenant_id=tenant_id,
                            )
                            # Atualiza o dicionário de categorias
                            user_categories[tx['category_name']] = category_id
                            created_categories.append(tx['category_name'])
                        except Exception as e:
                            errors.append(f'Linha {idx + 2}: Erro ao criar categoria "{tx["category_name"]}": {str(e)}')
                            continue
                else:
                    # Para Nubank/OFX, primeiro tenta resolver via aliases persistentes
                    detected = None
                    alias_category = None

                    if alias_service:
                        alias_result = alias_service.find_category_for_description(
                            user_id=request.user_id,
                            tenant_id=tenant_id,
                            description=tx['description'],
                            category_type=tx['type'],
                        )
                        if alias_result:
                            alias_name, alias_type = alias_result
                            alias_category = (alias_name, alias_type)
                            current_app.logger.debug(
                                "ImportTransactions: alias aplicado",
                                extra={
                                    "user_id": request.user_id,
                                    "tenant_id": tenant_id,
                                    "description": tx['description'],
                                    "tx_type": tx['type'],
                                    "alias_category_name": alias_name,
                                    "alias_category_type": alias_type,
                                },
                            )
                        else:
                            current_app.logger.debug(
                                "ImportTransactions: nenhum alias encontrado",
                                extra={
                                    "user_id": request.user_id,
                                    "tenant_id": tenant_id,
                                    "description": tx['description'],
                                    "tx_type": tx['type'],
                                },
                            )

                    if alias_category:
                        # Usa categoria padronizada do alias; cor/ícone são derivados pela heurística genérica
                        alias_name, alias_type = alias_category
                        detected = detect_category_from_description(alias_name) or (alias_name, None, None)
                    else:
                        # Se não houver alias, usa heurística pela descrição original
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
                                icon,
                                tenant_id=tenant_id,
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
                tenant_id = getattr(request, 'tenant_id', None)
                if not tenant_id:
                    errors.append('Importação exige workspace. Recarregue a página ou faça login novamente.')
                    continue
                transaction_data = {
                    'id': str(uuid.uuid4()),
                    'user_id': request.user_id,
                    'tenant_id': tenant_id,
                    'account_tenant_id': tenant_id,
                    'category_tenant_id': tenant_id,
                    'description': tx['description'],
                    'amount': tx['amount'],
                    'type': tx['type'],
                    'category_id': category_id,
                    'date': date_val,
                    'is_recurring': False,
                    'status': 'paid',
                    'responsible_person': 'Leandro',
                    'installment_info': None,
                    # Propaga FITID (quando disponível) para deduplicação e rastreio
                    'fitid': (tx.get('raw_data') or {}).get('fitid'),
                }
                # account_id já foi garantido/validado anteriormente e é obrigatório
                transaction_data['account_id'] = account_id
                imported_transactions.append(transaction_data)
            except Exception as e:
                errors.append(f'Transação {idx + 1}: Erro inesperado - {str(e)}')

        duplicates_skipped = 0

        if imported_transactions:
            # Deduplicação básica por FITID (quando disponível)
            fitids = sorted(
                {tx.get('fitid') for tx in imported_transactions if tx.get('fitid')}
            )
            existing_fitids = set()
            if fitids:
                existing_fitids = set(
                    transaction_repo.find_existing_fitids(
                        request.user_id,
                        account_id,
                        fitids,
                        tenant_id=tenant_id,
                    )
                )

            deduped_transactions = []
            for tx in imported_transactions:
                tx_fitid = tx.get('fitid')
                if tx_fitid and tx_fitid in existing_fitids:
                    duplicates_skipped += 1
                    continue
                deduped_transactions.append(tx)

            if deduped_transactions:
                service.create_many_transactions(deduped_transactions)

                # Atualiza o saldo da conta apenas para transações realmente inseridas
                total_change = 0
                for tx in deduped_transactions:
                    if tx.get('status') == 'paid':
                        amount = tx['amount']
                        if tx['type'] == 'expense':
                            amount = -amount
                        total_change += amount

                if total_change != 0:
                    account_service.update_balance(account_id, total_change)
        else:
            deduped_transactions = []

        result = {
            'message': f'{len(deduped_transactions)} transações importadas com sucesso',
            'imported_count': len(deduped_transactions),
            'error_count': len(errors),
            'file_format': file_format,
            'categories_created': len(created_categories),
            'categories_created_list': list(set(created_categories)),  # Remove duplicatas
            'account_created': account_created,
            'account_name': created_account_name,
            'account_id': account_id if account_id else None,
            'duplicates_skipped': duplicates_skipped,
        }

        if errors:
            result['errors'] = errors
        return jsonify(result), 201 if deduped_transactions else 400
    except ValidationException as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500


@bp.route('/facets', methods=['GET'])
@require_auth
@require_tenant
def transactions_facets():
    """
    Retorna contadores agregados de categorias, contas e tipos
    para enriquecer a UX de filtros.
    """
    transaction_repo = current_app.config['TRANSACTIONS']
    categories_repo = current_app.config['CATEGORIES']
    accounts_repo = current_app.config['ACCOUNTS']
    _ = TransactionService(transaction_repo, categories_repo, accounts_repo)

    # Reaproveita lógica de filtros avançados (sem paginação)
    filters = {
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
        'month': request.args.get('month'),
        'year': request.args.get('year'),
        'type': request.args.get('type'),
        'account_ids': request.args.get('account_ids'),
        'category_ids': request.args.get('category_ids'),
        'min_amount': request.args.get('min_amount'),
        'max_amount': request.args.get('max_amount'),
        'search': request.args.get('search'),
        'status': request.args.get('status'),
        'is_recurring': request.args.get('is_recurring'),
        # Não usamos paginação aqui
    }

    # Aplica filtros principais de período / tipo / método, etc, de forma similar a find_advanced
    params = {k: v for k, v in filters.items() if v not in (None, '', [])}
    from repositories.transaction_repository_supabase import TransactionRepository
    tmp_repo = TransactionRepository()

    tenant_id = getattr(request, 'tenant_id', None)
    adv = tmp_repo.find_advanced(request.user_id, {**params, 'limit': 5000}, tenant_id=tenant_id)
    data = adv.get('data') or []

    # Agregações em memória (para o subconjunto filtrado)
    from collections import Counter

    cat_counter = Counter()
    acc_counter = Counter()
    type_counter = Counter()

    for tx in data:
        if tx.get('category_id'):
            cat_counter[tx['category_id']] += 1
        if tx.get('account_id'):
            acc_counter[tx['account_id']] += 1
        if tx.get('type'):
            type_counter[tx['type']] += 1

    # Resolve nomes de categorias e contas
    categories = []
    if cat_counter:
        cat_ids = list(cat_counter.keys())
        for cid in cat_ids:
            cat = categories_repo.find_by_id(cid) if hasattr(categories_repo, 'find_by_id') else None
            if cat:
                categories.append({
                    'id': cid,
                    'name': cat.get('name', ''),
                    'count': cat_counter[cid],
                })

    accounts = []
    if acc_counter:
        acc_ids = list(acc_counter.keys())
        for aid in acc_ids:
            acc = accounts_repo.find_by_id(aid) if hasattr(accounts_repo, 'find_by_id') else None
            if acc:
                accounts.append({
                    'id': aid,
                    'name': acc.get('name', ''),
                    'count': acc_counter[aid],
                })

    types = [{'type': t, 'count': c} for t, c in type_counter.items()]

    return jsonify({
        'categories': categories,
        'accounts': accounts,
        'types': types,
    })
