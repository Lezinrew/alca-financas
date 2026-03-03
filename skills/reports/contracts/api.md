# API Contracts — reports

## GET /api/overview

**Description:** Financial overview report for specified period

**Auth Required:** Yes

**Query Parameters:**
- `start_date` (date, required) — Start date (YYYY-MM-DD)
- `end_date` (date, required) — End date (YYYY-MM-DD)
- `account_id` (uuid, optional) — Filter by account
- `category_id` (uuid, optional) — Filter by category

**Response (200 OK):**
```json
{
  "period": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  },
  "summary": {
    "total_income": 96000.00,
    "total_expenses": -42000.00,
    "net": 54000.00,
    "transaction_count": 450
  },
  "by_category": [
    {
      "category": "Salary",
      "type": "income",
      "amount": 96000.00,
      "percentage": 100.0,
      "transaction_count": 12
    },
    {
      "category": "Groceries",
      "type": "expense",
      "amount": -12000.00,
      "percentage": 28.6,
      "transaction_count": 120
    }
  ],
  "by_month": [
    {
      "month": "2026-01",
      "income": 8000.00,
      "expenses": -3500.00,
      "net": 4500.00
    }
  ]
}
```

**Errors:**
- `400 Bad Request` — Invalid date range (end before start, range too large)

---

## GET /api/evolution

**Description:** Evolution report showing trends over time

**Auth Required:** Yes

**Query Parameters:**
- `start_date` (date, required) — Start date
- `end_date` (date, required) — End date
- `granularity` (string, optional) — "day" | "week" | "month" (default: "month")

**Response (200 OK):**
```json
{
  "period": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  },
  "evolution": [
    {
      "period": "2026-01",
      "income": 8000.00,
      "expenses": -3500.00,
      "net": 4500.00,
      "income_growth": 0.0,
      "expense_growth": 0.0
    },
    {
      "period": "2026-02",
      "income": 8500.00,
      "expenses": -3200.00,
      "net": 5300.00,
      "income_growth": 6.25,
      "expense_growth": -8.57
    }
  ],
  "trends": {
    "average_income": 8250.00,
    "average_expenses": -3350.00,
    "income_trend": "increasing",
    "expense_trend": "decreasing"
  }
}
```

---

## GET /api/comparison

**Description:** Comparison report between two periods

**Auth Required:** Yes

**Query Parameters:**
- `period1_start` (date, required) — Period 1 start
- `period1_end` (date, required) — Period 1 end
- `period2_start` (date, required) — Period 2 start
- `period2_end` (date, required) — Period 2 end

**Response (200 OK):**
```json
{
  "period1": {
    "start": "2026-01-01",
    "end": "2026-01-31",
    "income": 8000.00,
    "expenses": -3500.00,
    "net": 4500.00
  },
  "period2": {
    "start": "2025-01-01",
    "end": "2025-01-31",
    "income": 7500.00,
    "expenses": -4000.00,
    "net": 3500.00
  },
  "comparison": {
    "income_diff": 500.00,
    "income_change_pct": 6.67,
    "expenses_diff": 500.00,
    "expense_change_pct": -12.5,
    "net_diff": 1000.00,
    "net_change_pct": 28.57
  },
  "by_category": [
    {
      "category": "Groceries",
      "period1_amount": -1200.00,
      "period2_amount": -1500.00,
      "diff": 300.00,
      "change_pct": -20.0
    }
  ]
}
```

---

## Standard Error Format

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE"
}
```
