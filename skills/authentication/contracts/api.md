# API Contracts — authentication

All authentication endpoints are under `/api/auth` prefix.

---

## POST /api/auth/register

**Description:** Register a new user account

**Auth Required:** No

**Rate Limit:** 3 requests per minute per IP

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe"
}
```

**Response (201 Created):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "is_admin": false,
    "settings": {
      "currency": "BRL",
      "theme": "light",
      "language": "pt"
    }
  }
}
```

**Errors:**
- `400 Bad Request` — Invalid input format
- `409 Conflict` — Email already exists
- `422 Unprocessable Entity` — Validation error (weak password, invalid email)
- `429 Too Many Requests` — Rate limit exceeded

---

## POST /api/auth/login

**Description:** Login with email and password

**Auth Required:** No

**Rate Limit:** 5 attempts per minute per IP

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "is_admin": false,
    "settings": {...}
  }
}
```

**Errors:**
- `401 Unauthorized` — Invalid email or password
- `429 Too Many Requests` — Rate limit exceeded

---

## POST /api/auth/refresh

**Description:** Refresh access token using refresh token

**Auth Required:** Yes (refresh token)

**Request:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Errors:**
- `401 Unauthorized` — Invalid or expired refresh token

---

## GET /api/auth/me

**Description:** Get current authenticated user profile

**Auth Required:** Yes (access token)

**Request Headers:**
```
Authorization: Bearer eyJhbGc...
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "is_admin": false,
  "profile_picture": "https://...",
  "settings": {
    "currency": "BRL",
    "theme": "light",
    "language": "pt"
  },
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Errors:**
- `401 Unauthorized` — Missing or invalid token

---

## POST /api/auth/logout

**Description:** Logout user (client-side token deletion)

**Auth Required:** Yes

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

---

## POST /api/auth/forgot-password

**Description:** Request password reset email

**Auth Required:** No

**Rate Limit:** 5 requests per hour per IP

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "If the email exists, a reset link has been sent"
}
```

**Note:** Returns success even if email doesn't exist (security best practice)

---

## POST /api/auth/reset-password

**Description:** Reset password with token from email

**Auth Required:** No

**Request:**
```json
{
  "token": "secure-reset-token",
  "new_password": "NewSecurePass456!"
}
```

**Response (200 OK):**
```json
{
  "message": "Password reset successfully"
}
```

**Errors:**
- `400 Bad Request` — Invalid or expired token
- `422 Unprocessable Entity` — Weak password

---

## GET /api/auth/google/login

**Description:** Initiate Google OAuth login flow

**Auth Required:** No

**Response:** HTTP 302 Redirect to Google OAuth consent screen

---

## GET /api/auth/google/callback

**Description:** Google OAuth callback (handles OAuth code exchange)

**Auth Required:** No

**Query Parameters:**
- `code` — OAuth authorization code
- `state` — CSRF protection state

**Response:** HTTP 302 Redirect to frontend with tokens in URL fragment

**Errors:**
- `400 Bad Request` — Invalid state or code
- `401 Unauthorized` — OAuth flow failed

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
  "message": "Settings updated",
  "settings": {
    "currency": "USD",
    "theme": "dark",
    "language": "en"
  }
}
```

---

## Standard Error Format

All endpoints return errors in this format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Field-specific error"
  }
}
```

**Common Error Codes:**
- `VALIDATION_ERROR` — Input validation failed
- `UNAUTHORIZED` — Authentication failed
- `FORBIDDEN` — Insufficient permissions
- `RATE_LIMIT_EXCEEDED` — Too many requests
- `INTERNAL_ERROR` — Server error
