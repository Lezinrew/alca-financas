"""
Rotas do módulo Planejamento.
GET  /api/planning/month           — payload agregado (summary, expense_categories, income_categories, alerts).
PUT  /api/planning/month           — salva planejamento completo (planned_income, savings_percentage, category_plans).
POST /api/planning/month           — cria/atualiza linhas de orçamento.
GET  /api/planning/month/categories — categorias disponíveis para planejamento (agrupadas por tipo).
DELETE /api/planning/month/<id>    — remove uma linha de orçamento.
"""
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from utils.exceptions import ValidationException

bp = Blueprint("planning", __name__, url_prefix="/api/planning")


def _get_month_year_from_args():
    month = request.args.get("month", type=int) or datetime.now().month
    year = request.args.get("year", type=int) or datetime.now().year
    return month, year


def _validate_month_year(month: int, year: int) -> None:
    if month < 1 or month > 12:
        raise ValidationException("month deve ser entre 1 e 12")
    if year < 2020 or year > 2100:
        raise ValidationException("year inválido")


@bp.route("/month", methods=["GET"])
@require_auth
@require_tenant
def planning_month_get():
    """
    Retorna payload único: summary, expense_categories, income_categories, alerts.
    Query: year, month.
    """
    month, year = _get_month_year_from_args()
    _validate_month_year(month, year)

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
    except ValidationException as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception("planning_month_get error: %s", e)
        return jsonify({"error": "Erro ao carregar planejamento"}), 500


@bp.route("/month", methods=["PUT"])
@require_auth
@require_tenant
def planning_month_put():
    """
    Salva planejamento completo.
    Body: month, year, planned_income, savings_percentage, category_plans: [{ category_id, planned_amount }].
    """
    data = request.get_json() or {}
    month = data.get("month") or datetime.now().month
    year = data.get("year") or datetime.now().year
    _validate_month_year(month, year)
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
    user_id = request.user_id
    budget_repo = current_app.config.get("BUDGET_REPO")
    if not budget_repo:
        return jsonify({"error": "Planejamento não disponível para este ambiente"}), 503

    from services.planning_service import save_planning_month

    try:
        result = save_planning_month(
            tenant_id=tenant_id,
            user_id=user_id,
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


@bp.route("/month", methods=["POST"])
@require_auth
@require_tenant
def planning_month_post():
    """
    Cria ou atualiza linhas de orçamento do mês.
    Body: month, year, lines: [{ category_id, planned_amount, notes? }].
    """
    data = request.get_json() or {}
    month = data.get("month") or datetime.now().month
    year = data.get("year") or datetime.now().year
    _validate_month_year(month, year)
    lines = data.get("lines") or []
    if not isinstance(lines, list):
        raise ValidationException("lines deve ser uma lista")

    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    budget_repo = current_app.config.get("BUDGET_REPO")
    if not budget_repo:
        return jsonify({"error": "Planejamento não disponível"}), 503

    from services.planning_service import create_or_upsert_budget_lines

    try:
        result = create_or_upsert_budget_lines(
            tenant_id=tenant_id,
            user_id=user_id,
            month=month,
            year=year,
            lines=lines,
            budget_repo=budget_repo,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("planning_month_post error: %s", e)
        return jsonify({"error": "Erro ao atualizar orçamento"}), 500


@bp.route("/month/categories", methods=["GET"])
@require_auth
@require_tenant
def planning_month_categories():
    """
    Lista categorias disponíveis para planejamento, agrupadas por tipo (income / expense).
    """
    categories_repo = current_app.config["CATEGORIES"]
    user_id = request.user_id
    tenant_id = getattr(request, "tenant_id", None)

    expense = []
    income = []
    if hasattr(categories_repo, "find_by_type"):
        expense = categories_repo.find_by_type(user_id, "expense", tenant_id=tenant_id)
        income = categories_repo.find_by_type(user_id, "income", tenant_id=tenant_id)
    else:
        all_cats = categories_repo.find_by_user(user_id, tenant_id=tenant_id) if hasattr(categories_repo, "find_by_user") else []
        expense = [c for c in all_cats if (c.get("type") or "").lower() == "expense"]
        income = [c for c in all_cats if (c.get("type") or "").lower() == "income"]

    def _norm(c):
        return {
            "id": c.get("id") or c.get("_id"),
            "name": c.get("name", ""),
            "type": (c.get("type") or "expense").lower(),
            "color": c.get("color", "#6b7280"),
            "icon": c.get("icon", "circle"),
        }

    return jsonify({
        "expense": [_norm(c) for c in expense],
        "income": [_norm(c) for c in income],
    })


@bp.route("/month/<plan_id>", methods=["DELETE"])
@require_auth
@require_tenant
def planning_month_delete_line(plan_id: str):
    """Remove uma linha de orçamento por id."""
    if not plan_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    budget_repo = current_app.config.get("BUDGET_REPO")
    if not budget_repo:
        return jsonify({"error": "Planejamento não disponível"}), 503

    try:
        ok = budget_repo.delete_plan_by_id(plan_id, tenant_id, user_id)
        if ok:
            return jsonify({"message": "Linha de orçamento removida"})
        return jsonify({"error": "Linha não encontrada"}), 404
    except Exception as e:
        current_app.logger.exception("planning_month_delete error: %s", e)
        return jsonify({"error": "Erro ao remover"}), 500
