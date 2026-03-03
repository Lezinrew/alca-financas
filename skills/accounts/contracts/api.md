# API Contracts — accounts

## GET /api/accounts

**Description:** List all user accounts

**Auth Required:** Yes

**Query Parameters:**
- `type` (string, optional) — Filter by account type (`bank` | `credit_card` | `savings` | `investment` | `cash`)
- `active` (boolean, optional) — Filter by active status

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "Main Bank Account",
      "type": "bank",
      "color": "#4CAF50",
      "icon": "bank",
      "balance": 5000.00,
      "currency": "BRL",
      "active": true,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-02-27T14:30:00Z"
    }
  ]
}
```

---

## POST /api/accounts

**Description:** Create a new account

**Auth Required:** Yes

**Request:**
```json
{
  "name": "Credit Card Visa",
  "type": "credit_card",
  "color": "#2196F3",
  "icon": "credit_card",
  "balance": 0.00,
  "currency": "BRL",
  "active": true
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Credit Card Visa",
  "type": "credit_card",
  "color": "#2196F3",
  "icon": "credit_card",
  "balance": 0.00,
  "currency": "BRL",
  "active": true,
  "created_at": "2026-02-27T14:30:00Z",
  "updated_at": "2026-02-27T14:30:00Z"
}
```

**Errors:**
- `422 Unprocessable Entity` — Validation error (invalid type, currency)

---

## GET /api/accounts/:id

**Description:** Get single account details

**Auth Required:** Yes

**Response (200 OK):** Same as single account object above

**Errors:**
- `404 Not Found` — Account not found or belongs to another user

---

## PUT /api/accounts/:id

**Description:** Update account

**Auth Required:** Yes

**Request:** Same fields as POST (partial update supported)

**Response (200 OK):** Updated account object

**Errors:**
- `404 Not Found` — Account not found
- `422 Unprocessable Entity` — Validation error

---

## DELETE /api/accounts/:id

**Description:** Delete account (transactions will have account_id set to NULL)

**Auth Required:** Yes

**Response (204 No Content)**

**Errors:**
- `404 Not Found` — Account not found

---

## POST /api/accounts/:id/import

**Description:** Import transactions to specific account from CSV

**Auth Required:** Yes

**Rate Limit:** 5 imports per hour

**Request:** `multipart/form-data` with file

**Response (200 OK):**
```json
{
  "imported": 25,
  "errors": [
    {
      "row": 5,
      "error": "Invalid date format"
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
