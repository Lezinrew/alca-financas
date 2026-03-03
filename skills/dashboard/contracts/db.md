# Database Contracts — dashboard

## No Dedicated Tables

Dashboard skill does not own any tables. It queries existing tables to aggregate data.

---

## Queried Tables

### `transactions`
Used for:
- Income/expense aggregation
- Recent transactions list
- Category breakdown
- Period filtering

### `accounts`
Used for:
- Current balance calculation (sum of all account balances)
- Account-specific filtering

### `categories`
Used for:
- Category names and metadata
- Category breakdown charts

---

## Key Queries

**KPIs Calculation:**
```sql
-- Current balance (sum of all account balances)
SELECT SUM(balance) as current_balance
FROM accounts
WHERE user_id = :user_id AND active = true;

-- Monthly income
SELECT SUM(amount) as monthly_income
FROM transactions
WHERE user_id = :user_id
  AND type = 'income'
  AND status = 'paid'
  AND date >= :start_date
  AND date <= :end_date;

-- Monthly expenses
SELECT SUM(amount) as monthly_expenses
FROM transactions
WHERE user_id = :user_id
  AND type = 'expense'
  AND status = 'paid'
  AND date >= :start_date
  AND date <= :end_date;

-- Pending transactions count
SELECT COUNT(*) as pending_count
FROM transactions
WHERE user_id = :user_id
  AND status = 'pending';
```

**Income vs Expenses Chart:**
```sql
SELECT
  DATE(date) as date,
  SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
  SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
FROM transactions
WHERE user_id = :user_id
  AND status = 'paid'
  AND date >= :start_date
  AND date <= :end_date
GROUP BY DATE(date)
ORDER BY date;
```

**Category Breakdown:**
```sql
SELECT
  c.name as category,
  SUM(t.amount) as amount,
  COUNT(t.id) as transaction_count
FROM transactions t
JOIN categories c ON t.category_id = c.id
WHERE t.user_id = :user_id
  AND t.status = 'paid'
  AND t.date >= :start_date
  AND t.date <= :end_date
GROUP BY c.id, c.name
ORDER BY ABS(SUM(t.amount)) DESC;
```

**Recent Transactions:**
```sql
SELECT
  t.id,
  t.description,
  t.amount,
  t.date,
  c.name as category,
  a.name as account
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
LEFT JOIN accounts a ON t.account_id = a.id
WHERE t.user_id = :user_id
ORDER BY t.date DESC, t.created_at DESC
LIMIT 10;
```

---

## Performance Considerations

**Indexes Required:**
- `transactions(user_id, date DESC)` — Fast period filtering
- `transactions(user_id, status)` — Pending count
- `transactions(user_id, type, status)` — Income/expense aggregation
- `accounts(user_id, active)` — Balance calculation

**Caching Strategy:**
- Cache dashboard data for 5 minutes
- Invalidate cache on transaction CRUD
- Use Redis for cache storage

---

## Future Optimizations

- Materialized view for monthly aggregates
- Denormalized KPI table updated via triggers
- Background job for pre-calculating common periods
