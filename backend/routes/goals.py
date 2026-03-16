"""
Rotas do módulo Metas (Goals).
GET  /api/goals                 — lista metas do usuário (filtro status opcional).
POST /api/goals                 — cria meta.
GET  /api/goals/<id>            — detalhe da meta (com progresso).
PUT  /api/goals/<id>            — atualiza meta.
DELETE /api/goals/<id>          — remove meta.
GET  /api/goals/<id>/contributions — lista aportes.
POST /api/goals/<id>/contributions — adiciona aporte.
"""
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from utils.exceptions import ValidationException

bp = Blueprint("goals", __name__, url_prefix="/api/goals")


@bp.route("", methods=["GET"])
@require_auth
@require_tenant
def goals_list():
    """Lista metas do usuário. Query: status (opcional)."""
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    status = request.args.get("status", type=str)
    if status and status not in ("active", "completed", "paused"):
        raise ValidationException("status deve ser active, completed ou paused")

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    from services.goal_service import list_goals
    goals = list_goals(tenant_id=tenant_id, user_id=user_id, status=status or None, goal_repo=goal_repo)
    return jsonify(goals)


@bp.route("", methods=["POST"])
@require_auth
@require_tenant
def goals_create():
    """Cria uma meta. Body: title, description?, target_amount, current_amount?, target_date?, image_url?, status?."""
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationException("title é obrigatório")
    target_amount = float(data.get("target_amount", 0))
    if target_amount < 0:
        raise ValidationException("target_amount deve ser >= 0")

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    from services.goal_service import create_goal
    payload = {
        "title": title,
        "description": data.get("description"),
        "target_amount": target_amount,
        "current_amount": float(data.get("current_amount", 0)),
        "target_date": data.get("target_date"),
        "image_url": data.get("image_url"),
        "status": (data.get("status") or "active").lower(),
    }
    created = create_goal(tenant_id=tenant_id, user_id=user_id, data=payload, goal_repo=goal_repo)
    return jsonify(created), 201


@bp.route("/<goal_id>", methods=["GET"])
@require_auth
@require_tenant
def goals_get(goal_id: str):
    """Detalhe da meta com progress_percent, remaining_amount, months_remaining, monthly_needed."""
    if not goal_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    from services.goal_service import get_goal
    goal = get_goal(goal_id=goal_id, tenant_id=tenant_id, user_id=user_id, goal_repo=goal_repo)
    if not goal:
        return jsonify({"error": "Meta não encontrada"}), 404
    return jsonify(goal)


@bp.route("/<goal_id>", methods=["PUT"])
@require_auth
@require_tenant
def goals_update(goal_id: str):
    """Atualiza meta. Body: title?, description?, target_amount?, current_amount?, target_date?, image_url?, status?."""
    if not goal_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    data = request.get_json() or {}
    if data.get("status") and data["status"] not in ("active", "completed", "paused"):
        raise ValidationException("status deve ser active, completed ou paused")

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    from services.goal_service import update_goal
    updated = update_goal(goal_id=goal_id, tenant_id=tenant_id, user_id=user_id, data=data, goal_repo=goal_repo)
    if not updated:
        return jsonify({"error": "Meta não encontrada"}), 404
    return jsonify(updated)


@bp.route("/<goal_id>", methods=["DELETE"])
@require_auth
@require_tenant
def goals_delete(goal_id: str):
    """Remove uma meta (e aportes em cascata)."""
    if not goal_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    ok = goal_repo.delete_goal(goal_id=goal_id, tenant_id=tenant_id, user_id=user_id)
    if not ok:
        return jsonify({"error": "Meta não encontrada"}), 404
    return jsonify({"message": "Meta removida"}), 200


@bp.route("/<goal_id>/contributions", methods=["GET"])
@require_auth
@require_tenant
def goals_contributions_list(goal_id: str):
    """Lista aportes da meta."""
    if not goal_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    contributions = goal_repo.list_contributions(goal_id=goal_id, tenant_id=tenant_id, user_id=user_id)
    return jsonify(contributions)


@bp.route("/<goal_id>/contributions", methods=["POST"])
@require_auth
@require_tenant
def goals_contributions_add(goal_id: str):
    """Adiciona aporte à meta. Body: amount, date?, source_type?, source_reference_id?, notes?."""
    if not goal_id:
        return jsonify({"error": "id é obrigatório"}), 400
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        return jsonify({"error": "Workspace não identificado"}), 403
    user_id = request.user_id
    data = request.get_json() or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        raise ValidationException("amount deve ser maior que zero")

    goal_repo = current_app.config.get("GOAL_REPO")
    if not goal_repo:
        return jsonify({"error": "Módulo Metas não disponível"}), 503

    from services.goal_service import add_contribution
    contribution = add_contribution(
        goal_id=goal_id,
        tenant_id=tenant_id,
        user_id=user_id,
        amount=amount,
        date_iso=data.get("date"),
        source_type=data.get("source_type"),
        source_reference_id=data.get("source_reference_id"),
        notes=data.get("notes"),
        goal_repo=goal_repo,
    )
    if not contribution:
        return jsonify({"error": "Meta não encontrada"}), 404
    return jsonify(contribution), 201
