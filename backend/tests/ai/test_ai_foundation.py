"""Fundação: migrations, RLS, contexto resolvido no servidor e grants."""

from __future__ import annotations

import psycopg2
import pytest

from services.ai import policy
from services.ai.db import scoped_tx, write_audit
from services.ai.errors import AiError, CONTRACT_MINIMUM_CODES, is_known_code
from services.ai.scope import resolve_scope
from services.ai.types import money_str

from .support import pg, seed


pytestmark = pytest.mark.integration


def test_migrations_apply_and_app_role_is_not_superuser(pool):
    with scoped_tx(pool, seed.new_id()) as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        role = cursor.fetchone()
        cursor.execute(
            r"SELECT count(*) AS total FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'ai\_%'"
        )
        assert cursor.fetchone()["total"] == 12
    assert role["rolsuper"] is False and role["rolbypassrls"] is False


def test_rls_hides_other_tenant_rows_even_without_where(pool, world, other_world):
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT tenant_id FROM financial_spaces")
        tenants = {str(row["tenant_id"]) for row in cursor.fetchall()}
    assert tenants == {world.tenant_id}

    # Sem escopo definido nenhuma linha é visível.
    connection = pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM financial_spaces")
            assert cursor.fetchone()[0] == 0
        connection.rollback()
    finally:
        pool.putconn(connection)


def test_rls_blocks_insert_for_other_tenant(pool, world, other_world):
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with scoped_tx(pool, world.tenant_id) as cursor:
            cursor.execute(
                "INSERT INTO financial_spaces (tenant_id, kind, name) VALUES (%s, 'personal', 'Invasor')",
                (other_world.tenant_id,),
            )


def test_scope_is_resolved_on_server_and_foreign_space_is_not_found(pool, world, other_world):
    context = world.context(pool, "personal")
    assert context.tenant_id == world.tenant_id
    assert context.allowed_account_ids == frozenset({world.personal_account_id})

    with pytest.raises(AiError) as excinfo:
        resolve_scope(
            pool,
            user_id=world.user_id,
            requested_tenant_id=world.tenant_id,
            requested_space_id=other_world.personal_space_id,
        )
    assert excinfo.value.code == "not_found"

    with pytest.raises(AiError) as excinfo:
        resolve_scope(pool, user_id=world.user_id, requested_tenant_id=other_world.tenant_id)
    assert excinfo.value.code == "scope_denied"


def test_two_spaces_require_explicit_choice(pool, world):
    with pytest.raises(AiError) as excinfo:
        resolve_scope(pool, user_id=world.user_id)
    assert excinfo.value.code == "invalid_request"


def test_no_grant_means_no_capability(pool, world):
    context = world.context(pool)
    with scoped_tx(pool, context.tenant_id) as cursor:
        grants = policy.load_active_grants(cursor, context)
    assert grants == []
    with pytest.raises(AiError) as excinfo:
        policy.authorize(grants, "finance.read")
    assert excinfo.value.code == "capability_denied"


def test_delegated_grant_requires_explicit_amount_decision(pool, world):
    context = world.context(pool)
    with pytest.raises(AiError) as excinfo:
        policy.create_grant(pool, context, mode="delegated", capabilities=["finance.apply_change"])
    assert excinfo.value.code == "invalid_request"

    grant = policy.create_grant(
        pool, context, mode="delegated", capabilities=["finance.apply_change"], amount_limit="500.00"
    )
    assert grant.amount_limit == policy.to_decimal("500.00") and grant.amount_unlimited is False
    effect = policy.EffectRequest("finance.apply_change", amount=policy.to_decimal("500.01"))
    assert policy.grant_violation(grant, effect) == "valor acima do limite do grant"


def test_grant_from_one_space_does_not_cover_another(pool, world):
    personal = world.context(pool, "personal")
    business = world.context(pool, "business")
    policy.create_grant(pool, personal, mode="observe", capabilities=["finance.read"])
    with scoped_tx(pool, business.tenant_id) as cursor:
        assert policy.load_active_grants(cursor, business) == []


def test_revoked_grant_is_rejected_at_effect_time_and_audited(pool, world):
    context = world.context(pool)
    grant = policy.create_grant(
        pool, context, mode="delegated", capabilities=["finance.apply_change"], amount_unlimited=True
    )
    effect = policy.EffectRequest("finance.apply_change", amount=policy.to_decimal("10"))
    with scoped_tx(pool, context.tenant_id) as cursor:
        assert policy.lock_grant_for_effect(
            cursor, context, effect, grant_id=grant.id, grant_version=grant.version
        ).id == grant.id

    policy.revoke_grant(pool, context, grant.id, "teste de revogação")
    with pytest.raises(AiError) as excinfo:
        with scoped_tx(pool, context.tenant_id) as cursor:
            policy.lock_grant_for_effect(cursor, context, effect, grant_id=grant.id, grant_version=grant.version)
    assert excinfo.value.code == "capability_denied"
    events = seed.count_rows(pool, world.tenant_id, "audit_events", "event_type LIKE 'ai.grant.%%'")
    assert events == 2


def test_grant_restricted_to_accounts_reads_ids_and_requires_identified_account(pool, world):
    """``account_ids`` (uuid[]) volta como lista de ids, não como texto cru."""
    context = world.context(pool)
    grant = policy.create_grant(
        pool, context, mode="delegated", capabilities=["finance.apply_change"],
        amount_unlimited=True, account_ids=[world.personal_account_id],
    )
    assert grant.account_ids == frozenset({world.personal_account_id})
    with scoped_tx(pool, context.tenant_id) as cursor:
        loaded = policy.load_active_grants(cursor, context)
    assert loaded[0].account_ids == frozenset({world.personal_account_id})
    assert loaded[0].to_public_dict()["account_ids"] == [world.personal_account_id]

    inside = policy.EffectRequest("finance.apply_change", account_ids=[world.personal_account_id])
    outside = policy.EffectRequest("finance.apply_change", account_ids=[world.business_account_id])
    unidentified = policy.EffectRequest("finance.apply_change")
    assert policy.grant_violation(loaded[0], inside) is None
    assert policy.grant_violation(loaded[0], outside) == "conta fora do grant"
    assert policy.grant_violation(loaded[0], unidentified) == "efeito sem conta identificada"
    with scoped_tx(pool, context.tenant_id) as cursor:
        assert policy.lock_grant_for_effect(
            cursor, context, inside, grant_id=grant.id, grant_version=grant.version
        ).id == grant.id


def test_only_space_owner_manages_grants(pool, world):
    member_id = seed.create_user(pool, "integrante-alfa@example.test", "Integrante")
    seed.add_tenant_member(pool, world.tenant_id, member_id, "member")
    seed.add_space_member(pool, world.tenant_id, world.personal_space_id, member_id, "member")
    member_context = resolve_scope(
        pool, user_id=member_id, requested_tenant_id=world.tenant_id,
        requested_space_id=world.personal_space_id,
    )
    with scoped_tx(pool, world.tenant_id) as cursor:
        assert policy.space_role(cursor, member_context) == "member"
    with pytest.raises(AiError) as excinfo:
        policy.create_grant(pool, member_context, mode="observe", capabilities=["finance.read"])
    assert excinfo.value.code == "capability_denied"


def test_jsonb_storage_survives_nul_and_lone_surrogates(pool, world):
    dirty = "a" + chr(0) + "b" + chr(0xD800) + "c"
    with scoped_tx(pool, world.tenant_id) as cursor:
        write_audit(
            cursor, tenant_id=world.tenant_id, actor_user_id=world.user_id,
            event_type="ai.test.hygiene", metadata={"texto": dirty},
        )
        cursor.execute("SELECT metadata FROM audit_events WHERE event_type = 'ai.test.hygiene'")
        assert cursor.fetchone()["metadata"]["texto"] == "a" + chr(0xFFFD) + "b" + chr(0xFFFD) + "c"


def test_one_active_email_connection_per_owner_and_space(pool, world):
    insert = (
        "INSERT INTO ai_email_connections "
        "(tenant_id, financial_space_id, owner_user_id, provider, mailbox_label, status) "
        "VALUES (%s, %s, %s, 'fixture', %s, 'active')"
    )
    params = (world.tenant_id, world.personal_space_id, world.user_id)
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute(insert, params + ("caixa-1",))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with scoped_tx(pool, world.tenant_id) as cursor:
            cursor.execute(insert, params + ("caixa-2",))


def test_error_catalog_covers_contract_minimum_codes():
    assert all(is_known_code(code) for code in CONTRACT_MINIMUM_CODES)
    payload = AiError("stale_proposal").to_dict("trace-1")
    assert set(payload) == {"code", "retryable", "safe_message", "trace_id"}


def test_money_is_never_float():
    assert money_str("1234.5") == "1234.50"
    assert money_str(0.1 + 0.2) == "0.30"


def test_down_migration_removes_only_ai_objects():
    """A reversão da 0002 remove o estado da IA e preserva as tabelas da 0001."""
    database = pg.provision()
    if database is None:
        pytest.skip("PostgreSQL de teste indisponível")
    try:
        script = (pg.MIGRATIONS_DIR / "0002_ai_platform.down.sql").read_text(encoding="utf-8")
        connection = psycopg2.connect(database.app_dsn)
        try:
            with connection.cursor() as cursor:
                cursor.execute(script)
            connection.commit()
            with connection.cursor() as cursor:
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                tables = {row[0] for row in cursor.fetchall()}
        finally:
            connection.close()
    finally:
        pg.destroy(database)
    assert not {name for name in tables if name.startswith("ai_") or name.startswith("financial_space")}
    assert {"users", "tenants", "accounts", "payables", "payable_payments", "transactions", "audit_events"} <= tables
