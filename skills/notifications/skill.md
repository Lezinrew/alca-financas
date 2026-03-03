# Skill: notifications

**Status:** Active
**Risk Level:** Medium
**Owner:** Platform Team
**Last Updated:** 2026-02-27

---

## Purpose

Send notifications to users via email including password recovery, welcome emails, alerts, and reminders. Provides reliable email delivery with proper templating and tracking.

## Business Value

- **User Communication:** Critical for password resets and system alerts
- **User Engagement:** Welcome emails, reminders increase engagement
- **Security:** Password recovery enables account recovery
- **Impact if Failed:** Users cannot reset passwords; no system alerts

## Boundaries

### In Scope
- Email sending via SMTP
- Email templates (HTML + plaintext)
- Password reset emails
- Welcome emails (future)
- System alerts (future)
- Email delivery tracking (future)

### Out of Scope
- Push notifications → Future feature
- SMS notifications → Future feature
- In-app notifications → Future feature
- Marketing emails → Future feature

## Core Responsibilities

1. **Send transactional emails** (password reset, welcome)
2. **Render email templates** with user data
3. **Handle SMTP connection** and retries
4. **Track email delivery** (future)
5. **Manage email queue** (future for high volume)

## User Journeys

### Journey 1: Password Reset Email
1. User requests password reset
2. Authentication service calls email service
3. Email service renders reset template
4. Email service sends via SMTP
5. User receives email with reset link

### Journey 2: Welcome Email (Future)
1. User registers account
2. Authentication service calls email service
3. Email service sends welcome email
4. User receives onboarding email

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| SMTP server down | Critical: No emails sent | Queue emails for retry; use backup SMTP |
| Invalid email address | Low: Delivery fails | Validate email format before sending |
| Email marked as spam | Medium: User doesn't receive | Use verified sender domain; proper SPF/DKIM |
| Rate limit exceeded | Medium: Delayed emails | Implement email queue with rate limiting |

## Dependencies

### Upstream
- `authentication` — Password recovery emails
- `users-profile` — User email addresses

### Downstream
- None (leaf service)

## Code Map

### Backend
- **Services:** `backend/services/email_service.py`
- **Templates:** `backend/templates/emails/` (future)

### Frontend
- No frontend components (backend service only)

### Database
- No dedicated tables (future: email_logs)

## Security Considerations

- Never log email content (may contain sensitive data)
- Use TLS for SMTP connection
- Validate email addresses before sending
- Rate limit to prevent abuse
- Use environment variables for SMTP credentials

## Observability Plan

### Logs
- Email sent (recipient, template, success/failure)
- SMTP connection errors
- Delivery failures

### Metrics
- `emails.sent.count` — Total emails sent
- `emails.failed.count` — Failed deliveries
- `emails.delivery_time.ms` — Email send latency

## Future Evolution

### v1.0 (Current)
- Password reset emails
- Basic SMTP sending

### v2.0 (Planned)
- Welcome emails
- Email templates system
- Email delivery tracking
- Email queue with retries

### v3.0 (Vision)
- Push notifications
- SMS notifications
- In-app notifications
- User notification preferences
- Notification center

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
