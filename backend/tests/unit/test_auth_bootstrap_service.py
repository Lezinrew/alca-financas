import pytest
from flask import Flask

from services.bootstrap_service import AuthBootstrapService, TenantBootstrapError


class FakeUsersRepo:
    def __init__(self):
        self.rows = {}
        self.deleted = []

    def find_by_id(self, user_id):
        return self.rows.get(user_id)

    def find_by_email(self, email):
        for row in self.rows.values():
            if row.get("email") == email:
                return row
        return None

    def delete(self, user_id):
        if user_id in self.rows:
            self.deleted.append(user_id)
            del self.rows[user_id]
            return True
        return False

    def create(self, payload):
        self.rows[payload["id"]] = payload


class FakeTenantRepo:
    def __init__(self):
        self.members = {}
        self.calls = []
        # user_id -> lista de memberships (vazio = sem workspace; usado por _remove_stale_user_same_email)
        self.user_tenants_by_user = {}

    def get_user_tenants(self, user_id):
        return list(self.user_tenants_by_user.get(user_id, []))

    def get_default_tenant_id(self, user_id):
        self.calls.append(("get_default_tenant_id", user_id))
        return self.members.get(user_id)

    def ensure_default_tenant(self, user_id):
        self.calls.append(("ensure_default_tenant", user_id))
        self.members[user_id] = f"tenant-{user_id}"
        return self.members[user_id]


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.app_context():
        yield app


def test_bootstrap_creates_user_before_tenant_membership(app_ctx, monkeypatch):
    users_repo = FakeUsersRepo()
    tenant_repo = FakeTenantRepo()
    service = AuthBootstrapService(tenant_repo=tenant_repo)
    user_id = "user-123"

    monkeypatch.setattr(
        service,
        "_extract_profile_from_auth",
        lambda *_a, **_kw: ("Novo Usuário", "novo@example.com"),
    )

    create_calls = []

    def _spy_create_user(repo, payload, hash_password=None):
        create_calls.append(("create_user", payload["id"]))
        repo.create(payload)

    monkeypatch.setattr("services.bootstrap_service.create_user", _spy_create_user)

    result = service.ensure_user_and_tenant(
        user_id=user_id,
        users_repo=users_repo,
        access_token="token",
    )

    assert result.tenant_id == f"tenant-{user_id}"
    assert users_repo.find_by_id(user_id) is not None
    assert create_calls == [("create_user", user_id)]
    assert tenant_repo.calls == [
        ("get_default_tenant_id", user_id),
        ("ensure_default_tenant", user_id),
    ]


def test_bootstrap_returns_existing_tenant_without_recreating(app_ctx, monkeypatch):
    users_repo = FakeUsersRepo()
    users_repo.create({"id": "u1", "name": "U1", "email": "u1@example.com", "password": ""})

    tenant_repo = FakeTenantRepo()
    tenant_repo.members["u1"] = "tenant-existing"
    service = AuthBootstrapService(tenant_repo=tenant_repo)

    called = {"extract": False}

    monkeypatch.setattr(
        service,
        "_extract_profile_from_auth",
        lambda *_a, **_kw: (called.update(extract=True) or ("unused", "unused@example.com")),
    )

    result = service.ensure_user_and_tenant(user_id="u1", users_repo=users_repo, access_token="token")

    assert result.tenant_id == "tenant-existing"
    assert called["extract"] is False
    assert tenant_repo.calls == [("get_default_tenant_id", "u1")]


def test_bootstrap_raises_stable_error_when_tenant_cannot_be_ensured(app_ctx, monkeypatch):
    users_repo = FakeUsersRepo()
    users_repo.create({"id": "u2", "name": "U2", "email": "u2@example.com", "password": ""})

    tenant_repo = FakeTenantRepo()

    def _none(_):
        return None

    tenant_repo.get_default_tenant_id = _none
    tenant_repo.ensure_default_tenant = _none

    service = AuthBootstrapService(tenant_repo=tenant_repo)

    with pytest.raises(TenantBootstrapError) as exc:
        service.ensure_user_and_tenant(user_id="u2", users_repo=users_repo, access_token="token")

    assert exc.value.code == "tenant_bootstrap_failed"
    assert exc.value.status_code == 503


def test_ensure_minimum_tenant_uses_repo_methods_only(monkeypatch):
    captured_selects = []

    class _Exec:
        def __init__(self, data):
            self.data = data

    class _Query:
        def __init__(self, table):
            self.table = table
            self._filters = {}

        def select(self, cols):
            captured_selects.append((self.table, cols))
            self._select = cols
            return self

        def eq(self, key, value):
            self._filters[key] = value
            return self

        def limit(self, _n):
            return self

        def execute(self):
            if self.table == "tenant_members":
                return _Exec([{"tenant_id": "t1", "role": "owner"}])
            if self.table == "tenants":
                return _Exec([{"id": "t1", "name": "Meu espaço", "slug": "personal-u1"}])
            return _Exec([])

    class _Supabase:
        def table(self, table):
            return _Query(table)

    from repositories import tenant_repository as tr

    monkeypatch.setattr(tr, "get_supabase", lambda: _Supabase())

    repo = tr.TenantRepository()
    tenants = repo.get_user_tenants("u1")

    assert tenants[0]["tenant_id"] == "t1"
    assert ("tenant_members", "tenant_id, role") in captured_selects
    assert all("tenants!inner" not in cols for _table, cols in captured_selects)


def test_bootstrap_reconciles_stale_email_without_memberships(app_ctx, monkeypatch):
    users_repo = FakeUsersRepo()
    users_repo.create(
        {"id": "legacy-id", "name": "Legacy", "email": "same@example.com", "password": ""}
    )
    tenant_repo = FakeTenantRepo()
    service = AuthBootstrapService(tenant_repo=tenant_repo)

    monkeypatch.setattr(
        service,
        "_extract_profile_from_auth",
        lambda *_: ("Novo Usuário", "same@example.com"),
    )
    monkeypatch.setattr("services.bootstrap_service.create_user", lambda repo, payload, **_: repo.create(payload))

    result = service.ensure_user_and_tenant(
        user_id="new-auth-id",
        users_repo=users_repo,
        access_token="token",
        jwt_claims={"email": "same@example.com"},
    )

    assert result.tenant_id == "tenant-new-auth-id"
    assert users_repo.find_by_id("legacy-id") is None
    assert users_repo.find_by_id("new-auth-id") is not None
    assert users_repo.deleted == ["legacy-id"]


def test_bootstrap_blocks_conflicting_email_when_legacy_has_membership(app_ctx, monkeypatch):
    users_repo = FakeUsersRepo()
    users_repo.create(
        {"id": "legacy-id", "name": "Legacy", "email": "same@example.com", "password": ""}
    )

    tenant_repo = FakeTenantRepo()
    tenant_repo.user_tenants_by_user["legacy-id"] = [{"tenant_id": "tenant-legacy", "role": "owner"}]
    service = AuthBootstrapService(tenant_repo=tenant_repo)

    monkeypatch.setattr(
        service,
        "_extract_profile_from_auth",
        lambda *_: ("Novo Usuário", "same@example.com"),
    )
    monkeypatch.setattr("services.bootstrap_service.create_user", lambda repo, payload, **_: repo.create(payload))

    with pytest.raises(TenantBootstrapError) as exc:
        service.ensure_user_and_tenant(
            user_id="new-auth-id",
            users_repo=users_repo,
            access_token="token",
            jwt_claims={"email": "same@example.com"},
        )

    assert exc.value.code == "tenant_bootstrap_failed"
    assert exc.value.status_code == 503
    assert "já está associado a outro perfil" in exc.value.message
