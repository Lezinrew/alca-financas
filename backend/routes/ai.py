"""API da fatia de execuções da IA, com sessão V2 e escopo no servidor."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import List, Literal, Optional

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from werkzeug.exceptions import HTTPException

from extensions import limiter
from routes.auth_v2 import _session_cookie_name
from services.auth_v2_service import AuthV2Error
from services.ai import CONTRACT_VERSION, policy, runs, scope
from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.types import Privacy


bp = Blueprint("ai", __name__)
logger = logging.getLogger("ai.api")
MAX_BODY_BYTES = 64 * 1024

# Limites próprios. Sem eles valeria o padrão global do app (50 por hora, por
# IP), que o acompanhamento de uma execução estoura em minutos: a tela consulta
# GET /runs/<id> a cada poucos segundos.
READ_LIMIT = "240 per minute"
CREATE_LIMIT = "30 per minute"
WRITE_LIMIT = "60 per minute"


def _rate_key() -> str:
    """Chave do limite: a sessão, não o IP.

    Atrás do proxy todos os usuários chegam pelo mesmo IP. O limitador roda
    antes da validação da sessão, por isso usa um resumo do cookie (nunca o
    valor) e cai para o IP quando não há cookie.
    """
    token = request.cookies.get(_session_cookie_name(), "")
    if token:
        return "ai:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return "ai-ip:" + (request.remote_addr or "unknown")


def _trace_id() -> str:
    """O limitador pode recusar antes do before_request do blueprint."""
    if not getattr(g, "ai_trace_id", None):
        g.ai_trace_id = str(uuid.uuid4())
    return g.ai_trace_id


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRun(RequestModel):
    task: Literal["finance_question", "statement_import"]
    message: str = Field(min_length=1, max_length=runs.MESSAGE_MAX_CHARS)
    financial_space_id: Optional[str] = None
    privacy: Literal["local_only"] = "local_only"
    input_refs: List[str] = Field(default_factory=list, max_length=runs.INPUT_REFS_MAX)


class SpaceQuery(RequestModel):
    financial_space_id: Optional[str] = None


class ListQuery(SpaceQuery):
    limit: int = Field(default=runs.LIST_DEFAULT_LIMIT, ge=1, le=runs.LIST_MAX_LIMIT)
    cursor: Optional[str] = Field(default=None, min_length=1, max_length=400)


def _validate(model, payload):
    try:
        return model.model_validate(payload)
    except ValidationError:
        # Não devolver erros pydantic: incluem valores do corpo recebido.
        raise AiError("invalid_request") from None


def _body(model):
    if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
        raise AiError("payload_too_large")
    raw = request.stream.read(MAX_BODY_BYTES + 1)
    if len(raw) > MAX_BODY_BYTES:
        raise AiError("payload_too_large")
    if not request.is_json:
        raise AiError("invalid_request")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AiError("invalid_request") from None
    return _validate(model, payload)


def _query(model):
    if any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise AiError("invalid_request")
    return _validate(model, request.args.to_dict())


@bp.before_request
def guard_request():
    _trace_id()
    # O preflight não transporta cookie de sessão.
    if request.method == "OPTIONS":
        return None
    platform = current_app.config.get("AI_PLATFORM")
    if platform is None or not platform.settings.enabled:
        if request.endpoint == "ai.status":
            return jsonify({"enabled": False})
        raise AiError("ai_disabled")
    g.ai_platform = platform
    service = current_app.config.get("AUTH_V2_SERVICE")
    if service is None:
        raise AiError("unauthorized")
    try:
        g.ai_session = service.get_session(request.cookies.get(_session_cookie_name(), ""))
    except AuthV2Error:
        raise AiError("unauthorized") from None
    if request.method == "POST":
        try:
            service.require_csrf(g.ai_session, request.headers.get("X-CSRF-Token"))
        except AuthV2Error:
            raise AiError("invalid_csrf") from None


@bp.after_request
def response_headers(response):
    response.headers["X-Trace-Id"] = _trace_id()
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.errorhandler(AiError)
def ai_error(exc):
    return jsonify({"error": {
        "code": exc.code, "retryable": bool(exc.retryable),
        "safe_message": exc.safe_message, "trace_id": _trace_id(),
    }}), exc.http_status


@bp.errorhandler(Exception)
def unexpected_error(exc):
    if isinstance(exc, HTTPException):
        code = {413: "payload_too_large", 429: "rate_limited"}.get(exc.code, "invalid_request")
        return ai_error(AiError(code, http_status=exc.code))
    logger.error("api_failed error_type=%s trace_id=%s", type(exc).__name__, _trace_id())
    return ai_error(AiError("internal_error"))


@bp.record_once
def protect_routing_errors(state):
    """Flask não chama handlers do blueprint em erros de roteamento (404/405)."""
    prefix = state.url_prefix or "/api/ai/v1"

    @state.app.before_request
    def routing_error():
        if request.blueprint == bp.name or not (request.path == prefix or request.path.startswith(prefix + "/")):
            return None
        error = request.routing_exception
        if error is None:
            return None
        try:
            response = guard_request()
            if response is None:
                code = "not_found" if error.code == 404 else "invalid_request"
                response = ai_error(AiError(code, http_status=error.code))
        except AiError as exc:
            response = ai_error(exc)
        except Exception as exc:
            response = unexpected_error(exc)
        return response_headers(current_app.make_response(response))


def _tenant():
    try:
        return str(scope.resolve_tenant(
            g.ai_platform.pool, str(g.ai_session["id"]), request.headers.get("X-Tenant-Id"),
        )["tenant_id"])
    except AiError as exc:
        if exc.code == "scope_denied":
            raise AiError("not_found") from None
        raise


def _context(space_id=None, run_id=None):
    platform = g.ai_platform
    tenant_id = _tenant()
    if run_id is not None and space_id is None:
        space_id = runs.run_space_id(
            platform.pool, tenant_id=tenant_id, actor_id=str(g.ai_session["id"]), run_id=run_id,
        )
    try:
        return scope.resolve_scope(
            platform.pool, user_id=str(g.ai_session["id"]),
            requested_tenant_id=tenant_id, requested_space_id=space_id,
            privacy=Privacy.LOCAL_ONLY, trace_id=g.ai_trace_id,
        )
    except AiError as exc:
        if exc.code == "scope_denied":
            raise AiError("not_found") from None
        raise


@bp.get("/status")
@limiter.limit(READ_LIMIT, key_func=_rate_key)
def status():
    platform = g.ai_platform
    tenant_id = _tenant()
    spaces = scope.list_spaces(platform.pool, tenant_id, str(g.ai_session["id"]))
    capabilities = set()
    for space in spaces:
        ctx = _context(str(space["id"]))
        with scoped_tx(platform.pool, tenant_id) as cursor:
            grants = policy.load_active_grants(cursor, ctx)
        capabilities.update(tool["name"] for tool in platform.registry.specs_for(grants))
    return jsonify({
        "enabled": True,
        "flags": {"cloud": platform.settings.cloud_enabled, "email": platform.settings.email_enabled,
                  "write": platform.settings.write_enabled},
        "spaces": [{"id": str(item["id"]), "name": item["name"], "kind": item["kind"]} for item in spaces],
        "capabilities": sorted(capabilities), "contract_version": CONTRACT_VERSION,
    })


@bp.post("/runs")
@limiter.limit(CREATE_LIMIT, key_func=_rate_key)
def create_run():
    payload = _body(CreateRun)
    ctx = _context(payload.financial_space_id)
    accepted = runs.create_run(
        g.ai_platform.pool, ctx, task=payload.task, message=payload.message,
        input_refs=payload.input_refs, idempotency_key=request.headers.get("Idempotency-Key"),
        settings=g.ai_platform.settings,
    )
    return jsonify({key: accepted[key] for key in ("run_id", "status", "trace_id")}), 202


@bp.get("/runs")
@limiter.limit(READ_LIMIT, key_func=_rate_key)
def list_runs():
    query = _query(ListQuery)
    result = runs.list_runs(
        g.ai_platform.pool, _context(query.financial_space_id), cursor=query.cursor, limit=query.limit,
    )
    return jsonify({"runs": result["items"], "next_cursor": result["next_cursor"]})


@bp.get("/runs/<run_id>")
@limiter.limit(READ_LIMIT, key_func=_rate_key)
def get_run(run_id):
    query = _query(SpaceQuery)
    return jsonify(runs.get_run_view(
        g.ai_platform.pool, _context(query.financial_space_id, run_id), run_id,
    ))


@bp.post("/runs/<run_id>/cancel")
@limiter.limit(WRITE_LIMIT, key_func=_rate_key)
def cancel_run(run_id):
    _body(RequestModel)
    query = _query(SpaceQuery)
    return jsonify(runs.request_cancel(
        g.ai_platform.pool, _context(query.financial_space_id, run_id), run_id,
    ))
