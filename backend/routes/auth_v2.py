"""Rotas da autenticação PostgreSQL V2."""

# Compatibilidade com o Python 3.9 do CI: as assinaturas usam `X | None`.
from __future__ import annotations

from functools import wraps
import hashlib
import os

from flask import Blueprint, current_app, g, jsonify, request

from extensions import limiter
from services.auth_v2_service import (
    AuthV2Error,
    AuthV2Service,
    InactiveUserError,
    InvalidSessionError,
)


bp = Blueprint("auth_v2", __name__)


def _service() -> AuthV2Service:
    return current_app.config["AUTH_V2_SERVICE"]


def _cookie_secure() -> bool:
    configured = os.getenv("AUTH_V2_COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes"}
    return os.getenv("FLASK_ENV", "").strip().lower() == "production"


def _session_cookie_name() -> str:
    return "__Host-alcahub_session" if _cookie_secure() else "alcahub_session"


def _csrf_cookie_name() -> str:
    return "__Host-alcahub_csrf" if _cookie_secure() else "alcahub_csrf"


def _set_auth_cookies(response, token: str, csrf_token: str, max_age: int | None):
    common = {
        "secure": _cookie_secure(),
        "samesite": "Lax",
        "path": "/",
        "max_age": max_age,
    }
    response.set_cookie(_session_cookie_name(), token, httponly=True, **common)
    response.set_cookie(_csrf_cookie_name(), csrf_token, httponly=False, **common)


def _clear_auth_cookies(response):
    common = {"secure": _cookie_secure(), "samesite": "Lax", "path": "/"}
    response.delete_cookie(_session_cookie_name(), httponly=True, **common)
    response.delete_cookie(_csrf_cookie_name(), httponly=False, **common)


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _login_rate_key() -> str:
    payload = request.get_json(silent=True) or {}
    email = payload.get("email") if isinstance(payload, dict) else ""
    normalized = email.strip().lower() if isinstance(email, str) else ""
    email_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{request.remote_addr or 'unknown'}:{email_key}"


def require_v2_session(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = request.cookies.get(_session_cookie_name(), "")
        try:
            g.auth_v2_session = _service().get_session(token)
        except AuthV2Error as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.status_code
        return view(*args, **kwargs)

    return wrapped


@bp.errorhandler(AuthV2Error)
def handle_auth_v2_error(exc: AuthV2Error):
    return jsonify({"error": str(exc), "code": exc.code}), exc.status_code


@bp.post("/auth/login")
@limiter.limit("5 per minute", key_func=_login_rate_key)
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "E-mail e senha são obrigatórios", "code": "validation_error"}), 400
    remember_me = payload.get("remember_me", False)
    if not isinstance(remember_me, bool):
        return jsonify({"error": "remember_me deve ser booleano", "code": "validation_error"}), 400
    result = _service().login(
        email=email,
        password=password,
        remember_me=remember_me,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.remote_addr,
    )
    max_age = int((result.expires_at.timestamp() - __import__("time").time()))
    response = jsonify({"user": result.user, "csrf_token": result.csrf_token})
    _set_auth_cookies(response, result.token, result.csrf_token, max_age)
    return _no_store(response)


@bp.get("/auth/me")
@require_v2_session
def me():
    session = g.auth_v2_session
    response = jsonify(
        {
            "id": str(session["id"]),
            "email": session["email"],
            "name": session["name"],
            "role": session["global_role"],
            "status": session["status"],
            "settings": session.get("settings") or {},
        }
    )
    return _no_store(response)


@bp.get("/auth/csrf")
@require_v2_session
def csrf():
    token = _service().rotate_csrf(g.auth_v2_session["session_id"])
    response = jsonify({"csrf_token": token})
    response.set_cookie(
        _csrf_cookie_name(),
        token,
        httponly=False,
        secure=_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    return _no_store(response)


@bp.post("/auth/logout")
def logout():
    token = request.cookies.get(_session_cookie_name(), "")
    try:
        session = _service().get_session(token)
    except (InvalidSessionError, InactiveUserError):
        # Logout é idempotente: sessão ausente/expirada ainda deve remover cookies.
        session = None
    if session is not None:
        _service().require_csrf(session, request.headers.get("X-CSRF-Token"))
        _service().logout(session["session_id"])
    else:
        _service().logout_by_token(token)
    response = jsonify({"ok": True})
    _clear_auth_cookies(response)
    return _no_store(response)
