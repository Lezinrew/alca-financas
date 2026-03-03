# Test Strategy — authentication

Comprehensive testing approach for the authentication skill.

---

## Test Pyramid

```
        /\
       /  \
      / E2E \ ────── 10% (Critical user journeys)
     /______\
    /        \
   / Integr.  \ ──── 30% (API + DB + Services)
  /____________\
 /              \
/     Unit       \ ── 60% (Business logic, helpers)
/__________________\
```

---

## Unit Tests

**Scope:** Test individual functions in isolation (no DB, no network)

**Location:** `backend/tests/unit/test_auth_*.py`

### Coverage

#### `utils/auth_utils.py`

| Function | Test Cases | Mocking |
|----------|------------|---------|
| `generate_access_token(user_id, email, is_admin)` | Valid input, JWT structure, claims, expiry | None |
| `generate_refresh_token(user_id)` | Valid input, JWT structure, expiry | None |
| `verify_token(token, token_type)` | Valid token, expired token, invalid signature, wrong type | None |
| `hash_password(password)` | Bcrypt hash format, salt randomness | None |
| `verify_password(password, hash)` | Correct password, incorrect password, invalid hash | None |
| `require_auth(f)` | Valid token, missing token, invalid token, expired token | Request mock |

#### `schemas/auth_schemas.py`

| Schema | Test Cases |
|--------|------------|
| `UserRegisterSchema` | Valid input, invalid email, weak password, missing fields |
| `UserLoginSchema` | Valid input, invalid email, missing fields |
| `PasswordResetSchema` | Valid input, weak new password |

#### `services/user_service.py`

| Method | Test Cases | Mocking |
|--------|------------|---------|
| `create_user(email, name, password)` | Valid input, email exists | UserRepository |
| `get_user_by_email(email)` | User exists, user not found | UserRepository |
| `get_user_by_id(user_id)` | User exists, user not found | UserRepository |
| `update_user_settings(user_id, settings)` | Valid settings, invalid JSON | UserRepository |

### Example Unit Test

```python
def test_generate_access_token():
    """Test JWT access token generation"""
    user_id = "test-uuid"
    email = "test@example.com"
    is_admin = False

    token = generate_access_token(user_id, email, is_admin)

    # Decode token (without verification for testing)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["is_admin"] == is_admin
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
```

---

## Integration Tests

**Scope:** Test multiple components together (API + DB + Services)

**Location:** `backend/tests/integration/test_auth_api.py`

### Coverage

#### Registration Endpoint

- [ ] POST /api/auth/register with valid data → 201 Created
- [ ] POST /api/auth/register with existing email → 409 Conflict
- [ ] POST /api/auth/register with invalid email → 422 Unprocessable Entity
- [ ] POST /api/auth/register with weak password → 422 Unprocessable Entity
- [ ] POST /api/auth/register exceeding rate limit → 429 Too Many Requests
- [ ] Verify password is hashed in database
- [ ] Verify user created with default settings

#### Login Endpoint

- [ ] POST /api/auth/login with correct credentials → 200 OK
- [ ] POST /api/auth/login with incorrect password → 401 Unauthorized
- [ ] POST /api/auth/login with non-existent email → 401 Unauthorized
- [ ] POST /api/auth/login exceeding rate limit → 429 Too Many Requests
- [ ] Verify tokens returned (access + refresh)
- [ ] Verify token claims match user

#### Token Refresh Endpoint

- [ ] POST /api/auth/refresh with valid refresh token → 200 OK
- [ ] POST /api/auth/refresh with expired token → 401 Unauthorized
- [ ] POST /api/auth/refresh with access token (wrong type) → 401 Unauthorized
- [ ] POST /api/auth/refresh with invalid token → 401 Unauthorized

#### Protected Endpoint (GET /api/auth/me)

- [ ] GET /api/auth/me with valid access token → 200 OK
- [ ] GET /api/auth/me with missing token → 401 Unauthorized
- [ ] GET /api/auth/me with expired token → 401 Unauthorized
- [ ] GET /api/auth/me with invalid token → 401 Unauthorized
- [ ] Verify returned user data matches database

#### Password Reset Endpoints

- [ ] POST /api/auth/forgot-password with existing email → 200 OK
- [ ] POST /api/auth/forgot-password with non-existent email → 200 OK (security)
- [ ] POST /api/auth/forgot-password exceeding rate limit → 429 Too Many Requests
- [ ] POST /api/auth/reset-password with valid token → 200 OK
- [ ] POST /api/auth/reset-password with expired token → 400 Bad Request
- [ ] POST /api/auth/reset-password with used token → 400 Bad Request
- [ ] Verify password changed in database

### Example Integration Test

```python
def test_login_with_correct_credentials(client, db_session):
    """Test successful login flow"""
    # Setup: Create user
    user = create_test_user(email="test@example.com", password="SecurePass123!")

    # Execute: Login
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })

    # Assert: Success
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@example.com"

    # Verify token is valid
    token_payload = jwt.decode(data["access_token"], verify=False)
    assert token_payload["sub"] == user.id
```

---

## End-to-End (E2E) Tests

**Scope:** Test critical user journeys through the UI

**Location:** `frontend/e2e/auth.spec.ts`

**Tool:** Playwright

### Coverage

#### Registration Journey

1. User navigates to /register
2. User fills in email, name, password
3. User submits form
4. User is redirected to /dashboard
5. Verify user is logged in (see user name in header)

#### Login Journey

1. User navigates to /login
2. User enters email + password
3. User submits form
4. User is redirected to /dashboard
5. Verify user is logged in

#### Forgot Password Journey

1. User navigates to /login
2. User clicks "Forgot Password"
3. User enters email
4. User submits form
5. Verify success message shown
6. (Email verification out of scope for E2E)

#### OAuth Login Journey (Google)

1. User navigates to /login
2. User clicks "Sign in with Google"
3. User is redirected to Google
4. (Mock Google approval in test)
5. User is redirected back to app
6. Verify user is logged in

### Example E2E Test

```typescript
test('user can register and login', async ({ page }) => {
  const email = `test-${Date.now()}@example.com`;
  const password = 'SecurePass123!';

  // Register
  await page.goto('/register');
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="name"]', 'Test User');
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // Verify redirected to dashboard
  await page.waitForURL('/dashboard');
  await expect(page.locator('text=Test User')).toBeVisible();

  // Logout
  await page.click('button:has-text("Logout")');

  // Login again
  await page.goto('/login');
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // Verify logged in
  await page.waitForURL('/dashboard');
  await expect(page.locator('text=Test User')).toBeVisible();
});
```

---

## Edge Cases to Test

### Security Edge Cases

- [ ] JWT with tampered signature
- [ ] JWT with tampered claims (user_id, is_admin)
- [ ] Replay attack (use same token multiple times)
- [ ] OAuth CSRF attack (invalid state parameter)
- [ ] SQL injection in email field
- [ ] XSS in name field
- [ ] Brute force attack (rapid login attempts)
- [ ] Password reset token reuse
- [ ] Concurrent logins from multiple devices

### Boundary Cases

- [ ] Email at max length (255 chars)
- [ ] Password at min length (8 chars)
- [ ] Password at max length (128 chars)
- [ ] Name with special characters (unicode)
- [ ] Extremely long JWT token
- [ ] Token expiry at exact second boundary

### Error Handling

- [ ] Database connection lost mid-request
- [ ] SMTP server unavailable (password reset)
- [ ] Google OAuth provider unavailable
- [ ] Invalid JSON in request body
- [ ] Missing required fields

---

## Test Fixtures

### `create_test_user(email, password, is_admin=False)`

Creates a test user in the database with hashed password.

### `get_valid_access_token(user_id, email, is_admin=False)`

Generates a valid JWT access token for testing.

### `get_expired_access_token(user_id)`

Generates an expired JWT access token for testing.

### `mock_email_service()`

Mocks email service to prevent actual email sending during tests.

---

## Coverage Goals

| Test Type | Current | Target |
|-----------|---------|--------|
| Unit Tests | 75% | 80% |
| Integration Tests | 60% | 70% |
| E2E Tests | 40% | 50% |
| Overall Coverage | 65% | 75% |

---

## Continuous Testing

### Pre-Commit Hooks

```bash
# Run unit tests before commit
pytest backend/tests/unit/test_auth_*.py
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
- name: Run Auth Tests
  run: |
    pytest backend/tests/unit/test_auth_*.py
    pytest backend/tests/integration/test_auth_api.py
    npx playwright test e2e/auth.spec.ts
```

### Test Reports

- **Unit + Integration:** JUnit XML → uploaded to CI artifacts
- **E2E:** Playwright HTML report → uploaded to CI artifacts
- **Coverage:** Coverage.py report → displayed in PR comments

---

## Manual Testing Checklist

Before releasing auth changes:

- [ ] Register new user via UI
- [ ] Login with email/password via UI
- [ ] Login with Google OAuth via UI
- [ ] Request password reset via UI
- [ ] Reset password via email link
- [ ] Access protected route while logged in
- [ ] Access protected route while logged out (should redirect)
- [ ] Token refresh works automatically (wait 15 min)
- [ ] Logout works correctly
- [ ] Admin can access admin panel
- [ ] Non-admin cannot access admin panel

---

## Performance Testing

### Load Tests (k6 or Locust)

- Login endpoint: 100 req/s for 5 minutes
- Token refresh endpoint: 50 req/s for 5 minutes
- Register endpoint: 10 req/s for 5 minutes

**Expected:**
- P95 latency <1s
- Error rate <1%
- No memory leaks

---

**Remember:** Test early, test often, test in production (with monitoring).
