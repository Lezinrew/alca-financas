"""
Testes unitários para Issue #1: Financial Inconsistency

Garante que overview_report_supabase() filtra apenas transações
com status='paid', mantendo consistência com dashboard e saldo de contas.
"""

import pytest
from datetime import datetime
from services.report_service import overview_report_supabase


class MockTransactionsRepo:
    def __init__(self, transactions):
        self.transactions = transactions

    def find_by_user_and_date_range(self, user_id, start, end, tenant_id=None):
        return self.transactions


class MockCategoriesRepo:
    def __init__(self, categories):
        self.categories = categories

    def find_by_user(self, user_id, tenant_id=None):
        return self.categories


class MockAccountsRepo:
    def __init__(self, accounts):
        self.accounts = accounts

    def find_by_user(self, user_id, tenant_id=None):
        return self.accounts


@pytest.fixture
def transactions_with_pending():
    """Transações mistas: paid e pending"""
    return [
        {'type': 'expense', 'amount': 100, 'category_id': 'cat1', 'account_id': 'acc1', 'status': 'paid'},
        {'type': 'expense', 'amount': 50, 'category_id': 'cat1', 'account_id': 'acc1', 'status': 'pending'},
        {'type': 'income', 'amount': 200, 'category_id': 'cat2', 'account_id': 'acc1', 'status': 'paid'},
        {'type': 'income', 'amount': 100, 'category_id': 'cat2', 'account_id': 'acc1', 'status': 'pending'},
    ]


@pytest.fixture
def categories():
    return [
        {'id': 'cat1', 'name': 'Despesas', 'color': '#ff0000', 'icon': 'expense'},
        {'id': 'cat2', 'name': 'Receitas', 'color': '#00ff00', 'icon': 'income'},
    ]


@pytest.fixture
def accounts():
    return [
        {'id': 'acc1', 'name': 'Conta', 'color': '#0000ff', 'icon': 'wallet', 'is_active': True},
    ]


def test_expenses_by_category_ignores_pending(transactions_with_pending, categories, accounts):
    """expenses_by_category deve ignorar transações pending"""
    repos = (
        MockTransactionsRepo(transactions_with_pending),
        MockCategoriesRepo(categories),
        MockAccountsRepo(accounts)
    )

    result = overview_report_supabase(
        *repos, 'user1', 1, 2024, 'expenses_by_category', tenant_id='tenant1'
    )

    # Total deve ser 100 (paid), não 150 (paid + pending)
    assert result['total_amount'] == 100.0


def test_income_by_category_ignores_pending(transactions_with_pending, categories, accounts):
    """income_by_category deve ignorar transações pending"""
    repos = (
        MockTransactionsRepo(transactions_with_pending),
        MockCategoriesRepo(categories),
        MockAccountsRepo(accounts)
    )

    result = overview_report_supabase(
        *repos, 'user1', 1, 2024, 'income_by_category', tenant_id='tenant1'
    )

    # Total deve ser 200 (paid), não 300 (paid + pending)
    assert result['total_amount'] == 200.0


def test_expenses_by_account_ignores_pending(transactions_with_pending, categories, accounts):
    """expenses_by_account deve ignorar transações pending"""
    repos = (
        MockTransactionsRepo(transactions_with_pending),
        MockCategoriesRepo(categories),
        MockAccountsRepo(accounts)
    )

    result = overview_report_supabase(
        *repos, 'user1', 1, 2024, 'expenses_by_account', tenant_id='tenant1'
    )

    # Total deve ser 100 (paid), não 150 (paid + pending)
    assert result['total_amount'] == 100.0


def test_income_by_account_ignores_pending(transactions_with_pending, categories, accounts):
    """income_by_account deve ignorar transações pending"""
    repos = (
        MockTransactionsRepo(transactions_with_pending),
        MockCategoriesRepo(categories),
        MockAccountsRepo(accounts)
    )

    result = overview_report_supabase(
        *repos, 'user1', 1, 2024, 'income_by_account', tenant_id='tenant1'
    )

    # Total deve ser 200 (paid), não 300 (paid + pending)
    assert result['total_amount'] == 200.0
