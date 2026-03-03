# Skill: infrastructure-platform

**Status:** Active
**Risk Level:** High
**Owner:** DevOps/SRE Team
**Last Updated:** 2026-02-27

---

## Purpose

Cross-cutting infrastructure concerns including Row Level Security (RLS), rate limiting, CORS configuration, CI/CD pipelines, Docker containerization, deployment automation, monitoring, and logging infrastructure.

## Business Value

- **Security:** RLS, rate limiting, CORS protect all endpoints
- **Reliability:** CI/CD ensures tested deployments
- **Scalability:** Docker and orchestration enable scaling
- **Observability:** Logging and monitoring enable debugging
- **Impact if Failed:** Complete system unavailability or security breach

## Boundaries

### In Scope
- Row Level Security (RLS) policies
- Rate limiting configuration
- CORS and security headers
- CI/CD pipelines (GitHub Actions)
- Docker containerization
- Deployment scripts and automation
- Database migrations
- Monitoring setup (Prometheus, Grafana)
- Logging infrastructure
- Backup and recovery

### Out of Scope
- Application business logic → Other skills own business logic
- Feature development → Product teams
- User-facing functionality → Other skills

## Core Responsibilities

1. **Enforce security policies** (RLS, CORS, rate limiting)
2. **Provide CI/CD pipelines** for automated testing and deployment
3. **Containerize applications** with Docker
4. **Automate deployments** to production
5. **Enable monitoring** with metrics and logs
6. **Manage database schema** via migrations
7. **Ensure high availability** and disaster recovery

## Key Components

### Security Layer
- **RLS Policies:** Row-level security for all tables
- **Rate Limiting:** Flask-Limiter on critical endpoints
- **CORS:** Configured allowed origins
- **Security Headers:** X-Frame-Options, CSP, HSTS

### CI/CD Pipeline
- **Continuous Integration:** GitHub Actions on every commit
- **Automated Testing:** Run test suite before merge
- **Continuous Deployment:** Auto-deploy to production on main branch
- **Deployment Gates:** Manual approval for production

### Containerization
- **Docker:** Backend (Flask), Frontend (Nginx), Database (Postgres via Supabase)
- **Docker Compose:** Local development environment
- **Production:** DigitalOcean Droplet with Docker

### Monitoring
- **Logs:** Application logs, access logs, error logs
- **Metrics:** CPU, memory, request rate, response time (future: Prometheus)
- **Alerts:** Critical errors, high latency (future)

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| RLS misconfiguration | Critical: Data leak | Thorough testing; peer review; audit logs |
| CI/CD pipeline broken | High: No deployments | Monitoring pipeline health; fallback manual deploy |
| Rate limit too strict | Medium: Users blocked | Gradual rollout; monitoring false positives |
| CORS misconfiguration | High: Frontend broken | Test in staging; rollback mechanism |
| Deployment failure | Critical: Downtime | Blue-green deployment; automated rollback |
| Database migration error | Critical: Data corruption | Backup before migration; test in staging first |

## Dependencies

### Upstream
- None (infrastructure provides foundation)

### Downstream
- **All skills** — All application code depends on infrastructure

## Code Map

### Backend Configuration
- **App Setup:** `backend/app.py` (Flask app, CORS, rate limiting)
- **Extensions:** `backend/extensions.py` (limiter, CORS)
- **WSGI:** `backend/gunicorn.conf.py` (production server config)

### Database
- **Schema:** `backend/database/schema.sql` (initial schema with RLS)
- **Migrations:** `backend/database/migrations/` (versioned schema changes)

### CI/CD
- **CI Pipeline:** `.github/workflows/ci.yml` (tests, linting)
- **Deploy Pipeline:** `.github/workflows/deploy-production.yml` (automated deployment)

### Docker
- **Development:** `docker-compose.yml` (local dev environment)
- **Production:** `docker-compose.prod.yml` (production config)
- **Nginx:** `nginx.conf` (reverse proxy config)

### Deployment Scripts
- **Production Scripts:** `scripts/prod/` (deployment automation)
- **Deploy Frontend:** `scripts/prod/deploy-frontend-only.sh`
- **Deploy Backend:** `scripts/prod/deploy-backend.sh` (future)

## Security Considerations

### RLS Policies
- Current: `USING (true)` (effectively disabled, application-level filtering)
- Future: Proper RLS with `auth.uid()` matching `user_id`

### Rate Limiting
- Login: 5 attempts/minute
- Register: 3 attempts/minute
- General API: 100 requests/minute per user
- Import: 5 requests/hour

### CORS
- Development: `localhost:3000`, `localhost:5173`
- Production: `https://alcahub.cloud`

### Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

## Observability Plan

### Logs
- Application logs (INFO, WARNING, ERROR)
- Access logs (Nginx)
- Deployment logs (GitHub Actions)

### Metrics (Future: Prometheus)
- `http_requests_total` — Total HTTP requests
- `http_request_duration_seconds` — Request latency
- `http_errors_total` — Error count
- `db_connections_active` — Database connections

### Traces (Future: Jaeger)
- End-to-end request tracing
- Database query tracing

## Deployment Process

### Current Process
1. Push to `main` branch
2. GitHub Actions runs tests
3. If tests pass, deploy to production
4. SSH into server
5. Pull latest code
6. Rebuild Docker containers
7. Restart services
8. Verify deployment

### Future Process (Blue-Green)
1. Deploy to blue environment
2. Run smoke tests
3. Switch traffic to blue
4. Keep green as backup
5. Decommission green after verification

## Future Evolution

### v1.0 (Current)
- Basic RLS (application-level)
- Rate limiting
- CORS
- Docker deployment
- GitHub Actions CI/CD

### v2.0 (Planned)
- Proper RLS with auth.uid()
- Prometheus + Grafana monitoring
- Automated database backups
- Blue-green deployments
- Kubernetes (if scaling needed)

### v3.0 (Vision)
- Multi-region deployment
- Auto-scaling
- Distributed tracing
- Chaos engineering
- GitOps with ArgoCD

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
- [CI/CD Documentation](/.github/workflows/README.md)
- [Deployment Guide](/scripts/prod/README.md)
