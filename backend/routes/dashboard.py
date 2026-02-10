from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from utils.auth_utils import require_auth
from services.report_service import (
    dashboard_summary,
    dashboard_summary_supabase,
    monthly_evolution,
    monthly_evolution_supabase,
)


bp = Blueprint('dashboard', __name__, url_prefix='/api')


def _dashboard_data():
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    transactions = current_app.config['TRANSACTIONS']
    categories = current_app.config['CATEGORIES']
    user_id = request.user_id
    if current_app.config.get('DB_TYPE') == 'supabase':
        data = dashboard_summary_supabase(transactions, categories, user_id, month, year)
        if request.args.get('show_evolution', 'true').lower() in ('1', 'true', 'yes'):
            data['monthly_evolution'] = monthly_evolution_supabase(transactions, user_id, 6)
    else:
        data = dashboard_summary(transactions, categories, user_id, month, year)
        if request.args.get('show_evolution', 'true').lower() in ('1', 'true', 'yes'):
            data['monthly_evolution'] = monthly_evolution(transactions, user_id, 6)
    return data


@bp.route('/dashboard', methods=['GET'])
@require_auth
def dashboard():
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    transactions = current_app.config['TRANSACTIONS']
    categories = current_app.config['CATEGORIES']
    if current_app.config.get('DB_TYPE') == 'supabase':
        data = dashboard_summary_supabase(transactions, categories, request.user_id, month, year)
    else:
        data = dashboard_summary(transactions, categories, request.user_id, month, year)
    return jsonify(data)


@bp.route('/dashboard-advanced', methods=['GET'])
@require_auth
def dashboard_advanced():
    data = _dashboard_data()
    return jsonify(data)


@bp.route('/dashboard-settings', methods=['GET', 'PUT'])
@require_auth
def dashboard_settings():
    users_repo = current_app.config['USERS']
    if request.method == 'GET':
        user = users_repo.find_by_id(request.user_id) if hasattr(users_repo, 'find_by_id') else users_repo.find_one({'_id': request.user_id})
        if not user:
            dashboard_config = {
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
            }
        else:
            # Supabase: dashboard pode estar em user.dashboard_settings ou em settings.dashboard_settings
            settings = user.get('settings') or {}
            dashboard_config = user.get('dashboard_settings') or settings.get('dashboard_settings') or {
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
            }
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
    if not data:
        return jsonify({'message': 'Nenhuma configuração enviada'}), 400
    if hasattr(users_repo, 'update') and hasattr(users_repo, 'find_by_id'):
        user = users_repo.find_by_id(request.user_id)
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        settings = dict(user.get('settings') or {})
        current = dict(settings.get('dashboard_settings') or {})
        for k in allowed_settings:
            if k in data:
                current[k] = data[k]
        settings['dashboard_settings'] = current
        users_repo.update(request.user_id, {'settings': settings})
    else:
        update_data = {f'dashboard_settings.{k}': data[k] for k in allowed_settings if k in data}
        if update_data:
            users_repo.update_one({'_id': request.user_id}, {'$set': update_data})
    return jsonify({'message': 'Configurações do dashboard atualizadas com sucesso'})


