"""Auditoria administrativa em public.admin_audit_logs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repository_supabase import BaseRepository


class AdminAuditRepository(BaseRepository):
    def __init__(self):
        super().__init__("admin_audit_logs")

    def insert_log(
        self,
        *,
        actor_user_id: Optional[str],
        actor_email: Optional[str],
        target_user_id: Optional[str],
        action: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[str]:
        row = {
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "target_user_id": target_user_id,
            "action": action,
            "details_json": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        res = self.supabase.table(self.table_name).insert(row).execute()
        if res.data and len(res.data) > 0:
            rid = res.data[0].get("id")
            return str(rid) if rid else None
        return None

    def list_logs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        action_filter: Optional[str] = None,
        admin_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            q = self.supabase.table(self.table_name).select("*")
            if action_filter:
                q = q.eq("action", action_filter)
            if admin_filter:
                q = q.eq("actor_user_id", admin_filter)
            q = q.order("created_at", desc=True).range(offset, offset + max(limit, 1) - 1)
            res = q.execute()
            return res.data or []
        except Exception:
            return []
