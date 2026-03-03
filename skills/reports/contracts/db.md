# Database Contracts — reports

## No Dedicated Tables

Reports skill does not own any tables. It queries existing tables to generate reports.

---

## Queried Tables

### `transactions`
Used for:
- Income/expense aggregation
- Period filtering
- Transaction counting
- Evolution calculations

### `categories`
Used for:
- Category names and metadata
- Category-based grouping

### `accounts`
Used for:
- Account-based filtering
- Account names

---

## Key Queries

**Overview Report:**
```sql
-- Summary totals
SELECT
  SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
  SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
  COUNT(*) as transaction_count
FROM transactions
WHERE user_id = :user_id
  AND status = 'paid'
  AND date BETWEEN :start_date AND :end_date;

-- By category
SELECT
  c.name as category,
  t.type,
  SUM(t.amount) as amount,
  COUNT(t.id) as transaction_count,
  (SUM(t.amount) / :total * 100) as percentage
FROM transactions t
JOIN categories c ON t.category_id = c.id
WHERE t.user_id = :user_id
  AND t.status = 'paid'
  AND t.date BETWEEN :start_date AND :end_date
GROUP BY c.id, c.name, t.type
ORDER BY ABS(SUM(t.amount)) DESC;

-- By month
SELECT
  DATE_TRUNC('month', date) as month,
  SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
  SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
FROM transactions
WHERE user_id = :user_id
  AND status = 'paid'
  AND date BETWEEN :start_date AND :end_date
GROUP BY DATE_TRUNC('month', date)
ORDER BY month;
```

**Evolution Report:**
```sql
-- Evolution with growth rates
WITH monthly_totals AS (
  SELECT
    DATE_TRUNC('month', date) as month,
    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
  FROM transactions
  WHERE user_id = :user_id
    AND status = 'paid'
    AND date BETWEEN :start_date AND :end_date
  GROUP BY DATE_TRUNC('month', date)
)
SELECT
  month,
  income,
  expenses,
  income + expenses as net,
  LAG(income) OVER (ORDER BY month) as prev_income,
  LAG(expenses) OVER (ORDER BY month) as prev_expenses,
  ((income - LAG(income) OVER (ORDER BY month)) / LAG(income) OVER (ORDER BY month) * 100) as income_growth,
  ((expenses - LAG(expenses) OVER (ORDER BY month)) / LAG(expenses) OVER (ORDER BY month) * 100) as expense_growth
FROM monthly_totals
ORDER BY month;
```

**Comparison Report:**
```sql
-- Period 1 and Period 2 aggregation
SELECT
  'period1' as period,
  SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
  SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
FROM transactions
WHERE user_id = :user_id
  AND status = 'paid'
  AND date BETWEEN :period1_start AND :period1_end

UNION ALL

SELECT
  'period2' as period,
  SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
  SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses
FROM transactions
WHERE user_id = :user_id
  AND status = 'paid'
  AND date BETWEEN :period2_start AND :period2_end;
```

---

## Performance Considerations

**Indexes Required:**
- `transactions(user_id, date, status)` — Fast period filtering
- `transactions(user_id, category_id)` — Category grouping
- `transactions(user_id, account_id)` — Account filtering

**Query Optimization:**
- Use covering indexes where possible
- Add EXPLAIN ANALYZE for slow queries
- Consider materialized views for common report periods

**Caching Strategy:**
- Cache report results for 1 hour
- Invalidate cache on transaction changes
- Use Redis for cache storage

---

## Future Optimizations

- Pre-aggregated monthly summaries table
- Materialized view for year-to-date totals
- Background job for generating common reports
- Partitioning transactions table by year
