# API Contracts — imports-integrations

## POST /api/transactions/import

**Description:** Bulk import transactions from CSV file

**Auth Required:** Yes

**Rate Limit:** 5 imports per hour

**Request:** `multipart/form-data`
- `file` (file, required) — CSV file
- `account_id` (uuid, optional) — Default account for all transactions

**CSV Format:**
```csv
date,description,amount,type,category,account,status
2026-02-01,Salary,5000.00,income,Salary,Main Bank,paid
2026-02-05,Groceries,-150.00,expense,Food,Credit Card,paid
2026-02-10,Coffee,-4.50,expense,Dining Out,Cash,paid
```

**Required Columns:**
- `date` — Transaction date (YYYY-MM-DD)
- `description` — Transaction description
- `amount` — Transaction amount (negative for expenses)

**Optional Columns:**
- `type` — income | expense (auto-detected from amount sign if missing)
- `category` — Category name (auto-detected if missing)
- `account` — Account name (auto-detected if missing)
- `status` — paid | pending (default: paid)

**Response (200 OK):**
```json
{
  "imported": 145,
  "skipped": 5,
  "errors": [
    {
      "row": 12,
      "error": "Invalid date format",
      "data": {
        "date": "2026/02/15",
        "description": "Store ABC"
      }
    },
    {
      "row": 23,
      "error": "Missing required field: amount",
      "data": {
        "date": "2026-02-20",
        "description": "Payment"
      }
    }
  ],
  "detections": {
    "categories": 89,
    "accounts": 12
  }
}
```

**Errors:**
- `400 Bad Request` — No file uploaded or invalid file type
- `413 Payload Too Large` — File exceeds size limit (10MB)
- `422 Unprocessable Entity` — Invalid CSV format
- `429 Too Many Requests` — Rate limit exceeded

---

## POST /api/accounts/:id/import

**Description:** Import transactions to specific account

**Auth Required:** Yes

**Rate Limit:** 5 imports per hour

**Request:** `multipart/form-data` with CSV file

All transactions will be assigned to the specified account.

**Response:** Same as /api/transactions/import

---

## POST /api/categories/import

**Description:** Import categories from file

**Auth Required:** Yes

**Request:** `multipart/form-data` with CSV file

**CSV Format:**
```csv
name,type,color,icon,essential
Salary,income,#10B981,wallet,true
Groceries,expense,#F59E0B,shopping-cart,true
Entertainment,expense,#8B5CF6,music,false
```

**Response (200 OK):**
```json
{
  "imported": 15,
  "errors": []
}
```

---

## Standard Error Format

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {
    "row": 12,
    "field": "amount"
  }
}
```

---

## CSV Import Best Practices

1. **Use UTF-8 encoding** for special characters
2. **Include header row** with column names
3. **Use consistent date format** (YYYY-MM-DD recommended)
4. **Negative amounts for expenses** or use separate type column
5. **Keep file size under 10MB** (split large files)
6. **Review import summary** for errors and corrections
