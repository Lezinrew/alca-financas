"""Consultas administrativas sobre public.users (service_role)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database.connection import get_supabase

logger = logging.getLogger(__name__)


def _escape_ilike(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


class AdminUserRepository:
    def __init__(self):
        self.supabase = get_supabase()
        self.table = "users"

    def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            res = self.supabase.table(self.table).select("*").eq("id", user_id).limit(1).execute()
            if res.data:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("admin find_by_id: %s", exc)
            return None

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            res = (
                self.supabase.table(self.table)
                .select("*")
                .eq("email", email.strip().lower())
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
            return None
        except Exception as exc:
            logger.error("admin find_by_email: %s", exc)
            return None

    def _base_select(self):
        return self.supabase.table(self.table).select(
            "id,email,name,role,status,is_admin,created_at,updated_at,"
            "last_login_at,last_activity_at,inactive_warning_sent_at,"
            "scheduled_deletion_at,deleted_at,auth_providers,settings",
            count="exact",
        )

    def list_users(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str = "",
        status_filter: str = "all",
        admins_only: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        per_page = max(1, min(per_page, 100))
        page = max(1, page)
        offset = (page - 1) * per_page

        q = self._base_select()

        if admins_only:
            q = q.eq("role", "admin")

        if status_filter and status_filter != "all":
            q = q.eq("status", status_filter)

        if search and search.strip():
            s = _escape_ilike(search.strip())
            pattern = f"%{s}%"
            q = q.or_(f"name.ilike.{pattern},email.ilike.{pattern}")

        q = q.order("created_at", desc=True).range(offset, offset + per_page - 1)
        try:
            res = q.execute()
            rows = res.data or []
            total = getattr(res, "count", None) or len(rows)
            return rows, int(total)
        except Exception as exc:
            logger.error("admin list_users: %s", exc)
            return [], 0

    def count_by_status(self) -> Dict[str, int]:
        out = {"active": 0, "inactive": 0, "pending_deletion": 0, "disabled": 0, "total": 0}
        try:
            res = (
                self.supabase.table(self.table)
                .select("status", count="exact")
                .execute()
            )
            out["total"] = int(getattr(res, "count", 0) or 0)
        except Exception as exc:
            logger.error("count_by_status total: %s", exc)

        for st in ("active", "inactive", "pending_deletion", "disabled"):
            try:
                r = (
                    self.supabase.table(self.table)
                    .select("id", count="exact")
                    .eq("status", st)
                    .execute()
                )
                out[st] = int(getattr(r, "count", 0) or 0)
            except Exception as exc:
                logger.error("count_by_status %s: %s", st, exc)
        return out

    def count_admins(self) -> int:
        try:
            r = (
                self.supabase.table(self.table)
                .select("id", count="exact")
                .eq("role", "admin")
                .is_("deleted_at", "null")
                .execute()
            )
            return int(getattr(r, "count", 0) or 0)
        except Exception as exc:
            logger.error("count_admins: %s", exc)
            return 0

    def count_created_since(self, since_iso: str) -> int:
        try:
            r = (
                self.supabase.table(self.table)
                .select("id", count="exact")
                .gte("created_at", since_iso)
                .execute()
            )
            return int(getattr(r, "count", 0) or 0)
        except Exception as exc:
            logger.error("count_created_since: %s", exc)
            return 0

    def list_inactive_candidates(self, *, min_days_idle: int = 30, limit: int = 500) -> List[Dict[str, Any]]:
        """Usuários com referência de atividade anterior a min_days_idle (aproximação em Python)."""
        try:
            res = (
                self.supabase.table(self.table)
                .select(
                    "id,email,name,role,status,last_login_at,last_activity_at,created_at,"
                    "inactive_warning_sent_at,scheduled_deletion_at"
                )
                .is_("deleted_at", "null")
                .neq("status", "disabled")
                .limit(limit)
                .execute()
            )
            rows = res.data or []
        except Exception as exc:
            logger.error("list_inactive_candidates: %s", exc)
            return []

        cutoff = datetime.now(timezone.utc).timestamp() - min_days_idle * 86400
        out: List[Dict[str, Any]] = []

        def _ts(row: Dict[str, Any], key: str) -> Optional[float]:
            v = row.get(key)
            if not v:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            try:
                return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except Exception:
                return None

        for row in rows:
            ref = _ts(row, "last_activity_at") or _ts(row, "last_login_at") or _ts(row, "created_at")
            if ref is not None and ref < cutoff:
                out.append(row)
        return out

    def update_user(self, user_id: str, data: Dict[str, Any]) -> bool:
        try:
            payload = dict(data)
            if "updated_at" not in payload:
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "role" in payload:
                payload["is_admin"] = payload["role"] == "admin"
            res = self.supabase.table(self.table).update(payload).eq("id", user_id).execute()
            return bool(res.data)
        except Exception as exc:
            logger.error("admin update_user %s: %s", user_id, exc)
            return False

    def delete_user_row(self, user_id: str) -> bool:
        """Remove a linha em public.users (CASCADE apaga dados da app ligados a este id)."""
        try:
            res = self.supabase.table(self.table).delete().eq("id", user_id).execute()
            rows = res.data or []
            return len(rows) > 0
        except Exception as exc:
            logger.error("admin delete_user_row %s: %s", user_id, exc)
            return False
