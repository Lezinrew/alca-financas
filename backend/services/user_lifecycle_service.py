"""
Regras centralizadas de inatividade / ciclo de vida da conta.

Referência de atividade: last_activity_at ?? last_login_at ?? created_at
- >= 60 dias sem atividade => status sugerido/automático disabled (exceto contas já disabled com deleted_at)
- >= 45 dias => pending_deletion
- >= 30 dias => inactive
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

INACTIVE_DAYS = 30
PENDING_DELETION_DAYS = 45
DISABLED_DAYS = 60


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def reference_activity_at(user: Dict[str, Any]) -> Optional[datetime]:
    for key in ("last_activity_at", "last_login_at", "created_at"):
        dt = _parse_ts(user.get(key))
        if dt:
            return dt
    return None


def days_since_activity(user: Dict[str, Any]) -> Optional[float]:
    ref = reference_activity_at(user)
    if not ref:
        return None
    delta = datetime.now(timezone.utc) - ref
    return delta.total_seconds() / 86400.0


def derive_status_from_idle(user: Dict[str, Any]) -> Optional[str]:
    """
    Retorna o status automático baseado apenas em ociosidade, ou None se não aplicável.
    Não altera contas com deleted_at preenchido.
    """
    if user.get("deleted_at"):
        return None
    days = days_since_activity(user)
    if days is None:
        return None
    if days >= DISABLED_DAYS:
        return "disabled"
    if days >= PENDING_DELETION_DAYS:
        return "pending_deletion"
    if days >= INACTIVE_DAYS:
        return "inactive"
    return "active"


def should_apply_auto_idle(user: Dict[str, Any]) -> bool:
    """Só aplica transição automática por idle em contas sem encerramento lógico."""
    if user.get("deleted_at"):
        return False
    st = user.get("status")
    if st == "disabled" and user.get("deleted_at"):
        return False
    return True


def classify_idle_bucket(user: Dict[str, Any]) -> str:
    """Rótulo para UI / relatórios: active | inactive | pending_deletion | disabled_idle."""
    days = days_since_activity(user)
    if days is None:
        return "active"
    if days >= DISABLED_DAYS:
        return "disabled_idle"
    if days >= PENDING_DELETION_DAYS:
        return "pending_deletion"
    if days >= INACTIVE_DAYS:
        return "inactive"
    return "active"


def next_status_for_idle(user: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    Retorna (novo_status_ou_None, motivo).
    Escala por ociosidade; se a atividade voltou a ser recente, reativa contas inactive/pending_deletion.
    """
    if not should_apply_auto_idle(user):
        return None, "skip_deleted_or_closed"

    days = days_since_activity(user)
    if days is None:
        return None, "no_reference"

    current = user.get("status") or "active"

    if days >= DISABLED_DAYS:
        if current == "disabled":
            return None, "already"
        return "disabled", "idle_60d"

    if days >= PENDING_DELETION_DAYS:
        if current == "pending_deletion":
            return None, "already"
        return "pending_deletion", "idle_45d"

    if days >= INACTIVE_DAYS:
        if current == "inactive":
            return None, "already"
        return "inactive", "idle_30d"

    # Atividade recente: recupera estados intermediários automáticos
    if current in ("inactive", "pending_deletion"):
        return "active", "recovered_by_activity"

    return None, "within_active_window"
