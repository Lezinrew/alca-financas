# Database Contracts — infrastructure-platform

## Row Level Security (RLS)

### Current Implementation

**Status:** RLS enabled but with permissive policies

All tables use `USING (true)` which allows all rows to be read/modified. Security is enforced at application layer by filtering with `user_id` from JWT.

**Backend uses service_role key which bypasses RLS.**

**Example Policy (Current):**
```sql
CREATE POLICY "users_policy" ON users
    FOR ALL USING (true);
```

### Future Implementation (Proper RLS)

**Use Supabase auth.uid() to enforce user isolation:**

```sql
-- Users can only read own data
CREATE POLICY "users_read_policy" ON users
    FOR SELECT USING (id = auth.uid());

-- Users can update own data (except is_admin)
CREATE POLICY "users_update_policy" ON users
    FOR UPDATE USING (id = auth.uid());

-- Transactions: users can only access own
CREATE POLICY "transactions_policy" ON transactions
    FOR ALL USING (user_id = auth.uid());

-- Accounts: users can only access own
CREATE POLICY "accounts_policy" ON accounts
    FOR ALL USING (user_id = auth.uid());

-- Categories: users can only access own
CREATE POLICY "categories_policy" ON categories
    FOR ALL USING (user_id = auth.uid());
```

**Admins Bypass RLS:**
```sql
CREATE POLICY "admin_bypass" ON transactions
    FOR ALL USING (
        auth.uid() IN (
            SELECT id FROM users WHERE is_admin = true
        )
    );
```

---

## Database Migrations

### Migration Process

1. Create migration file: `backend/database/migrations/###_description.sql`
2. Test in development environment
3. Review changes with team
4. Apply to Supabase staging via SQL Editor
5. Verify in staging
6. Apply to production
7. Document changes

### Migration Template
```sql
-- Migration: ###_description
-- Date: 2026-02-27
-- Author: DevOps Team

BEGIN;

-- Add migration SQL here
ALTER TABLE transactions ADD COLUMN new_field VARCHAR(100);

-- Create indexes if needed
CREATE INDEX idx_transactions_new_field ON transactions(new_field);

-- Backfill data if needed
UPDATE transactions SET new_field = 'default' WHERE new_field IS NULL;

COMMIT;
```

### Migration Files

**Location:** `backend/database/migrations/`

**Existing Migrations:**
- `001_initial_schema.sql` — Initial database schema
- `002_add_oauth_states.sql` — OAuth state table
- `003_add_rls_policies.sql` — Initial RLS policies
- `004_improve_rls_security.sql` — Enhanced RLS
- `005_add_missing_account_columns.sql` — Account enhancements

---

## Database Indexes

### Critical Indexes (Existing)

**users:**
- `idx_users_email` on `email` (UNIQUE)

**transactions:**
- `idx_transactions_user_id` on `user_id`
- `idx_transactions_date` on `date`
- `idx_transactions_user_date` on `(user_id, date DESC)`

**accounts:**
- `idx_accounts_user_id` on `user_id`

**categories:**
- `idx_categories_user_id` on `user_id`
- `idx_categories_type` on `type`

### Future Indexes (Planned)

```sql
-- Composite indexes for common queries
CREATE INDEX idx_transactions_user_status ON transactions(user_id, status);
CREATE INDEX idx_transactions_user_category ON transactions(user_id, category_id);
CREATE INDEX idx_transactions_user_account ON transactions(user_id, account_id);

-- Full-text search (future)
CREATE INDEX idx_transactions_description_fts ON transactions
    USING gin(to_tsvector('english', description));
```

---

## Database Backups

### Supabase Automatic Backups
- **Frequency:** Daily
- **Retention:** 7 days (Pro plan)
- **Point-in-Time Recovery:** Available (Pro plan)

### Manual Export
- Users can export own data via `/api/auth/backup/export`
- Admins can export user data via `/api/users/:id/export`

### Backup Strategy (Future)
- Automated daily backups to S3
- Weekly full backups
- Monthly archives (long-term retention)
- Disaster recovery plan documented

---

## Database Constraints

### Foreign Keys with Cascade Delete

```sql
-- User deletion cascades to all user data
ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE;

ALTER TABLE accounts
    ADD CONSTRAINT fk_accounts_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE;

ALTER TABLE categories
    ADD CONSTRAINT fk_categories_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE;
```

### Foreign Keys with SET NULL

```sql
-- Category/account deletion sets to NULL (not cascade)
ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_category
    FOREIGN KEY (category_id) REFERENCES categories(id)
    ON DELETE SET NULL;

ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_account
    FOREIGN KEY (account_id) REFERENCES accounts(id)
    ON DELETE SET NULL;
```

---

## Database Monitoring (Future)

### Metrics to Track
- Connection pool usage
- Query latency (p50, p95, p99)
- Slow query log (queries > 1s)
- Table sizes and growth
- Index usage and efficiency

### Alerts
- Connection pool exhaustion
- Query timeout spikes
- Database disk space > 80%
- Replication lag (if applicable)
