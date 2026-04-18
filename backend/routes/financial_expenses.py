"""
API: contas a pagar (financial_expenses).
"""
from typing import Optional

from flask import Blueprint, jsonify, request, current_app

from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from extensions import limiter
from services.financial_expense_service import FinancialExpenseService
from utils.exceptions import ValidationException, NotFoundException

bp = Blueprint("financial_expenses", __name__, url_prefix="/api/financial-expenses")


def _service() -> Optional[FinancialExpenseService]:
    repo = current_app.config.get("FINANCIAL_EXPENSE_REPO")
    if not repo:
        return None
    return FinancialExpenseService(repo)


@bp.route("", methods=["GET"])
@require_auth
@limiter.limit("200 per hour")  # alinhado a /api/accounts — listagens + HMR dev
@require_tenant
def list_expenses():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("limit", default=50, type=int)
    page = max(1, page)
    per_page = min(max(1, per_page), 200)

    query = {
        "month": request.args.get("month"),
        "year": request.args.get("year"),
        "status": request.args.get("status"),
        "category": request.args.get("category"),
        "responsible": request.args.get("responsible"),
        "is_recurring": request.args.get("is_recurring"),
        "outstanding_only": request.args.get("outstanding_only"),
    }
    query = {k: v for k, v in query.items() if v not in (None, "")}

    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        result = svc.list_expenses(
            request.user_id,
            request.tenant_id,
            query,
            page=page,
            per_page=per_page,
        )
        return jsonify(result)
    except ValidationException as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route("", methods=["POST"])
@require_auth
@require_tenant
def create_expense():
    data = request.get_json() or {}
    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        row = svc.create_expense(request.user_id, request.tenant_id, data)
        return jsonify(row), 201
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route("/<expense_id>", methods=["GET"])
@require_auth
@require_tenant
def get_expense(expense_id: str):
    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        row = svc.get_expense(request.user_id, request.tenant_id, expense_id)
        return jsonify(row)
    except NotFoundException as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route("/<expense_id>", methods=["PUT"])
@require_auth
@require_tenant
def update_expense(expense_id: str):
    data = request.get_json() or {}
    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        row = svc.update_expense(request.user_id, request.tenant_id, expense_id, data)
        return jsonify(row)
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route("/<expense_id>", methods=["DELETE"])
@require_auth
@require_tenant
def delete_expense(expense_id: str):
    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        svc.delete_expense(request.user_id, request.tenant_id, expense_id)
        return jsonify({"message": "Despesa removida"}), 200
    except NotFoundException as e:
        return jsonify(e.to_dict()), e.status_code


@bp.route("/<expense_id>/mark-paid", methods=["POST"])
@require_auth
@require_tenant
def mark_paid(expense_id: str):
    body = request.get_json() if request.is_json else {}
    svc = _service()
    if not svc:
        return jsonify({"error": "Módulo de despesas não disponível"}), 503
    try:
        row = svc.mark_paid(request.user_id, request.tenant_id, expense_id, body)
        return jsonify(row)
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code
