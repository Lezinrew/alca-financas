from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from services.report_service import overview_report, comparison_report


bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@bp.route('/overview', methods=['GET'])
@require_auth
def reports_overview():
    try:
        month = int(request.args.get('month', datetime.now().month))
        year = int(request.args.get('year', datetime.now().year))
        report_type = request.args.get('type', 'expenses_by_category')
        account_id = request.args.get('account_id')  # Filtro opcional por conta
        
        # Valida o tipo de relatório
        valid_types = ['expenses_by_category', 'expenses_by_account', 'income_by_category', 'income_by_account', 'balance_by_account']
        if report_type not in valid_types:
            return jsonify({'error': f'Tipo de relatório inválido. Tipos válidos: {", ".join(valid_types)}'}), 400
        
        # Valida mês e ano
        if month < 1 or month > 12:
            return jsonify({'error': 'Mês inválido. Use um valor entre 1 e 12'}), 400
        
        if year < 2000 or year > 2100:
            return jsonify({'error': 'Ano inválido'}), 400
        
        # Valida account_id se fornecido
        if account_id:
            accounts_collection = current_app.config['ACCOUNTS']
            account = accounts_collection.find_one({'_id': account_id, 'user_id': request.user_id})
            if not account:
                return jsonify({'error': 'Conta não encontrada'}), 404
        
        transactions_collection = current_app.config['TRANSACTIONS']
        categories_collection = current_app.config['CATEGORIES']
        accounts_collection = current_app.config['ACCOUNTS']
        
        data = overview_report(transactions_collection, categories_collection, accounts_collection, request.user_id, month, year, report_type, account_id)
        return jsonify(data)
    except ValueError as e:
        current_app.logger.error(f"Erro de validação em reports_overview: {str(e)}")
        return jsonify({'error': f'Erro de validação: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Erro inesperado em reports_overview: {str(e)}", exc_info=True)
        return jsonify({'error': f'Erro ao gerar relatório: {str(e)}'}), 500


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


