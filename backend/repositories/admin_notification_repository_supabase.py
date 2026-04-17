"""Idempotência de notificações administrativas."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base_repository_supabase import BaseRepository

logger = logging.getLogger(__name__)


class AdminNotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__("admin_notification_delivery")

    def try_claim_event(
        self, *, event_type: str, subject_user_id: str, payload: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Retorna True se este processo deve enviar (primeira reivindicação).
        Retorna False se o evento já existia (idempotência).
        """
        row = {
            "event_type": event_type,
            "subject_user_id": subject_user_id,
            "payload_json": payload or {},
            "email_sent": False,
        }
        try:
            ex = (
                self.supabase.table(self.table_name)
                .select("id")
                .eq("event_type", event_type)
                .eq("subject_user_id", subject_user_id)
                .limit(1)
                .execute()
            )
            if ex.data:
                return False
            self.supabase.table(self.table_name).insert(row).execute()
            return True
        except Exception as exc:
            err = str(exc).lower()
            if "duplicate" in err or "unique" in err or "23505" in err:
                return False
            logger.error("admin_notification_delivery insert failed: %s", exc)
            raise

    def mark_sent(self, event_type: str, subject_user_id: str) -> None:
        try:
            self.supabase.table(self.table_name).update({"email_sent": True, "last_error": None}).eq(
                "event_type", event_type
            ).eq("subject_user_id", subject_user_id).execute()
        except Exception as exc:
            logger.warning("mark_sent notification: %s", exc)

    def mark_failed(self, event_type: str, subject_user_id: str, error: str) -> None:
        try:
            self.supabase.table(self.table_name).update({"last_error": (error or "")[:2000]}).eq(
                "event_type", event_type
            ).eq("subject_user_id", subject_user_id).execute()
        except Exception as exc:
            logger.warning("mark_failed notification: %s", exc)
