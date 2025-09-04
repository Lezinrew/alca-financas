from datetime import datetime, timedelta
from typing import Dict, Any, List


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


def overview_report(transactions_collection, categories_collection, accounts_collection, user_id: str, month: int, year: int, report_type: str) -> Dict[str, Any]:
    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    period_filter = {'user_id': user_id, 'date': {'$gte': start_date, '$lt': end_date}}

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
            category = categories_collection.find_one({'_id': item['_id']})
            if category:
                total_amount += item['total']
                categories_data.append({
                    'category_id': item['_id'],
                    'category_name': category['name'],
                    'category_color': category['color'],
                    'category_icon': category['icon'],
                    'total': item['total'],
                    'count': item['count']
                })
        for item in categories_data:
            item['percentage'] = (item['total'] / total_amount * 100) if total_amount > 0 else 0
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
            category = categories_collection.find_one({'_id': item['_id']})
            if category:
                total_amount += item['total']
                categories_data.append({
                    'category_id': item['_id'],
                    'category_name': category['name'],
                    'category_color': category['color'],
                    'category_icon': category['icon'],
                    'total': item['total'],
                    'count': item['count']
                })
        for item in categories_data:
            item['percentage'] = (item['total'] / total_amount * 100) if total_amount > 0 else 0
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
            account_name = account['name'] if account else 'Conta Padrão'
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
            item['percentage'] = (item['total'] / total_amount * 100) if total_amount > 0 else 0
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
            account = accounts_collection.find_one({'_id': item['_id']}) if item['_id'] else None
            account_name = account['name'] if account else 'Conta Padrão'
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
            item['percentage'] = (item['total'] / total_amount * 100) if total_amount > 0 else 0
        result['data'] = accounts_data
        result['total_amount'] = total_amount

    elif report_type == 'balance_by_account':
        accounts_list = list(accounts_collection.find({'user_id': user_id, 'is_active': True}))
        accounts_data: List[Dict[str, Any]] = []
        for account in accounts_list:
            account_transactions = list(transactions_collection.find({'user_id': user_id, 'account_id': account['_id']}))
            income_total = sum(t['amount'] for t in account_transactions if t['type'] == 'income')
            expense_total = sum(t['amount'] for t in account_transactions if t['type'] == 'expense')
            current_balance = account.get('initial_balance', 0) + income_total - expense_total
            accounts_data.append({
                'account_id': account['_id'],
                'account_name': account['name'],
                'account_color': account['color'],
                'account_icon': account['icon'],
                'account_type': account['type'],
                'initial_balance': account.get('initial_balance', 0),
                'current_balance': current_balance,
                'total_income': income_total,
                'total_expense': expense_total
            })
        result['data'] = accounts_data
        result['total_amount'] = sum(item['current_balance'] for item in accounts_data)

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



