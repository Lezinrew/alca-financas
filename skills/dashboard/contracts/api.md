# API Contracts — dashboard

## GET /api/dashboard

**Description:** Get dashboard data including KPIs, charts, and recent transactions

**Auth Required:** Yes

**Query Parameters:**
- `month` (int, optional) — Filter by month (1-12)
- `year` (int, optional) — Filter by year (e.g., 2026)

**Response (200 OK):**
```json
{
  "kpis": {
    "current_balance": 12500.00,
    "monthly_income": 8000.00,
    "monthly_expenses": -3500.00,
    "pending_transactions": 5,
    "period": "2026-02"
  },
  "charts": {
    "income_vs_expenses": [
      {
        "date": "2026-02-01",
        "income": 1000.00,
        "expenses": -500.00
      }
    ],
    "by_category": [
      {
        "category": "Salary",
        "amount": 8000.00,
        "percentage": 45.0
      },
      {
        "category": "Groceries",
        "amount": -1200.00,
        "percentage": 15.0
      }
    ]
  },
  "recent_transactions": [
    {
      "id": "uuid",
      "description": "Supermarket",
      "amount": -150.00,
      "date": "2026-02-27",
      "category": "Groceries",
      "account": "Credit Card"
    }
  ]
}
```

---

## GET /api/dashboard-advanced

**Description:** Advanced dashboard metrics and analytics

**Auth Required:** Yes

**Query Parameters:**
- `period` (string, optional) — "month" | "quarter" | "year"

**Response (200 OK):**
```json
{
  "trends": {
    "income_growth": 5.2,
    "expense_growth": -2.1,
    "savings_rate": 35.5
  },
  "comparisons": {
    "vs_last_month": {
      "income_diff": 500.00,
      "expense_diff": -200.00
    }
  },
  "top_categories": [
    {
      "category": "Groceries",
      "amount": -1200.00,
      "transaction_count": 15
    }
  ]
}
```

---

## GET /api/dashboard-settings

**Description:** Get dashboard configuration and preferences

**Auth Required:** Yes

**Response (200 OK):**
```json
{
  "widgets_visible": {
    "kpis": true,
    "income_chart": true,
    "category_chart": true,
    "recent_transactions": true
  },
  "default_period": "month",
  "chart_type": "area"
}
```

---

## PUT /api/dashboard-settings

**Description:** Update dashboard configuration

**Auth Required:** Yes

**Request:**
```json
{
  "widgets_visible": {
    "kpis": true,
    "income_chart": false,
    "category_chart": true,
    "recent_transactions": true
  },
  "default_period": "quarter"
}
```

**Response (200 OK):**
```json
{
  "message": "Dashboard settings updated",
  "settings": {...}
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
