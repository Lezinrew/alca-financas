from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import current_app

from database.connection import get_supabase
from repositories.tenant_repository import TenantRepository
from services.user_service import create_user


@dataclass
class BootstrapResult:
    tenant_id: str
    user_created: bool


class TenantBootstrapError(Exception):
    def __init__(self, message: str, code: str = "tenant_bootstrap_failed", status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AuthBootstrapService:
    """
    Serviço para garantir estado mínimo pós-auth:
    1) public.users existe para user_id
    2) usuário possui ao menos um membership em tenant_members

    Esta ordem é obrigatória porque tenant_members.user_id referencia public.users(id).
    """

    def __init__(self, tenant_repo: Optional[TenantRepository] = None):
        self.tenant_repo = tenant_repo or TenantRepository()

    @staticmethod
    def _find_existing_user(users_repo, user_id: str):
        if hasattr(users_repo, "find_by_id"):
            return users_repo.find_by_id(user_id)
        return users_repo.find_one({"id": user_id})

    @staticmethod
    def _extract_profile_from_auth(access_token: str):
        sb = get_supabase()
        auth_user = sb.auth.get_user(access_token)
        email = auth_user.user.email if auth_user and auth_user.user else None
        name = None
        if auth_user and auth_user.user:
            name = (auth_user.user.user_metadata or {}).get("name")
        if not name and email:
            name = email.split("@")[0]
        return name or "Usuário", email or ""

    def ensure_minimum_tenant(self, user_id: str) -> Optional[str]:
        tenant_id = self.tenant_repo.get_default_tenant_id(user_id)
        if tenant_id:
            return tenant_id
        return self.tenant_repo.ensure_default_tenant(user_id)

    def ensure_user_and_tenant(self, *, user_id: str, users_repo, access_token: str) -> BootstrapResult:
        logger = current_app.logger
        user_created = False

        if not self._find_existing_user(users_repo, user_id):
            user_created = True
            try:
                name, email = self._extract_profile_from_auth(access_token)
                create_user(
                    users_repo,
                    {
                        "id": user_id,
                        "name": name,
                        "email": email,
                        "password": "",
                    },
                    hash_password=None,
                )
            except Exception as exc:
                logger.error("auth bootstrap: failed creating public.users for user_id=%s: %s", user_id, exc)
                raise TenantBootstrapError(
                    "Não foi possível preparar o usuário para o workspace.",
                    code="tenant_bootstrap_failed",
                    status_code=503,
                ) from exc

        tenant_id = self.ensure_minimum_tenant(user_id)
        if not tenant_id:
            logger.error("auth bootstrap: failed resolving/creating tenant for user_id=%s", user_id)
            raise TenantBootstrapError(
                "Não foi possível criar o workspace. Verifique migrações tenants no Supabase e logs do servidor.",
                code="tenant_bootstrap_failed",
                status_code=503,
            )

        return BootstrapResult(tenant_id=tenant_id, user_created=user_created)
