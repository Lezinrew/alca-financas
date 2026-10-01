"""Autenticação própria com Argon2id e sessões opacas no PostgreSQL V2."""

# Compatibilidade com o Python 3.9 do CI: as assinaturas usam `X | None`.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from psycopg2.extras import RealDictCursor

from database.v2_connection import v2_connection


SESSION_HOURS = 12
REMEMBER_SESSION_DAYS = 30
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AuthV2Error(Exception):
    status_code = 400
    code = "auth_error"


class InvalidCredentialsError(AuthV2Error):
    status_code = 401
    code = "invalid_credentials"


class InactiveUserError(AuthV2Error):
    status_code = 403
    code = "user_inactive"


class InvalidSessionError(AuthV2Error):
    status_code = 401
    code = "invalid_session"


class InvalidCsrfError(AuthV2Error):
    status_code = 403
    code = "invalid_csrf"


class BootstrapConflictError(AuthV2Error):
    status_code = 409
    code = "bootstrap_conflict"


@dataclass(frozen=True)
class SessionResult:
    token: str
    csrf_token: str
    expires_at: datetime
    user: dict[str, Any]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"],
        "role": row["global_role"],
        "status": row["status"],
        "settings": row.get("settings") or {},
    }


class AuthV2Service:
    def __init__(self, database_pool, password_hasher: PasswordHasher | None = None):
        self.database_pool = database_pool
        self.password_hasher = password_hasher or PasswordHasher()
        # Verificação usada quando o e-mail não existe para reduzir enumeração por tempo.
        self._dummy_hash = self.password_hasher.hash("dummy-password-never-used")

    @staticmethod
    def validate_password(password: str) -> None:
        if not isinstance(password, str):
            raise ValueError("Senha inválida")
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"A senha deve ter entre {PASSWORD_MIN_LENGTH} e {PASSWORD_MAX_LENGTH} caracteres"
            )

    def hash_password(self, password: str) -> str:
        self.validate_password(password)
        return self.password_hasher.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        try:
            return self.password_hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def create_initial_admin(
        self,
        *,
        email: str,
        name: str,
        password: str,
        tenant_name: str,
        tenant_slug: str,
    ) -> dict[str, Any]:
        email = email.strip().lower()
        name = name.strip()
        tenant_name = tenant_name.strip()
        tenant_slug = tenant_slug.strip().lower()
        if not email or "@" not in email:
            raise ValueError("E-mail inválido")
        if len(name) < 2:
            raise ValueError("Nome deve ter pelo menos 2 caracteres")
        if not tenant_name:
            raise ValueError("Nome da organização é obrigatório")
        if not SLUG_PATTERN.fullmatch(tenant_slug):
            raise ValueError("Slug deve conter letras minúsculas, números e hífens")
        password_hash = self.hash_password(password)

        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext('alcahub:v2:initial-admin'))")
                cursor.execute("SELECT EXISTS (SELECT 1 FROM users WHERE global_role = 'admin')")
                if cursor.fetchone()["exists"]:
                    raise BootstrapConflictError("O administrador inicial já foi criado")
                cursor.execute(
                    """
                    INSERT INTO users (
                        email, name, password_hash, global_role, status, email_verified_at
                    ) VALUES (%s, %s, %s, 'admin', 'active', now())
                    RETURNING id, email, name, global_role, status, settings
                    """,
                    (email, name, password_hash),
                )
                user = cursor.fetchone()
                cursor.execute(
                    "INSERT INTO tenants (name, slug) VALUES (%s, %s) RETURNING id",
                    (tenant_name, tenant_slug),
                )
                tenant_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO tenant_members (tenant_id, user_id, role)
                    VALUES (%s, %s, 'owner')
                    """,
                    (tenant_id, user["id"]),
                )
        result = _public_user(user)
        result["tenant_id"] = str(tenant_id)
        return result

    def login(
        self,
        *,
        email: str,
        password: str,
        remember_me: bool,
        user_agent: str | None,
        ip_address: str | None,
    ) -> SessionResult:
        normalized_email = (email or "").strip().lower()
        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, email, name, password_hash, global_role, status, settings
                    FROM users
                    WHERE email = %s AND deleted_at IS NULL
                    """,
                    (normalized_email,),
                )
                user = cursor.fetchone()
                hash_to_check = user["password_hash"] if user else self._dummy_hash
                password_valid = self.verify_password(hash_to_check, password or "")
                if not user or not password_valid:
                    raise InvalidCredentialsError("E-mail ou senha incorretos")
                if user["status"] != "active":
                    raise InactiveUserError("Usuário indisponível")
                if self.password_hasher.check_needs_rehash(user["password_hash"]):
                    cursor.execute(
                        "UPDATE users SET password_hash = %s, password_changed_at = now() WHERE id = %s",
                        (self.password_hasher.hash(password), user["id"]),
                    )

                now = _utcnow()
                expires_at = now + (
                    timedelta(days=REMEMBER_SESSION_DAYS)
                    if remember_me
                    else timedelta(hours=SESSION_HOURS)
                )
                token = secrets.token_urlsafe(32)
                csrf_token = secrets.token_urlsafe(32)
                cursor.execute(
                    """
                    INSERT INTO auth_sessions (
                        user_id, token_hash, csrf_hash, remember_me,
                        user_agent, ip_address, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user["id"],
                        _token_hash(token),
                        _token_hash(csrf_token),
                        remember_me,
                        (user_agent or "")[:500] or None,
                        ip_address,
                        expires_at,
                    ),
                )
                cursor.execute(
                    "UPDATE users SET last_login_at = %s, last_activity_at = %s WHERE id = %s",
                    (now, now, user["id"]),
                )
        return SessionResult(token, csrf_token, expires_at, _public_user(user))

    def get_session(self, token: str) -> dict[str, Any]:
        if not token:
            raise InvalidSessionError("Sessão ausente")
        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        s.id AS session_id, s.csrf_hash, s.expires_at,
                        u.id, u.email, u.name, u.global_role, u.status, u.settings
                    FROM auth_sessions s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = %s
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.deleted_at IS NULL
                    """,
                    (_token_hash(token),),
                )
                session = cursor.fetchone()
                if not session:
                    raise InvalidSessionError("Sessão inválida ou expirada")
                if session["status"] != "active":
                    raise InactiveUserError("Usuário indisponível")
                cursor.execute(
                    "UPDATE auth_sessions SET last_seen_at = now() WHERE id = %s",
                    (session["session_id"],),
                )
        return session

    @staticmethod
    def require_csrf(session: dict[str, Any], csrf_token: str | None) -> None:
        if not csrf_token or not hmac.compare_digest(
            session["csrf_hash"], _token_hash(csrf_token)
        ):
            raise InvalidCsrfError("Token CSRF inválido")

    def rotate_csrf(self, session_id) -> str:
        csrf_token = secrets.token_urlsafe(32)
        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "UPDATE auth_sessions SET csrf_hash = %s WHERE id = %s AND revoked_at IS NULL",
                    (_token_hash(csrf_token), session_id),
                )
                if cursor.rowcount != 1:
                    raise InvalidSessionError("Sessão inválida")
        return csrf_token

    def logout(self, session_id) -> None:
        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "UPDATE auth_sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL",
                    (session_id,),
                )

    def logout_by_token(self, token: str) -> None:
        """Revoga quando possível; nunca falha se o cookie já expirou ou foi revogado."""
        if not token:
            return
        with v2_connection(self.database_pool) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE token_hash = %s
                    """,
                    (_token_hash(token),),
                )
