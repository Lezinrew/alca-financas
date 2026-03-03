# Conventions — Alça Finanças

**Purpose:** System-wide conventions for naming, APIs, database, security, and observability.

**Status:** Active — all new code must follow these conventions.

---

## General Principles

1. **Consistency:** Follow established patterns; deviations require justification
2. **Clarity:** Prefer explicit over clever; favor readability
3. **English:** Code, APIs, logs, and technical docs in English; UI can be i18n
4. **RESTful:** APIs follow REST principles where applicable
5. **Security First:** Security is not optional; validate, sanitize, authorize

---

## Naming Standards

### Skill Names
- **Format:** lowercase with hyphens
- **Length:** 2-3 words maximum
- **Examples:** `authentication`, `users-profile`, `imports-integrations`
- **Avoid:** Technical jargon (e.g., `jwt-handler`); use domain language

### API Routes
- **Base:** `/api/<resource>`
- **Collection:** `/api/<resources>` (plural)
- **Item:** `/api/<resources>/:id` (use UUIDs)
- **Actions:** `/api/<resources>/:id/<action>` (verbs only when not CRUD)
- **Examples:**
  - `GET /api/transactions` — List
  - `POST /api/transactions` — Create
  - `GET /api/transactions/:id` — Read
  - `PUT /api/transactions/:id` — Update
  - `DELETE /api/transactions/:id` — Delete
  - `POST /api/transactions/import` — Special action

### Database Tables
- **Format:** lowercase with underscores, plural
- **Examples:** `users`, `transactions`, `oauth_states`
- **Columns:** lowercase with underscores, singular
- **Timestamps:** Always include `created_at`, `updated_at` (TIMESTAMPTZ)
- **Foreign Keys:** `<table_singular>_id` (e.g., `user_id`, `category_id`)
- **IDs:** Use UUIDs (`UUID PRIMARY KEY DEFAULT uuid_generate_v4()`)

### Python Code
- **Files:** lowercase with underscores (e.g., `transaction_service.py`)
- **Classes:** PascalCase (e.g., `TransactionService`)
- **Functions:** snake_case (e.g., `get_transaction_by_id`)
- **Constants:** UPPERCASE with underscores (e.g., `MAX_IMPORT_SIZE`)
- **Private:** Prefix with `_` (e.g., `_validate_amount`)

### TypeScript/React Code
- **Files:** PascalCase for components (e.g., `TransactionsList.tsx`), camelCase for utils (e.g., `api.ts`)
- **Components:** PascalCase (e.g., `function TransactionsList() {}`)
- **Functions:** camelCase (e.g., `getUserProfile()`)
- **Constants:** UPPERCASE with underscores (e.g., `API_BASE_URL`)
- **Types/Interfaces:** PascalCase (e.g., `Transaction`, `UserProfile`)

### Environment Variables
- **Format:** UPPERCASE with underscores
- **Prefixes:**
  - `VITE_` for frontend env vars (Vite exposes these)
  - `SUPABASE_` for Supabase-related vars
  - No prefix for backend-only vars
- **Examples:** `SECRET_KEY`, `JWT_SECRET`, `SUPABASE_URL`, `VITE_API_URL`

---

## API Standards

### HTTP Methods
- `GET` — Retrieve resource(s), idempotent, no side effects
- `POST` — Create resource, non-idempotent
- `PUT` — Full update of resource, idempotent
- `PATCH` — Partial update (use PUT if full replacement is needed)
- `DELETE` — Remove resource, idempotent

### Status Codes
- **2xx Success:**
  - `200 OK` — Success with body (GET, PUT)
  - `201 Created` — Resource created (POST), include `Location` header
  - `204 No Content` — Success without body (DELETE)
- **4xx Client Error:**
  - `400 Bad Request` — Invalid request syntax
  - `401 Unauthorized` — Missing or invalid authentication
  - `403 Forbidden` — Authenticated but insufficient permissions
  - `404 Not Found` — Resource does not exist
  - `422 Unprocessable Entity` — Validation error (semantic)
  - `429 Too Many Requests` — Rate limit exceeded
- **5xx Server Error:**
  - `500 Internal Server Error` — Unexpected server error
  - `503 Service Unavailable` — Temporary unavailability

### Request/Response Format

#### Request
```json
{
  "field": "value",
  "nested": {
    "key": "value"
  },
  "array": [1, 2, 3]
}
```

- **Content-Type:** `application/json`
- **Validation:** Use Pydantic schemas on backend
- **Sanitization:** Strip whitespace, validate formats (email, UUID, date)

#### Response (Success)
```json
{
  "id": "uuid",
  "data": "value",
  "created_at": "2026-02-27T12:00:00Z"
}
```

#### Response (Error)
```json
{
  "error": "Error message for user",
  "code": "VALIDATION_ERROR",
  "details": {
    "field": "Field-specific error"
  }
}
```

- **Error Codes:** Use semantic codes (e.g., `VALIDATION_ERROR`, `UNAUTHORIZED`, `RESOURCE_NOT_FOUND`)
- **Details:** Provide field-level details for validation errors

### Pagination
For list endpoints returning many items:

**Request:**
- Query params: `?page=1&limit=20` (default: page=1, limit=20, max=100)

**Response:**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

### Filtering
Use query params:
- `?type=expense` — Filter by type
- `?status=paid` — Filter by status
- `?month=2&year=2026` — Filter by date
- `?category_id=uuid` — Filter by foreign key

### Sorting
- `?sort=date` — Sort ascending
- `?sort=-date` — Sort descending (prefix with `-`)

### API Versioning
- **Current:** No versioning (v1 implicit)
- **Future:** Use URL path versioning: `/api/v2/transactions`
- **Deprecation:** Announce 6 months before removing old version

---

## Database Standards

### Schema Design

#### Primary Keys
- Always use UUIDs: `id UUID PRIMARY KEY DEFAULT uuid_generate_v4()`
- Never expose sequential integers (security risk)

#### Foreign Keys
- Always use foreign keys with `ON DELETE CASCADE` or `ON DELETE SET NULL`
- Example: `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`

#### Timestamps
Every table must have:
```sql
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
```

Use trigger to auto-update `updated_at`:
```sql
CREATE TRIGGER update_<table>_updated_at BEFORE UPDATE ON <table>
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### Soft Deletes (Optional)
If needed, add `deleted_at TIMESTAMP WITH TIME ZONE` (NULL = not deleted)

#### JSONB Columns
Use JSONB for semi-structured data:
- `settings JSONB DEFAULT '{}'::jsonb`
- Index frequently queried keys: `CREATE INDEX idx_users_settings_currency ON users((settings->>'currency'))`

#### Enums via CHECK Constraints
```sql
type VARCHAR(20) NOT NULL CHECK (type IN ('income', 'expense'))
status VARCHAR(20) CHECK (status IN ('paid', 'pending', 'overdue', 'cancelled'))
```

#### Indexes
- Index all foreign keys: `CREATE INDEX idx_<table>_<column> ON <table>(<column>)`
- Index frequently filtered columns: `created_at`, `date`, `status`, `active`
- Composite indexes for common queries: `CREATE INDEX idx_transactions_user_date ON transactions(user_id, date DESC)`

### Row Level Security (RLS)

#### Enable RLS
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
```

#### Policy Pattern
```sql
-- Read policy
CREATE POLICY "<table>_read_policy" ON <table>
    FOR SELECT USING (user_id = auth.uid());

-- Insert policy
CREATE POLICY "<table>_insert_policy" ON <table>
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Update policy
CREATE POLICY "<table>_update_policy" ON <table>
    FOR UPDATE USING (user_id = auth.uid());

-- Delete policy
CREATE POLICY "<table>_delete_policy" ON <table>
    FOR DELETE USING (user_id = auth.uid());
```

**Note:** Backend uses `service_role` which bypasses RLS. Application must filter by `user_id` in all queries.

### Migrations
- **Location:** `backend/database/migrations/`
- **Naming:** `###_description.sql` (e.g., `003_add_accounts_table.sql`)
- **Format:** Plain SQL, idempotent where possible
- **Always:** Test on local DB before applying to production
- **Rollback:** Include comments on how to rollback (or create separate rollback file)

---

## Security Standards

### Authentication
- **JWT:** Use short-lived access tokens (15 min) + long-lived refresh tokens (7 days)
- **Storage:** Frontend stores tokens in `localStorage` (consider `httpOnly` cookies for sensitive apps)
- **Validation:** Always validate JWT on backend (`@require_auth` decorator)
- **Expiry:** Check token expiry and refresh automatically

### Authorization
- **User-Level:** Filter all queries by `user_id` from JWT
- **Admin-Level:** Check `is_admin` flag in users table (`@admin_required` decorator)
- **Never trust client:** Always verify permissions on backend

### Input Validation
- **Backend:** Use Pydantic schemas for all incoming data
- **Frontend:** Use form validation libraries (React Hook Form, Zod)
- **Sanitize:** Strip HTML, escape special chars, validate formats

### Output Encoding
- **HTML:** React escapes by default
- **JSON:** Use built-in JSON encoders (no manual string concatenation)
- **SQL:** Use parameterized queries (Supabase client does this automatically)

### Secrets Management
- **Never hardcode:** All secrets in `.env` files
- **Gitignore:** Ensure `.env`, `.env.production`, etc. are in `.gitignore`
- **Production:** Use environment variables from hosting platform
- **Rotation:** Rotate secrets periodically (SECRET_KEY, JWT_SECRET, API keys)

### Rate Limiting
- **Critical endpoints:** Apply rate limits to login, register, password reset
- **Pattern:** `@limiter.limit("5 per minute")` (Flask-Limiter)
- **Gradual:** 5 attempts per minute for auth, 100 requests per minute for general API

### CORS
- **Development:** Allow `localhost:3000`, `localhost:5173`
- **Production:** Whitelist specific origins (e.g., `https://alcahub.cloud`)
- **Never:** Use `*` in production

### Security Headers
Set in production:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### Audit Logging
- **Admin actions:** Log all user CRUD operations
- **Auth events:** Log login attempts, password changes, token refreshes
- **Critical operations:** Log deletes, bulk imports, settings changes
- **Format:** Structured JSON logs with `user_id`, `action`, `timestamp`, `ip_address`

---

## Observability Standards

### Logging

#### Log Levels
- **DEBUG:** Detailed diagnostic info (dev only, never in prod)
- **INFO:** General informational messages (app startup, config loaded)
- **WARNING:** Unexpected but recoverable (deprecated API used, slow query)
- **ERROR:** Errors that need attention (failed API call, validation error)
- **CRITICAL:** System-level failures (DB connection lost, out of memory)

#### What to Log
- **Auth:** Login success/failure, token refresh, logout
- **Business Logic:** Transaction created, import completed, report generated
- **Errors:** Exception type, message, stack trace (sanitize PII)
- **Performance:** Slow queries (>1s), slow API calls (>2s)

#### What NOT to Log
- **Passwords:** Never log passwords, even hashed
- **Tokens:** Do not log JWT tokens or API keys
- **PII:** Avoid logging email, full name, SSN, credit card numbers
- **Sensitive Data:** Financial amounts (aggregate only), account balances

#### Log Format
```python
logger.info(
    "Transaction created",
    extra={
        "user_id": user_id,
        "transaction_id": transaction_id,
        "amount": amount,
        "type": "income",
        "correlation_id": request.headers.get("X-Correlation-ID")
    }
)
```

### Metrics

#### Key Metrics to Track
- **Requests:** Total requests, requests per endpoint, requests per user
- **Latency:** P50, P95, P99 response times
- **Errors:** Error rate (%), 4xx vs 5xx
- **Business:** Transactions created per day, users registered per day
- **Infrastructure:** CPU, memory, disk usage

#### Metric Naming
- **Format:** `<namespace>.<metric_name>.<unit>`
- **Examples:**
  - `alca.api.requests.count`
  - `alca.api.latency.ms`
  - `alca.transactions.created.count`

### Traces

#### Distributed Tracing
- **Correlation ID:** Generate UUID per request, pass in `X-Correlation-ID` header
- **Span Context:** Include service name, operation name, start/end time
- **Propagation:** Pass correlation ID to downstream services

#### What to Trace
- **User Journeys:** Login → dashboard → create transaction
- **Integrations:** CSV import → validation → batch insert
- **Slow Operations:** Queries >1s, API calls >2s

---

## Testing Standards

### Unit Tests
- **Scope:** Test single function/class in isolation
- **Mocking:** Mock external dependencies (DB, API calls)
- **Coverage:** Aim for 80%+ coverage on business logic
- **Naming:** `test_<function>_<scenario>_<expected_result>`
  - Example: `test_create_transaction_invalid_amount_raises_error`

### Integration Tests
- **Scope:** Test multiple components working together
- **Database:** Use test database or in-memory DB
- **Fixtures:** Create reusable test data fixtures
- **Cleanup:** Always clean up test data after test

### End-to-End (E2E) Tests
- **Scope:** Test full user journeys through UI
- **Tools:** Playwright (frontend), pytest (backend)
- **Critical Paths:** Auth flow, transaction CRUD, import CSV
- **Avoid:** Excessive E2E tests (slow, brittle); prefer integration tests

### Test Data
- **Fixtures:** Use realistic but anonymized data
- **Factories:** Use factory pattern for generating test data
- **Cleanup:** Delete test data after test completes
- **Isolation:** Each test should be independent

---

## Backward Compatibility

### API Changes
- **Additive:** Safe to add new fields, endpoints
- **Breaking:** Removing fields, changing field types, changing semantics
- **Deprecation:** Mark as deprecated, log warnings, remove after 6 months

### Database Changes
- **Additive:** Safe to add columns (with defaults), add indexes
- **Breaking:** Removing columns, changing column types
- **Migration Path:** Multi-step migrations for breaking changes:
  1. Add new column
  2. Backfill data
  3. Switch application to use new column
  4. Remove old column (separate migration)

### Code Deprecation
```python
import warnings

@deprecated("Use new_function() instead. Will be removed in v2.0")
def old_function():
    warnings.warn("old_function is deprecated", DeprecationWarning)
    ...
```

---

## Documentation Standards

### Code Comments
- **When:** Explain WHY, not WHAT (code should be self-explanatory)
- **Docstrings:** Use for public functions/classes
- **Format (Python):**
  ```python
  def create_transaction(user_id: str, amount: float, type: str) -> Transaction:
      """
      Create a new transaction for a user.

      Args:
          user_id: UUID of the user
          amount: Transaction amount (positive for income, negative for expense)
          type: Transaction type ('income' or 'expense')

      Returns:
          Created transaction object

      Raises:
          ValidationException: If amount sign doesn't match type
      """
  ```

### Architecture Decision Records (ADRs)
- **When:** Major architectural decisions that affect multiple skills
- **Location:** `skills/ADRs/`
- **Template:** See `0001-skills-architecture.md`

### Skill Documentation
- **Always:** Keep skill docs up to date with code changes
- **Review:** Quarterly review of all skill docs
- **Links:** Use relative links between docs

---

## Performance Standards

### API Response Time
- **Target:** P95 < 500ms for simple queries
- **Acceptable:** P95 < 2s for complex reports
- **Optimization:** Add indexes, optimize queries, cache when appropriate

### Database Queries
- **N+1 Problem:** Always use joins or batch queries
- **Pagination:** Always paginate lists >100 items
- **Indexes:** Ensure all filtered/sorted columns are indexed

### Frontend Performance
- **Bundle Size:** Keep main bundle <500KB gzipped
- **Lazy Loading:** Lazy load routes and heavy components
- **Memoization:** Use React.memo, useMemo, useCallback appropriately

---

## Git Conventions

### Branch Naming
- **Feature:** `feature/<skill>-<description>`
- **Bugfix:** `bugfix/<skill>-<description>`
- **Hotfix:** `hotfix/<description>`
- **Examples:** `feature/transactions-import-csv`, `bugfix/auth-token-refresh`

### Commit Messages
- **Format:** `<type>(<scope>): <description>`
- **Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- **Examples:**
  - `feat(transactions): add CSV import endpoint`
  - `fix(auth): handle expired tokens correctly`
  - `docs(skills): update registry with new routes`

### Pull Requests
- **Title:** Same as commit message format
- **Description:** Include context, what changed, why, testing done
- **Size:** Keep PRs small (<500 lines if possible)
- **Review:** At least one approval required before merge

---

## CI/CD Standards

### Continuous Integration
- **Linting:** Run ESLint (frontend), Flake8 (backend)
- **Tests:** Run unit + integration tests
- **Build:** Ensure build succeeds
- **Security:** Run security scan (Trivy, Snyk)

### Continuous Deployment
- **Stages:** CI → Staging → Production
- **Smoke Tests:** Run basic health checks after deploy
- **Rollback:** Have automated rollback plan
- **Notifications:** Alert team on deployment success/failure

---

## Exceptions

If you need to deviate from these conventions:
1. Document the reason (comment in code or ADR)
2. Get team approval for significant deviations
3. Plan migration path to standard convention

---

**Last Updated:** 2026-02-27
**Next Review:** 2026-05-27 (Quarterly)

---

**Remember:** Conventions exist to make the system predictable and maintainable. Follow them unless you have a strong reason not to.
