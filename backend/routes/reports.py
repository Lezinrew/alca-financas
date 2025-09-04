from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from services.report_service import overview_report, comparison_report


bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@bp.route('/overview', methods=['GET'])
@require_auth
def reports_overview():
    month = int(request.args.get('month',  datetime.now().month))
    year = int(request.args.get('year',  datetime.now().year))
    report_type = request.args.get('type', 'expenses_by_category')
    transactions_collection = current_app.config['TRANSACTIONS']
    categories_collection = current_app.config['CATEGORIES']
    accounts_collection = current_app.config['ACCOUNTS']
    data = overview_report(transactions_collection, categories_collection, accounts_collection, request.user_id, month, year, report_type)
    return jsonify(data)


@bp.route('/evolution', methods=['GET'])
@require_auth
def reports_evolution():
    # The evolution data is now part of dashboard advanced via monthly_evolution, keeping endpoint minimal
    return jsonify({'message': 'Use /api/dashboard-advanced with show_evolution=true'})


@bp.route('/comparison', methods=['GET'])
@require_auth
def reports_comparison():
    current_month = int(request.args.get('current_month',  datetime.now().month))
    current_year = int(request.args.get('current_year',  datetime.now().year))
    transactions_collection = current_app.config['TRANSACTIONS']
    data = comparison_report(transactions_collection, request.user_id, current_month, current_year)
    return jsonify(data)


