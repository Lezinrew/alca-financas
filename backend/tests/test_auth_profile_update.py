"""Offline contract tests for PUT /api/auth/profile (no real DB, no real JWT)."""
from copy import deepcopy

import pytest
from flask import Flask, jsonify

from extensions import limiter
from routes import auth as auth_routes
from utils import auth_utils
from utils.exceptions import AppException

USER_ID = "11111111-1111-1111-1111-111111111111"


class MemoryUsers:
    def __init__(self, rows, update_ok=True):
        self.rows = {row["id"]: row for row in rows}
        self.update_ok = update_ok
        self.updates = []

    def find_one(self, filter_query):
        row = self.rows.get(filter_query.get("id"))
        return deepcopy(row) if row else None

    def update(self, user_id, data):
        self.updates.append((user_id, dict(data)))
        if not self.update_ok or user_id not in self.rows:
            return False
        self.rows[user_id].update(data)
        return True


def _user(**overrides):
    row = {"id": USER_ID, "name": "Antigo", "email": "ana@example.com",
           "settings": {"currency": "BRL"}, "auth_providers": [], "role": "user", "status": "active"}
    row.update(overrides)
    return row


@pytest.fixture
def users():
    return MemoryUsers([_user(), _user(id="other", name="Outro", email="o@example.com")])


@pytest.fixture
def client(users, monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False, DB_TYPE="supabase", USERS=users)
    limiter.init_app(app)
    app.register_blueprint(auth_routes.bp, url_prefix="/api")

    @app.errorhandler(AppException)
    def _handle(e):
        return jsonify(e.to_dict()), e.status_code

    def fake_verify(token):
        if token != "valid":
            raise ValueError("bad token")
        return {"sub": USER_ID}

    monkeypatch.setattr(auth_utils, "verify_supabase_jwt", fake_verify)
    return app.test_client()


AUTH = {"Authorization": "Bearer valid"}


def test_valid_name_updates_own_row_and_returns_me_shape(client, users):
    res = client.put("/api/auth/profile", json={"name": "  Ana Souza  "}, headers=AUTH)
    assert res.status_code == 200
    body = res.get_json()
    assert body["name"] == "Ana Souza"
    assert body["id"] == USER_ID and body["email"] == "ana@example.com"
    assert set(body) == {"id", "name", "email", "settings", "auth_providers", "role", "status", "is_admin"}
    assert users.updates[0][0] == USER_ID
    assert users.updates[0][1]["name"] == "Ana Souza"
    assert users.rows["other"]["name"] == "Outro"

    me = client.get("/api/auth/me", headers=AUTH).get_json()
    assert me == body


@pytest.mark.parametrize("payload", [
    {"name": ""}, {"name": "   "}, {"name": "A"}, {"name": " A "}, {"name": "x" * 121},
    {"name": None}, {"name": 123}, {}, {"name": "Ana\x00"}, {"name": "Ana\nSouza"},
    {"name": "Ana​Souza"},
])
def test_invalid_names_are_rejected_without_writing(client, users, payload):
    res = client.put("/api/auth/profile", json=payload, headers=AUTH)
    assert res.status_code == 400
    assert res.get_json()["error"]
    assert users.updates == []


def test_boundary_lengths_are_accepted(client):
    assert client.put("/api/auth/profile", json={"name": "Al"}, headers=AUTH).status_code == 200
    assert client.put("/api/auth/profile", json={"name": "x" * 120}, headers=AUTH).status_code == 200


def test_email_in_body_is_rejected_and_nothing_changes(client, users):
    res = client.put("/api/auth/profile", json={"name": "Ana Souza", "email": "novo@example.com"},
                     headers=AUTH)
    assert res.status_code == 400
    assert res.get_json()["field"] == "email"
    assert users.updates == []
    assert users.rows[USER_ID]["email"] == "ana@example.com"


def test_id_in_body_cannot_target_another_user(client, users):
    res = client.put("/api/auth/profile", json={"name": "Hacker", "id": "other"}, headers=AUTH)
    assert res.status_code == 400
    assert users.rows["other"]["name"] == "Outro"
    assert users.updates == []


def test_non_json_body_is_rejected(client, users):
    res = client.put("/api/auth/profile", data="name=Ana", headers=AUTH)
    assert res.status_code == 400
    assert users.updates == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}])
def test_requires_authentication(client, users, headers):
    res = client.put("/api/auth/profile", json={"name": "Ana Souza"}, headers=headers)
    assert res.status_code == 401
    assert users.updates == []


def test_persistence_failure_is_not_reported_as_success(client, users):
    users.update_ok = False
    res = client.put("/api/auth/profile", json={"name": "Ana Souza"}, headers=AUTH)
    assert res.status_code == 503
    assert "name" not in res.get_json()
    assert users.rows[USER_ID]["name"] == "Antigo"


def test_missing_user_row_returns_404(client, users):
    del users.rows[USER_ID]
    res = client.put("/api/auth/profile", json={"name": "Ana Souza"}, headers=AUTH)
    assert res.status_code == 404
    assert users.updates == []
