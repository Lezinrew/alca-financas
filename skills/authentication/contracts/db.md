# Database Contracts — authentication

## Tables

### Table: `users`

**Purpose:** Stores user accounts and authentication credentials

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY DEFAULT uuid_generate_v4() | Unique user identifier |
| `email` | VARCHAR(255) | UNIQUE NOT NULL | User email (login) |
| `name` | VARCHAR(255) | NOT NULL | User display name |
| `password` | BYTEA | NULL | bcrypt hashed password (NULL for OAuth-only users) |
| `settings` | JSONB | DEFAULT '{"currency": "BRL", "theme": "light", "language": "pt"}'::jsonb | User preferences |
| `auth_providers` | JSONB | DEFAULT '[]'::jsonb | OAuth providers used (e.g., ["google"]) |
| `is_admin` | BOOLEAN | DEFAULT FALSE | Admin flag |
| `profile_picture` | TEXT | NULL | Profile picture URL |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Account creation time |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_users_email` on `email` (UNIQUE) — Fast email lookups for login
- `idx_users_created_at` on `created_at` — Admin queries, analytics

**RLS Policies:**
```sql
-- Users can view own data
CREATE POLICY "users_read_policy" ON users
    FOR SELECT USING (id = auth.uid());

-- Users can update own data (excluding is_admin)
CREATE POLICY "users_update_policy" ON users
    FOR UPDATE USING (id = auth.uid());
```

**Note:** Backend uses `service_role` which bypasses RLS. Application filters by `user_id` from JWT.

**Triggers:**
```sql
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### Table: `oauth_states`

**Purpose:** Temporary storage for OAuth flow state (CSRF protection)

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY DEFAULT uuid_generate_v4() | Unique identifier |
| `state` | VARCHAR(255) | UNIQUE NOT NULL | Random state value |
| `provider` | VARCHAR(50) | NOT NULL | OAuth provider (e.g., "google") |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiry time (10 minutes) |

**Indexes:**
- `idx_oauth_states_state` on `state` (UNIQUE) — Fast state lookups
- `idx_oauth_states_expires_at` on `expires_at` — Cleanup of expired states

**Cleanup:**
Expired states should be cleaned up periodically (cron job or trigger):
```sql
DELETE FROM oauth_states WHERE expires_at < NOW();
```

---

## Password Reset (Future Table)

**Note:** Currently, password reset tokens are not persisted in DB. Consider adding a `password_reset_tokens` table for:
- Auditability (who requested reset when)
- Revocation (user can cancel pending resets)
- Rate limiting (track reset attempts per user)

**Proposed Schema:**
```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Data Integrity Rules

1. **Email Uniqueness:** Email must be unique across all users
2. **Password Required:** Password must be set unless auth_providers is non-empty (OAuth-only users)
3. **Admin Flag Immutable:** `is_admin` should only be modified by admins (enforced in application)
4. **OAuth State Expiry:** OAuth states expire after 10 minutes

---

## Migrations

**Initial Schema:** `backend/database/schema.sql`

**Future Migrations:**
- Add `password_reset_tokens` table
- Add `user_sessions` table for session tracking
- Add `audit_log` table for auth events
