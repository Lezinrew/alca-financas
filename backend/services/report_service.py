from datetime import datetime, timedelta
from typing import Dict, Any, List


def _period_iso(month: int, year: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def dashboard_summary_supabase(transactions_repo, categories_repo, user_id: str, month: int, year: int) -> Dict[str, Any]:
    """Dashboard summary usando repositórios Supabase (find_all, find_by_id, etc.)."""
    start_iso, end_iso = _period_iso(month, year)
    transactions_list = transactions_repo.find_by_user_and_date_range(user_id, start_iso, end_iso)
    total_income = sum(float(t.get('amount', 0)) for t in transactions_list if t.get('type') == 'income')
    total_expense = sum(float(t.get('amount', 0)) for t in transactions_list if t.get('type') == 'expense')
    balance = total_income - total_expense

    recent_raw = transactions_repo.find_by_user_limit(user_id, 10)
    recent_transactions = []
    for t in recent_raw:
        row = dict(t)
        cat_id = row.get('category_id')
        if cat_id:
            category = categories_repo.find_by_id(cat_id)
            if category:
                row['category'] = {
                    'name': category.get('name', ''),
                    'color': category.get('color', '#6b7280'),
                    'icon': category.get('icon', 'circle')
                }
        row['id'] = row.get('id') or row.get('_id')
        row.pop('_id', None)
        recent_transactions.append(row)

    expense_by_category = []
    income_by_category = []
    by_cat_expense: Dict[str, Dict[str, Any]] = {}
    by_cat_income: Dict[str, Dict[str, Any]] = {}
    for t in transactions_list:
        cat_id = t.get('category_id') or ''
        amount = float(t.get('amount', 0))
        typ = t.get('type', 'expense')
        if typ == 'expense':
            by_cat_expense.setdefault(cat_id, {'total': 0, 'count': 0})
            by_cat_expense[cat_id]['total'] += amount
            by_cat_expense[cat_id]['count'] += 1
        else:
            by_cat_income.setdefault(cat_id, {'total': 0, 'count': 0})
            by_cat_income[cat_id]['total'] += amount
            by_cat_income[cat_id]['count'] += 1

    for cat_id, v in sorted(by_cat_expense.items(), key=lambda x: -x[1]['total']):
        category = categories_repo.find_by_id(cat_id) if cat_id else None
        expense_by_category.append({
            'category_id': cat_id,
            'category_name': category.get('name', 'Sem categoria') if category else 'Sem categoria',
            'category_color': category.get('color', '#6b7280') if category else '#6b7280',
            'category_icon': category.get('icon', 'circle') if category else 'circle',
            'total': v['total'],
            'count': v['count'],
            'percentage': (v['total'] / total_expense * 100) if total_expense > 0 else 0
        })
    for cat_id, v in sorted(by_cat_income.items(), key=lambda x: -x[1]['total']):
        category = categories_repo.find_by_id(cat_id) if cat_id else None
        income_by_category.append({
            'category_id': cat_id,
            'category_name': category.get('name', 'Sem categoria') if category else 'Sem categoria',
            'category_color': category.get('color', '#6b7280') if category else '#6b7280',
            'category_icon': category.get('icon', 'circle') if category else 'circle',
            'total': v['total'],
            'count': v['count'],
            'percentage': (v['total'] / total_income * 100) if total_income > 0 else 0
        })

    return {
        'period': {
            'month': month,
            'year': year,
            'start_date': datetime(year, month, 1).isoformat(),
            'end_date': (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)).isoformat()
        },
        'summary': {
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': balance,
            'transactions_count': len(transactions_list)
        },
        'recent_transactions': recent_transactions,
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category
    }


def monthly_evolution_supabase(transactions_repo, user_id: str, months_back: int) -> List[Dict[str, Any]]:
    """Evolução mensal usando repositório Supabase."""
    evolution_data: List[Dict[str, Any]] = []
    current_date = datetime.now()
    for i in range(months_back - 1, -1, -1):
        target_date = current_date - timedelta(days=30 * i)
        month_start = target_date.replace(day=1)
        if target_date.month == 12:
            month_end = target_date.replace(year=target_date.year + 1, month=1, day=1)
        else:
            month_end = target_date.replace(month=target_date.month + 1, day=1)
        start_iso = month_start.strftime('%Y-%m-%d')
        end_iso = month_end.strftime('%Y-%m-%d')
        month_transactions = transactions_repo.find_by_user_and_date_range(user_id, start_iso, end_iso)
        month_income = sum(float(t.get('amount', 0)) for t in month_transactions if t.get('type') == 'income')
        month_expense = sum(float(t.get('amount', 0)) for t in month_transactions if t.get('type') == 'expense')
        evolution_data.append({
            'period': target_date.strftime('%m/%Y'),
            'month': target_date.month,
            'year': target_date.year,
            'income': month_income,
            'expense': month_expense,
            'balance': month_income - month_expense,
            'transactions_count': len(month_transactions)
        })
    return evolution_data


def dashboard_summary(transactions_collection, categories_collection, user_id: str, month: int, year: int) -> Dict[str, Any]:
    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    period_filter = {'user_id': user_id, 'date': {'$gte': start_date, '$lt': end_date}}

    transactions_list = list(transactions_collection.find(period_filter))
    total_income = sum(t['amount'] for t in transactions_list if t['type'] == 'income')
    total_expense = sum(t['amount'] for t in transactions_list if t['type'] == 'expense')
    balance = total_income - total_expense

    recent_transactions = list(transactions_collection.find({'user_id': user_id}).sort('date', -1).limit(10))
    for transaction in recent_transactions:
        category = categories_collection.find_one({'_id': transaction['category_id']})
        if category:
            transaction['category'] = {
                'name': category['name'],
                'color': category['color'],
                'icon': category['icon']
            }
        if '_id' in transaction:
            transaction['id'] = transaction['_id']
            transaction.pop('_id', None)

    expense_pipeline = [
        {'$match': {**period_filter, 'type': 'expense'}},
        {'$group': {'_id': '$category_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
        {'$sort': {'total': -1}}
    ]
    expense_by_category = []
    for item in transactions_collection.aggregate(expense_pipeline):
        category = categories_collection.find_one({'_id': item['_id']})
        if category:
            expense_by_category.append({
                'category_id': item['_id'],
                'category_name': category['name'],
                'category_color': category['color'],
                'category_icon': category['icon'],
                'total': item['total'],
                'count': item['count'],
                'percentage': (item['total'] / total_expense * 100) if total_expense > 0 else 0
            })

    income_pipeline = [
        {'$match': {**period_filter, 'type': 'income'}},
        {'$group': {'_id': '$category_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
        {'$sort': {'total': -1}}
    ]
    income_by_category = []
    for item in transactions_collection.aggregate(income_pipeline):
        category = categories_collection.find_one({'_id': item['_id']})
        if category:
            income_by_category.append({
                'category_id': item['_id'],
                'category_name': category['name'],
                'category_color': category['color'],
                'category_icon': category['icon'],
                'total': item['total'],
                'count': item['count'],
                'percentage': (item['total'] / total_income * 100) if total_income > 0 else 0
            })

    return {
        'period': {
            'month': month,
            'year': year,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'summary': {
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': balance,
            'transactions_count': len(transactions_list)
        },
        'recent_transactions': recent_transactions,
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category
    }


def monthly_evolution(transactions_collection, user_id: str, months_back: int):
    evolution_data: List[Dict[str, Any]] = []
    current_date = datetime.now()
    for i in range(months_back - 1, -1, -1):
        target_date = current_date - timedelta(days=30 * i)
        month_start = target_date.replace(day=1)
        month_end = target_date.replace(year=target_date.year + 1, month=1, day=1) if target_date.month == 12 else target_date.replace(month=target_date.month + 1, day=1)
        month_filter = {'user_id': user_id, 'date': {'$gte': month_start, '$lt': month_end}}
        month_transactions = list(transactions_collection.find(month_filter))
        month_income = sum(t['amount'] for t in month_transactions if t['type'] == 'income')
        month_expense = sum(t['amount'] for t in month_transactions if t['type'] == 'expense')
        evolution_data.append({
            'period': target_date.strftime('%m/%Y'),
            'month': target_date.month,
            'year': target_date.year,
            'income': month_income,
            'expense': month_expense,
            'balance': month_income - month_expense,
            'transactions_count': len(month_transactions)
        })
    return evolution_data


def overview_report(transactions_collection, categories_collection, accounts_collection, user_id: str, month: int, year: int, report_type: str, account_id: str = None) -> Dict[str, Any]:
    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    period_filter = {'user_id': user_id, 'date': {'$gte': start_date, '$lt': end_date}}
    
    # Adiciona filtro por conta se fornecido
    if account_id:
        period_filter['account_id'] = account_id

    result: Dict[str, Any] = {
        'period': {
            'month': month,
            'year': year,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'report_type': report_type
    }

    if report_type == 'expenses_by_category':
        pipeline = [
            {'$match': {**period_filter, 'type': 'expense'}},
            {'$group': {'_id': '$category_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
            {'$sort': {'total': -1}}
        ]
        total_amount = 0.0
        categories_data: List[Dict[str, Any]] = []
        for item in transactions_collection.aggregate(pipeline):
            category = categories_collection.find_one({'_id': item['_id']}) if item.get('_id') else None
            if category:
                total_amount += item.get('total', 0)
                categories_data.append({
                    'category_id': item.get('_id'),
                    'category_name': category.get('name', 'Sem categoria'),
                    'category_color': category.get('color', '#6b7280'),
                    'category_icon': category.get('icon', 'circle'),
                    'total': item.get('total', 0),
                    'count': item.get('count', 0)
                })
        for item in categories_data:
            item['percentage'] = (item.get('total', 0) / total_amount * 100) if total_amount > 0 else 0
        result['data'] = categories_data
        result['total_amount'] = total_amount

    elif report_type == 'income_by_category':
        pipeline = [
            {'$match': {**period_filter, 'type': 'income'}},
            {'$group': {'_id': '$category_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
            {'$sort': {'total': -1}}
        ]
        total_amount = 0.0
        categories_data: List[Dict[str, Any]] = []
        for item in transactions_collection.aggregate(pipeline):
            category = categories_collection.find_one({'_id': item['_id']}) if item.get('_id') else None
            if category:
                total_amount += item.get('total', 0)
                categories_data.append({
                    'category_id': item.get('_id'),
                    'category_name': category.get('name', 'Sem categoria'),
                    'category_color': category.get('color', '#6b7280'),
                    'category_icon': category.get('icon', 'circle'),
                    'total': item.get('total', 0),
                    'count': item.get('count', 0)
                })
        for item in categories_data:
            item['percentage'] = (item.get('total', 0) / total_amount * 100) if total_amount > 0 else 0
        result['data'] = categories_data
        result['total_amount'] = total_amount

    elif report_type == 'expenses_by_account':
        pipeline = [
            {'$match': {**period_filter, 'type': 'expense'}},
            {'$group': {'_id': '$account_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
            {'$sort': {'total': -1}}
        ]
        total_amount = 0.0
        accounts_data: List[Dict[str, Any]] = []
        for item in transactions_collection.aggregate(pipeline):
            account = accounts_collection.find_one({'_id': item['_id']}) if item['_id'] else None
            # Se não encontrar a conta, indica que são transações sem conta associada
            account_name = account['name'] if account else 'Sem conta associada'
            account_color = account['color'] if account else '#6c757d'
            account_icon = account['icon'] if account else 'wallet2'
            total_amount += item['total']
            accounts_data.append({
                'account_id': item['_id'],
                'account_name': account_name,
                'account_color': account_color,
                'account_icon': account_icon,
                'total': item['total'],
                'count': item['count']
            })
        for item in accounts_data:
            item['percentage'] = (item.get('total', 0) / total_amount * 100) if total_amount > 0 else 0
        result['data'] = accounts_data
        result['total_amount'] = total_amount

    elif report_type == 'income_by_account':
        pipeline = [
            {'$match': {**period_filter, 'type': 'income'}},
            {'$group': {'_id': '$account_id', 'total': {'$sum': '$amount'}, 'count': {'$sum': 1}}},
            {'$sort': {'total': -1}}
        ]
        total_amount = 0.0
        accounts_data: List[Dict[str, Any]] = []
        for item in transactions_collection.aggregate(pipeline):
            account = accounts_collection.find_one({'_id': item['_id']}) if item.get('_id') else None
            # Se não encontrar a conta, indica que são transações sem conta associada
            account_name = account.get('name', 'Sem conta associada') if account else 'Sem conta associada'
            account_color = account.get('color', '#6c757d') if account else '#6c757d'
            account_icon = account.get('icon', 'wallet2') if account else 'wallet2'
            total_amount += item.get('total', 0)
            accounts_data.append({
                'account_id': item.get('_id'),
                'account_name': account_name,
                'account_color': account_color,
                'account_icon': account_icon,
                'total': item.get('total', 0),
                'count': item.get('count', 0)
            })
        for item in accounts_data:
            item['percentage'] = (item.get('total', 0) / total_amount * 100) if total_amount > 0 else 0
        result['data'] = accounts_data
        result['total_amount'] = total_amount

    elif report_type == 'balance_by_account':
        accounts_list = list(accounts_collection.find({'user_id': user_id, 'is_active': True}))
        accounts_data: List[Dict[str, Any]] = []
        for account in accounts_list:
            account_transactions = list(transactions_collection.find({'user_id': user_id, 'account_id': account.get('_id')}))
            income_total = sum(t.get('amount', 0) for t in account_transactions if t.get('type') == 'income')
            expense_total = sum(t.get('amount', 0) for t in account_transactions if t.get('type') == 'expense')
            current_balance = account.get('initial_balance', 0) + income_total - expense_total
            accounts_data.append({
                'account_id': account.get('_id'),
                'account_name': account.get('name', 'Sem nome'),
                'account_color': account.get('color', '#6b7280'),
                'account_icon': account.get('icon', 'wallet2'),
                'account_type': account.get('type', 'wallet'),
                'initial_balance': account.get('initial_balance', 0),
                'current_balance': current_balance,
                'total_income': income_total,
                'total_expense': expense_total
            })
        result['data'] = accounts_data
        result['total_amount'] = sum(item.get('current_balance', 0) for item in accounts_data)
    else:
        # Tipo de relatório não reconhecido - retorna estrutura vazia
        result['data'] = []
        result['total_amount'] = 0.0

    # Garante que sempre há uma lista de dados, mesmo que vazia
    if 'data' not in result:
        result['data'] = []
    if 'total_amount' not in result:
        result['total_amount'] = 0.0

    return result


def comparison_report(transactions_collection, user_id: str, current_month: int, current_year: int) -> Dict[str, Any]:
    current_start = datetime(current_year, current_month, 1)
    current_end = datetime(current_year + 1, 1, 1) if current_month == 12 else datetime(current_year, current_month + 1, 1)
    if current_month == 1:
        prev_start = datetime(current_year - 1, 12, 1)
        prev_end = datetime(current_year, 1, 1)
    else:
        prev_start = datetime(current_year, current_month - 1, 1)
        prev_end = current_start

    current_transactions = list(transactions_collection.find({'user_id': user_id, 'date': {'$gte': current_start, '$lt': current_end}}))
    current_income = sum(t['amount'] for t in current_transactions if t['type'] == 'income')
    current_expense = sum(t['amount'] for t in current_transactions if t['type'] == 'expense')

    prev_transactions = list(transactions_collection.find({'user_id': user_id, 'date': {'$gte': prev_start, '$lt': prev_end}}))
    prev_income = sum(t['amount'] for t in prev_transactions if t['type'] == 'income')
    prev_expense = sum(t['amount'] for t in prev_transactions if t['type'] == 'expense')

    income_variation = ((current_income - prev_income) / prev_income * 100) if prev_income > 0 else 0
    expense_variation = ((current_expense - prev_expense) / prev_expense * 100) if prev_expense > 0 else 0

    return {
        'current_period': {
            'start_date': current_start.isoformat(),
            'end_date': current_end.isoformat(),
            'income': current_income,
            'expense': current_expense,
            'balance': current_income - current_expense,
            'transactions_count': len(current_transactions)
        },
        'previous_period': {
            'start_date': prev_start.isoformat(),
            'end_date': prev_end.isoformat(),
            'income': prev_income,
            'expense': prev_expense,
            'balance': prev_income - prev_expense,
            'transactions_count': len(prev_transactions)
        },
        'variations': {
            'income_variation': income_variation,
            'expense_variation': expense_variation,
            'balance_variation': ((current_income - current_expense) - (prev_income - prev_expense)),
            'transactions_variation': len(current_transactions) - len(prev_transactions)
        }
    }



