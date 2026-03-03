# API Contracts — categories

## GET /api/categories

**Description:** List all user categories

**Auth Required:** Yes

**Query Parameters:**
- `type` (string, optional) — Filter by type (`income` | `expense`)
- `active` (boolean, optional) — Filter by active status

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "Salary",
      "type": "income",
      "color": "#10B981",
      "icon": "wallet",
      "description": "Monthly salary income",
      "active": true,
      "essential": true,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-02-27T14:30:00Z"
    },
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "Groceries",
      "type": "expense",
      "color": "#F59E0B",
      "icon": "shopping-cart",
      "description": "Food and groceries",
      "active": true,
      "essential": true,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-02-27T14:30:00Z"
    }
  ]
}
```

---

## POST /api/categories

**Description:** Create a new category

**Auth Required:** Yes

**Request:**
```json
{
  "name": "Freelance Income",
  "type": "income",
  "color": "#3B82F6",
  "icon": "briefcase",
  "description": "Income from freelance work",
  "active": true,
  "essential": false
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Freelance Income",
  "type": "income",
  "color": "#3B82F6",
  "icon": "briefcase",
  "description": "Income from freelance work",
  "active": true,
  "essential": false,
  "created_at": "2026-02-27T14:30:00Z",
  "updated_at": "2026-02-27T14:30:00Z"
}
```

**Errors:**
- `422 Unprocessable Entity` — Validation error (invalid type, missing name)

---

## GET /api/categories/:id

**Description:** Get single category details

**Auth Required:** Yes

**Response (200 OK):** Same as single category object above

**Errors:**
- `404 Not Found` — Category not found or belongs to another user

---

## PUT /api/categories/:id

**Description:** Update category

**Auth Required:** Yes

**Request:** Same fields as POST (partial update supported)

**Response (200 OK):** Updated category object

**Errors:**
- `404 Not Found` — Category not found
- `422 Unprocessable Entity` — Validation error

---

## DELETE /api/categories/:id

**Description:** Delete category (transactions will have category_id set to NULL)

**Auth Required:** Yes

**Response (204 No Content)**

**Errors:**
- `404 Not Found` — Category not found

---

## POST /api/categories/import

**Description:** Import categories from file

**Auth Required:** Yes

**Request:** `multipart/form-data` with file

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
  "code": "ERROR_CODE"
}
```
