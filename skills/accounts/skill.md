# Skill: accounts

**Status:** Active
**Risk Level:** Medium
**Owner:** Core Finance Team
**Last Updated:** 2026-02-27

---

## Purpose

Management of financial accounts including bank accounts, credit cards, savings accounts, investment accounts, and cash accounts. Handles account creation, balance tracking, and account lifecycle management.

## Business Value

- **Financial Organization:** Users can track multiple accounts in one place
- **Balance Accuracy:** Real-time account balance updates from transactions
- **User Control:** Flexibility to organize accounts by type, color, and icon
- **Impact if Failed:** Users cannot track account balances or organize finances

## Boundaries

### In Scope
- Account CRUD operations (create, read, update, delete)
- Account types: bank, credit card, savings, investment, cash
- Account metadata: name, color, icon, currency
- Account balance tracking
- Active/inactive account status
- Account-specific transaction imports

### Out of Scope
- Balance calculations → Derived from `transactions` skill
- Bank integrations → `imports-integrations` skill
- Account sharing/collaboration → Future feature
- Multi-currency conversion → Future feature

## Core Responsibilities

1. **Store account records** with name, type, balance, metadata
2. **Validate account data** (name required, valid type, valid currency)
3. **Support balance updates** when transactions are created/modified
4. **Enable account filtering** by type, active status
5. **Provide account list** for transaction categorization
6. **Auto-detect accounts** during CSV import (AI-powered)

## User Journeys

### Journey 1: Create Account
1. User clicks "New Account"
2. User fills form: name, type, initial balance, color, icon, currency
3. Frontend validates input
4. Backend creates account record
5. User sees account in list

### Journey 2: View Accounts
1. User navigates to Accounts page
2. Backend fetches all user accounts
3. Frontend displays accounts grouped by type
4. User sees balances for each account

### Journey 3: Update Account Balance
1. User creates/edits transaction
2. Transaction service updates account balance
3. Account balance recalculated
4. User sees updated balance in real-time

### Journey 4: Delete Account
1. User clicks "Delete" on account
2. Frontend shows confirmation dialog
3. Backend marks transactions with null account_id (soft delete)
4. Backend deletes account
5. User sees account removed from list

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Balance out of sync | Critical: Incorrect financial data | Periodic balance reconciliation; audit logs |
| Account deletion with transactions | Medium: Orphaned transactions | ON DELETE SET NULL foreign key; UI handles null |
| Duplicate account names | Low: User confusion | Allow duplicates; display type + name |
| Invalid currency | Low: Display issues | Validate currency codes (ISO 4217) |

## Dependencies

### Upstream
- `users-profile` — Account ownership (user_id)
- `transactions` — Balance updates
- `ai-insights` — Account detection during import

### Downstream
- `transactions` — References account_id
- `dashboard` — Displays account balances
- `reports` — Filters by account

## Code Map

### Backend
- **Routes:** `backend/routes/accounts.py`
- **Services:** `backend/services/account_service.py`, `backend/services/account_detector.py`
- **Repositories:** `backend/repositories/account_repository_supabase.py`

### Frontend
- **Components:** `frontend/src/components/accounts/*`
- **Pages:** `frontend/src/pages/Accounts.tsx`

### Database
- **Tables:** `accounts`
- **Migrations:** `backend/database/schema.sql`

## Security Considerations

- All queries filtered by `user_id` from JWT
- Users can only access own accounts
- Account deletion requires confirmation
- Balance modifications only through transaction service

## Observability Plan

### Logs
- Account created/updated/deleted (user_id, account_id, type)
- Balance updates (account_id, old_balance, new_balance)
- Account detection hits (import_id, detected_account_name)

### Metrics
- `accounts.total.count` — Total accounts per user
- `accounts.by_type.count` — Accounts by type distribution
- `accounts.balance_updates.count` — Balance update frequency

## Future Evolution

### v1.0 (Current)
- Basic CRUD
- Balance tracking
- Auto-detection

### v2.0 (Planned)
- Account sharing (joint accounts)
- Multi-currency support with conversion
- Account statements/history
- Bank integration (Plaid, Open Banking)

### v3.0 (Vision)
- Real-time balance sync
- Account alerts (low balance, unusual activity)
- Account groups (e.g., "Business Accounts")
- Account analytics (spending patterns per account)

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
