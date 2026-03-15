"""
Serviço de Planejamento: agrega orçamento planejado (budget_*) e fatos (transactions).
Regras: PLANS = budget_plans/budget_monthly, FACTS = transactions.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from services.planning_constants import (
    EXPENSE_STATUS_SAFE,
    EXPENSE_STATUS_WARNING,
    EXPENSE_STATUS_EXCEEDED,
    EXPENSE_STATUS_UNPLANNED,
    EXPENSE_SAFE_THRESHOLD_PERCENT,
    EXPENSE_WARNING_MAX_PERCENT,
    INCOME_STATUS_ON_TRACK,
    INCOME_STATUS_BELOW_TARGET,
    INCOME_STATUS_EXCEEDED_TARGET,
    ALERT_UNPLANNED_EXPENSE,
    ALERT_ABOVE_BUDGET,
    ALERT_CLOSE_TO_LIMIT,
)


def _period_iso(month: int, year: int) -> Tuple[str, str]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _expense_status(planned: float, spent: float) -> str:
    if planned <= 0 and spent > 0:
        return EXPENSE_STATUS_UNPLANNED
    if planned <= 0:
        return EXPENSE_STATUS_SAFE
    progress = (spent / planned) * 100
    if progress <= EXPENSE_SAFE_THRESHOLD_PERCENT:
        return EXPENSE_STATUS_SAFE
    if progress <= EXPENSE_WARNING_MAX_PERCENT:
        return EXPENSE_STATUS_WARNING
    return EXPENSE_STATUS_EXCEEDED


def _income_status(planned: float, received: float) -> str:
    if planned <= 0:
        return INCOME_STATUS_ON_TRACK
    if received >= planned:
        return INCOME_STATUS_EXCEEDED_TARGET if received > planned else INCOME_STATUS_ON_TRACK
    return INCOME_STATUS_BELOW_TARGET


def get_planning_month_payload(
    *,
    user_id: str,
    tenant_id: Optional[str],
    month: int,
    year: int,
    transactions_repo,
    categories_repo,
    budget_repo,
) -> Dict[str, Any]:
    """
    Um único payload para a tela de Planejamento.
    Separa expense_categories e income_categories; inclui summary e alerts.
    """
    start_iso, end_iso = _period_iso(month, year)

    planned_income = 0.0
    planned_expenses = 0.0
    budget_monthly = None
    plans: List[Dict[str, Any]] = []
    if tenant_id and budget_repo:
        budget_monthly = budget_repo.get_monthly(tenant_id, month, year)
        if budget_monthly:
            planned_income = float(budget_monthly.get("planned_income") or 0)
        plans = budget_repo.get_plans_for_month(tenant_id, user_id, month, year)

    transactions_list = transactions_repo.find_by_user_and_date_range(
        user_id, start_iso, end_iso, tenant_id=tenant_id
    )
    real_income = sum(float(t.get("amount", 0)) for t in transactions_list if t.get("type") == "income")
    real_expenses = sum(float(t.get("amount", 0)) for t in transactions_list if t.get("type") == "expense")
    real_balance = real_income - real_expenses
    savings_rate = (real_balance / real_income * 100) if real_income > 0 else 0.0

    spent_by_cat: Dict[str, float] = {}
    received_by_cat: Dict[str, float] = {}
    for t in transactions_list:
        cid = t.get("category_id")
        cid_str = str(cid) if cid else "__none__"
        amount = float(t.get("amount", 0))
        if t.get("type") == "expense":
            spent_by_cat[cid_str] = spent_by_cat.get(cid_str, 0) + amount
        else:
            received_by_cat[cid_str] = received_by_cat.get(cid_str, 0) + amount

    planned_by_cat: Dict[str, float] = {}
    for p in plans:
        cid = str(p.get("category_id", ""))
        planned_by_cat[cid] = float(p.get("planned_amount") or 0)
    planned_expenses = sum(
        planned_by_cat.get(cid, 0) for cid in planned_by_cat
        if _category_type(categories_repo, cid) == "expense"
    )
    planned_income_from_plans = sum(
        planned_by_cat.get(cid, 0) for cid in planned_by_cat
        if _category_type(categories_repo, cid) == "income"
    )
    if planned_income_from_plans > 0:
        planned_income = planned_income_from_plans
    planned_balance = planned_income - planned_expenses

    expense_categories: List[Dict[str, Any]] = []
    income_categories: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []

    all_cat_ids = set(planned_by_cat.keys()) | set(spent_by_cat.keys()) | set(received_by_cat.keys())
    all_cat_ids.discard("__none__")

    for cid in all_cat_ids:
        cat = _get_category(categories_repo, cid)
        cat_type = cat.get("type", "expense") if cat else "expense"
        name = cat.get("name", "Sem categoria") if cat else "Sem categoria"
        color = cat.get("color", "#6b7280") if cat else "#6b7280"
        icon = cat.get("icon", "circle") if cat else "circle"

        if cat_type == "expense":
            planned = planned_by_cat.get(cid, 0)
            spent = spent_by_cat.get(cid, 0)
            remaining = planned - spent
            progress = (spent / planned * 100) if planned > 0 else (100.0 if spent > 0 else 0)
            status = _expense_status(planned, spent)
            expense_categories.append({
                "category_id": cid,
                "category_name": name,
                "category_color": color,
                "category_icon": icon,
                "planned_amount": round(planned, 2),
                "spent_amount": round(spent, 2),
                "remaining_amount": round(remaining, 2),
                "progress_percent": round(progress, 2),
                "status": status,
            })
            if status == EXPENSE_STATUS_UNPLANNED and spent > 0:
                alerts.append({
                    "type": ALERT_UNPLANNED_EXPENSE,
                    "category_id": cid,
                    "category_name": name,
                    "spent_amount": round(spent, 2),
                })
            elif status == EXPENSE_STATUS_EXCEEDED:
                alerts.append({
                    "type": ALERT_ABOVE_BUDGET,
                    "category_id": cid,
                    "category_name": name,
                    "spent_amount": round(spent, 2),
                    "planned_amount": round(planned, 2),
                })
            elif status == EXPENSE_STATUS_WARNING:
                alerts.append({
                    "type": ALERT_CLOSE_TO_LIMIT,
                    "category_id": cid,
                    "category_name": name,
                    "spent_amount": round(spent, 2),
                    "planned_amount": round(planned, 2),
                })
        else:
            planned = planned_by_cat.get(cid, 0)
            received = received_by_cat.get(cid, 0)
            difference = received - planned
            progress = (received / planned * 100) if planned > 0 else (100.0 if received > 0 else 0)
            status = _income_status(planned, received)
            income_categories.append({
                "category_id": cid,
                "category_name": name,
                "category_color": color,
                "category_icon": icon,
                "planned_amount": round(planned, 2),
                "received_amount": round(received, 2),
                "difference_amount": round(difference, 2),
                "progress_percent": round(progress, 2),
                "status": status,
            })

    expense_categories.sort(key=lambda x: -x["spent_amount"])
    income_categories.sort(key=lambda x: -x["received_amount"])

    return {
        "period": {"year": year, "month": month},
        "summary": {
            "planned_income": round(planned_income, 2),
            "planned_expenses": round(planned_expenses, 2),
            "planned_balance": round(planned_balance, 2),
            "real_income": round(real_income, 2),
            "real_expenses": round(real_expenses, 2),
            "real_balance": round(real_balance, 2),
            "savings_rate": round(savings_rate, 2),
        },
        "expense_categories": expense_categories,
        "income_categories": income_categories,
        "alerts": alerts,
    }


def _get_category(categories_repo, category_id: str) -> Optional[Dict[str, Any]]:
    if not category_id or category_id == "__none__":
        return None
    if hasattr(categories_repo, "find_by_id"):
        return categories_repo.find_by_id(category_id)
    return None


def _category_type(categories_repo, category_id: str) -> str:
    cat = _get_category(categories_repo, category_id)
    if not cat:
        return "expense"
    return (cat.get("type") or "expense").lower()


def save_planning_month(
    *,
    tenant_id: str,
    user_id: str,
    month: int,
    year: int,
    planned_income: float,
    savings_percentage: float,
    category_plans: List[Dict[str, Any]],
    budget_repo,
) -> Dict[str, Any]:
    """Persiste budget_monthly e budget_plans para o mês (PUT /api/planning/month)."""
    budget_repo.upsert_monthly(tenant_id, month, year, planned_income, savings_percentage)
    budget_repo.upsert_plans(tenant_id, user_id, month, year, category_plans)
    return {"message": "Planejamento salvo com sucesso", "month": month, "year": year}


def create_or_upsert_budget_lines(
    *,
    tenant_id: str,
    user_id: str,
    month: int,
    year: int,
    lines: List[Dict[str, Any]],
    budget_repo,
) -> Dict[str, Any]:
    """Cria ou atualiza linhas de orçamento (POST /api/planning/month)."""
    budget_repo.upsert_plans(tenant_id, user_id, month, year, lines)
    return {"message": "Orçamento atualizado", "month": month, "year": year}
