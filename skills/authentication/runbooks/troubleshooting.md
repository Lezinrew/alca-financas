# Troubleshooting — authentication

Common authentication issues and how to resolve them.

---

## Issue: Users Cannot Login (401 Unauthorized)

### Symptoms
- Users report "Invalid credentials" error
- Login endpoint returns 401 even with correct password

### Possible Causes
1. **Database connection issue** — Backend cannot reach Supabase
2. **Password hash mismatch** — Password hashing algorithm changed
3. **Email case sensitivity** — Email lookup is case-sensitive but shouldn't be
4. **JWT secret changed** — Existing tokens invalid (doesn't affect new logins)

### Diagnosis
```bash
# Check backend logs
tail -f logs/backend-*.log | grep "login"

# Test database connection
curl -H "apikey: $SUPABASE_ANON_KEY" $SUPABASE_URL/rest/v1/users?select=email&limit=1

# Test login endpoint directly
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass"}'
```

### Resolution
1. **DB Connection:** Check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`
2. **Password Hash:** Verify bcrypt version consistent; reset passwords if needed
3. **Email Case:** Convert email to lowercase before lookup
4. **JWT Secret:** If changed, users must re-login (expected behavior)

---

## Issue: Token Expired Immediately

### Symptoms
- Users logged out seconds after login
- Frontend shows "Session expired" repeatedly

### Possible Causes
1. **System clock skew** — Server clock incorrect
2. **Token expiry too short** — JWT_ACCESS_TOKEN_EXPIRES misconfigured
3. **Frontend refreshing incorrectly** — Token refresh logic broken

### Diagnosis
```bash
# Check server time
date

# Decode JWT to see expiry
echo "eyJhbGc..." | base64 -d 2>/dev/null | jq .exp

# Compare with current timestamp
date +%s
```

### Resolution
1. **Clock Skew:** Sync server clock with NTP
2. **Expiry Config:** Check `JWT_ACCESS_TOKEN_EXPIRES` (should be 900 seconds = 15 min)
3. **Frontend Logic:** Review `AuthContext.tsx` token refresh implementation

---

## Issue: OAuth Login Fails (Google)

### Symptoms
- Google OAuth redirects to error page
- Backend logs show "Invalid state parameter"

### Possible Causes
1. **OAuth state expired** — User took >10 min to approve
2. **State mismatch** — CSRF attack or browser cookie issue
3. **Invalid OAuth credentials** — `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` wrong
4. **Redirect URI mismatch** — Configured URI doesn't match actual callback URL

### Diagnosis
```bash
# Check OAuth states in DB
psql $DATABASE_URL -c "SELECT * FROM oauth_states WHERE provider='google' ORDER BY created_at DESC LIMIT 5;"

# Check backend logs for OAuth errors
grep "oauth" logs/backend-*.log
```

### Resolution
1. **Expired State:** User must retry OAuth flow (normal)
2. **State Mismatch:** Clear browser cookies, retry
3. **Invalid Credentials:** Verify in Google Cloud Console → API & Services → Credentials
4. **Redirect URI:** Update in Google Console to match: `https://alcahub.cloud/api/auth/google/callback`

---

## Issue: Rate Limit Blocking Legitimate Users

### Symptoms
- Users get "Too many requests" error
- Cannot login even once

### Possible Causes
1. **Shared IP** — Multiple users behind same NAT/proxy
2. **Rate limit too strict** — Limit set too low
3. **Attacker** — Brute force attack exhausting rate limit

### Diagnosis
```bash
# Check Flask-Limiter logs
grep "rate limit exceeded" logs/backend-*.log

# Check source IPs
grep "401 Unauthorized" logs/backend-*.log | awk '{print $1}' | sort | uniq -c | sort -rn
```

### Resolution
1. **Shared IP:** Temporarily whitelist IP or increase rate limit for corporate networks
2. **Too Strict:** Adjust rate limit in `extensions.py` (e.g., 10/min instead of 5/min)
3. **Attack:** Block attacker IP at firewall/nginx level

---

## Issue: Password Reset Email Not Received

### Symptoms
- User requests password reset but doesn't get email

### Possible Causes
1. **Email service down** — SMTP server unreachable
2. **Wrong email address** — User entered typo
3. **Spam filter** — Email in spam/junk folder
4. **Rate limit** — Too many reset requests

### Diagnosis
```bash
# Check email service logs
grep "password_reset" logs/backend-*.log

# Test SMTP connection
telnet $SMTP_HOST $SMTP_PORT

# Check email service status
python -c "from services.email_service import EmailService; EmailService().send_test_email()"
```

### Resolution
1. **Service Down:** Check SMTP credentials in `.env`; verify SMTP server status
2. **Wrong Email:** User must retry with correct email
3. **Spam Filter:** Instruct user to check spam folder; whitelist sender
4. **Rate Limit:** Wait 1 hour or manually reset password via admin panel

---

## Issue: Admin Cannot Access Admin Panel (403 Forbidden)

### Symptoms
- User with `is_admin=true` gets 403 error on admin endpoints

### Possible Causes
1. **JWT doesn't include is_admin claim** — Old token from before promotion
2. **is_admin flag not set correctly** — DB value is false
3. **Admin middleware broken** — `@admin_required` decorator issue

### Diagnosis
```bash
# Check user's is_admin flag in DB
psql $DATABASE_URL -c "SELECT id, email, is_admin FROM users WHERE email='admin@example.com';"

# Decode user's JWT to check claims
echo "eyJhbGc..." | base64 -d | jq .is_admin
```

### Resolution
1. **Old Token:** User must logout and login again to get new token with `is_admin=true`
2. **DB Flag:** Set `is_admin=true` via SQL or admin script
3. **Middleware:** Review `@admin_required` decorator in `utils/auth_utils.py`

---

## Escalation

If issue persists after troubleshooting:

1. **Check logs:** `logs/backend-*.log` for detailed error traces
2. **Check monitoring:** Metrics dashboard for auth endpoint errors
3. **Check status:** Supabase status page (status.supabase.io)
4. **Contact on-call:** Page DevOps engineer if critical
5. **Rollback:** If recent deploy caused issue, rollback to previous version

---

## Useful Commands

```bash
# Tail auth-related logs
tail -f logs/backend-*.log | grep -i "auth\|login\|token"

# Count failed login attempts
grep "401 Unauthorized" logs/backend-*.log | grep "login" | wc -l

# List users created today
psql $DATABASE_URL -c "SELECT email, created_at FROM users WHERE created_at > NOW() - INTERVAL '1 day';"

# Clear expired OAuth states
psql $DATABASE_URL -c "DELETE FROM oauth_states WHERE expires_at < NOW();"

# Manually create admin user
python backend/scripts/create_admin.py --email admin@example.com

# Test auth endpoint health
curl http://localhost:8001/api/auth/me -H "Authorization: Bearer $TOKEN"
```
