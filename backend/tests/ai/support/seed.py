"""Dados sintéticos para os testes da plataforma de IA.

Tudo aqui é fictício. Os helpers gravam direto nas tabelas V2, no escopo do
tenant, e devolvem ids em string.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from services.ai.db import plain_tx, scoped_tx
from services.ai.policy import CAPABILITIES
from services.ai.scope import resolve_scope
from services.ai.types import ExecutionContext, Privacy


# Hash sintético: estes usuários não fazem login por senha nos testes de IA.
_PLACEHOLDER_HASH = "$argon2id$placeholder-not-a-real-hash"


def new_id() -> str:
    return str(uuid.uuid4())


def create_user(pool, email: str, name: str = "Pessoa Teste") -> str:
    with plain_tx(pool) as cursor:
        cursor.execute(
            """
            INSERT INTO users (email, name, password_hash, status, email_verified_at)
            VALUES (%s, %s, %s, 'active', now()) RETURNING id
            """,
            (email.lower(), name, _PLACEHOLDER_HASH),
        )
        return str(cursor.fetchone()["id"])


def create_tenant(pool, name: str, slug: str) -> str:
    with plain_tx(pool) as cursor:
        cursor.execute("INSERT INTO tenants (name, slug) VALUES (%s, %s) RETURNING id", (name, slug))
        return str(cursor.fetchone()["id"])


def add_tenant_member(pool, tenant_id: str, user_id: str, role: str = "owner") -> None:
    with plain_tx(pool) as cursor:
        cursor.execute(
            "INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (%s, %s, %s)",
            (tenant_id, user_id, role),
        )


def create_space(pool, tenant_id: str, name: str, kind: str = "personal") -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "INSERT INTO financial_spaces (tenant_id, kind, name) VALUES (%s, %s, %s) RETURNING id",
            (tenant_id, kind, name),
        )
        return str(cursor.fetchone()["id"])


def add_space_member(pool, tenant_id: str, space_id: str, user_id: str, role: str = "owner") -> None:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO financial_space_members (tenant_id, financial_space_id, user_id, role)
            VALUES (%s, %s, %s, %s)
            """,
            (tenant_id, space_id, user_id, role),
        )


def create_account(pool, tenant_id: str, space_id: Optional[str], name: str,
                   account_type: str = "checking", institution: str = "Banco Fictício") -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO accounts (tenant_id, name, type, institution)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (tenant_id, name, account_type, institution),
        )
        account_id = str(cursor.fetchone()["id"])
        if space_id:
            cursor.execute(
                """
                INSERT INTO financial_space_accounts (account_id, tenant_id, financial_space_id)
                VALUES (%s, %s, %s)
                """,
                (account_id, tenant_id, space_id),
            )
        return account_id


def create_category(pool, tenant_id: str, name: str, category_type: str = "expense") -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "INSERT INTO categories (tenant_id, name, type) VALUES (%s, %s, %s) RETURNING id",
            (tenant_id, name, category_type),
        )
        return str(cursor.fetchone()["id"])


def create_transaction(
    pool,
    tenant_id: str,
    account_id: str,
    category_id: str,
    *,
    description: str,
    amount: Any,
    occurred_on: date,
    tx_type: str = "expense",
    status: str = "paid",
    source_file: Optional[str] = "extrato-sintetico.ofx",
    entry_source: str = "ofx",
    fitid: Optional[str] = None,
) -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO transactions (
                tenant_id, account_id, category_id, description, amount, type,
                occurred_on, status, entry_source, source_file, fitid
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                tenant_id, account_id, category_id, description, Decimal(str(amount)), tx_type,
                occurred_on, status, entry_source, source_file, fitid or uuid.uuid4().hex,
            ),
        )
        return str(cursor.fetchone()["id"])


def create_payable(
    pool,
    tenant_id: str,
    space_id: Optional[str],
    *,
    title: str,
    amount_expected: Any,
    competency_month: date,
    due_date: Optional[date] = None,
    category_id: Optional[str] = None,
) -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO payables (tenant_id, category_id, title, amount_expected, due_date, competency_month)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (tenant_id, category_id, title, Decimal(str(amount_expected)), due_date, competency_month),
        )
        payable_id = str(cursor.fetchone()["id"])
        if space_id:
            cursor.execute(
                """
                INSERT INTO financial_space_payables (payable_id, tenant_id, financial_space_id)
                VALUES (%s, %s, %s)
                """,
                (payable_id, tenant_id, space_id),
            )
        return payable_id


def create_grant(
    pool,
    tenant_id: str,
    space_id: str,
    user_id: str,
    *,
    mode: str = "observe",
    capabilities: Optional[Sequence[str]] = None,
    amount_limit: Optional[Any] = None,
    amount_unlimited: bool = False,
    account_ids: Optional[Sequence[str]] = None,
    allowed_sources: Optional[Sequence[str]] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> str:
    """Insere um grant direto na tabela (atalho de teste)."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO ai_grants (
                tenant_id, financial_space_id, actor_user_id, granted_by_user_id, mode, capabilities,
                account_ids, amount_limit, amount_unlimited, allowed_sources, period_start, period_end
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                tenant_id, space_id, user_id, user_id, mode,
                list(capabilities) if capabilities is not None else list(CAPABILITIES),
                list(account_ids) if account_ids else None,
                Decimal(str(amount_limit)) if amount_limit is not None else None,
                amount_unlimited,
                list(allowed_sources) if allowed_sources else None,
                period_start, period_end,
            ),
        )
        return str(cursor.fetchone()["id"])


@dataclass
class World:
    """Um tenant sintético com um titular, espaços e contas."""

    tenant_id: str
    user_id: str
    personal_space_id: str
    business_space_id: str
    personal_account_id: str
    business_account_id: str
    expense_category_id: str
    income_category_id: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def context(self, pool, space: str = "personal", privacy: Privacy = Privacy.LOCAL_ONLY) -> ExecutionContext:
        space_id = self.personal_space_id if space == "personal" else self.business_space_id
        return resolve_scope(
            pool,
            user_id=self.user_id,
            requested_tenant_id=self.tenant_id,
            requested_space_id=space_id,
            privacy=privacy,
        )


def make_world(pool, slug: str) -> World:
    """Cria tenant + titular + espaço pessoal e de negócio, cada um com uma conta."""
    tenant_id = create_tenant(pool, "Organização %s" % slug, slug)
    user_id = create_user(pool, "titular-%s@example.test" % slug, "Titular %s" % slug)
    add_tenant_member(pool, tenant_id, user_id, "owner")
    personal = create_space(pool, tenant_id, "Pessoal", "personal")
    business = create_space(pool, tenant_id, "Marketing digital", "business")
    add_space_member(pool, tenant_id, personal, user_id, "owner")
    add_space_member(pool, tenant_id, business, user_id, "owner")
    personal_account = create_account(pool, tenant_id, personal, "Conta pessoal %s" % slug)
    business_account = create_account(pool, tenant_id, business, "Conta negócio %s" % slug)
    expense = create_category(pool, tenant_id, "Moradia", "expense")
    income = create_category(pool, tenant_id, "Salário", "income")
    return World(
        tenant_id=tenant_id,
        user_id=user_id,
        personal_space_id=personal,
        business_space_id=business,
        personal_account_id=personal_account,
        business_account_id=business_account,
        expense_category_id=expense,
        income_category_id=income,
    )


def utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def count_rows(pool, tenant_id: str, table: str, where: str = "true", params: Sequence[Any] = ()) -> int:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT count(*) AS total FROM %s WHERE %s" % (table, where), tuple(params))
        return int(cursor.fetchone()["total"])
