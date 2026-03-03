# Database Contracts — accounts

## Table: `accounts`

**Purpose:** Stores user financial accounts (bank, credit card, savings, etc.)

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY DEFAULT uuid_generate_v4() | Account ID |
| `user_id` | UUID | NOT NULL, FK(users.id) ON DELETE CASCADE | Owner |
| `name` | VARCHAR(255) | NOT NULL | Account name |
| `type` | VARCHAR(50) | NOT NULL, CHECK(type IN ('bank', 'credit_card', 'savings', 'investment', 'cash')) | Account type |
| `color` | VARCHAR(20) | DEFAULT '#4CAF50' | Display color (hex) |
| `icon` | VARCHAR(50) | DEFAULT 'bank' | Icon identifier |
| `balance` | DECIMAL(15, 2) | DEFAULT 0.00 | Current balance |
| `currency` | VARCHAR(3) | DEFAULT 'BRL' | Currency code (ISO 4217) |
| `active` | BOOLEAN | DEFAULT TRUE | Active status |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_accounts_user_id` on `user_id` — Fast user account lookups
- `idx_accounts_type` on `type` — Filter by account type
- `idx_accounts_active` on `active` — Filter active accounts

**RLS Policies:**
```sql
-- Users can view own accounts
CREATE POLICY "accounts_read_policy" ON accounts
    FOR SELECT USING (user_id = auth.uid());

-- Users can manage own accounts
CREATE POLICY "accounts_write_policy" ON accounts
    FOR ALL USING (user_id = auth.uid());
```

**Triggers:**
```sql
CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Data Integrity Rules

1. **Account Name Required:** Name cannot be empty
2. **Valid Account Type:** Must be one of: bank, credit_card, savings, investment, cash
3. **Valid Currency:** Must be valid ISO 4217 code (BRL, USD, EUR, etc.)
4. **Balance Consistency:** Balance should match sum of transactions (recalculated periodically)
5. **User Ownership:** All accounts must belong to a user (cascading delete)

---

## Balance Calculation

Account balance is updated when:
- Transaction is created (balance += transaction.amount)
- Transaction is updated (balance = balance - old_amount + new_amount)
- Transaction is deleted (balance -= transaction.amount)
- Periodic reconciliation runs (recalculate from scratch)

**Reconciliation Query:**
```sql
UPDATE accounts SET balance = (
    SELECT COALESCE(SUM(amount), 0)
    FROM transactions
    WHERE account_id = accounts.id AND status = 'paid'
)
WHERE id = :account_id;
```

---

## Migrations

**Initial Schema:** `backend/database/schema.sql`

**Future Migrations:**
- Add `initial_balance` column (separate from current balance)
- Add `institution` column (bank name)
- Add `account_number` column (last 4 digits for reference)
- Add `shared_with` JSONB column for shared accounts
