# Database Contracts — notifications

## No Dedicated Tables (Current)

Notifications skill currently does not persist any data to the database. Emails are sent immediately without queuing or logging.

---

## Future Tables

### Table: `email_logs` (Planned)

**Purpose:** Track email delivery status for audit and retry

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Email log ID |
| `user_id` | UUID | FK(users.id) ON DELETE CASCADE | Recipient user |
| `recipient` | VARCHAR(255) | NOT NULL | Recipient email |
| `template` | VARCHAR(100) | NOT NULL | Email template name |
| `subject` | VARCHAR(500) | NOT NULL | Email subject |
| `status` | VARCHAR(20) | DEFAULT 'pending' | sent, failed, pending |
| `error_message` | TEXT | NULL | Error if failed |
| `sent_at` | TIMESTAMPTZ | NULL | When sent |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | When queued |

**Indexes:**
- `idx_email_logs_user_id` on `user_id`
- `idx_email_logs_status` on `status`
- `idx_email_logs_created_at` on `created_at`

---

### Table: `email_queue` (Planned)

**Purpose:** Queue emails for async processing with retries

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Queue item ID |
| `user_id` | UUID | FK(users.id) ON DELETE CASCADE | Recipient user |
| `recipient` | VARCHAR(255) | NOT NULL | Recipient email |
| `template` | VARCHAR(100) | NOT NULL | Email template |
| `data` | JSONB | NOT NULL | Template data |
| `status` | VARCHAR(20) | DEFAULT 'pending' | pending, processing, sent, failed |
| `attempts` | INT | DEFAULT 0 | Retry attempts |
| `max_attempts` | INT | DEFAULT 3 | Max retries |
| `scheduled_for` | TIMESTAMPTZ | DEFAULT NOW() | When to send |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Queue time |

**Indexes:**
- `idx_email_queue_status_scheduled` on `(status, scheduled_for)` — Process queue

---

### Table: `notification_preferences` (Future)

**Purpose:** User notification preferences

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `user_id` | UUID | PRIMARY KEY, FK(users.id) | User |
| `email_enabled` | BOOLEAN | DEFAULT TRUE | Email notifications |
| `push_enabled` | BOOLEAN | DEFAULT TRUE | Push notifications |
| `sms_enabled` | BOOLEAN | DEFAULT FALSE | SMS notifications |
| `preferences` | JSONB | DEFAULT '{}' | Granular preferences |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update |

**Preferences JSONB:**
```json
{
  "password_reset": true,
  "welcome_email": true,
  "transaction_alerts": false,
  "weekly_summary": true,
  "marketing": false
}
```

---

## Email Queue Processing

**Worker Query:**
```sql
SELECT * FROM email_queue
WHERE status = 'pending'
  AND scheduled_for <= NOW()
  AND attempts < max_attempts
ORDER BY created_for ASC
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

**Update Status:**
```sql
UPDATE email_queue
SET status = 'sent',
    sent_at = NOW()
WHERE id = :id;
```

**Retry Failed:**
```sql
UPDATE email_queue
SET status = 'pending',
    attempts = attempts + 1,
    scheduled_for = NOW() + INTERVAL '5 minutes' * attempts
WHERE id = :id;
```
