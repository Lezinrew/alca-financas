# Domain Events — authentication

**Note:** Currently, the system does not have an event bus. Events listed here are **future considerations** for when event-driven architecture is adopted.

---

## Events Emitted

### Event: `auth.user.registered`

**When:** New user successfully registers

**Payload:**
```json
{
  "event_id": "uuid",
  "event_type": "auth.user.registered",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid",
  "data": {
    "email": "user@example.com",
    "name": "John Doe",
    "auth_method": "email_password | google_oauth"
  }
}
```

**Potential Consumers:**
- `notifications` — Send welcome email
- `analytics` — Track user acquisition
- `admin-governance` — Log registration event

**Idempotency:** Use `event_id` for deduplication

---

### Event: `auth.user.logged_in`

**When:** User successfully logs in

**Payload:**
```json
{
  "event_id": "uuid",
  "event_type": "auth.user.logged_in",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid",
  "data": {
    "auth_method": "email_password | google_oauth",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Potential Consumers:**
- `admin-governance` — Audit log
- `notifications` — Send login alert (if from new device)
- `analytics` — Track engagement

---

### Event: `auth.password.reset_requested`

**When:** User requests password reset

**Payload:**
```json
{
  "event_id": "uuid",
  "event_type": "auth.password.reset_requested",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid",
  "data": {
    "email": "user@example.com",
    "ip_address": "192.168.1.1"
  }
}
```

**Consumers:**
- `notifications` — Send reset email
- `admin-governance` — Log for security monitoring

---

### Event: `auth.password.reset_completed`

**When:** User successfully resets password

**Payload:**
```json
{
  "event_id": "uuid",
  "event_type": "auth.password.reset_completed",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid",
  "data": {
    "ip_address": "192.168.1.1"
  }
}
```

**Consumers:**
- `notifications` — Send confirmation email
- `admin-governance` — Audit log

---

### Event: `auth.token.refreshed`

**When:** User refreshes access token

**Payload:**
```json
{
  "event_id": "uuid",
  "event_type": "auth.token.refreshed",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid"
}
```

**Consumers:**
- `admin-governance` — Session tracking

---

## Events Consumed

Currently, authentication does not consume events from other skills.

**Future:** May consume events like:
- `users-profile.updated` — Invalidate cached user data in tokens
- `admin-governance.user.disabled` — Revoke user sessions

---

## Event Processing Guarantees

**Delivery:** At-least-once (idempotent consumers required)

**Ordering:** No ordering guarantees across events; use timestamps for reconciliation

**Failure Handling:**
- Retry failed event processing 3 times with exponential backoff
- Dead-letter queue (DLQ) for failed events after max retries
- Alert on-call engineer if DLQ has items

---

## Future Implementation

When adopting event-driven architecture:
1. Use event bus (e.g., RabbitMQ, Kafka, AWS SNS/SQS)
2. Publish events asynchronously (non-blocking)
3. Include `correlation_id` in all events for tracing
4. Version events (e.g., `auth.user.registered.v1`)
