# Database Contracts — admin-governance

## No Dedicated Tables (Current)

Admin-governance skill reads from existing tables for admin operations.

---

## Tables Read

### `users`
**Operations:**
- SELECT all users for user list
- SELECT user by ID for details
- INSERT for admin user creation
- UPDATE for admin user modification
- DELETE for admin user deletion

**Admin-Specific Queries:**
```sql
-- List all users with stats
SELECT
  u.id,
  u.email,
  u.name,
  u.is_admin,
  u.created_at,
  COUNT(DISTINCT t.id) as transaction_count,
  COUNT(DISTINCT a.id) as account_count
FROM users u
LEFT JOIN transactions t ON u.id = t.user_id
LEFT JOIN accounts a ON u.id = a.user_id
GROUP BY u.id
ORDER BY u.created_at DESC;

-- System stats
SELECT
  COUNT(*) as total_users,
  COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as active_30d
FROM users;
```

### `transactions`
**Operations:**
- SELECT for user statistics
- SELECT for system statistics

### `accounts`
**Operations:**
- SELECT for user statistics

### `categories`
**Operations:**
- SELECT for user statistics

---

## Future Tables

### Table: `audit_logs` (Planned)

**Purpose:** Track all admin actions for compliance and security

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Log entry ID |
| `admin_id` | UUID | NOT NULL, FK(users.id) | Admin who performed action |
| `action` | VARCHAR(100) | NOT NULL | Action type (user_created, user_deleted, etc.) |
| `target_type` | VARCHAR(50) | NULL | Target entity type (user, transaction, etc.) |
| `target_id` | UUID | NULL | Target entity ID |
| `details` | JSONB | NULL | Additional details |
| `ip_address` | INET | NULL | Admin IP address |
| `user_agent` | TEXT | NULL | Admin browser/client |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | When action occurred |

**Indexes:**
- `idx_audit_logs_admin_id` on `admin_id` — Filter by admin
- `idx_audit_logs_action` on `action` — Filter by action type
- `idx_audit_logs_created_at` on `created_at DESC` — Time-based queries
- `idx_audit_logs_target` on `(target_type, target_id)` — Entity history

**Audit Actions:**
- `user_created` — Admin created user
- `user_updated` — Admin updated user
- `user_deleted` — Admin deleted user
- `data_exported` — Admin exported user data
- `settings_updated` — Admin changed system settings
- `admin_login` — Admin logged in
- `admin_access_denied` — Non-admin tried admin endpoint

---

### Table: `system_settings` (Planned)

**Purpose:** Store global system configuration

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `key` | VARCHAR(100) | PRIMARY KEY | Setting key |
| `value` | JSONB | NOT NULL | Setting value |
| `description` | TEXT | NULL | Setting description |
| `updated_by` | UUID | FK(users.id) | Last admin who updated |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update time |

**Example Settings:**
```sql
INSERT INTO system_settings VALUES
  ('maintenance_mode', 'false', 'Enable maintenance mode'),
  ('max_upload_size_mb', '10', 'Max file upload size'),
  ('rate_limit_requests_per_minute', '60', 'Global rate limit');
```

---

## Admin Access Control

**Admin Check:**
```sql
SELECT is_admin FROM users WHERE id = :user_id;
```

**Grant Admin:**
```sql
UPDATE users
SET is_admin = true,
    updated_at = NOW()
WHERE id = :user_id;
```

**Note:** Admin flag should only be set via direct database access or super admin, never via API

---

## User Deletion (Cascading)

**Delete User and All Data:**
```sql
BEGIN;

-- Delete transactions (cascades from user_id)
DELETE FROM transactions WHERE user_id = :user_id;

-- Delete accounts (cascades from user_id)
DELETE FROM accounts WHERE user_id = :user_id;

-- Delete categories (cascades from user_id)
DELETE FROM categories WHERE user_id = :user_id;

-- Delete user
DELETE FROM users WHERE id = :user_id;

COMMIT;
```

**Foreign Keys Handle Cascade:**
```sql
-- All tables should have ON DELETE CASCADE for user_id
ALTER TABLE transactions
  ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id)
  REFERENCES users(id)
  ON DELETE CASCADE;
```

---

## Performance Considerations

**Indexes for Admin Queries:**
- `users(created_at DESC)` — Recent users
- `users(LOWER(email))` — Email search
- `users(LOWER(name))` — Name search

**Stats Caching:**
- Cache system stats for 5 minutes
- Invalidate on user CRUD operations
