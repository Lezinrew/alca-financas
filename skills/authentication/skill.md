# Skill: authentication

**Status:** Active
**Risk Level:** 🔴 High
**Owner:** Security Team
**Last Updated:** 2026-02-27

---

## Purpose

Manages all user authentication flows including JWT-based authentication, OAuth social logins (Google), Supabase Auth integration, password recovery via email, and session management.

## Business Value

- **Critical Security Layer:** Protects all user data and operations
- **User Experience:** Enables seamless login, social auth, and password recovery
- **Compliance:** Meets security standards for financial applications
- **Impact if Failed:** Complete system unavailability; data breach risk

## Boundaries

### In Scope
- User registration (email/password)
- User login (email/password, OAuth)
- JWT token generation and validation
- Token refresh mechanism
- Password reset flow (forgot password → email → reset)
- Session management
- User authentication middleware (`@require_auth`)
- Supabase Auth integration (alternative auth method)

### Out of Scope
- User profile management → `users-profile` skill
- Admin role checks → `admin-governance` skill (uses this skill's auth first)
- Two-factor authentication (2FA) → future feature
- Biometric auth → future feature

## Core Responsibilities

1. **Authenticate users** via email/password or OAuth providers
2. **Generate secure JWT tokens** (access + refresh)
3. **Validate JWT tokens** on protected endpoints
4. **Manage token lifecycle** (expiry, refresh, revocation)
5. **Facilitate password recovery** via email-based reset flow
6. **Provide auth middleware** for route protection
7. **Integrate with Supabase Auth** as alternative auth backend

## User Journeys

### Journey 1: Register New User
1. User fills registration form (email, name, password)
2. Frontend validates input (format, strength)
3. Backend validates via Pydantic schema
4. Backend hashes password with bcrypt
5. Backend creates user in Supabase `users` table
6. Backend generates JWT access + refresh tokens
7. Frontend stores tokens in localStorage
8. User redirected to dashboard

### Journey 2: Login with Email/Password
1. User enters email + password
2. Frontend sends POST /api/auth/login
3. Backend retrieves user by email from Supabase
4. Backend verifies password hash with bcrypt
5. Backend generates JWT tokens
6. Frontend stores tokens
7. User redirected to dashboard

### Journey 3: Login with Google OAuth
1. User clicks "Login with Google"
2. Frontend redirects to /api/auth/google/login
3. Backend redirects to Google OAuth consent screen
4. User approves permissions on Google
5. Google redirects to /api/auth/google/callback with code
6. Backend exchanges code for Google user info
7. Backend finds or creates user in Supabase
8. Backend generates JWT tokens
9. Frontend stores tokens
10. User redirected to dashboard

### Journey 4: Forgot Password
1. User clicks "Forgot Password"
2. User enters email address
3. Backend generates secure reset token
4. Backend sends reset email via email service
5. User clicks link in email
6. Frontend shows reset password form
7. User enters new password
8. Backend validates token and updates password
9. User redirected to login

### Journey 5: Token Refresh
1. Frontend detects access token expiring soon
2. Frontend sends POST /api/auth/refresh with refresh_token
3. Backend validates refresh token
4. Backend generates new access token
5. Frontend updates stored access token
6. Request continues with new token

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| JWT secret leaked | 🔴 Critical: All tokens compromised | Rotate JWT_SECRET immediately; invalidate all sessions |
| Password hash weak | 🔴 Critical: Brute force possible | Use bcrypt with cost factor 12+; enforce password strength |
| Token stored insecurely | 🟡 Medium: XSS attack steals token | Use httpOnly cookies (future); implement CSP |
| OAuth callback vulnerable | 🔴 High: Account takeover | Validate state parameter; use PKCE flow |
| Email reset token guessable | 🔴 High: Account takeover | Use cryptographically secure random tokens (32+ bytes) |
| Rate limiting bypassed | 🟡 Medium: Brute force attacks | Implement IP-based rate limiting + CAPTCHA |
| Supabase unavailable | 🔴 Critical: No auth possible | Implement circuit breaker; fallback to read-only mode |

## Dependencies

### Upstream (Skills this depends on)
- `users-profile` — Creates/reads user records during auth
- `notifications` — Sends password reset emails
- `infrastructure-platform` — Rate limiting, CORS, logging

### Downstream (Skills that depend on this)
- **All skills** — All protected endpoints require auth
- `admin-governance` — Admin endpoints check auth first, then admin role

## Code Map

### Backend
- **Routes:**
  - `backend/routes/auth.py` — Custom JWT auth endpoints
  - `backend/routes/auth_supabase.py` — Supabase Auth integration
- **Services:**
  - `backend/services/user_service.py` — User CRUD operations
  - `backend/services/supabase_auth_service.py` — Supabase Auth wrapper
- **Utilities:**
  - `backend/utils/auth_utils.py` — JWT helpers, @require_auth decorator
  - `backend/utils/auth_utils_supabase.py` — Supabase-specific auth utils
- **Schemas:**
  - `backend/schemas/auth_schemas.py` — Pydantic validation (UserRegisterSchema, UserLoginSchema)
- **Middleware:**
  - `@require_auth` decorator in `auth_utils.py`
  - `@admin_required` decorator in `auth_utils.py`

### Frontend
- **Components:**
  - `frontend/src/components/auth/Login.tsx`
  - `frontend/src/components/auth/Register.tsx`
  - `frontend/src/components/auth/ForgotPassword.tsx`
  - `frontend/src/components/auth/ResetPassword.tsx`
- **Contexts:**
  - `frontend/src/contexts/AuthContext.tsx` — Global auth state
- **Utils:**
  - `frontend/src/utils/api.ts` — HTTP client with auth headers
  - `frontend/src/utils/tokenStorage.ts` — Token storage/retrieval

### Database
- **Tables:** `users`, `oauth_states`
- **Migrations:** `backend/database/schema.sql`, `backend/database/migrations/`

## Security Considerations

### Authentication
- **Password Storage:** bcrypt with cost factor 12
- **JWT Secret:** Strong secret (32+ bytes), stored in env vars, never hardcoded
- **Token Expiry:** Access token 15min, refresh token 7 days
- **Token Storage:** localStorage (frontend), consider httpOnly cookies for enhanced security

### Authorization
- All protected routes must use `@require_auth` decorator
- User ID extracted from JWT, used to filter all queries
- Never trust client-provided user IDs

### Password Reset
- Reset tokens are cryptographically secure (32 bytes)
- Tokens expire after 1 hour
- Tokens are single-use (deleted after reset)
- Rate limit reset requests (5 per hour per IP)

### OAuth Security
- State parameter validated to prevent CSRF
- Nonce used for replay protection
- OAuth state stored in DB with expiry
- Redirect URIs whitelisted

### Rate Limiting
- Login: 5 attempts per minute per IP
- Register: 3 attempts per minute per IP
- Password reset: 5 requests per hour per IP

## Observability Plan

### Logs
- **INFO:** Successful login, logout, token refresh
- **WARNING:** Failed login attempts (invalid credentials), expired tokens
- **ERROR:** JWT validation errors, OAuth flow errors, password reset failures
- **Exclude:** Never log passwords, tokens, or PII

### Metrics
- `auth.login.success.count` — Successful logins
- `auth.login.failure.count` — Failed login attempts
- `auth.register.count` — New user registrations
- `auth.token_refresh.count` — Token refreshes
- `auth.password_reset.count` — Password reset requests
- `auth.oauth.success.count` — OAuth logins
- `auth.response_time.ms` — Auth endpoint latency

### Traces
- Login flow: Form submit → API call → DB query → Token generation
- OAuth flow: Redirect → Callback → Token exchange → User creation
- Password reset: Request → Email send → Token validation → Password update

## Future Evolution

### v1.0 (Current)
- JWT authentication
- Google OAuth
- Password recovery
- Supabase Auth integration (alternative)

### v2.0 (Planned — Q2 2026)
- Two-factor authentication (2FA) via TOTP
- OAuth providers: Microsoft, Apple
- Passwordless login (magic links)
- Session management dashboard (view active sessions, revoke)

### v3.0 (Vision — Q4 2026)
- Biometric authentication (WebAuthn)
- Risk-based authentication (device fingerprinting, IP reputation)
- Federated identity (SAML, OpenID Connect)
- Zero-trust architecture

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
- [Domain Model](./design/domain-model.md)
- [Invariants](./design/invariants.md)
- [Threat Model](./design/threats.md)
- [Troubleshooting](./runbooks/troubleshooting.md)
- [Observability](./runbooks/observability.md)
- [Test Strategy](./tests/test-strategy.md)
