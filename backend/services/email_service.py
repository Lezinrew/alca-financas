"""Envio de e-mail com fallback em log estruturado (sem quebrar fluxos)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

logger = logging.getLogger(__name__)


def _parse_recipients(raw: str) -> List[str]:
    return [p.strip() for p in (raw or "").replace(";", ",").split(",") if p.strip()]


def send_email(
    *,
    to_addresses: List[str],
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> None:
    """
    Envia via SMTP se SMTP_HOST estiver definido; caso contrário registra log estruturado.
    """
    to_addresses = [t for t in to_addresses if t]
    if not to_addresses:
        logger.warning("email_service: lista de destinatários vazia, assunto=%s", subject)
        return

    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    mail_from = (os.getenv("EMAIL_FROM") or user or "no-reply@alca.financas").strip()

    if not host:
        logger.info(
            "email_service:fallback_log to=%s subject=%s body_preview=%s",
            to_addresses,
            subject,
            (text_body or "")[:500],
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(to_addresses)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.getenv("SMTP_TLS", "true").strip().lower() in ("1", "true", "yes"):
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(mail_from, to_addresses, msg.as_string())
        logger.info("email_service:sent to=%s subject=%s", to_addresses, subject)
    except Exception as exc:
        logger.error("email_service:smtp_failed to=%s subject=%s err=%s", to_addresses, subject, exc)
        raise
