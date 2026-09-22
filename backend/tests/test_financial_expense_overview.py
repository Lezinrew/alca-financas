"""Offline contract tests; run with --noconftest to bypass legacy Mongo fixtures."""
from copy import deepcopy
from unittest.mock import Mock

import pytest

from services import financial_expense_service as service_module
from services.financial_expense_service import FinancialExpenseService
from repositories import financial_expense_repository_supabase as repository_module
from utils.exceptions import AppException, ValidationException


def expense(identifier, status="pending", expected="10.00", paid="0", due="2026-09-20"):
    return {"id": str(identifier), "status": status, "amount_expected": expected,
            "amount_paid": paid, "due_date": due, "title": "Conta", "category": "outros"}


class MemoryRepo:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_for_tenant(self, user_id, tenant_id, filters, page=1, per_page=50):
        self.calls.append((user_id, tenant_id, deepcopy(filters), page, per_page))
        offset = (page - 1) * per_page
        return {"data": deepcopy(self.rows[offset:offset + per_page]),
                "pagination": {"total": len(self.rows)}}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(service_module, "_today_iso", lambda: "2026-09-21")


def overview(rows, **query):
    return FinancialExpenseService(MemoryRepo(rows)).get_overview("u", "t", query)


def test_september_acceptance_totals():
    rows = [expense(i, "paid", "960.00", "960.00") for i in range(5)]
    rows.append(expense(5, "paid", "966.63", "966.63"))
    rows.extend(expense(i, expected="200.00") for i in range(6, 20))
    rows.append(expense(20, expected="939.80"))
    result = overview(rows, month="9", year="2026")
    assert (result["expected"], result["paid"], result["remaining"]) == (9506.43, 5766.63, 3739.80)
    assert result["total"] == 21
    assert result["counts"] == {"pending": 15, "partial": 0, "paid": 6, "canceled": 0, "overdue": 15}
    assert result["complete"] is True


def test_partial_canceled_and_due_groups_are_distinct_from_competency():
    rows = [expense(1, "partial", "100.10", "25.05", "2026-08-30"),
            expense(2, expected="50", due="2026-09-21"),
            expense(3, expected="40", due="2026-10-01"),
            expense(4, expected="30", due=None),
            expense(5, "paid", "20", "20"),
            expense(6, "canceled", "900", "800")]
    result = overview(rows, month="9", year="2026")
    assert (result["expected"], result["paid"], result["remaining"]) == (240.10, 45.05, 195.05)
    assert result["counts"] == {"pending": 3, "partial": 1, "paid": 1, "canceled": 1, "overdue": 1}
    assert result["due_groups"] == {
        "before": {"count": 1, "remaining": 75.05},
        "month": {"count": 1, "remaining": 50.0},
        "after": {"count": 1, "remaining": 40.0},
        "undated": {"count": 1, "remaining": 30.0},
    }
    assert result["as_of"] == "2026-09-21"


def test_full_pagination_more_than_one_thousand_uses_stable_scope_and_decimal():
    repo = MemoryRepo([expense(i, expected="0.10") for i in range(1201)])
    result = FinancialExpenseService(repo).get_overview("user", "tenant", {})
    assert result["total"] == 1201
    assert result["remaining"] == 120.1
    assert len(repo.calls) == 7
    assert all(call[:2] == ("user", "tenant") for call in repo.calls)
    assert all(call[2]["stable_order"] is True and call[2]["as_of"] == "2026-09-21" for call in repo.calls)


def test_competency_groups_do_not_reclassify_by_due_date():
    rows = [expense(1, due="2026-10-01"), expense(2, due="2026-08-01"),
            expense(3, due=None), expense(4)]
    rows[0].update(competency_month=8, competency_year=2026)
    rows[1].update(competency_month=9, competency_year=2026)
    rows[2].update(competency_month=10, competency_year=2026)
    result = overview(rows, reference_month="9", reference_year="2026")
    assert result["competency_groups"] == {
        key: {"count": 1, "remaining": 10.0} for key in ("before", "month", "after", "undated")
    }
    assert result["due_groups"]["after"]["count"] == 1
    assert rows[0]["competency_month"] == 8


def test_list_and_overview_share_business_filters():
    repo = MemoryRepo([])
    service = FinancialExpenseService(repo)
    query = {"month": "9", "year": "2026", "status": "overdue", "category": "saúde",
             "responsible": " Ana ", "is_recurring": "false", "outstanding_only": "true"}
    service.list_expenses("u", "t", query)
    service.get_overview("u", "t", query)
    list_filters, overview_filters = repo.calls[0][2], repo.calls[1][2]
    assert list_filters == {key: value for key, value in overview_filters.items()
                            if key not in ("as_of", "stable_order")}
    assert list_filters["is_recurring"] is False
    assert list_filters["overdue_only"] is True


@pytest.mark.parametrize("query", [
    {"month": "13", "year": "2026"}, {"month": "0", "year": "2026"},
    {"month": "9"}, {"year": "not-year"}, {"year": "2101"},
    {"reference_month": "0"}, {"reference_year": "1999"}, {"status": "wrong"},
])
def test_invalid_period_or_status_is_rejected_before_query(query):
    repo = MemoryRepo([])
    with pytest.raises(ValidationException):
        FinancialExpenseService(repo).get_overview("u", "t", query)
    assert not repo.calls


def test_empty_is_complete_and_zero_amount_overpayment_remains_nonnegative():
    assert overview([])["total"] == 0
    result = overview([expense(1, expected="0"), expense(2, "paid", "10", "12")])
    assert result["expected"] == 10
    assert result["paid"] == 12
    assert result["remaining"] == 0


@pytest.mark.parametrize("failure", ["truncated", "duplicate", "changed_count", "missing_count"])
def test_incomplete_results_never_return_complete_or_partial_money(failure):
    repo = MemoryRepo([expense(i) for i in range(201)])
    original = repo.list_for_tenant

    def broken(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure == "truncated":
            result["data"] = result["data"][:10]
        elif failure == "duplicate" and kwargs["page"] == 2:
            result["data"][0]["id"] = "0"
        elif failure == "changed_count" and kwargs["page"] == 2:
            result["pagination"]["total"] += 1
        elif failure == "missing_count":
            result["pagination"] = {}
        return result

    repo.list_for_tenant = broken
    with pytest.raises(AppException) as error:
        FinancialExpenseService(repo).get_overview("u", "t", {})
    assert error.value.status_code == 503


def test_repository_outage_is_not_empty_or_not_found(monkeypatch):
    repo = object.__new__(repository_module.FinancialExpenseRepository)
    repo.table_name = "financial_expenses"
    monkeypatch.setattr(repository_module, "get_supabase", Mock(side_effect=RuntimeError("offline")))
    for operation in (lambda: repo.list_for_tenant("u", "t", {}),
                      lambda: repo.find_by_id_for_tenant("id", "u", "t")):
        with pytest.raises(AppException) as error:
            operation()
        assert error.value.status_code == 503


@pytest.mark.parametrize("method", ["update", "delete", "pay"])
def test_mutation_failure_is_not_reported_as_success(method):
    repo = Mock()
    repo.find_by_id_for_tenant.return_value = expense(1)
    repo.update_row.return_value = False
    repo.delete_row.return_value = False
    service = FinancialExpenseService(repo)
    with pytest.raises(AppException) as error:
        if method == "update":
            service.update_expense("u", "t", "1", {"title": "Renamed"})
        elif method == "delete":
            service.delete_expense("u", "t", "1")
        else:
            service.mark_paid("u", "t", "1")
    assert error.value.status_code == 503


def test_legacy_summary_retains_its_existing_semantics():
    repo = MemoryRepo([expense(1, "paid", "100", "120"), expense(2, "partial", "100", "20")])
    result = FinancialExpenseService(repo).get_summary("u", "t", 9, 2026)
    assert result["paid_sum_expected"] == 100
    assert result["open_remaining_sum"] == 80
    assert "expected" not in result
