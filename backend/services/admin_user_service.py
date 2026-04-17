"""
Regras de negócio do módulo administrativo de utilizadores (Supabase).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import request
from supabase import create_client

from repositories.admin_audit_repository_supabase import AdminAuditRepository
from repositories.admin_user_repository_supabase import AdminUserRepository
from services.admin_notification_service import send_inactive_warning_emails
from services.user_lifecycle_service import days_since_activity, next_status_for_idle

logger = logging.getLogger(__name__)


class AdminUserService:
    def __init__(self):
        self.repo = AdminUserRepository()
        self.audit = AdminAuditRepository()

    def _actor(self) -> Tuple[str, Optional[str]]:
        uid = getattr(request, "user_id", None)
        if not uid:
            return "", None
        row = self.repo.find_by_id(str(uid))
        return str(uid), (row or {}).get("email")

    def _log(
        self,
        action: str,
        target_user_id: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        actor_id, actor_email = self._actor()
        try:
            self.audit.insert_log(
                actor_user_id=actor_id or None,
                actor_email=actor_email,
                target_user_id=target_user_id,
                action=action,
                details=details or {},
                ip_address=getattr(request, "remote_addr", None),
                user_agent=request.headers.get("User-Agent") if request else None,
            )
        except Exception as exc:
            logger.warning("admin audit insert failed action=%s err=%s", action, exc)

    def sync_idle_statuses(self, *, max_scan: int = 800) -> int:
        """Percorre utilizadores e aplica transições automáticas de status por ociosidade."""
        updated = 0
        offset = 0
        batch = 200
        while offset < max_scan:
            try:
                from database.connection import get_supabase

                res = (
                    get_supabase()
                    .table("users")
                    .select("id,status,last_activity_at,last_login_at,created_at,deleted_at")
                    .is_("deleted_at", "null")
                    .range(offset, offset + batch - 1)
                    .execute()
                )
                rows = res.data or []
            except Exception as exc:
                logger.error("sync_idle_statuses fetch: %s", exc)
                break
            if not rows:
                break
            for row in rows:
                nxt, _reason = next_status_for_idle(row)
                if nxt and nxt != row.get("status"):
                    extra: Dict[str, Any] = {"status": nxt, "updated_at": datetime.now(timezone.utc).isoformat()}
                    if nxt == "pending_deletion" and not row.get("scheduled_deletion_at"):
                        extra["scheduled_deletion_at"] = (
                            datetime.now(timezone.utc) + timedelta(days=15)
                        ).isoformat()
                    if self.repo.update_user(str(row["id"]), extra):
                        updated += 1
            offset += batch
            if len(rows) < batch:
                break
        return updated

    def list_users(
        self,
        *,
        page: int,
        per_page: int,
        search: str,
        status_filter: str,
        admins_only: bool,
    ) -> Dict[str, Any]:
        self.sync_idle_statuses(max_scan=400)
        rows, total = self.repo.list_users(
            page=page,
            per_page=per_page,
            search=search,
            status_filter=status_filter,
            admins_only=admins_only,
        )
        pages = max(1, (total + per_page - 1) // per_page)
        return {"users": rows, "total": total, "page": page, "per_page": per_page, "pages": pages}

    def user_stats(self) -> Dict[str, Any]:
        self.sync_idle_statuses(max_scan=800)
        by_status = self.repo.count_by_status()
        admins = self.repo.count_admins()
        return {
            "total_users": by_status.get("total", 0),
            "active": by_status.get("active", 0),
            "inactive": by_status.get("inactive", 0),
            "pending_deletion": by_status.get("pending_deletion", 0),
            "disabled": by_status.get("disabled", 0),
            "admins": admins,
        }

    def inactive_users(self, *, min_days: int = 30, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.repo.list_inactive_candidates(min_days_idle=min_days, limit=limit)
        out = []
        for r in rows:
            d = days_since_activity(r)
            if d is not None and d >= min_days:
                out.append({**r, "days_since_activity": round(d, 2)})
        return out

    def set_role(self, target_id: str, new_role: str) -> Dict[str, Any]:
        actor_id, _ = self._actor()
        if new_role not in ("admin", "user"):
            return {"ok": False, "error": "invalid_role", "status": 400}

        target = self.repo.find_by_id(target_id)
        if not target:
            return {"ok": False, "error": "user_not_found", "status": 404}

        if new_role == "user" and target.get("role") == "admin":
            admins = self.repo.count_admins()
            if admins <= 1:
                return {"ok": False, "error": "cannot_remove_last_admin", "status": 400}

        ok = self.repo.update_user(target_id, {"role": new_role})
        if not ok:
            return {"ok": False, "error": "update_failed", "status": 500}

        self._log(
            "promote_admin" if new_role == "admin" else "demote_admin",
            target_id,
            {"new_role": new_role},
        )
        return {"ok": True, "user": self.repo.find_by_id(target_id)}

    def set_status(self, target_id: str, new_status: str) -> Dict[str, Any]:
        actor_id, _ = self._actor()
        allowed = {"active", "inactive", "pending_deletion", "disabled"}
        if new_status not in allowed:
            return {"ok": False, "error": "invalid_status", "status": 400}

        target = self.repo.find_by_id(target_id)
        if not target:
            return {"ok": False, "error": "user_not_found", "status": 404}

        if new_status == "disabled" and str(target_id) == str(actor_id):
            return {"ok": False, "error": "cannot_disable_self", "status": 400}

        payload: Dict[str, Any] = {"status": new_status}
        now = datetime.now(timezone.utc).isoformat()
        if new_status == "pending_deletion":
            payload.setdefault(
                "scheduled_deletion_at",
                (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
            )
        if new_status == "disabled":
            payload["deleted_at"] = now
        if new_status == "active":
            payload["deleted_at"] = None
            payload["scheduled_deletion_at"] = None

        ok = self.repo.update_user(target_id, payload)
        if not ok:
            return {"ok": False, "error": "update_failed", "status": 500}

        self._log("status_change", target_id, {"new_status": new_status})
        return {"ok": True, "user": self.repo.find_by_id(target_id)}

    def send_inactive_warning(self, target_id: str) -> Dict[str, Any]:
        actor_id, actor_email = self._actor()
        target = self.repo.find_by_id(target_id)
        if not target:
            return {"ok": False, "error": "user_not_found", "status": 404}
        d = days_since_activity(target)
        if d is None:
            d = 0.0
        res = send_inactive_warning_emails(
            target_user=target,
            actor_user_id=str(actor_id),
            actor_email=actor_email,
            days_idle=float(d),
        )
        if res.get("ok") and not res.get("skipped"):
            self.repo.update_user(
                target_id,
                {"inactive_warning_sent_at": datetime.now(timezone.utc).isoformat()},
            )
            self._log("send_inactive_warning", target_id, {"days_idle": d})
        elif res.get("skipped"):
            self._log("send_inactive_warning_skipped", target_id, {"reason": res.get("reason")})
        return res

    def send_bulk_inactive_warnings(self, user_ids: List[str]) -> Dict[str, Any]:
        results = {"sent": 0, "skipped": 0, "errors": 0}
        for uid in user_ids:
            r = self.send_inactive_warning(uid)
            if r.get("ok") and not r.get("skipped"):
                results["sent"] += 1
            elif r.get("skipped"):
                results["skipped"] += 1
            else:
                results["errors"] += 1
        self._log("bulk_inactive_warning", None, results)
        return {"ok": True, "results": results}

    def deactivate_user(self, target_id: str) -> Dict[str, Any]:
        """Desativação lógica (não apaga linhas nem auth.users)."""
        actor_id, _ = self._actor()
        if str(target_id) == str(actor_id):
            return {"ok": False, "error": "cannot_deactivate_self", "status": 400}
        target = self.repo.find_by_id(target_id)
        if not target:
            return {"ok": False, "error": "user_not_found", "status": 404}
        now = datetime.now(timezone.utc).isoformat()
        ok = self.repo.update_user(
            target_id,
            {"status": "disabled", "deleted_at": now},
        )
        if not ok:
            return {"ok": False, "error": "update_failed", "status": 500}
        self._log("deactivate_user", target_id, {"soft": True})
        return {"ok": True}

    def reactivate_user(self, target_id: str) -> Dict[str, Any]:
        ok = self.repo.update_user(
            target_id,
            {
                "status": "active",
                "deleted_at": None,
                "scheduled_deletion_at": None,
            },
        )
        if not ok:
            return {"ok": False, "error": "update_failed", "status": 500}
        self._log("reactivate_user", target_id, {})
        return {"ok": True}

    def _try_delete_auth_user(self, user_id: str) -> Dict[str, Any]:
        """Apaga auth.users (requer SUPABASE_SERVICE_ROLE_KEY). Ignora se o utilizador não existir no Auth."""
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not key:
            return {"ok": False, "error": "service_role_required", "status": 503}
        try:
            client = create_client(url, key)
            client.auth.admin.delete_user(user_id)
            return {"ok": True}
        except Exception as exc:
            low = str(exc).lower()
            if any(
                s in low
                for s in (
                    "not found",
                    "user not found",
                    "no user found",
                    "user_not_found",
                )
            ):
                return {"ok": True, "skipped": "auth_missing"}
            logger.warning("admin purge: auth delete failed uid=%s err=%s", user_id, exc)
            return {"ok": False, "error": "auth_delete_failed", "status": 502, "detail": str(exc)}

    def purge_user(self, target_id: str, confirm_email: str) -> Dict[str, Any]:
        """
        Exclusão total: remove sessão Auth e apaga public.users (CASCADE nos dados da app).
        confirm_email deve coincidir com o e-mail do alvo (case-insensitive).
        """
        actor_id, _ = self._actor()
        if str(target_id) == str(actor_id):
            return {"ok": False, "error": "cannot_purge_self", "status": 400}

        ce = (confirm_email or "").strip().lower()
        if not ce:
            return {"ok": False, "error": "confirm_email_required", "status": 400}

        target = self.repo.find_by_id(target_id)
        if not target:
            return {"ok": False, "error": "user_not_found", "status": 404}

        email = (target.get("email") or "").strip().lower()
        if ce != email:
            return {"ok": False, "error": "confirm_email_mismatch", "status": 400}

        if target.get("role") == "admin" or bool(target.get("is_admin")):
            if self.repo.count_admins() <= 1:
                return {"ok": False, "error": "cannot_purge_last_admin", "status": 400}

        auth_res = self._try_delete_auth_user(str(target_id))
        if not auth_res.get("ok"):
            return {
                "ok": False,
                "error": auth_res.get("error", "auth_delete_failed"),
                "status": int(auth_res.get("status") or 502),
                "detail": auth_res.get("detail"),
            }

        if not self.repo.delete_user_row(str(target_id)):
            return {"ok": False, "error": "profile_delete_failed", "status": 500}

        self._log(
            "purge_user",
            None,
            {"purged_user_id": str(target_id), "email": email, "auth": auth_res},
        )
        return {"ok": True}

    def legacy_put_user(self, target_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibilidade com PUT antigo (is_blocked / is_admin)."""
        if "is_admin" in body:
            role = "admin" if body.get("is_admin") else "user"
            r = self.set_role(target_id, role)
            if not r.get("ok"):
                return r
        if "is_blocked" in body:
            st = "disabled" if body.get("is_blocked") else "active"
            r = self.set_status(target_id, st)
            if not r.get("ok"):
                return r
        return {"ok": True, "user": self.repo.find_by_id(target_id)}
