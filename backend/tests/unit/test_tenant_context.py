from flask import Flask, request

from utils.tenant_context import require_tenant


class _RepoNoTenant:
    def user_is_member(self, user_id, tenant_id):
        return False

    def get_default_tenant_id(self, user_id):
        return None


class _BootstrapResult:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


def test_require_tenant_uses_bootstrap_fallback_and_avoids_tenant_required(monkeypatch):
    app = Flask(__name__)
    app.config["USERS"] = object()

    monkeypatch.setattr("utils.tenant_context._get_tenant_repo", lambda: _RepoNoTenant())

    class _BootstrapServiceFake:
        def __init__(self, repo):
            self.repo = repo

        def ensure_user_and_tenant(self, **kwargs):
            assert kwargs["user_id"] == "u-1"
            return _BootstrapResult("tenant-u-1")

    monkeypatch.setattr("utils.tenant_context.AuthBootstrapService", _BootstrapServiceFake)

    @require_tenant
    def _protected_route():
        return {"ok": True, "tenant_id": request.tenant_id}, 200

    with app.test_request_context(
        "/api/accounts",
        headers={"Authorization": "Bearer valid-token"},
    ):
        request.user_id = "u-1"
        response, status = _protected_route()

    assert status == 200
    assert response["ok"] is True
    assert response["tenant_id"] == "tenant-u-1"
