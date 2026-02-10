"""
Serviço de e-mail para reset de senha.
Em produção: configurar SMTP (SendGrid, etc.) e implementar send_reset_link.
Em dev: loga o link no console para copiar e testar.
"""
import os
import logging

logger = logging.getLogger(__name__)


def send_reset_link(email: str, reset_url: str) -> bool:
    """
    Envia e-mail com link de redefinição de senha.
    Retorna True se enviado (ou em dev, se logado com sucesso).
    """
    smtp_configured = bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_USER'))
    if smtp_configured:
        return _send_via_smtp(email, reset_url)
    # Modo dev: logar link no console
    logger.warning("SMTP não configurado. Modo dev: link de reset no console.")
    print("\n" + "=" * 60)
    print("[DEV] Link de redefinição de senha (não enviado por e-mail):")
    print(reset_url)
    print("=" * 60 + "\n")
    return True


def _send_via_smtp(email: str, reset_url: str) -> bool:
    """Envia e-mail via SMTP quando configurado."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Alça Finanças - Redefinir senha'
        msg['From'] = os.getenv('SMTP_FROM', os.getenv('SMTP_USER', ''))
        msg['To'] = email
        text = f"Use o link abaixo para redefinir sua senha (válido por 1 hora):\n\n{reset_url}"
        html = f"<p>Use o link abaixo para redefinir sua senha (válido por 1 hora):</p><p><a href=\"{reset_url}\">{reset_url}</a></p>"
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT', 587))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USER', ''), os.getenv('SMTP_PASSWORD', ''))
            server.send_message(msg)
        return True
    except Exception as e:
        logger.exception("Erro ao enviar e-mail de reset: %s", e)
        return False
