"""
Rotas administrativas (Supabase). Autorização real via public.users.role / is_admin.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, current_app, jsonify, request

from services.admin_user_service import AdminUserService
from services.user_service import create_default_categories
from services.supabase_auth_service import SupabaseAuthService
from utils.admin_logger import get_admin_logs, log_admin_action
from utils.auth_utils import require_admin

logger = logging.getLogger(__name__)

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _admin_service() -> AdminUserService:
    return AdminUserService()


@bp.route("/stats", methods=["GET"])
@require_admin
def get_stats():
    svc = _admin_service()
    ustats = svc.user_stats()
    transactions_repo = current_app.config["TRANSACTIONS"]
    categories_repo = current_app.config["CATEGORIES"]
    accounts_repo = current_app.config["ACCOUNTS"]

    total_transactions = transactions_repo.count({}) if hasattr(transactions_repo, "count") else 0
    total_categories = categories_repo.count({}) if hasattr(categories_repo, "count") else 0
    total_accounts = accounts_repo.count({}) if hasattr(accounts_repo, "count") else 0

    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    new_users_month = svc.repo.count_created_since(start_of_month)

    last_24h = (now - timedelta(days=1)).isoformat()
    new_users_24h = svc.repo.count_created_since(last_24h)

    total_volume = 0.0
    top_categories: list = []
    monthly_growth: list = []

    return jsonify(
        {
            "users": {
                "total": ustats["total_users"],
                "new_this_month": new_users_month,
                "active_24h": new_users_24h,
                "active": ustats["active"],
                "inactive": ustats["inactive"],
                "pending_deletion": ustats["pending_deletion"],
                "disabled": ustats["disabled"],
                "admins": ustats["admins"],
            },
            "data": {
                "transactions": total_transactions,
                "categories": total_categories,
                "accounts": total_accounts,
            },
            "financial": {"total_volume": total_volume, "top_categories": top_categories},
            "growth": {"monthly": monthly_growth},
            "system_status": "healthy",
        }
    )


@bp.route("/users/stats", methods=["GET"])
@require_admin
def users_stats():
    return jsonify(_admin_service().user_stats())


@bp.route("/users/inactive", methods=["GET"])
@require_admin
def users_inactive():
    min_days = int(request.args.get("min_days", 30))
    limit = int(request.args.get("limit", 200))
    return jsonify({"users": _admin_service().inactive_users(min_days=min_days, limit=limit)})


@bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    search = request.args.get("search", "")
    status_filter = request.args.get("status", "all")
    admins_only = request.args.get("admins_only", "").lower() in ("1", "true", "yes")
    return jsonify(
        _admin_service().list_users(
            page=page,
            per_page=per_page,
            search=search,
            status_filter=status_filter,
            admins_only=admins_only,
        )
    )


@bp.route("/users/<user_id>/role", methods=["PATCH"])
@require_admin
def patch_user_role(user_id):
    body = request.get_json() or {}
    role = body.get("role")
    if not role:
        return jsonify({"error": "role é obrigatório"}), 400
    r = _admin_service().set_role(user_id, role)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "erro")}), r.get("status", 400)
    return jsonify({"user": r.get("user")})


@bp.route("/users/<user_id>/status", methods=["PATCH"])
@require_admin
def patch_user_status(user_id):
    body = request.get_json() or {}
    status = body.get("status")
    if not status:
        return jsonify({"error": "status é obrigatório"}), 400
    r = _admin_service().set_status(user_id, status)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "erro")}), r.get("status", 400)
    return jsonify({"user": r.get("user")})


@bp.route("/users/<user_id>/send-inactive-warning", methods=["POST"])
@require_admin
def send_inactive_warning(user_id):
    r = _admin_service().send_inactive_warning(user_id)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "falha")}), 400
    return jsonify(r)


@bp.route("/users/send-bulk-inactive-warning", methods=["POST"])
@require_admin
def send_bulk_inactive_warning():
    body = request.get_json() or {}
    ids = body.get("user_ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "user_ids (lista) é obrigatório"}), 400
    return jsonify(_admin_service().send_bulk_inactive_warnings(ids))


@bp.route("/users/<user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    r = _admin_service().deactivate_user(user_id)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "erro")}), r.get("status", 400)
    return jsonify({"message": "Conta desativada (remoção lógica)."})


@bp.route("/users/<user_id>/purge", methods=["POST"])
@require_admin
def purge_user(user_id):
    body = request.get_json() or {}
    confirm_email = body.get("confirm_email") or body.get("confirmEmail") or ""
    r = _admin_service().purge_user(user_id, str(confirm_email))
    if not r.get("ok"):
        payload = {"error": r.get("error", "erro")}
        if r.get("detail"):
            payload["detail"] = r["detail"]
        return jsonify(payload), r.get("status", 400)
    return jsonify({"message": "Conta e dados removidos permanentemente."})


@bp.route("/users/<user_id>/reactivate", methods=["POST"])
@require_admin
def reactivate_user(user_id):
    r = _admin_service().reactivate_user(user_id)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "erro")}), r.get("status", 400)
    return jsonify({"message": "Conta reativada."})


@bp.route("/users/<user_id>", methods=["PUT"])
@require_admin
def update_user_put(user_id):
    data = request.get_json() or {}
    r = _admin_service().legacy_put_user(user_id, data)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "erro")}), r.get("status", 400)
    log_admin_action(
        admin_id=request.user_id,
        admin_email=getattr(request, "user_email", "") or "",
        action="legacy_update_user",
        target_id=user_id,
        details=data,
    )
    return jsonify({"message": "Usuário atualizado", "user": r.get("user")})


@bp.route("/users/<user_id>/details", methods=["GET"])
@require_admin
def get_user_details(user_id):
    svc = _admin_service()
    user = svc.repo.find_by_id(user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    transactions_collection = current_app.config["TRANSACTIONS"]
    categories_collection = current_app.config["CATEGORIES"]
    accounts_collection = current_app.config["ACCOUNTS"]

    total_transactions = 0
    total_categories = 0
    total_accounts = 0
    try:
        if hasattr(transactions_collection, "count"):
            total_transactions = transactions_collection.count({"user_id": user_id})
        if hasattr(categories_collection, "count"):
            total_categories = categories_collection.count({"user_id": user_id})
        if hasattr(accounts_collection, "count"):
            total_accounts = accounts_collection.count({"user_id": user_id})
    except Exception as exc:
        logger.warning("get_user_details counts: %s", exc)

    auth_provider = "email"
    try:
        provs = user.get("auth_providers") or []
        if provs and isinstance(provs[0], dict):
            auth_provider = provs[0].get("provider", "email")
    except Exception:
        pass

    return jsonify(
        {
            "user": {
                "id": user["id"],
                "name": user.get("name"),
                "email": user.get("email"),
                "role": user.get("role", "user"),
                "status": user.get("status", "active"),
                "is_admin": user.get("role") == "admin" or bool(user.get("is_admin")),
                "is_blocked": user.get("status") == "disabled",
                "created_at": user.get("created_at"),
                "last_login_at": user.get("last_login_at"),
                "last_activity_at": user.get("last_activity_at"),
                "inactive_warning_sent_at": user.get("inactive_warning_sent_at"),
                "scheduled_deletion_at": user.get("scheduled_deletion_at"),
                "auth_provider": auth_provider,
            },
            "stats": {
                "transactions": total_transactions,
                "categories": total_categories,
                "accounts": total_accounts,
                "total_income": 0.0,
                "total_expense": 0.0,
                "balance": 0.0,
            },
            "recent_transactions": [],
            "accounts": [],
        }
    )


@bp.route("/users", methods=["POST"])
@require_admin
def create_user_admin():
    data = request.get_json() or {}
    if not data.get("email") or not data.get("password") or not data.get("name"):
        return jsonify({"error": "Nome, email e senha são obrigatórios"}), 400

    try:
        auth_service = SupabaseAuthService()
        result = auth_service.sign_up(
            email=str(data["email"]).strip().lower(),
            password=data["password"],
            name=data["name"],
        )
        uid = result["user"]["id"]
        categories_repo = current_app.config["CATEGORIES"]
        create_default_categories(categories_repo, uid)

        if data.get("is_admin") or data.get("role") == "admin":
            _admin_service().repo.update_user(uid, {"role": "admin"})

        log_admin_action(
            admin_id=request.user_id,
            admin_email=getattr(request, "user_email", "") or "",
            action="create_user_admin",
            target_id=uid,
            details={"email": data.get("email")},
        )

        return (
            jsonify(
                {
                    "message": "Usuário criado com sucesso",
                    "user": {
                        "id": uid,
                        "name": data["name"],
                        "email": data["email"],
                        "role": "admin" if data.get("is_admin") or data.get("role") == "admin" else "user",
                    },
                }
            ),
            201,
        )
    except Exception as e:
        err = str(e).lower()
        if "already registered" in err or "user already exists" in err or "duplicate" in err:
            return jsonify({"error": "Email já cadastrado"}), 400
        logger.error("create_user_admin: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/logs", methods=["GET"])
@require_admin
def list_admin_logs():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    action_filter = request.args.get("action")
    admin_filter = request.args.get("admin_id")
    skip = (page - 1) * per_page
    logs = get_admin_logs(limit=per_page, skip=skip, action_filter=action_filter, admin_filter=admin_filter)
    return jsonify({"logs": logs, "page": page, "per_page": per_page})


@bp.route("/users/<user_id>/export", methods=["GET"])
@require_admin
def export_user_data(user_id):
    svc = _admin_service()
    user = svc.repo.find_by_id(user_id)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    transactions_collection = current_app.config["TRANSACTIONS"]
    categories_collection = current_app.config["CATEGORIES"]
    accounts_collection = current_app.config["ACCOUNTS"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["=== DADOS DO USUÁRIO ==="])
    writer.writerow(["Nome", user.get("name", "")])
    writer.writerow(["Email", user.get("email", "")])
    writer.writerow(["Cadastro", user.get("created_at", "")])
    writer.writerow([])

    writer.writerow(["=== CONTAS ==="])
    writer.writerow(["Nome", "Tipo", "Saldo"])
    try:
        acc_rows = (
            accounts_collection.find_all({"user_id": user_id}) if hasattr(accounts_collection, "find_all") else []
        )
        for account in acc_rows:
            writer.writerow(
                [
                    account.get("name", ""),
                    account.get("type", ""),
                    account.get("balance", 0),
                ]
            )
    except Exception as exc:
        logger.warning("export accounts: %s", exc)
    writer.writerow([])

    writer.writerow(["=== CATEGORIAS ==="])
    writer.writerow(["Nome", "Tipo", "Cor"])
    try:
        cat_rows = (
            categories_collection.find_all({"user_id": user_id})
            if hasattr(categories_collection, "find_all")
            else []
        )
        for category in cat_rows:
            writer.writerow(
                [
                    category.get("name", ""),
                    category.get("type", ""),
                    category.get("color", ""),
                ]
            )
    except Exception as exc:
        logger.warning("export categories: %s", exc)
    writer.writerow([])

    writer.writerow(["=== TRANSAÇÕES ==="])
    writer.writerow(["Data", "Descrição", "Tipo", "Valor", "Categoria", "Conta"])
    try:
        trans_rows = (
            transactions_collection.find_all({"user_id": user_id})
            if hasattr(transactions_collection, "find_all")
            else []
        )
        for trans in trans_rows:
            writer.writerow(
                [
                    trans.get("date", ""),
                    trans.get("description", ""),
                    trans.get("type", ""),
                    trans.get("amount", 0),
                    trans.get("category_id", ""),
                    trans.get("account_id", ""),
                ]
            )
    except Exception as exc:
        logger.warning("export transactions: %s", exc)

    log_admin_action(
        admin_id=request.user_id,
        admin_email=getattr(request, "user_email", "") or "",
        action="export_user_data",
        target_id=user_id,
        details={"user_email": user.get("email")},
    )

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename=user_data_{user_id}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
        },
    )
