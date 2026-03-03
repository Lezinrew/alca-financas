# API Contracts — users-profile

## GET /api/auth/me

**Description:** Get current user profile

**Auth Required:** Yes

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "is_admin": false,
  "profile_picture": "https://example.com/avatar.jpg",
  "settings": {
    "currency": "BRL",
    "theme": "light",
    "language": "pt"
  },
  "auth_providers": ["google"],
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-02-27T14:30:00Z"
}
```

**Errors:**
- `401 Unauthorized` — Missing or invalid auth token

---

## GET /api/auth/settings

**Description:** Get user settings

**Auth Required:** Yes

**Response (200 OK):**
```json
{
  "currency": "BRL",
  "theme": "light",
  "language": "pt"
}
```

---

## PUT /api/auth/settings

**Description:** Update user settings

**Auth Required:** Yes

**Request:**
```json
{
  "currency": "USD",
  "theme": "dark",
  "language": "en"
}
```

**Response (200 OK):**
```json
{
  "message": "Settings updated successfully",
  "settings": {
    "currency": "USD",
    "theme": "dark",
    "language": "en"
  }
}
```

**Errors:**
- `422 Unprocessable Entity` — Invalid currency code or theme/language

---

## GET /api/auth/backup/export

**Description:** Export all user data (transactions, accounts, categories)

**Auth Required:** Yes

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

## POST /api/auth/backup/import

**Description:** Import user data from export file

**Auth Required:** Yes

**Request:** `multipart/form-data` with JSON file

**Response (200 OK):**
```json
{
  "imported": {
    "transactions": 150,
    "accounts": 3,
    "categories": 25
  }
}
```

---

## POST /api/auth/data/clear

**Description:** Clear all user data (transactions, accounts, categories)

**Auth Required:** Yes

**Request:**
```json
{
  "confirmation": "DELETE_MY_DATA"
}
```

**Response (200 OK):**
```json
{
  "message": "All data cleared successfully"
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
