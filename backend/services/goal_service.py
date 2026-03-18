"""
Serviço de Metas (Goals): progresso, restante, aportes.
Domínio: goals = objetivos de longo prazo; separado de transactions e planning.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            return None
    return None


def _months_remaining(target: Optional[date]) -> Optional[float]:
    if not target:
        return None
    today = date.today()
    if target <= today:
        return 0.0
    return max(0, (target.year - today.year) * 12 + (target.month - today.month)) + 1


def enrich_goal(goal: Dict[str, Any]) -> Dict[str, Any]:
    """Adiciona progress_percent, remaining_amount, months_remaining, monthly_needed."""
    target_amount = float(goal.get("target_amount") or 0)
    current_amount = float(goal.get("current_amount") or 0)
    remaining = max(0, target_amount - current_amount)

    progress_percent = (current_amount / target_amount * 100) if target_amount > 0 else 0.0
    target_d = _parse_date(goal.get("target_date"))
    months_rem = _months_remaining(target_d)
    monthly_needed = (remaining / months_rem) if months_rem and months_rem > 0 else None

    out = dict(goal)
    out["progress_percent"] = round(progress_percent, 2)
    out["remaining_amount"] = round(remaining, 2)
    out["months_remaining"] = months_rem
    out["monthly_needed"] = round(monthly_needed, 2) if monthly_needed is not None else None
    return out


def list_goals(
    tenant_id: str,
    user_id: str,
    status: Optional[str],
    goal_repo,
) -> List[Dict[str, Any]]:
    goals = goal_repo.list_goals(tenant_id, user_id, status=status)
    return [enrich_goal(g) for g in goals]


def get_goal(
    goal_id: str,
    tenant_id: str,
    user_id: str,
    goal_repo,
) -> Optional[Dict[str, Any]]:
    goal = goal_repo.get_goal_by_id(goal_id, tenant_id, user_id)
    if not goal:
        return None
    return enrich_goal(goal)


def create_goal(
    tenant_id: str,
    user_id: str,
    data: Dict[str, Any],
    goal_repo,
) -> Dict[str, Any]:
    created = goal_repo.create_goal(tenant_id, user_id, data)
    return enrich_goal(created)


def update_goal(
    goal_id: str,
    tenant_id: str,
    user_id: str,
    data: Dict[str, Any],
    goal_repo,
) -> Optional[Dict[str, Any]]:
    updated = goal_repo.update_goal(goal_id, tenant_id, user_id, data)
    if not updated:
        return None
    return enrich_goal(updated)


def add_contribution(
    goal_id: str,
    tenant_id: str,
    user_id: str,
    amount: float,
    goal_repo,
    date_iso: Optional[str] = None,
    source_type: Optional[str] = None,
    source_reference_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return goal_repo.add_contribution(
        goal_id=goal_id,
        tenant_id=tenant_id,
        user_id=user_id,
        amount=amount,
        date=date_iso,
        source_type=source_type,
        source_reference_id=source_reference_id,
        notes=notes,
    )
