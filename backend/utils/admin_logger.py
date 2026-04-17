"""
Auditoria administrativa — grava em public.admin_audit_logs (Supabase).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import request

logger = logging.getLogger(__name__)


def log_admin_action(
    admin_id: str,
    admin_email: str,
    action: str,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    try:
        from repositories.admin_audit_repository_supabase import AdminAuditRepository

        repo = AdminAuditRepository()
        repo.insert_log(
            actor_user_id=admin_id or None,
            actor_email=admin_email,
            target_user_id=target_id,
            action=action,
            details=details or {},
            ip_address=getattr(request, "remote_addr", None) if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
        )
    except Exception as exc:
        logger.warning("log_admin_action failed: %s", exc)


def get_admin_logs(
    limit: int = 50,
    skip: int = 0,
    action_filter: Optional[str] = None,
    admin_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    try:
        from repositories.admin_audit_repository_supabase import AdminAuditRepository

        rows = AdminAuditRepository().list_logs(
            limit=limit,
            offset=skip,
            action_filter=action_filter,
            admin_filter=admin_filter,
        )
        out: List[Dict[str, Any]] = []
        for log in rows:
            out.append(
                {
                    "id": str(log.get("id")),
                    "admin_id": log.get("actor_user_id"),
                    "admin_email": log.get("actor_email"),
                    "action": log.get("action"),
                    "target_id": log.get("target_user_id"),
                    "details": log.get("details_json") or {},
                    "ip_address": log.get("ip_address"),
                    "timestamp": log.get("created_at"),
                }
            )
        return out
    except Exception as exc:
        logger.warning("get_admin_logs failed: %s", exc)
        return []
