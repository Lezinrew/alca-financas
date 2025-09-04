from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from utils.auth_utils import require_auth
from services.report_service import dashboard_summary, monthly_evolution


bp = Blueprint('dashboard', __name__, url_prefix='/api')


@bp.route('/dashboard', methods=['GET'])
@require_auth
def dashboard():
    month = int(request.args.get('month',  datetime.now().month))
    year = int(request.args.get('year',  datetime.now().year))
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    data = dashboard_summary(transactions_collection, categories_collection, request.user_id, month, year)
    return jsonify(data)


@bp.route('/dashboard-advanced', methods=['GET'])
@require_auth
def dashboard_advanced():
    month = int(request.args.get('month',  datetime.now().month))
    year = int(request.args.get('year',  datetime.now().year))
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    data = dashboard_summary(transactions_collection, categories_collection, request.user_id, month, year)
    if request.args.get('show_evolution', 'true').lower() in ('1', 'true', 'yes'):
        data['monthly_evolution'] = monthly_evolution(transactions_collection, request.user_id, 6)
    return jsonify(data)


@bp.route('/dashboard-settings', methods=['GET', 'PUT'])
@require_auth
def dashboard_settings():
    users_collection = current_app.config['USERS']
    if request.method == 'GET':
        user = users_collection.find_one({'_id': request.user_id})
        dashboard_config = user.get('dashboard_settings', {
            'show_expenses_by_category': True,
            'show_income_by_category': True,
            'show_expense_frequency': True,
            'show_balance_chart': True,
            'show_monthly_balance': True,
            'show_quarterly_balance': False,
            'show_pending_transactions': True,
            'show_credit_card_info': False,
            'show_budget_summary': False,
            'show_goals': False,
            'show_savings_info': False,
            'show_profile_info': True,
            'show_accounts_summary': True
        })
        return jsonify(dashboard_config)

    data = request.get_json()
    allowed_settings = [
        'show_expenses_by_category', 'show_income_by_category',
        'show_expense_frequency', 'show_balance_chart',
        'show_monthly_balance', 'show_quarterly_balance',
        'show_pending_transactions', 'show_credit_card_info',
        'show_budget_summary', 'show_goals', 'show_savings_info',
        'show_profile_info', 'show_accounts_summary'
    ]
    update_data = {f'dashboard_settings.{k}': data[k] for k in allowed_settings if k in data}
    if update_data:
        users_collection.update_one({'_id': request.user_id}, {'$set': update_data})
    return jsonify({'message': 'Configurações do dashboard atualizadas com sucesso'})


