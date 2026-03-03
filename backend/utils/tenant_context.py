"""
Tenant context resolution utilities.

Responsabilidades:
- Resolver tenant_id para a request atual (JWT claim, header, default membership).
- Validar se (user_id, tenant_id) é um membership válido.
- Anexar request.tenant_id para uso em serviços/repositórios.
"""
from typing import Optional, Tuple
from flask import request, jsonify

from repositories.tenant_repository import TenantRepository


def _get_tenant_repo() -> TenantRepository:
    return TenantRepository()


def resolve_tenant_id(
    user_id: str,
    token_payload: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[object]]:
    """
    Resolve tenant_id para o usuário autenticado.

    Prioridade:
    A) Claim 'tenant_id' no JWT (se presente)
    B) Header 'X-Tenant-Id' (validado via membership)
    C) Tenant padrão do usuário (primeiro membership)

    Retorna (tenant_id, error_response). Se error_response != None, deve ser retornado pela rota.
    """
    repo = _get_tenant_repo()

    # A) JWT claim tenant_id
    tenant_id_claim: Optional[str] = None
    if token_payload:
        maybe_tenant = token_payload.get("tenant_id")
        if isinstance(maybe_tenant, str) and maybe_tenant.strip():
            tenant_id_claim = maybe_tenant.strip()

    if tenant_id_claim:
        if repo.user_is_member(user_id, tenant_id_claim):
            return tenant_id_claim, None
        # Se claim inválida, não derruba request, apenas ignora e continua

    # B) Header X-Tenant-Id (explicit override)
    header_tenant = request.headers.get("X-Tenant-Id")
    if header_tenant:
        header_tenant = header_tenant.strip()
        if header_tenant:
            if repo.user_is_member(user_id, header_tenant):
                return header_tenant, None
            # Membership inválido -> 403 explícito
            return None, (
                jsonify(
                    {
                        "error": "Tenant não encontrado ou acesso negado",
                        "code": "tenant_forbidden",
                    }
                ),
                403,
            )

    # C) Default tenant (first membership)
    default_tenant_id = repo.get_default_tenant_id(user_id)
    return default_tenant_id, None


def require_tenant(f):
    """
    Decorator para rotas que manipulam dados multi-tenant.
    Pré-requisito: request.user_id já definido por require_auth ou require_auth_supabase.
    """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, "user_id"):
            return jsonify({"error": "Autenticação necessária"}), 401

        # Payload opcional pode ter sido colocado por decorators de auth no futuro
        token_payload = getattr(request, "jwt_payload", None)
        tenant_id, error_response = resolve_tenant_id(request.user_id, token_payload)
        if error_response is not None:
            return error_response

        # Anexa tenant_id (pode ser None para modo legado / single-tenant)
        setattr(request, "tenant_id", tenant_id)
        return f(*args, **kwargs)

    return decorated

