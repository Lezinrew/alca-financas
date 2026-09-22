"""Offline contract tests for GET /api/transactions/totals (service + filters)."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

from routes import transactions as routes_module
from services.transaction_service import TOTALS_PAGE_SIZE, TransactionService
from utils.exceptions import AppException


def tx(identifier, amount="10.00", status="paid", type_="expense"):
    return {"id": str(identifier), "amount": amount, "status": status, "type": type_,
            "account_id": "card-1", "date": "2026-09-15"}


class MemoryRepo:
    """Imita find_advanced: pagina sobre `rows` e registra cada chamada."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def find_advanced(self, user_id, params, tenant_id=None, raise_on_error=False):
        self.calls.append((user_id, tenant_id, deepcopy(params), raise_on_error))
        page, limit = int(params["page"]), int(params["limit"])
        offset = (page - 1) * limit
        return {"data": deepcopy(self.rows[offset:offset + limit]),
                "pagination": {"total": len(self.rows), "page": page, "per_page": limit}}


def totals(repo, filters=None, user_id="u", tenant_id="t"):
    return TransactionService(repo, Mock(), Mock()).get_totals(user_id, filters or {}, tenant_id=tenant_id)


def test_sums_more_than_500_items_across_pages_with_decimal_precision():
    repo = MemoryRepo([tx(i, "0.10") for i in range(1201)])
    result = totals(repo)
    assert result["count"] == 1201
    assert result["expense_total"] == 120.1
    assert result["income_total"] == 0
    assert result["complete"] is True
    assert [call[2]["page"] for call in repo.calls] == [1, 2, 3]
    assert all(call[2]["limit"] == TOTALS_PAGE_SIZE for call in repo.calls)
    # Ordem estável (id) e falhas do banco propagadas em todas as páginas
    assert all(call[2]["sort"] == "id:asc" and call[3] is True for call in repo.calls)


def test_includes_pending_and_overdue_and_excludes_cancelled_from_totals():
    rows = [tx(1, "100.00", "paid"), tx(2, "50.50", "pending"), tx(3, "20", "overdue"),
            tx(4, "999", "cancelled"), tx(5, "1", "canceled"), tx(6, "30", "paid", "income"),
            tx(7, "5", None)]
    result = totals(MemoryRepo(rows))
    assert result["count"] == 7
    assert result["expense_total"] == 175.5
    assert result["income_total"] == 30
    assert result["net_total"] == -145.5
    assert result["by_status"] == {
        "paid": {"count": 2, "expense_total": 100.0, "income_total": 30.0},
        "pending": {"count": 2, "expense_total": 55.5, "income_total": 0.0},
        "overdue": {"count": 1, "expense_total": 20.0, "income_total": 0.0},
        "cancelled": {"count": 2, "expense_total": 1000.0, "income_total": 0.0},
    }
    assert result["excluded_statuses"] == ["cancelled"]


def test_negative_stored_amounts_are_summed_as_absolute_values():
    result = totals(MemoryRepo([tx(1, "-40"), tx(2, -2.5, "pending")]))
    assert result["expense_total"] == 42.5


def test_account_period_and_tenant_are_passed_to_every_page_and_pagination_is_ignored():
    repo = MemoryRepo([tx(i) for i in range(501)])
    filters = {"account_ids": "card-1", "date_from": "2026-08-11", "date_to": "2026-09-10",
               "types": "expense", "page": 9, "limit": 3, "sort": "amount:asc"}
    totals(repo, filters, user_id="user-a", tenant_id="tenant-a")
    assert len(repo.calls) == 2
    for user_id, tenant_id, params, _ in repo.calls:
        assert (user_id, tenant_id) == ("user-a", "tenant-a")
        assert params["account_ids"] == "card-1"
        assert (params["date_from"], params["date_to"], params["types"]) == ("2026-08-11", "2026-09-10", "expense")
        assert params["limit"] == TOTALS_PAGE_SIZE and params["sort"] == "id:asc"


def test_empty_result_is_complete_zero():
    result = totals(MemoryRepo([]))
    assert (result["count"], result["expense_total"], result["complete"]) == (0, 0, True)


@pytest.mark.parametrize("failure", ["raises", "empty_page", "changed_count", "duplicate",
                                     "truncated", "missing_count", "bad_amount", "bad_status"])
def test_page_failure_or_inconsistency_is_503_never_partial(failure):
    repo = MemoryRepo([tx(i) for i in range(1200)])
    original = repo.find_advanced

    def broken(user_id, params, tenant_id=None, raise_on_error=False):
        result = original(user_id, params, tenant_id=tenant_id, raise_on_error=raise_on_error)
        second = params["page"] == 2
        if failure == "raises" and second:
            raise RuntimeError("supabase offline")
        if failure == "empty_page" and second:
            # Comportamento legado do repositório em erro: página vazia com total 0
            return {"data": [], "pagination": {"total": 0}}
        if failure == "changed_count" and second:
            result["pagination"]["total"] += 1
        if failure == "duplicate" and second:
            result["data"][0]["id"] = "0"
        if failure == "truncated" and second:
            result["data"] = result["data"][:10]
        if failure == "missing_count":
            result["pagination"] = {}
        if failure == "bad_amount" and second:
            result["data"][0]["amount"] = "abc"
        if failure == "bad_status" and second:
            result["data"][0]["status"] = "weird"
        return result

    repo.find_advanced = broken
    with pytest.raises(AppException) as error:
        totals(repo)
    assert error.value.status_code == 503


def test_repository_propagates_errors_only_when_asked(monkeypatch):
    from database import connection
    from repositories.transaction_repository_supabase import TransactionRepository

    repo = object.__new__(TransactionRepository)
    repo.table_name = "transactions"
    monkeypatch.setattr(connection, "get_supabase", Mock(side_effect=RuntimeError("offline")))
    legacy = repo.find_advanced("u", {"page": 1, "limit": 10}, tenant_id="t")
    assert legacy["data"] == [] and legacy["pagination"]["total"] == 0
    with pytest.raises(RuntimeError):
        repo.find_advanced("u", {"page": 1, "limit": 10}, tenant_id="t", raise_on_error=True)


def test_totals_uses_same_business_filters_as_listing_and_route_is_registered():
    args = MultiDict({"account_ids": "card-1", "date_from": "2026-08-11", "date_to": "2026-09-10",
                      "types": "expense", "status": "", "page": "2", "limit": "500", "sort": "date:desc"})
    assert routes_module._listing_filters(args) == {
        "account_ids": "card-1", "date_from": "2026-08-11", "date_to": "2026-09-10", "types": "expense",
    }
    app = Flask(__name__)
    app.register_blueprint(routes_module.bp)
    endpoint, _ = app.url_map.bind("localhost").match("/api/transactions/totals", method="GET")
    assert endpoint == "transactions.transactions_totals"
