# Database Contracts — imports-integrations

## No Dedicated Tables

Imports-integrations skill does not own any tables. It creates records in existing tables.

---

## Tables Modified

### `transactions`
**Operations:**
- Bulk INSERT during CSV import
- Created with detected/provided account_id and category_id

### `accounts`
**Operations:**
- INSERT if new account detected during import
- Used for account name matching

### `categories`
**Operations:**
- INSERT if new category detected during import
- Used for category name matching

---

## Import Flow

1. **Parse CSV** — Read and validate CSV rows
2. **Validate Data** — Check required fields, data types
3. **Detect Accounts** — Match or create accounts based on names
4. **Detect Categories** — Match or create categories using AI
5. **Insert Transactions** — Batch insert valid transactions
6. **Update Balances** — Recalculate account balances
7. **Return Results** — Success count, error details

---

## Auto-Detection Logic

**Account Detection:**
```sql
-- Try to find existing account by name
SELECT id FROM accounts
WHERE user_id = :user_id
  AND LOWER(name) = LOWER(:account_name)
LIMIT 1;

-- If not found, create new account
INSERT INTO accounts (user_id, name, type, balance)
VALUES (:user_id, :account_name, 'bank', 0.00)
RETURNING id;
```

**Category Detection:**
```sql
-- Try to find existing category by name and type
SELECT id FROM categories
WHERE user_id = :user_id
  AND LOWER(name) = LOWER(:category_name)
  AND type = :transaction_type
LIMIT 1;

-- If not found, use AI detection service
-- Then create new category if confidence > 0.8
INSERT INTO categories (user_id, name, type, color, icon)
VALUES (:user_id, :detected_name, :type, :color, :icon)
RETURNING id;
```

---

## Batch Insert Strategy

**Transactional Import (All or Nothing):**
```sql
BEGIN;
INSERT INTO transactions (user_id, category_id, account_id, description, amount, type, date, status)
VALUES
  (:user_id, :category_id1, :account_id1, :desc1, :amt1, :type1, :date1, :status1),
  (:user_id, :category_id2, :account_id2, :desc2, :amt2, :type2, :date2, :status2),
  ...
COMMIT;
```

**Partial Import (Skip Errors):**
- Insert transactions one by one
- Collect errors for failed rows
- Continue processing remaining rows

---

## Deduplication

**Duplicate Detection Query:**
```sql
SELECT id FROM transactions
WHERE user_id = :user_id
  AND description = :description
  AND amount = :amount
  AND date = :date
LIMIT 1;
```

**Deduplication Strategy:**
- Check for duplicates before insert
- Skip duplicate transactions
- Report skipped count to user

---

## Performance Considerations

**Indexes Required:**
- `transactions(user_id, description, amount, date)` — Duplicate detection
- `accounts(user_id, LOWER(name))` — Account matching
- `categories(user_id, LOWER(name), type)` — Category matching

**Optimization:**
- Use batch INSERT for large imports (100 rows per batch)
- Disable foreign key checks during bulk insert (careful!)
- Use connection pooling for parallel processing

---

## Future Tables

**Import History (Planned):**
```sql
CREATE TABLE import_history (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  file_name VARCHAR(255),
  row_count INT,
  imported_count INT,
  error_count INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Import Mappings (Planned):**
```sql
CREATE TABLE import_mappings (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(255),
  column_mappings JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```
