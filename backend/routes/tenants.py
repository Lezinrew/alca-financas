from flask import Blueprint, jsonify, request

from utils.auth_utils import require_auth
from utils.tenant_context import resolve_tenant_id
from repositories.tenant_repository import TenantRepository
from utils.auth_utils import generate_jwt

bp = Blueprint("tenants", __name__, url_prefix="/api/tenants")


@bp.route("", methods=["GET"])
@require_auth
def list_tenants():
    """
    Lista tenants (organizações) do usuário autenticado.
    """
    repo = TenantRepository()
    tenants = repo.get_user_tenants(request.user_id)
    return jsonify(tenants)


@bp.route("/switch", methods=["POST"])
@require_auth
def switch_tenant():
    """
    Muda o tenant ativo do usuário.

    Para o fluxo de JWT custom:
    - Retorna um novo token com claim tenant_id.

    Para Supabase Auth:
    - O backend não gera tokens Supabase; o frontend pode usar o tenant_id
      retornado + header X-Tenant-Id em chamadas subsequentes.
    """
    data = request.get_json() or {}
    tenant_id = (data.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"error": "tenant_id é obrigatório"}), 400

    repo = TenantRepository()
    if not repo.user_is_member(request.user_id, tenant_id):
        return (
            jsonify(
                {
                    "error": "Tenant não encontrado ou acesso negado",
                    "code": "tenant_forbidden",
                }
            ),
            403,
        )

    # Custom JWT flow: emite novo token com claim tenant_id
    # generate_jwt é backward compatible: tenant_id é claim extra.
    tokens = generate_jwt(request.user_id, tenant_id=tenant_id)

    response = {
        "message": "Tenant alterado com sucesso",
        "tenant_id": tenant_id,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    }
    return jsonify(response)

