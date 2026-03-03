# Skills Registry — Alça Finanças

**Last Updated:** 2026-02-27
**Purpose:** Complete mapping of skills to code locations, APIs, database, and dependencies.

---

## Registry Table

| Skill | Purpose | Risk Level | Dependencies | Status |
|-------|---------|------------|--------------|--------|
| **authentication** | User auth (JWT, OAuth, Supabase Auth) | 🔴 High | users-profile | ✅ Active |
| **users-profile** | User profile, settings, preferences | 🟡 Medium | authentication | ✅ Active |
| **tenant-core** | Multi-tenant model (tenants, membership, tenant_id, RLS helpers) | 🔴 High | authentication, users-profile, infrastructure-platform | ⚠️ Planned / in rollout |
| **accounts** | Financial accounts management | 🟡 Medium | users-profile, tenant-core, transactions | ✅ Active |
| **categories** | Income/expense categorization | 🟢 Low | users-profile, tenant-core | ✅ Active |
| **transactions** | Core financial ledger | 🔴 High | users-profile, accounts, categories, tenant-core | ✅ Active |
| **dashboard** | KPIs, charts, analytics | 🟢 Low | transactions, accounts, categories, tenant-core | ✅ Active |
| **reports** | Financial reports | 🟢 Low | transactions, accounts, categories, tenant-core | ✅ Active |
| **imports-integrations** | CSV import, auto-detection | 🟡 Medium | transactions, accounts, categories, ai-insights, tenant-core | ✅ Active |
| **notifications** | Email service, alerts | 🟡 Medium | authentication, users-profile, tenant-core | ✅ Active |
| **admin-governance** | Admin panel, audit logs | 🔴 High | users-profile, authentication, tenant-core | ✅ Active |
| **ai-insights** | AI-powered detection | 🟢 Low | categories, accounts | ✅ Active |
| **infrastructure-platform** | RLS, rate limiting, CI/CD | 🔴 High | all | ✅ Active |

---

## Skill: authentication

### Purpose
User authentication flows including JWT, OAuth (Google), Supabase Auth, password recovery, and session management.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/auth.py` (custom JWT auth)
  - `backend/routes/auth_supabase.py` (Supabase Auth integration)
- **Services:**
  - `backend/services/user_service.py`
  - `backend/services/supabase_auth_service.py`
- **Utils:**
  - `backend/utils/auth_utils.py`
  - `backend/utils/auth_utils_supabase.py`
- **Schemas:**
  - `backend/schemas/auth_schemas.py`
- **Middleware:**
  - `backend/utils/auth_utils.py:require_auth` decorator
  - `backend/utils/auth_utils.py:admin_required` decorator

#### Frontend
- **Components:**
  - `frontend/src/components/auth/Login.tsx`
  - `frontend/src/components/auth/Register.tsx`
  - `frontend/src/components/auth/ForgotPassword.tsx`
  - `frontend/src/components/auth/ResetPassword.tsx`
- **Contexts:**
  - `frontend/src/contexts/AuthContext.tsx`
- **Utils:**
  - `frontend/src/utils/api.ts`
  - `frontend/src/utils/tokenStorage.ts`

### API Routes
- `POST /api/auth/register` — Register new user
- `POST /api/auth/login` — Login with email/password
- `POST /api/auth/refresh` — Refresh access token
- `GET /api/auth/me` — Get current user
- `POST /api/auth/logout` — Logout user
- `POST /api/auth/forgot-password` — Request password reset
- `POST /api/auth/reset-password` — Reset password with token
- `GET /api/auth/google/login` — Google OAuth login
- `GET /api/auth/google/callback` — Google OAuth callback
- `GET /api/auth/settings` — Get user settings
- `PUT /api/auth/settings` — Update user settings
- `GET /api/auth/backup/export` — Export user data
- `POST /api/auth/backup/import` — Import user data
- `POST /api/auth/data/clear` — Clear user data

### Database Tables
- `users` (primary)
- `oauth_states` (OAuth flow state)

### RLS Policies
- Users can view/update own data (enforced in application layer)
- Service role bypasses RLS (backend only)

### Observability
- **Logs:** Login attempts, OAuth flows, token refresh, password resets
- **Metrics:** Login success/failure rate, token expiration rate
- **Traces:** Auth flow end-to-end (register → email → login)

### Dependencies
- users-profile (creates/reads user data)
- notifications (password recovery emails)
- infrastructure-platform (rate limiting, CORS)

### Test Coverage
- ✅ Unit tests: JWT generation/validation
- ✅ Integration tests: Login flow, token refresh
- ⚠️  E2E tests: OAuth flow (partial)

---

## Skill: users-profile

### Purpose
User profile management, settings, preferences, and user-specific configuration.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/auth.py` (settings endpoints)
- **Services:**
  - `backend/services/user_service.py`
- **Repositories:**
  - `backend/repositories/user_repository_supabase.py`

#### Frontend
- **Components:**
  - `frontend/src/components/settings/*`
  - `frontend/src/components/Profile.tsx`
- **Contexts:**
  - `frontend/src/contexts/AuthContext.tsx`

### API Routes
- `GET /api/auth/me` — Get user profile
- `GET /api/auth/settings` — Get user settings
- `PUT /api/auth/settings` — Update user settings

### Database Tables
- `users`
  - Columns: `id`, `email`, `name`, `password`, `settings` (JSONB), `auth_providers`, `is_admin`, `profile_picture`, `created_at`, `updated_at`

### Observability
- **Logs:** Profile updates, settings changes
- **Metrics:** Active users, settings usage patterns

### Dependencies
- authentication (user context)

---

## Skill: accounts

### Purpose
Management of financial accounts (bank accounts, credit cards, savings accounts, etc.).

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/accounts.py`
- **Services:**
  - `backend/services/account_service.py`
  - `backend/services/account_detector.py` (auto-detection)
- **Repositories:**
  - `backend/repositories/account_repository_supabase.py`

#### Frontend
- **Components:**
  - `frontend/src/components/accounts/*`
  - `frontend/src/pages/Accounts.tsx`

### API Routes
- `GET /api/accounts` — List user accounts
- `POST /api/accounts` — Create account
- `GET /api/accounts/:id` — Get account details
- `PUT /api/accounts/:id` — Update account
- `DELETE /api/accounts/:id` — Delete account
- `POST /api/accounts/:id/import` — Import transactions to account

### Database Tables
- `accounts`
  - Columns: `id`, `user_id`, `name`, `type`, `color`, `icon`, `balance`, `currency`, `active`, `created_at`, `updated_at`

### RLS Policies
- Users can only access own accounts (filtered by `user_id` in application)

### Observability
- **Logs:** Account creation, balance changes, account deletion
- **Metrics:** Total accounts per user, account types distribution

### Dependencies
- users-profile (account ownership)
- transactions (account balance updates)

---

## Skill: categories

### Purpose
Categorization of income and expenses with support for custom categories, icons, and colors.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/categories.py`
- **Services:**
  - `backend/services/category_service.py`
  - `backend/services/category_detector.py` (AI-powered)
- **Repositories:**
  - `backend/repositories/category_repository_supabase.py`

#### Frontend
- **Components:**
  - `frontend/src/components/categories/*`

### API Routes
- `GET /api/categories` — List categories
- `POST /api/categories` — Create category
- `GET /api/categories/:id` — Get category
- `PUT /api/categories/:id` — Update category
- `DELETE /api/categories/:id` — Delete category
- `POST /api/categories/import` — Import categories

### Database Tables
- `categories`
  - Columns: `id`, `user_id`, `name`, `type` (income/expense), `color`, `icon`, `description`, `active`, `essential`, `created_at`, `updated_at`

### Observability
- **Logs:** Category creation, updates, deletion
- **Metrics:** Categories per user, most used categories

### Dependencies
- users-profile (category ownership)
- ai-insights (category detection)

---

## Skill: transactions

### Purpose
Core financial ledger managing all income and expense transactions, including installments, recurring transactions, and transaction status.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/transactions.py`
- **Services:**
  - `backend/services/transaction_service.py`
- **Repositories:**
  - `backend/repositories/transaction_repository_supabase.py`

#### Frontend
- **Components:**
  - `frontend/src/components/dashboard/TransactionsList.tsx`
  - `frontend/src/components/transactions/*`
  - `frontend/src/pages/Transactions.tsx`

### API Routes
- `GET /api/transactions` — List transactions (with filters: month, year, type, status, category, account)
- `POST /api/transactions` — Create transaction
- `GET /api/transactions/:id` — Get transaction
- `PUT /api/transactions/:id` — Update transaction
- `DELETE /api/transactions/:id` — Delete transaction
- `POST /api/transactions/import` — Bulk import transactions (CSV)

### Database Tables
- `transactions`
  - Columns: `id`, `user_id`, `category_id`, `account_id`, `description`, `amount`, `type` (income/expense), `date`, `status` (paid/pending/overdue/cancelled), `responsible_person`, `is_recurring`, `installment_info` (JSONB), `tags`, `notes`, `created_at`, `updated_at`

### Invariants
- **Amount Sign:** Expenses must be negative, income must be positive (enforced in service layer)
- **Date Validity:** Transaction date cannot be in the future for paid transactions
- **Status Consistency:** Cancelled transactions cannot be edited
- **Installment Integrity:** Installment current <= total

### Observability
- **Logs:** Transaction CRUD, bulk imports, status changes
- **Metrics:** Transactions per day, average transaction amount, import success rate
- **Traces:** Import flow (CSV → validation → batch insert)

### Dependencies
- users-profile (transaction ownership)
- accounts (account_id reference)
- categories (category_id reference)
- imports-integrations (CSV import)

---

## Skill: dashboard

### Purpose
High-level financial overview with KPIs, charts, and analytics.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/dashboard.py`

#### Frontend
- **Components:**
  - `frontend/src/components/dashboard/*`
  - `frontend/src/pages/Dashboard.tsx`

### API Routes
- `GET /api/dashboard` — Get dashboard data (KPIs, charts)
- `GET /api/dashboard-advanced` — Advanced dashboard metrics
- `GET /api/dashboard-settings` — Get dashboard settings
- `PUT /api/dashboard-settings` — Update dashboard settings

### Observability
- **Logs:** Dashboard loads, settings changes
- **Metrics:** Dashboard load time, most viewed widgets

### Dependencies
- transactions (aggregate data)
- accounts (balance aggregation)
- categories (category breakdown)

---

## Skill: reports

### Purpose
Generate financial reports with historical comparisons, trends, and visualizations.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/reports.py`
- **Services:**
  - `backend/services/report_service.py`

#### Frontend
- **Components:**
  - `frontend/src/components/Reports.tsx`
  - `frontend/src/pages/Reports.tsx`

### API Routes
- `GET /api/overview` — Financial overview report
- `GET /api/evolution` — Evolution report (trends over time)
- `GET /api/comparison` — Comparison report (period vs period)

### Observability
- **Logs:** Report generation requests
- **Metrics:** Report generation time, most requested report types

### Dependencies
- transactions (data source)
- accounts (account filtering)
- categories (category filtering)

---

## Skill: imports-integrations

### Purpose
Import transactions from external sources (CSV), auto-detect accounts and categories.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/transactions.py:import` endpoint
  - `backend/routes/accounts.py:import` endpoint
  - `backend/routes/categories.py:import` endpoint
- **Services:**
  - `backend/services/import_service.py`
  - `backend/services/account_detector.py`
  - `backend/services/category_detector.py`

### API Routes
- `POST /api/transactions/import` — Import transactions from CSV
- `POST /api/accounts/:id/import` — Import transactions to specific account
- `POST /api/categories/import` — Import categories

### Observability
- **Logs:** Import requests, validation errors, auto-detection hits
- **Metrics:** Import success rate, records processed per import, auto-detection accuracy

### Dependencies
- transactions (creates transactions)
- accounts (creates/detects accounts)
- categories (creates/detects categories)
- ai-insights (uses AI detection services)

---

## Skill: notifications

### Purpose
Send notifications via email (password recovery, alerts, reminders).

### Code Locations

#### Backend
- **Services:**
  - `backend/services/email_service.py`

### Observability
- **Logs:** Email sent, email failures
- **Metrics:** Email delivery rate, average send time

### Dependencies
- authentication (password recovery emails)
- users-profile (user email address)

---

## Skill: admin-governance

### Purpose
Admin panel for user management, system monitoring, audit logs, and governance.

### Code Locations

#### Backend
- **Routes:**
  - `backend/routes/admin.py`
- **Middleware:**
  - `@admin_required` decorator

#### Frontend
- **Components:**
  - `frontend/src/pages/admin/*`

### API Routes
- `GET /api/stats` — System statistics
- `GET /api/users` — List all users (admin only)
- `POST /api/users` — Create user (admin only)
- `GET /api/users/:id/details` — Get user details
- `PUT /api/users/:id` — Update user
- `DELETE /api/users/:id` — Delete user
- `GET /api/logs` — Get audit logs
- `GET /api/users/:id/export` — Export user data

### Database Tables
- `users` (reads all users)

### Security
- **Admin Check:** `is_admin` flag in users table
- **Audit Logging:** All admin actions logged

### Observability
- **Logs:** Admin actions (user CRUD, data exports)
- **Metrics:** Admin actions per day, user creation rate

### Dependencies
- authentication (admin role check)
- users-profile (user CRUD operations)

---

## Skill: ai-insights

### Purpose
AI-powered detection and insights for categories and accounts using pattern matching and ML.

### Code Locations

#### Backend
- **Services:**
  - `backend/services/category_detector.py`
  - `backend/services/account_detector.py`

### Observability
- **Logs:** Detection requests, detection results
- **Metrics:** Detection accuracy, detection latency

### Dependencies
- categories (detection target)
- accounts (detection target)

---

## Skill: infrastructure-platform

### Purpose
Cross-cutting concerns including RLS, rate limiting, CORS, monitoring, CI/CD, deployment.

### Code Locations

#### Backend
- **Config:**
  - `backend/app.py` (CORS, rate limiting, OAuth)
  - `backend/extensions.py` (limiter)
  - `backend/gunicorn.conf.py`
- **Database:**
  - `backend/database/schema.sql` (RLS policies)
  - `backend/database/migrations/` (RLS updates, tenant migrations `006`–`009`)

#### CI/CD
- `.github/workflows/ci.yml`
- `.github/workflows/deploy-production.yml`

#### Infra
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `nginx.conf`
- `scripts/prod/` (deployment scripts)

### Security
- **RLS:** Row Level Security policies (currently `USING (true)` - needs improvement)
- **Rate Limiting:** Flask-Limiter on critical endpoints
- **CORS:** Configurable origins via env vars

### Observability
- **Logs:** Infrastructure events, deployment logs
- **Metrics:** Request rate, response time, error rate
- **Traces:** End-to-end request traces

### Dependencies
- All skills (provides infrastructure for all)

---

## Skill: tenant-core

### Purpose

Provide a consistent multi-tenant model (Tenant = Organization) with:

- `tenants` and `tenant_members` tables.
- `tenant_id` on domain tables.
- RLS helpers for tenant-aware isolation.

### Code Locations

#### Database

- `backend/database/schema.sql`
  - Current single-tenant schema (`user_id` on categories/accounts/transactions).
- `backend/database/migrations/006_create_tenants.sql`
  - Creates `tenants` and `tenant_members`.
- `backend/database/migrations/007_add_tenant_id_columns.sql`
  - Adds nullable `tenant_id` to `categories`, `accounts`, `transactions`.
- `backend/database/migrations/008_backfill_tenant_data.sql`
  - Creates default tenants and backfills `tenant_id` via `tenant_members`.
- `backend/database/migrations/009_tenant_rls_policies.sql`
  - Defines `current_tenant_id()` helper and enables RLS on tenant tables.

#### Docs

- `docs/04-database/tenancy.md`
  - Design and migration plan for multi-tenancy and RLS.

### Observability

- **Logs:** Tenant creation, membership changes, and (future) RLS-related errors.
- **Metrics (future):** Number of tenants per user, requests per tenant.

### Dependencies

- authentication (identity & tokens)
- users-profile (base user entity for membership)
- infrastructure-platform (RLS engine, migration/CI pipeline)


---

## Maintenance Notes

### Adding a New Skill
1. Add row to registry table above
2. Create skill folder: `skills/<skill-name>/`
3. Update [SKILLS_DEPENDENCY_GRAPH.mmd](./SKILLS_DEPENDENCY_GRAPH.mmd)
4. Add entry in [README.md](./README.md)
5. Document contracts (API, DB, events)

### Updating a Skill
1. Update code locations if changed
2. Update API routes if endpoints changed
3. Update dependencies if new dependencies added
4. Update risk level if security posture changed

### Deprecating a Skill
1. Mark as `⚠️  Deprecated` in Status column
2. Add deprecation note with migration path
3. Remove from dependency graph edges (but keep node)
4. Archive skill folder to `skills/deprecated/`

---

**Last Review:** 2026-02-27
**Next Review:** 2026-05-27 (Quarterly)
