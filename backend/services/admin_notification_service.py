"""
Notificações administrativas (nova conta, aviso de inatividade) com idempotência e auditoria.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import current_app

from repositories.admin_audit_repository_supabase import AdminAuditRepository
from repositories.admin_notification_repository_supabase import AdminNotificationRepository
from repositories.admin_user_repository_supabase import AdminUserRepository
from services.email_service import send_email

logger = logging.getLogger(__name__)

EVENT_NEW_ACCOUNT = "new_user_registration"
EVENT_INACTIVE_WARNING = "inactive_warning"


def _fallback_admin_emails() -> List[str]:
    raw = (current_app.config.get("ADMIN_ALERT_EMAILS") if current_app else None) or ""
    if isinstance(raw, str) and raw.strip():
        return [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    return ["lezinrew@gmail.com"]


def _active_admin_recipient_emails(admin_users: AdminUserRepository) -> List[str]:
    raw = ""
    try:
        raw = (current_app.config.get("ADMIN_ALERT_EMAILS") or "").strip()
    except Exception:
        raw = ""
    extra = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    try:
        rows, _total = admin_users.list_users(page=1, per_page=200, search="", status_filter="active", admins_only=True)
        emails: List[str] = []
        for r in rows:
            em = (r.get("email") or "").strip()
            if em and em not in emails:
                emails.append(em)
        merged = list(dict.fromkeys(extra + emails))
        return merged or _fallback_admin_emails()
    except Exception:
        return extra or _fallback_admin_emails()


def notify_new_account_if_needed(
    *,
    subject_user_id: str,
    name: str,
    email: str,
    status: str,
    tenant_id: Optional[str],
    source: str,
) -> None:
    """
    Dispara e-mail para administradores após criação consistente do perfil em public.users.
    Idempotente por (event_type, subject_user_id). Falhas de e-mail não impedem cadastro.
    """
    notif_repo = AdminNotificationRepository()
    audit_repo = AdminAuditRepository()
    admin_users = AdminUserRepository()

    payload = {
        "name": name,
        "email": email,
        "status": status,
        "tenant_id": tenant_id,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        claimed = notif_repo.try_claim_event(
            event_type=EVENT_NEW_ACCOUNT, subject_user_id=subject_user_id, payload=payload
        )
    except Exception as exc:
        logger.error("notify_new_account: claim failed user=%s err=%s", subject_user_id, exc)
        return

    if not claimed:
        return

    recipients = _active_admin_recipient_emails(admin_users)
    subject = "Nova conta criada no Alça Finanças"
    body = (
        f"Uma nova conta foi criada.\n\n"
        f"Nome: {name}\n"
        f"E-mail: {email}\n"
        f"Data/hora (UTC): {payload['created_at']}\n"
        f"Status inicial: {status}\n"
        f"Tenant / workspace: {tenant_id or 'n/d (será resolvido no primeiro bootstrap)'}\n"
        f"Origem do evento: {source}\n"
        f"ID do utilizador: {subject_user_id}\n"
    )

    try:
        send_email(to_addresses=recipients, subject=subject, text_body=body)
        notif_repo.mark_sent(EVENT_NEW_ACCOUNT, subject_user_id)
    except Exception as exc:
        notif_repo.mark_failed(EVENT_NEW_ACCOUNT, subject_user_id, str(exc))
        logger.error("notify_new_account: send failed user=%s err=%s", subject_user_id, exc)

    try:
        audit_repo.insert_log(
            actor_user_id=None,
            actor_email="system",
            target_user_id=subject_user_id,
            action="new_account_notification",
            details={"recipients": recipients, "payload": payload},
            ip_address=None,
            user_agent=None,
        )
    except Exception as exc:
        logger.warning("notify_new_account: audit log failed: %s", exc)


def send_inactive_warning_emails(
    *,
    target_user: Dict[str, Any],
    actor_user_id: str,
    actor_email: Optional[str],
    days_idle: float,
) -> Dict[str, Any]:
    """Envia aviso ao utilizador final; regista idempotência por utilizador+evento de aviso único recente."""
    notif_repo = AdminNotificationRepository()
    uid = str(target_user["id"])

    payload = {
        "days_idle": round(days_idle, 2),
        "email": target_user.get("email"),
    }

    try:
        claimed = notif_repo.try_claim_event(event_type=EVENT_INACTIVE_WARNING, subject_user_id=uid, payload=payload)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not claimed:
        return {"ok": True, "skipped": True, "reason": "already_sent_or_inflight"}

    to_addr = (target_user.get("email") or "").strip()
    if not to_addr:
        notif_repo.mark_failed(EVENT_INACTIVE_WARNING, uid, "sem_email")
        return {"ok": False, "error": "user_has_no_email"}

    subject = "Aviso de inatividade — Alça Finanças"
    body = (
        f"Olá {target_user.get('name') or ''},\n\n"
        "A sua conta está sem atividade há algum tempo no Alça Finanças.\n"
        "Contas muito tempo sem utilização podem ser marcadas para cancelamento.\n\n"
        "Para manter a conta ativa, entre novamente na aplicação e utilize o serviço.\n"
        "Se já utilizou recentemente, ignore este aviso.\n\n"
        "Obrigado,\nEquipa Alça Finanças\n"
    )

    try:
        send_email(to_addresses=[to_addr], subject=subject, text_body=body)
        notif_repo.mark_sent(EVENT_INACTIVE_WARNING, uid)
    except Exception as exc:
        notif_repo.mark_failed(EVENT_INACTIVE_WARNING, uid, str(exc))
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "skipped": False}
