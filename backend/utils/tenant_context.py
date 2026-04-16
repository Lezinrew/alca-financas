"""
Tenant context resolution utilities.

Responsabilidades:
- Resolver tenant_id para a request atual (JWT claim, header, default membership).
- Validar se (user_id, tenant_id) é um membership válido.
- Anexar request.tenant_id para uso em serviços/repositórios.
"""
from typing import Optional, Tuple
from flask import request, jsonify, current_app

from repositories.tenant_repository import TenantRepository
from services.bootstrap_service import AuthBootstrapService


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

    # C) Default tenant (first membership); se não existir, tenta bootstrap completo (users + tenant)
    import logging
    logger = logging.getLogger(__name__)
    bootstrap_service = AuthBootstrapService(repo)

    default_tenant_id = repo.get_default_tenant_id(user_id)
    if default_tenant_id is None:
        logger.warning(f"resolve_tenant_id: Usuário {user_id} não tem tenant padrão, criando...")
        auth_header = request.headers.get("Authorization") or ""
        access_token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header
        if access_token:
            users_repo = current_app.config.get("USERS")
            if users_repo is not None:
                try:
                    # Fallback de segurança: cobre usuário que pulou /auth/bootstrap
                    # e evita FK failure ao tentar membership sem public.users.
                    try:
                        result = bootstrap_service.ensure_user_and_tenant(
                            user_id=user_id,
                            users_repo=users_repo,
                            access_token=access_token,
                            jwt_claims=getattr(request, "jwt_payload", None),
                        )
                    except TypeError as exc:
                        # Compatibilidade: containers antigos podem ter ensure_user_and_tenant sem `jwt_claims`.
                        if "unexpected keyword argument" in str(exc) and "jwt_claims" in str(exc):
                            result = bootstrap_service.ensure_user_and_tenant(
                                user_id=user_id,
                                users_repo=users_repo,
                                access_token=access_token,
                            )
                        else:
                            raise
                    default_tenant_id = result.tenant_id
                except Exception as exc:
                    logger.warning(f"resolve_tenant_id: fallback user+tenant failed for user_id={user_id}: {exc}")

        # Nunca chamar ensure_minimum_tenant sozinho: cria tenants/tenant_members sem garantir
        # public.users (FK tenant_members_user_id_fkey). O caminho certo é ensure_user_and_tenant /bootstrap.
        if default_tenant_id is None:
            logger.error(f"resolve_tenant_id: Falha ao criar tenant padrão para usuário {user_id}")
        else:
            logger.info(f"resolve_tenant_id: Tenant padrão {default_tenant_id} criado para usuário {user_id}")
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
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"require_tenant: Tentativa de acesso sem user_id - Path: {request.path}")
            return jsonify({"error": "Autenticação necessária"}), 401

        # Payload opcional pode ter sido colocado por decorators de auth no futuro
        token_payload = getattr(request, "jwt_payload", None)
        tenant_id, error_response = resolve_tenant_id(request.user_id, token_payload)
        if error_response is not None:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"require_tenant: Resolução de tenant falhou - User: {request.user_id} - Path: {request.path}")
            return error_response

        # Rotas que exigem tenant (ex.: criar conta) precisam de tenant_id preenchido
        if tenant_id is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"require_tenant: Nenhum workspace disponível - User: {request.user_id} - Path: {request.path}")
            return (
                jsonify({
                    "error": "Nenhum workspace disponível. Não foi possível criar um workspace padrão.",
                    "code": "tenant_required",
                }),
                403,
            )

        setattr(request, "tenant_id", tenant_id)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"require_tenant: Tenant resolvido - User: {request.user_id} - Tenant: {tenant_id} - Path: {request.path}")
        return f(*args, **kwargs)

    return decorated
