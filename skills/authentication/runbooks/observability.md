# Observability — authentication

What to log, monitor, and trace for the authentication skill.

---

## Logging

### What to Log

#### INFO Level
- Successful login: `"User logged in", user_id, auth_method`
- Successful registration: `"User registered", user_id, email`
- Token refreshed: `"Token refreshed", user_id`
- Password reset requested: `"Password reset requested", email`
- Password reset completed: `"Password reset completed", user_id`
- OAuth flow started: `"OAuth flow initiated", provider`
- OAuth flow completed: `"OAuth flow completed", user_id, provider`

#### WARNING Level
- Failed login attempts: `"Login failed", email, reason="invalid_password|user_not_found"`
- Expired token used: `"Expired token", user_id`
- Invalid OAuth state: `"OAuth state invalid", state`
- Rate limit hit: `"Rate limit exceeded", endpoint, ip_address`
- Password reset for non-existent email: `"Password reset for unknown email", email`

#### ERROR Level
- JWT validation error: `"JWT validation failed", error_type`
- Database error: `"Database error during auth", error`
- Email send failure: `"Failed to send password reset email", email, error`
- OAuth provider error: `"OAuth provider error", provider, error`

#### CRITICAL Level
- JWT secret missing/invalid: `"JWT secret not configured"`
- Database connection lost: `"Cannot connect to database"`
- Multiple failed admin escalation attempts: `"Suspicious admin privilege escalation", user_id`

### What NOT to Log
- ❌ **Passwords** (plain or hashed)
- ❌ **JWT tokens** (full token)
- ❌ **Password reset tokens** (full token)
- ❌ **OAuth secrets** (client_secret, auth codes)
- ❌ **Full user records** (may contain PII)

### Log Format

```python
logger.info(
    "User logged in",
    extra={
        "user_id": user_id,
        "auth_method": "email_password",
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent"),
        "correlation_id": request.headers.get("X-Correlation-ID")
    }
)
```

### Structured Logs (JSON)

```json
{
  "timestamp": "2026-02-27T12:00:00Z",
  "level": "INFO",
  "message": "User logged in",
  "user_id": "uuid",
  "auth_method": "email_password",
  "ip_address": "192.168.1.1",
  "correlation_id": "uuid"
}
```

---

## Metrics

### Key Performance Indicators (KPIs)

| Metric | Type | Description | Target |
|--------|------|-------------|--------|
| `auth.login.success.count` | Counter | Successful logins | N/A |
| `auth.login.failure.count` | Counter | Failed login attempts | <5% of attempts |
| `auth.login.duration.ms` | Histogram | Login endpoint latency | P95 <500ms |
| `auth.register.count` | Counter | New user registrations | N/A |
| `auth.token_refresh.count` | Counter | Token refreshes | N/A |
| `auth.password_reset.requested.count` | Counter | Password reset requests | N/A |
| `auth.password_reset.completed.count` | Counter | Completed password resets | N/A |
| `auth.oauth.success.count` | Counter | OAuth logins | N/A |
| `auth.oauth.failure.count` | Counter | Failed OAuth attempts | <2% of attempts |
| `auth.rate_limit.exceeded.count` | Counter | Rate limit hits | Monitor for abuse |
| `auth.jwt_validation.failure.count` | Counter | Invalid tokens | Monitor for attacks |

### Business Metrics

| Metric | Description | Use Case |
|--------|-------------|----------|
| Daily Active Users (DAU) | Unique users logged in today | Growth tracking |
| New Registrations per Day | Users registered today | Acquisition tracking |
| OAuth Adoption Rate | % users using OAuth vs password | Feature adoption |
| Password Reset Rate | Resets per user per month | UX friction indicator |

### Security Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Brute Force Attempts | Failed logins from same IP | >20 in 1 minute |
| Suspicious Admin Escalation | Non-admin trying to set is_admin | >1 |
| Token Manipulation Attempts | Invalid JWT signatures | >10 per hour |
| OAuth State Mismatch | CSRF attack attempts | >5 per hour |

---

## Tracing

### Distributed Traces

#### Login Flow Trace

```
span: api.auth.login (1.2s)
├─ span: validate_input (10ms)
├─ span: db.query.get_user_by_email (50ms)
├─ span: bcrypt.verify_password (800ms)  ← Slowest
├─ span: jwt.generate_tokens (30ms)
└─ span: serialize_response (5ms)
```

**Optimization:** bcrypt verification is intentionally slow (security feature)

#### OAuth Flow Trace

```
span: api.auth.google.login (300ms)
└─ span: create_oauth_state (20ms)

span: api.auth.google.callback (1.5s)
├─ span: validate_oauth_state (15ms)
├─ span: exchange_code_for_token (800ms)  ← External call
├─ span: fetch_google_user_info (400ms)   ← External call
├─ span: db.query.find_or_create_user (100ms)
├─ span: jwt.generate_tokens (30ms)
└─ span: redirect_with_tokens (5ms)
```

**Optimization:** Cache Google user info briefly to reduce external calls

#### Token Refresh Flow Trace

```
span: api.auth.refresh (80ms)
├─ span: jwt.validate_refresh_token (20ms)
├─ span: db.query.get_user_by_id (30ms)
└─ span: jwt.generate_access_token (30ms)
```

**Optimization:** Consider caching user data to skip DB query

### Correlation IDs

- **Generate:** Create UUID on first request (frontend or API gateway)
- **Propagate:** Include `X-Correlation-ID` header in all requests
- **Log:** Include correlation_id in all log entries
- **Trace:** Use as trace_id in distributed tracing system

---

## Dashboards

### Auth Health Dashboard

**Panels:**
1. **Login Success Rate** (gauge) — % successful logins (target: >95%)
2. **Login Latency** (graph) — P50, P95, P99 over time
3. **Active Users** (counter) — Users logged in last 24 hours
4. **Failed Login Attempts** (graph) — Rate of failures over time
5. **OAuth Success Rate** (gauge) — % successful OAuth flows
6. **Rate Limit Hits** (graph) — Rate limit violations over time

### Security Dashboard

**Panels:**
1. **Brute Force Attempts** (graph) — Failed logins per IP
2. **Suspicious Activity** (list) — JWT tampering, admin escalation attempts
3. **Geographic Anomalies** (map) — Logins from unusual locations
4. **Password Reset Abuse** (graph) — Reset requests per user

### Business Dashboard

**Panels:**
1. **Daily Active Users** (graph) — DAU trend
2. **New Registrations** (graph) — Sign-ups per day
3. **OAuth Adoption** (pie chart) — Email/password vs Google vs other
4. **User Retention** (cohort analysis) — % users still active after N days

---

## Alerts

### Critical Alerts (Page On-Call)

| Alert | Condition | Action |
|-------|-----------|--------|
| Auth Service Down | 5xx error rate >10% for 2 minutes | Page engineer |
| Database Unreachable | No DB queries succeeding for 1 minute | Page engineer |
| JWT Secret Missing | App fails to start | Page engineer |

### High Priority Alerts (Slack)

| Alert | Condition | Action |
|-------|-----------|--------|
| High Failed Login Rate | Login failure rate >20% for 5 minutes | Notify security team |
| Brute Force Attack | >50 failed logins from single IP in 1 minute | Auto-block IP |
| OAuth Flow Broken | OAuth error rate >50% for 5 minutes | Notify team |

### Medium Priority Alerts (Email)

| Alert | Condition | Action |
|-------|-----------|--------|
| Password Reset Spike | Reset requests 10x normal for 10 minutes | Investigate |
| Slow Login Response | P95 latency >2s for 10 minutes | Investigate performance |
| High Token Refresh Rate | Refresh rate 5x normal | Investigate (possible attack) |

---

## Monitoring Checklist

- [x] Logs structured (JSON format)
- [x] Correlation IDs in all logs
- [ ] Metrics exported to Prometheus (TODO)
- [ ] Dashboards created in Grafana (TODO)
- [ ] Alerts configured (TODO)
- [ ] Distributed tracing with OpenTelemetry (TODO)
- [ ] PII excluded from logs
- [ ] Log retention policy defined (90 days)
- [ ] Metrics retention policy defined (1 year)

---

## Useful Queries

### Logs (Loki / CloudWatch)

```
# Failed logins by email
{service="backend"} |= "Login failed" | json | email != ""

# OAuth errors
{service="backend"} |= "OAuth" |= "error"

# Rate limit hits by IP
{service="backend"} |= "Rate limit exceeded" | json | count by ip_address

# Correlation ID trace
{service="backend"} | correlation_id="uuid"
```

### Metrics (PromQL)

```
# Login success rate (last 5 min)
sum(rate(auth_login_success_count[5m])) /
(sum(rate(auth_login_success_count[5m])) + sum(rate(auth_login_failure_count[5m])))

# P95 login latency
histogram_quantile(0.95, rate(auth_login_duration_ms_bucket[5m]))

# Failed logins per second
rate(auth_login_failure_count[1m])

# Top IPs by rate limit hits
topk(10, sum by (ip_address) (rate(auth_rate_limit_exceeded_count[5m])))
```

---

## References

- [OpenTelemetry Instrumentation](https://opentelemetry.io/docs/instrumentation/python/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
