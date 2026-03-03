# API Contracts — infrastructure-platform

## No Application-Level API

Infrastructure-platform does not expose application endpoints. It provides infrastructure configuration that applies to all API endpoints.

---

## Rate Limiting Configuration

### Authentication Endpoints
```
POST /api/auth/login         — 5 requests/minute per IP
POST /api/auth/register      — 3 requests/minute per IP
POST /api/auth/refresh       — 10 requests/minute per user
POST /api/auth/forgot-password — 5 requests/hour per IP
```

### Import Endpoints
```
POST /api/transactions/import — 5 requests/hour per user
POST /api/accounts/:id/import — 5 requests/hour per user
```

### General API
```
All other endpoints — 100 requests/minute per user
```

### Rate Limit Response
```json
HTTP 429 Too Many Requests

{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

---

## CORS Configuration

### Allowed Origins

**Development:**
- `http://localhost:3000`
- `http://localhost:5173`

**Production:**
- `https://alcahub.cloud`
- `https://www.alcahub.cloud`

### Allowed Methods
```
GET, POST, PUT, DELETE, OPTIONS
```

### Allowed Headers
```
Content-Type, Authorization, X-Requested-With
```

### Credentials
```
Access-Control-Allow-Credentials: true
```

---

## Security Headers

### Response Headers (All Endpoints)
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
```

---

## Health Check Endpoints (Future)

### GET /health

**Description:** Application health check

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-27T14:30:00Z",
  "services": {
    "database": "up",
    "redis": "up"
  }
}
```

### GET /metrics (Future: Prometheus)

**Description:** Prometheus metrics endpoint

**Response (200 OK):** Prometheus text format
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/transactions",status="200"} 1234

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 100
http_request_duration_seconds_bucket{le="0.5"} 450
http_request_duration_seconds_bucket{le="1.0"} 800
```

---

## Error Response Format (Global)

All API endpoints follow this error format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "field_name",
    "reason": "validation_failed"
  }
}
```

**Common Error Codes:**
- `UNAUTHORIZED` — 401: Missing or invalid authentication
- `FORBIDDEN` — 403: Insufficient permissions
- `NOT_FOUND` — 404: Resource not found
- `VALIDATION_ERROR` — 422: Input validation failed
- `RATE_LIMIT_EXCEEDED` — 429: Too many requests
- `INTERNAL_ERROR` — 500: Server error

---

## Request/Response Logging

**Format:**
```
[2026-02-27 14:30:00] INFO: GET /api/transactions user_id=abc123 status=200 duration=45ms
[2026-02-27 14:30:05] WARNING: POST /api/auth/login ip=1.2.3.4 status=401 reason=invalid_credentials
[2026-02-27 14:30:10] ERROR: GET /api/dashboard user_id=xyz789 status=500 error=database_timeout
```

**PII Handling:**
- Never log passwords, tokens, or sensitive data
- Hash user IDs in logs (optional for production)
- Redact email addresses
