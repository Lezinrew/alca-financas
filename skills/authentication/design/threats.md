# Threat Model — authentication

Using STRIDE framework to identify security threats.

---

## S — Spoofing (Identity)

### Threat: Attacker impersonates legitimate user

**Attack Vectors:**
1. **Stolen Credentials:** Phishing, keylogging, credential stuffing
2. **Weak Passwords:** Brute force attack
3. **Session Hijacking:** Stolen JWT token
4. **OAuth Hijacking:** CSRF in OAuth flow

**Mitigations:**
- ✅ Password hashing with bcrypt (cost factor 12)
- ✅ Rate limiting on login endpoint (5 attempts/min)
- ✅ Strong password requirements (min length, complexity)
- ✅ OAuth state parameter for CSRF protection
- ⚠️  TODO: Implement 2FA (TOTP, SMS)
- ⚠️  TODO: Implement device fingerprinting
- ⚠️  TODO: Implement suspicious login detection (new IP/device)

---

## T — Tampering (Data Integrity)

### Threat: Attacker modifies auth data

**Attack Vectors:**
1. **JWT Token Modification:** Attacker alters token claims (e.g., user_id, is_admin)
2. **Password Reset Token Manipulation:** Attacker modifies reset token to reset another user's password
3. **SQL Injection:** Attacker injects malicious SQL in login form

**Mitigations:**
- ✅ JWT signature validation (HMAC-SHA256)
- ✅ Strong JWT secret (32+ bytes, rotated periodically)
- ✅ Password reset tokens are cryptographically secure (32 bytes)
- ✅ Supabase client uses parameterized queries (no SQL injection)
- ✅ Input validation with Pydantic schemas

---

## R — Repudiation (Non-Repudiation)

### Threat: User denies performing auth action

**Attack Vectors:**
1. **User claims they didn't log in** (but attacker used their credentials)
2. **User claims they didn't reset password** (but they did)

**Mitigations:**
- ⚠️  TODO: Audit log for all auth events (login, logout, password change)
- ⚠️  TODO: Include IP address, user agent, timestamp in logs
- ⚠️  TODO: Send email notifications for security-critical actions
- ✅ Structured logging (user_id, action, timestamp)

---

## I — Information Disclosure (Confidentiality)

### Threat: Sensitive auth data exposed

**Attack Vectors:**
1. **JWT Token Leaked:** Token visible in logs, error messages, URLs
2. **Password Exposed:** Plain-text password in logs, error messages
3. **Email Enumeration:** Login endpoint reveals if email exists
4. **Timing Attack:** Response time differs for valid vs invalid email

**Mitigations:**
- ✅ Never log passwords or tokens
- ✅ JWT tokens not included in error messages
- ✅ Forgot password always returns success (even if email doesn't exist)
- ⚠️  TODO: Constant-time comparison for password verification
- ⚠️  TODO: Rate limiting to prevent email enumeration via timing
- ✅ HTTPS in production (encrypt data in transit)

---

## D — Denial of Service (Availability)

### Threat: Auth service becomes unavailable

**Attack Vectors:**
1. **Brute Force Login:** Attacker floods login endpoint
2. **Password Reset Flood:** Attacker requests resets for all users
3. **JWT Verification Overhead:** Attacker sends invalid tokens to slow down server

**Mitigations:**
- ✅ Rate limiting on login (5 attempts/min per IP)
- ✅ Rate limiting on password reset (5 requests/hour per IP)
- ✅ Rate limiting on registration (3 attempts/min per IP)
- ⚠️  TODO: Implement CAPTCHA after N failed attempts
- ⚠️  TODO: Monitor CPU/memory usage; alert on anomalies
- ✅ JWT validation is fast (signature verification + expiry check)

---

## E — Elevation of Privilege (Authorization)

### Threat: Non-admin user gains admin privileges

**Attack Vectors:**
1. **JWT Token Manipulation:** Attacker modifies `is_admin` claim in token
2. **Direct DB Modification:** Attacker gains DB access and sets `is_admin = true`
3. **OAuth Account Linking:** Attacker links their account to admin's OAuth

**Mitigations:**
- ✅ JWT signature prevents claim modification
- ✅ `is_admin` flag checked on every admin endpoint
- ✅ Admin flag can only be set by existing admins (application logic)
- ✅ RLS policies + application-level filtering by user_id
- ⚠️  TODO: Audit log for admin flag changes
- ⚠️  TODO: Require re-authentication for admin actions

---

## Attack Surface Summary

| Component | Exposure | Risk Level | Mitigations |
|-----------|----------|------------|-------------|
| Login Endpoint | Public | 🔴 High | Rate limiting, password hashing, input validation |
| Registration Endpoint | Public | 🔴 High | Rate limiting, email validation, password strength |
| Password Reset | Public | 🔴 High | Rate limiting, secure tokens, email verification |
| Token Refresh | Semi-public | 🟡 Medium | Refresh token validation, short access token TTL |
| OAuth Callback | Public | 🔴 High | State validation, HTTPS, provider trust |
| JWT Secret | Internal | 🔴 Critical | Strong secret, env vars, rotation policy |
| Password Hashes | Database | 🔴 Critical | bcrypt, high cost factor, salted |

---

## Incident Response

### If JWT Secret is Compromised:
1. **Immediate:** Rotate JWT_SECRET in .env
2. **Immediate:** Invalidate all existing tokens (force re-login)
3. **Within 1 hour:** Audit access logs for suspicious activity
4. **Within 24 hours:** Notify affected users
5. **Postmortem:** Document how secret was leaked, prevent recurrence

### If Password Database is Leaked:
1. **Immediate:** Force password reset for all users
2. **Immediate:** Notify all users via email
3. **Within 1 hour:** Audit for unauthorized access
4. **Within 24 hours:** Public disclosure (if legally required)
5. **Postmortem:** Review security practices, improve hashing

---

## Security Checklist

- [x] Passwords hashed with bcrypt (cost factor 12)
- [x] JWT secret is strong and in env vars
- [x] Rate limiting on auth endpoints
- [x] Input validation with Pydantic
- [x] HTTPS in production
- [x] OAuth state parameter for CSRF protection
- [ ] Implement 2FA (TODO)
- [ ] Implement audit logging (TODO)
- [ ] Implement CAPTCHA (TODO)
- [ ] Implement device fingerprinting (TODO)
- [ ] Regular security audits (TODO)
- [ ] Penetration testing (TODO)

---

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
