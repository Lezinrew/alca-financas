# API Contracts — transactions

## GET /api/transactions

**Description:** List user transactions with filtering

**Auth Required:** Yes

**Query Parameters:**
- `month` (int, optional) — Filter by month (1-12)
- `year` (int, optional) — Filter by year (e.g., 2026)
- `type` (string, optional) — Filter by type (`income` | `expense`)
- `status` (string, optional) — Filter by status (`paid` | `pending` | `overdue` | `cancelled`)
- `category_id` (uuid, optional) — Filter by category
- `account_id` (uuid, optional) — Filter by account
- `page` (int, optional, default=1) — Page number
- `limit` (int, optional, default=20, max=100) — Items per page

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "category_id": "uuid",
      "account_id": "uuid",
      "description": "Salary",
      "amount": 5000.00,
      "type": "income",
      "date": "2026-02-15",
      "status": "paid",
      "responsible_person": "Company XYZ",
      "is_recurring": false,
      "installment_info": null,
      "tags": ["salary", "monthly"],
      "notes": "February 2026 salary",
      "created_at": "2026-02-15T10:00:00Z",
      "updated_at": "2026-02-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

---

## POST /api/transactions

**Description:** Create a new transaction

**Auth Required:** Yes

**Request:**
```json
{
  "description": "Grocery shopping",
  "amount": -120.50,
  "type": "expense",
  "category_id": "uuid",
  "account_id": "uuid",
  "date": "2026-02-27",
  "status": "paid",
  "responsible_person": "Supermarket ABC",
  "is_recurring": false,
  "installment_info": null,
  "tags": ["groceries", "food"],
  "notes": "Weekly groceries"
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  ...
}
```

**Errors:**
- `422 Unprocessable Entity` — Validation error (amount sign wrong, invalid date, etc.)

---

## GET /api/transactions/:id

**Description:** Get single transaction

**Auth Required:** Yes

**Response (200 OK):** Same as single transaction object above

**Errors:**
- `404 Not Found` — Transaction not found or belongs to another user

---

## PUT /api/transactions/:id

**Description:** Update transaction

**Auth Required:** Yes

**Request:** Same fields as POST (partial update supported)

**Response (200 OK):** Updated transaction object

---

## DELETE /api/transactions/:id

**Description:** Delete transaction

**Auth Required:** Yes

**Response (204 No Content)**

---

## POST /api/transactions/import

**Description:** Bulk import transactions from CSV

**Auth Required:** Yes

**Rate Limit:** 5 imports per hour

**Request:** `multipart/form-data` with file

**CSV Format:**
```csv
date,description,amount,type,category,account,status
2026-02-01,Salary,5000.00,income,Salary,Main Bank,paid
2026-02-05,Groceries,-150.00,expense,Food,Credit Card,paid
```

**Response (200 OK):**
```json
{
  "imported": 45,
  "errors": [
    {
      "row": 12,
      "error": "Invalid date format"
    }
  ]
}
```
