"""
Rotas do módulo de Aliases de Categoria (merchant_category_aliases).

Permite ao usuário gerenciar suas próprias regras de categorização
(descrição/comerciante -> categoria) sem precisar de deploy — resolve o
achado S6: antes desta rota, a única forma de ajustar categorização era
editar o dicionário CATEGORY_KEYWORDS em código, ou inserir diretamente
no banco. Aliases criados por aqui ficam escopados ao tenant/usuário
(nunca globais), ao contrário do seed inicial que tinha entradas de
estabelecimentos pessoais com escopo global.

GET    /api/merchant-aliases       — lista aliases do tenant atual
POST   /api/merchant-aliases       — cria alias escopado ao tenant/usuário
PUT    /api/merchant-aliases/<id>  — atualiza alias (só se pertencer ao tenant)
DELETE /api/merchant-aliases/<id>  — remove alias (só se pertencer ao tenant)
"""
import unicodedata
from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from utils.tenant_context import require_tenant
from utils.exceptions import ValidationException

bp = Blueprint("merchant_aliases", __name__, url_prefix="/api/merchant-aliases")

_VALID_MATCH_TYPES = ("exact", "prefix", "contains")
_VALID_CATEGORY_TYPES = ("income", "expense")


def _normalize(text: str) -> str:
    base = (text or "").strip().lower()
    if not base:
        return ""
    normalized = unicodedata.normalize("NFKD", base)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@bp.route("", methods=["GET"])
@require_auth
@require_tenant
def list_aliases():
    """Lista aliases visíveis para o tenant atual (próprios + globais)."""
    repo = current_app.config.get("MERCHANT_ALIAS_REPO")
    if not repo:
        return jsonify({"error": "Módulo de aliases não disponível"}), 503

    tenant_id = request.tenant_id
    all_aliases = repo.find_all({"active": True})
    visible = [
        a for a in all_aliases
        if a.get("tenant_id") in (None, tenant_id)
    ]
    return jsonify(visible)


@bp.route("", methods=["POST"])
@require_auth
@require_tenant
def create_alias():
    """Cria um alias escopado ao tenant/usuário atual (nunca global)."""
    repo = current_app.config.get("MERCHANT_ALIAS_REPO")
    if not repo:
        return jsonify({"error": "Módulo de aliases não disponível"}), 503

    data = request.get_json(silent=True) or {}
    match_value = (data.get("match_value") or "").strip()
    match_type = data.get("match_type") or "contains"
    category_name = (data.get("category_name") or "").strip()
    category_type = data.get("category_type") or "expense"

    if not match_value:
        raise ValidationException("match_value é obrigatório")
    if not category_name:
        raise ValidationException("category_name é obrigatório")
    if match_type not in _VALID_MATCH_TYPES:
        raise ValidationException(f"match_type deve ser um de: {_VALID_MATCH_TYPES}")
    if category_type not in _VALID_CATEGORY_TYPES:
        raise ValidationException(f"category_type deve ser um de: {_VALID_CATEGORY_TYPES}")

    alias_data = {
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "match_type": match_type,
        "match_value": match_value,
        "normalized_value": _normalize(match_value),
        "category_name": category_name,
        "category_type": category_type,
        "active": True,
    }
    new_id = repo.create(alias_data)
    return jsonify({"id": new_id, **alias_data}), 201


@bp.route("/<alias_id>", methods=["PUT"])
@require_auth
@require_tenant
def update_alias(alias_id: str):
    """Atualiza um alias — só se pertencer ao tenant atual (nunca edita globais por aqui)."""
    repo = current_app.config.get("MERCHANT_ALIAS_REPO")
    if not repo:
        return jsonify({"error": "Módulo de aliases não disponível"}), 503

    existing = repo.find_by_id(alias_id)
    if not existing or existing.get("tenant_id") != request.tenant_id:
        return jsonify({"error": "Alias não encontrado"}), 404

    data = request.get_json(silent=True) or {}
    update_data = {}
    if "match_value" in data:
        match_value = (data.get("match_value") or "").strip()
        if not match_value:
            raise ValidationException("match_value não pode ser vazio")
        update_data["match_value"] = match_value
        update_data["normalized_value"] = _normalize(match_value)
    if "match_type" in data:
        if data["match_type"] not in _VALID_MATCH_TYPES:
            raise ValidationException(f"match_type deve ser um de: {_VALID_MATCH_TYPES}")
        update_data["match_type"] = data["match_type"]
    if "category_name" in data:
        category_name = (data.get("category_name") or "").strip()
        if not category_name:
            raise ValidationException("category_name não pode ser vazio")
        update_data["category_name"] = category_name
    if "category_type" in data:
        if data["category_type"] not in _VALID_CATEGORY_TYPES:
            raise ValidationException(f"category_type deve ser um de: {_VALID_CATEGORY_TYPES}")
        update_data["category_type"] = data["category_type"]
    if "active" in data:
        update_data["active"] = bool(data["active"])

    if not update_data:
        return jsonify({"error": "Nenhum campo para atualizar"}), 400

    repo.update(alias_id, update_data)
    return jsonify({"id": alias_id, **{**existing, **update_data}})


@bp.route("/<alias_id>", methods=["DELETE"])
@require_auth
@require_tenant
def delete_alias(alias_id: str):
    """Remove um alias — só se pertencer ao tenant atual (nunca remove globais por aqui)."""
    repo = current_app.config.get("MERCHANT_ALIAS_REPO")
    if not repo:
        return jsonify({"error": "Módulo de aliases não disponível"}), 503

    existing = repo.find_by_id(alias_id)
    if not existing or existing.get("tenant_id") != request.tenant_id:
        return jsonify({"error": "Alias não encontrado"}), 404

    repo.delete(alias_id)
    return jsonify({"message": "Alias removido"}), 200
