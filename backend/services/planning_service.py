"""
Serviço de Planejamento: agrega orçamento planejado + transações reais em um único payload.
Separação clara: planned (budget_*) vs real (transactions).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


def _period_iso(month: int, year: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


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
    Retorna um único payload para a tela de Planejamento: planejado + real + progresso por categoria.
    Evita múltiplas chamadas do frontend.
    """
    start_iso, end_iso = _period_iso(month, year)

    planned_income = 0.0
    planned_expenses = 0.0
    budget_monthly = None
    if tenant_id and budget_repo:
        budget_monthly = budget_repo.get_monthly(tenant_id, month, year)
        if budget_monthly:
            planned_income = float(budget_monthly.get("planned_income") or 0)
        plans = budget_repo.get_plans_for_month(tenant_id, month, year)
    else:
        plans = []

    transactions_list = transactions_repo.find_by_user_and_date_range(
        user_id, start_iso, end_iso, tenant_id=tenant_id
    )
    real_income = sum(float(t.get("amount", 0)) for t in transactions_list if t.get("type") == "income")
    real_expenses = sum(float(t.get("amount", 0)) for t in transactions_list if t.get("type") == "expense")
    balance_real = real_income - real_expenses

    spent_by_category: Dict[str, float] = {}
    for t in transactions_list:
        if t.get("type") != "expense":
            continue
        cid = t.get("category_id")
        if cid is None:
            cid = "__none__"
        else:
            cid = str(cid)
        spent_by_category[cid] = spent_by_category.get(cid, 0) + float(t.get("amount", 0))

    planned_by_category: Dict[str, float] = {}
    for p in plans:
        cid = str(p.get("category_id", ""))
        planned_by_category[cid] = float(p.get("planned_amount") or 0)
    planned_expenses = sum(planned_by_category.values())

    balance_planned = planned_income - planned_expenses
    savings_rate = (balance_real / real_income * 100) if real_income > 0 else 0.0

    category_ids = set(planned_by_category.keys()) | set(spent_by_category.keys())
    category_ids.discard("__none__")

    categories_cache: Dict[str, Dict[str, Any]] = {}
    for cid in category_ids:
        if cid in categories_cache:
            continue
        cat = categories_repo.find_by_id(cid) if hasattr(categories_repo, "find_by_id") else None
        if cat:
            categories_cache[cid] = cat

    categories_payload: List[Dict[str, Any]] = []
    for cid in category_ids:
        cat = categories_cache.get(cid)
        if not cat and cid == "__none__":
            continue
        name = cat.get("name", "Sem categoria") if cat else "Sem categoria"
        planned = planned_by_category.get(cid, 0)
        spent = spent_by_category.get(cid, 0)
        remaining = planned - spent
        progress_percent = (spent / planned * 100) if planned > 0 else 0
        categories_payload.append({
            "category_id": cid,
            "category_name": name,
            "category_color": cat.get("color", "#6b7280") if cat else "#6b7280",
            "category_icon": cat.get("icon", "circle") if cat else "circle",
            "planned": round(planned, 2),
            "spent": round(spent, 2),
            "remaining": round(remaining, 2),
            "progress_percent": round(progress_percent, 2),
        })
    categories_payload.sort(key=lambda x: -x["spent"])

    return {
        "period": {"month": month, "year": year},
        "planned_income": round(planned_income, 2),
        "planned_expenses": round(planned_expenses, 2),
        "real_income": round(real_income, 2),
        "real_expenses": round(real_expenses, 2),
        "balance_real": round(balance_real, 2),
        "balance_planned": round(balance_planned, 2),
        "savings_rate": round(savings_rate, 2),
        "savings_percentage_planned": float(budget_monthly.get("savings_percentage") or 0) if budget_monthly else 0,
        "categories": categories_payload,
    }


def save_planning_month(
    *,
    tenant_id: str,
    month: int,
    year: int,
    planned_income: float,
    savings_percentage: float,
    category_plans: List[Dict[str, Any]],
    budget_repo,
) -> Dict[str, Any]:
    """Persiste budget_monthly e budget_plans para o mês."""
    budget_repo.upsert_monthly(tenant_id, month, year, planned_income, savings_percentage)
    budget_repo.upsert_plans(tenant_id, month, year, category_plans)
    return {"message": "Planejamento salvo com sucesso", "month": month, "year": year}
