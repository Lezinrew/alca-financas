from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

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
    def _extract_profile_from_auth(access_token: str, jwt_claims: Optional[Dict[str, Any]] = None):
        """
        Perfil para public.users: prefere Supabase Auth API; se falhar, usa claims do JWT
        (já validado em require_auth) — evita 503 quando get_user falha em dev/rede.
        """
        email: Optional[str] = None
        name: Optional[str] = None
        try:
            sb = get_supabase()
            auth_user = sb.auth.get_user(access_token)
            if auth_user and auth_user.user:
                email = auth_user.user.email
                name = (auth_user.user.user_metadata or {}).get("name")
        except Exception:
            pass

        claims = jwt_claims or {}
        if not email:
            raw = claims.get("email")
            email = (raw or "").strip() if isinstance(raw, str) else ""
        if not name:
            um = claims.get("user_metadata")
            if isinstance(um, dict):
                name = um.get("name") or um.get("full_name")
        if not name and email:
            name = email.split("@")[0]
        if not email:
            # NOT NULL + UNIQUE(email): um placeholder estável por usuário (auth.sub)
            sub = str(claims.get("sub") or "").strip()
            if sub:
                email = f"{sub}@users.internal"
        return name or "Usuário", email or ""

    @staticmethod
    def _parse_db_error(exc: Exception) -> Dict[str, str]:
        """
        Normaliza erros de PostgREST/Supabase para classificação robusta.
        """
        code = str(getattr(exc, "code", "") or "")
        message = str(getattr(exc, "message", "") or "")
        details = str(getattr(exc, "details", "") or "")
        hint = str(getattr(exc, "hint", "") or "")

        text_parts = [str(exc)]
        if message:
            text_parts.append(message)
        if details:
            text_parts.append(details)
        if hint:
            text_parts.append(hint)
        text = " | ".join(part for part in text_parts if part).lower()

        return {
            "code": code,
            "message": message,
            "details": details,
            "hint": hint,
            "text": text,
        }

    def ensure_minimum_tenant(self, user_id: str) -> Optional[str]:
        tenant_id = self.tenant_repo.get_default_tenant_id(user_id)
        if tenant_id:
            return tenant_id
        return self.tenant_repo.ensure_default_tenant(user_id)

    def _remove_stale_user_same_email(
        self,
        *,
        users_repo,
        user_id: str,
        email: str,
    ) -> None:
        """
        Se já existe public.users com o mesmo email mas outro id (dados legado/teste),
        remove a linha antiga quando não há memberships — caso contrário INSERT falha com 23505.
        """
        if not email or not hasattr(users_repo, "find_by_email"):
            return
        other = users_repo.find_by_email(email)
        if not other or str(other.get("id")) == str(user_id):
            return
        old_id = str(other.get("id"))
        if self.tenant_repo.get_user_tenants(old_id):
            raise TenantBootstrapError(
                "Este email já está associado a outro perfil na base de dados (com workspace). "
                "Peça suporte ou use outro email.",
                code="tenant_bootstrap_failed",
                status_code=503,
            )
        current_app.logger.warning(
            "auth bootstrap: removendo public.users legado id=%s email=%s (substituído por auth sub=%s)",
            old_id,
            email,
            user_id,
        )
        if hasattr(users_repo, "delete") and not users_repo.delete(old_id):
            raise TenantBootstrapError(
                "Não foi possível atualizar o registo do utilizador (email em conflito).",
                code="tenant_bootstrap_failed",
                status_code=503,
            )

    def ensure_user_and_tenant(
        self,
        *,
        user_id: str,
        users_repo,
        access_token: str,
        jwt_claims: Optional[Dict[str, Any]] = None,
    ) -> BootstrapResult:
        logger = current_app.logger
        user_created = False

        if not self._find_existing_user(users_repo, user_id):
            user_created = True
            email = ""
            try:
                name, email = self._extract_profile_from_auth(access_token, jwt_claims)
                self._remove_stale_user_same_email(
                    users_repo=users_repo, user_id=user_id, email=email
                )
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
            except TenantBootstrapError:
                raise
            except Exception as exc:
                db_error = self._parse_db_error(exc)
                err_txt = db_error["text"]
                db_code = db_error["code"]
                logger.error(
                    "auth bootstrap: failed creating public.users user_id=%s email=%s db_code=%s db_message=%s db_details=%s raw=%s",
                    user_id,
                    email,
                    db_code or "-",
                    db_error["message"] or "-",
                    db_error["details"] or "-",
                    exc,
                )

                if (
                    db_code == "23505"
                    or "unique" in err_txt
                    or "duplicate" in err_txt
                    or "users_email_key" in err_txt
                    or "users_pkey" in err_txt
                ):
                    raise TenantBootstrapError(
                        "Email ou id em conflito em public.users. Verifique duplicados no Supabase ou tente outra conta.",
                        code="tenant_bootstrap_failed",
                        status_code=503,
                    ) from exc

                if (
                    db_code == "42501"
                    or "permission denied" in err_txt
                    or "row-level security" in err_txt
                    or "rls" in err_txt
                    or "not allowed" in err_txt
                    or "insufficient_privilege" in err_txt
                ):
                    raise TenantBootstrapError(
                        "Sem permissão para criar usuário em public.users. Verifique permissões da conexão backend no Supabase.",
                        code="tenant_bootstrap_failed",
                        status_code=503,
                    ) from exc

                if (
                    db_code in {"23502", "22P02", "23514"}
                    or "not-null" in err_txt
                    or "null value in column" in err_txt
                    or "invalid input syntax" in err_txt
                    or "check constraint" in err_txt
                ):
                    raise TenantBootstrapError(
                        "Dados inválidos ao criar usuário em public.users. Verifique campos obrigatórios e formato dos dados.",
                        code="tenant_bootstrap_failed",
                        status_code=503,
                    ) from exc

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
