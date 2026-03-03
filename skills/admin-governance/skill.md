# Skill: admin-governance

**Status:** Active
**Risk Level:** High
**Owner:** Security Team
**Last Updated:** 2026-02-27

---

## Purpose

Admin panel for system administration, user management, monitoring, audit logs, and governance. Provides privileged access for system administrators to manage users and monitor system health.

## Business Value

- **System Control:** Admins can manage users and system settings
- **Monitoring:** System health and usage statistics
- **Security:** Audit logging for compliance
- **Support:** Admin can help users with account issues
- **Impact if Failed:** No admin oversight; potential security risks

## Boundaries

### In Scope
- User management (list, view, create, update, delete)
- System statistics and monitoring
- Audit logs (future)
- User data export (for support)
- Admin role enforcement

### Out of Scope
- User authentication → `authentication` skill
- Regular user self-service → `users-profile` skill
- System infrastructure monitoring → `infrastructure-platform` skill

## Core Responsibilities

1. **Enforce admin access** via @admin_required decorator
2. **Provide user CRUD** for admins
3. **Display system statistics** (users, transactions, storage)
4. **Export user data** for support/compliance
5. **Log admin actions** for audit (future)
6. **Manage system settings** (future)

## User Journeys

### Journey 1: View System Stats
1. Admin logs in
2. Admin navigates to Admin Dashboard
3. Frontend sends GET /api/stats
4. Backend aggregates system statistics
5. Admin sees user count, transaction count, storage usage

### Journey 2: Manage User
1. Admin searches for user
2. Frontend sends GET /api/users
3. Admin views user details
4. Admin updates user info or deletes account
5. System logs admin action

### Journey 3: Export User Data
1. Support request for user data
2. Admin navigates to user page
3. Admin clicks "Export Data"
4. Backend generates JSON export
5. Admin downloads file for support

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Non-admin access | Critical: Security breach | Strict role checks; audit all access |
| Mass user deletion | Critical: Data loss | Require confirmation; soft delete first |
| Audit log tampering | High: No accountability | Immutable audit logs; external logging |
| Stats query timeout | Low: Dashboard slow | Add indexes; cache results |

## Dependencies

### Upstream
- `authentication` — Admin role check (is_admin flag)
- `users-profile` — User CRUD operations

### Downstream
- All skills — Potential audit logging target

## Code Map

### Backend
- **Routes:** `backend/routes/admin.py`
- **Middleware:** `@admin_required` decorator in `backend/utils/auth_utils.py`

### Frontend
- **Pages:** `frontend/src/pages/admin/*`

### Database
- **Tables:** Reads from `users`, `transactions`, `accounts`, `categories`
- **Future:** `audit_logs`, `system_settings`

## Security Considerations

- ALL endpoints require @admin_required decorator
- Log all admin actions (user CRUD, data exports)
- Rate limit admin endpoints (prevent abuse)
- Admin flag cannot be self-granted (only DB update)
- Use separate admin UI (different route prefix)

## Observability Plan

### Logs
- Admin login (admin_id, ip_address)
- User CRUD (admin_id, action, target_user_id)
- Data export (admin_id, user_id, export_type)
- Admin access denied (user_id, attempted_endpoint)

### Metrics
- `admin.actions.count` — Total admin actions
- `admin.users_created.count` — Users created by admins
- `admin.users_deleted.count` — Users deleted by admins
- `admin.exports.count` — Data exports

## Future Evolution

### v1.0 (Current)
- Basic user management
- System statistics
- Admin role enforcement

### v2.0 (Planned)
- Audit logs table
- System settings management
- Bulk user operations
- Advanced search/filtering
- User impersonation (for support)

### v3.0 (Vision)
- Role-based access control (RBAC)
- Fine-grained permissions
- Admin team collaboration
- Automated alerts (anomaly detection)
- Compliance reports (GDPR, LGPD)

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
