# API Contracts — admin-governance

**All endpoints require admin authentication (`is_admin=true` in JWT)**

---

## GET /api/stats

**Description:** Get system statistics

**Auth Required:** Yes (admin only)

**Response (200 OK):**
```json
{
  "users": {
    "total": 150,
    "active_30d": 120,
    "new_this_month": 15
  },
  "transactions": {
    "total": 5000,
    "this_month": 350,
    "total_volume": 1250000.00
  },
  "accounts": {
    "total": 450
  },
  "categories": {
    "total": 380
  },
  "storage_mb": 124,
  "last_updated": "2026-02-27T14:30:00Z"
}
```

**Errors:**
- `403 Forbidden` — User is not admin

---

## GET /api/users

**Description:** List all users (admin view)

**Auth Required:** Yes (admin only)

**Query Parameters:**
- `page` (int, optional) — Page number (default: 1)
- `limit` (int, optional) — Items per page (default: 50)
- `search` (string, optional) — Search by email or name

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "name": "John Doe",
      "is_admin": false,
      "created_at": "2026-01-15T10:00:00Z",
      "transaction_count": 120,
      "last_login": "2026-02-27T09:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 150,
    "pages": 3
  }
}
```

---

## POST /api/users

**Description:** Create new user (admin operation)

**Auth Required:** Yes (admin only)

**Request:**
```json
{
  "email": "newuser@example.com",
  "name": "New User",
  "password": "SecurePass123!",
  "is_admin": false
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "email": "newuser@example.com",
  "name": "New User",
  "is_admin": false,
  "created_at": "2026-02-27T14:30:00Z"
}
```

---

## GET /api/users/:id/details

**Description:** Get detailed user information including statistics

**Auth Required:** Yes (admin only)

**Response (200 OK):**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "is_admin": false,
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-02-27T10:00:00Z"
  },
  "stats": {
    "transaction_count": 120,
    "account_count": 3,
    "category_count": 15,
    "total_income": 48000.00,
    "total_expenses": -21000.00,
    "first_transaction": "2026-01-20",
    "last_transaction": "2026-02-27"
  }
}
```

---

## PUT /api/users/:id

**Description:** Update user (admin operation)

**Auth Required:** Yes (admin only)

**Request:**
```json
{
  "name": "Updated Name",
  "is_admin": false
}
```

**Response (200 OK):** Updated user object

**Note:** Admin can change is_admin flag

---

## DELETE /api/users/:id

**Description:** Delete user and all associated data

**Auth Required:** Yes (admin only)

**Response (204 No Content)**

**Note:** Cascading delete removes transactions, accounts, categories

---

## GET /api/users/:id/export

**Description:** Export all user data (for support/compliance)

**Auth Required:** Yes (admin only)

**Response (200 OK):**
```json
{
  "user": {...},
  "transactions": [...],
  "accounts": [...],
  "categories": [...]
}
```

---

## GET /api/logs

**Description:** Get audit logs (future)

**Auth Required:** Yes (admin only)

**Query Parameters:**
- `start_date` (date, optional)
- `end_date` (date, optional)
- `action` (string, optional) — Filter by action type
- `admin_id` (uuid, optional) — Filter by admin

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "admin_id": "uuid",
      "action": "user_deleted",
      "target_user_id": "uuid",
      "details": {"reason": "user request"},
      "ip_address": "192.168.1.1",
      "created_at": "2026-02-27T14:30:00Z"
    }
  ]
}
```

---

## Standard Error Format

```json
{
  "error": "Human-readable error message",
  "code": "FORBIDDEN"
}
```
