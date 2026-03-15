"""
Rotas do módulo Planejamento: um endpoint agregado por mês.
GET /api/planning/month — retorna planejado + real + progresso por categoria.
PUT /api/planning/month — persiste orçamento (budget_monthly + budget_plans).
"""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from utils.exceptions import ValidationException

bp = Blueprint("planning", __name__, url_prefix="/api/planning")


@bp.route("/month", methods=["GET"])
@require_auth
def planning_month_get():
    """
    Retorna um único payload para a tela de Planejamento:
    planned_income, planned_expenses, real_income, real_expenses,
    balance_real, balance_planned, savings_rate, categories (planned, spent, remaining, progress_percent).
    """
    month = request.args.get("month", type=int) or datetime.now().month
    year = request.args.get("year", type=int) or datetime.now().year
    if month < 1 or month > 12:
        return jsonify({"error": "month deve ser entre 1 e 12"}), 400
    if year < 2020 or year > 2100:
        return jsonify({"error": "year inválido"}), 400

    transactions_repo = current_app.config["TRANSACTIONS"]
    categories_repo = current_app.config["CATEGORIES"]
    budget_repo = current_app.config.get("BUDGET_REPO")
    user_id = request.user_id
    tenant_id = getattr(request, "tenant_id", None)

    from services.planning_service import get_planning_month_payload

    try:
        data = get_planning_month_payload(
            user_id=user_id,
            tenant_id=tenant_id,
            month=month,
            year=year,
            transactions_repo=transactions_repo,
            categories_repo=categories_repo,
            budget_repo=budget_repo,
        )
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("planning_month_get error: %s", e)
        return jsonify({"error": "Erro ao carregar planejamento"}), 500


@bp.route("/month", methods=["PUT"])
@require_auth
@require_tenant
def planning_month_put():
    """
    Salva o planejamento do mês: planned_income, savings_percentage, category_plans.
    Body: { "month", "year", "planned_income", "savings_percentage", "category_plans": [ { "category_id", "planned_amount" } ] }
    """
    data = request.get_json() or {}
    month = data.get("month") or datetime.now().month
    year = data.get("year") or datetime.now().year
    if month < 1 or month > 12 or year < 2020 or year > 2100:
        raise ValidationException("month/year inválidos")
    planned_income = float(data.get("planned_income", 0))
    savings_percentage = float(data.get("savings_percentage", 0))
    if savings_percentage < 0 or savings_percentage > 100:
        raise ValidationException("savings_percentage deve ser entre 0 e 100")
    category_plans = data.get("category_plans") or []
    if not isinstance(category_plans, list):
        raise ValidationException("category_plans deve ser uma lista")

    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403

    budget_repo = current_app.config.get("BUDGET_REPO")
    if not budget_repo:
        return jsonify({"error": "Planejamento não disponível para este ambiente"}), 503

    from services.planning_service import save_planning_month

    try:
        result = save_planning_month(
            tenant_id=tenant_id,
            month=month,
            year=year,
            planned_income=planned_income,
            savings_percentage=savings_percentage,
            category_plans=category_plans,
            budget_repo=budget_repo,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("planning_month_put error: %s", e)
        return jsonify({"error": "Erro ao salvar planejamento"}), 500
