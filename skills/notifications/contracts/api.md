# API Contracts — notifications

## No Public API Endpoints

The notifications skill is an internal service called by other backend skills. It does not expose public HTTP endpoints.

---

## Internal Service API

### EmailService.send_password_reset_email(email, reset_token, reset_url)

**Description:** Send password reset email with reset link

**Parameters:**
- `email` (string) — Recipient email address
- `reset_token` (string) — Password reset token
- `reset_url` (string) — Full reset URL with token

**Returns:** `bool` — True if sent successfully, False otherwise

**Example:**
```python
from backend.services.email_service import EmailService

success = EmailService.send_password_reset_email(
    email="user@example.com",
    reset_token="secure-token-123",
    reset_url="https://app.example.com/reset-password?token=secure-token-123"
)
```

---

### EmailService.send_welcome_email(email, name) (Future)

**Description:** Send welcome email to new users

**Parameters:**
- `email` (string) — Recipient email address
- `name` (string) — User display name

**Returns:** `bool` — True if sent successfully

---

### EmailService.send_alert_email(email, subject, body) (Future)

**Description:** Send generic alert email

**Parameters:**
- `email` (string) — Recipient email address
- `subject` (string) — Email subject
- `body` (string) — Email body (HTML or plaintext)

**Returns:** `bool` — True if sent successfully

---

## Email Templates

### Password Reset Email

**Subject:** "Reset Your Password"

**Body:**
```
Hi [name],

You requested to reset your password for your Alça Finanças account.

Click the link below to reset your password:
[reset_url]

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Thanks,
The Alça Finanças Team
```

---

## SMTP Configuration

**Environment Variables:**
- `SMTP_HOST` — SMTP server host
- `SMTP_PORT` — SMTP server port (typically 587)
- `SMTP_USER` — SMTP username
- `SMTP_PASSWORD` — SMTP password
- `SMTP_FROM` — From email address
- `SMTP_FROM_NAME` — From display name

---

## Error Handling

**SMTPException:**
- Logged as ERROR
- Email marked as failed
- Retry attempted (future)

**Connection Timeout:**
- Logged as WARNING
- Retry with exponential backoff (future)
