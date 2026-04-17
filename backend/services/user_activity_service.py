"""Atualização sustentável de last_login_at / last_activity_at."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from repositories.user_repository_supabase import UserRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_login(user_repo: "UserRepository", user_id: str) -> None:
    user_repo.update(
        user_id,
        {
            "last_login_at": _now_iso(),
            "last_activity_at": _now_iso(),
        },
    )


def touch_activity_if_stale(
    user_repo: "UserRepository",
    user_id: str,
    *,
    min_interval_seconds: int = 300,
) -> bool:
    """
    Atualiza last_activity_at se o último registro for mais antigo que min_interval_seconds.
    Retorna True se gravou.
    """
    user = user_repo.find_by_id(user_id)
    if not user:
        return False
    last = user.get("last_activity_at") or user.get("last_login_at")
    if not last:
        return user_repo.update(user_id, {"last_activity_at": _now_iso()})
    try:
        s = str(last).replace("Z", "+00:00")
        prev = datetime.fromisoformat(s)
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=timezone.utc)
    except Exception:
        return user_repo.update(user_id, {"last_activity_at": _now_iso()})

    delta = datetime.now(timezone.utc) - prev
    if delta.total_seconds() < min_interval_seconds:
        return False
    return user_repo.update(user_id, {"last_activity_at": _now_iso()})
