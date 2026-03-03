# Invariants — authentication

**Invariants** are business rules that must **never** be violated. Violating an invariant indicates a bug or data corruption.

---

## Core Invariants

### 1. Email Uniqueness
**Rule:** No two active users can have the same email address.

**Why:** Email is the primary login identifier; duplicates would cause authentication ambiguity.

**Enforcement:**
- Database: UNIQUE constraint on `users.email`
- Application: Check email uniqueness before insert

**Test:** Attempt to register with existing email → expect 409 Conflict

---

### 2. Password OR OAuth Provider Required
**Rule:** User must have either a password OR at least one OAuth provider.

**Why:** User must have a way to authenticate; otherwise account is inaccessible.

**Enforcement:**
- Application: Validate on registration and profile update
- Database: CHECK constraint (future): `(password IS NOT NULL) OR (jsonb_array_length(auth_providers) > 0)`

**Test:**
- Register with email/password → success
- Register with Google OAuth → success
- Create user with no password and no OAuth → expect 422 Unprocessable Entity

---

### 3. JWT Must Be Signed
**Rule:** All issued JWTs must be signed with the server's secret.

**Why:** Unsigned or improperly signed tokens could be forged by attackers.

**Enforcement:**
- Application: Always sign tokens with `JWT_SECRET` using HS256 algorithm
- Application: Always verify signature before trusting token claims

**Test:**
- Modify JWT payload → expect 401 Unauthorized
- Use JWT with wrong signature → expect 401 Unauthorized

---

### 4. Expired Tokens Are Invalid
**Rule:** Tokens past their expiry time (`exp` claim) must be rejected.

**Why:** Prevents use of stolen/leaked tokens indefinitely.

**Enforcement:**
- Application: Check `exp` claim on every token validation
- Application: Reject tokens where `exp < current_time`

**Test:**
- Use expired access token → expect 401 Unauthorized
- Use expired refresh token → expect 401 Unauthorized

---

### 5. Password Must Be Hashed
**Rule:** Plain-text passwords must never be stored in the database.

**Why:** Prevents mass credential theft if database is compromised.

**Enforcement:**
- Application: Hash password with bcrypt before insert/update
- Code Review: Never call `db.insert()` with plain-text password

**Test:**
- Register user → verify password column contains bcrypt hash (starts with `$2b$`)
- Login with correct password → success
- Login with incorrect password → failure

---

### 6. Admin Flag Cannot Be Self-Granted
**Rule:** Non-admin users cannot set their own `is_admin` flag to `true`.

**Why:** Privilege escalation attack vector.

**Enforcement:**
- Application: `is_admin` updates require current user to be admin
- Route: Admin-only endpoints use `@admin_required` decorator

**Test:**
- Non-admin attempts to update own `is_admin` flag → expect 403 Forbidden
- Admin updates another user's `is_admin` flag → success

---

### 7. OAuth State Must Be Unique and Expiring
**Rule:** OAuth state values must be unique and expire within 10 minutes.

**Why:** CSRF protection; prevents replay attacks.

**Enforcement:**
- Application: Generate cryptographically secure random state (32 bytes)
- Application: Store state with expiry time in `oauth_states` table
- Application: Validate state on callback and delete after use
- Database: UNIQUE constraint on `oauth_states.state`

**Test:**
- Initiate OAuth → state stored with expiry
- Complete OAuth with valid state → success, state deleted
- Attempt OAuth with expired state → failure
- Attempt OAuth with reused state → failure (already deleted)

---

### 8. Token Claims Must Match User Record
**Rule:** JWT claims (`user_id`, `email`, `is_admin`) must match current user record in DB.

**Why:** Prevents stale tokens from granting incorrect permissions.

**Enforcement:**
- Application: Optionally re-fetch user from DB on sensitive operations
- (Future) Implement token revocation list for immediate invalidation

**Test:**
- Admin logs in, gets token with `is_admin=true`
- Admin demoted to regular user
- (Current) Token still works until expiry
- (Future) Token should be invalidated immediately

---

### 9. Rate Limits Must Be Enforced
**Rule:** Auth endpoints must enforce rate limits to prevent abuse.

**Why:** Prevents brute force attacks, credential stuffing, DoS.

**Enforcement:**
- Application: Flask-Limiter decorators on routes
- Configuration: Rate limits defined per endpoint (see CONVENTIONS.md)

**Test:**
- Exceed login rate limit → expect 429 Too Many Requests
- Wait for rate limit window → requests allowed again

---

## Invariant Violation Handling

If an invariant is violated:

1. **Detect:** Log error with `CRITICAL` level
2. **Reject:** Return 400/422/500 error to client
3. **Alert:** Notify on-call engineer (for critical invariants)
4. **Investigate:** Check logs, audit data integrity
5. **Fix:** Correct data if corrupted; fix code if bug

---

## Monitoring Invariants

**Database Constraints:** Catch violations at DB level (fail-safe)

**Application Validation:** Catch violations before DB insert (better UX)

**Periodic Audits:** Run cron jobs to detect data inconsistencies:
```sql
-- Find users with no password and no OAuth providers
SELECT id, email FROM users
WHERE password IS NULL AND jsonb_array_length(auth_providers) = 0;

-- Find expired OAuth states not cleaned up
SELECT COUNT(*) FROM oauth_states WHERE expires_at < NOW();
```

**Metrics:**
- `auth.invariant_violations.count` — Total violations detected
- `auth.password_resets.suspicious.count` — Unusual reset patterns

---

## Testing Strategy

- **Unit Tests:** Validate each invariant with positive and negative test cases
- **Integration Tests:** Test invariants across API boundaries (DB → Service → Route)
- **E2E Tests:** Validate invariants through user journeys
- **Property-Based Tests:** (Future) Use hypothesis/property testing to fuzz invariants

---

**Remember:** Invariants are your safety net. Never compromise on them.
