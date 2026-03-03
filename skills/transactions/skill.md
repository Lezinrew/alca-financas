# Skill: transactions

**Status:** Active
**Risk Level:** 🔴 High
**Owner:** Core Finance Team
**Last Updated:** 2026-02-27

---

## Purpose

Core financial ledger managing all income and expense transactions, including installment payments, recurring transactions, transaction status tracking, and bulk imports.

## Business Value

- **Core Business Logic:** Foundation of the entire finance platform
- **Data Integrity:** Source of truth for all financial data
- **User Trust:** Accurate transaction tracking is critical for user trust
- **Impact if Failed:** Complete loss of financial tracking functionality

## Boundaries

### In Scope
- Transaction CRUD operations (create, read, update, delete)
- Transaction types: income, expense
- Transaction status: paid, pending, overdue, cancelled
- Installment tracking (e.g., 3/12 installments)
- Recurring transactions flagging
- Transaction filtering (by date, category, account, status)
- Bulk CSV import
- Transaction amount validation
- Transaction date management

### Out of Scope
- Account balance calculation → `accounts` skill manages balances
- Category assignment logic → `categories` skill provides categories
- AI-powered categorization → `ai-insights` skill
- Report generation → `reports` skill consumes transaction data
- Budget enforcement → `budgets` skill (future)

## Core Responsibilities

1. **Store transaction records** with amount, type, date, description
2. **Validate business rules** (amount sign, date validity, status consistency)
3. **Manage transaction lifecycle** (create → paid/pending → overdue → cancelled)
4. **Support installments** (track current/total installments, link to parent)
5. **Enable bulk imports** (CSV parsing, validation, batch insert)
6. **Provide filtering** (date range, category, account, status)
7. **Maintain referential integrity** (user_id, category_id, account_id)

## User Journeys

### Journey 1: Create Single Transaction
1. User clicks "New Transaction"
2. User fills form: description, amount, type (income/expense), category, account, date, status
3. Frontend validates input
4. User submits
5. Backend validates business rules (amount sign, date)
6. Backend inserts transaction into database
7. Backend updates account balance (if applicable)
8. User sees transaction in list

### Journey 2: Import Transactions from CSV
1. User uploads CSV file
2. Backend parses CSV rows
3. Backend validates each row
4. Backend auto-detects categories/accounts (ai-insights)
5. Backend inserts transactions in batch
6. User sees import summary (N imported, M errors)

### Journey 3: Edit Transaction
1. User clicks "Edit" on transaction
2. User modifies fields
3. Backend validates changes
4. Backend updates transaction
5. Backend recalculates account balance (if amount or account changed)
6. User sees updated transaction

### Journey 4: Filter Transactions
1. User selects filters: month, year, category, account, status
2. Frontend sends GET /api/transactions with query params
3. Backend applies filters to query
4. Backend returns filtered transactions
5. User sees filtered list

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Incorrect amount sign | 🔴 Critical: Income/expense flipped | Validate amount sign matches type in service layer |
| Balance out of sync | 🔴 High: Account balance incorrect | Recalculate balance on each transaction change; periodic audit |
| CSV import partial failure | 🟡 Medium: Some transactions missing | Atomic import (all or nothing) or detailed error reporting |
| Duplicate transactions | 🟡 Medium: Inflated balances | Import deduplication (check description + amount + date) |
| Orphaned transactions | 🟡 Medium: Category/account deleted | ON DELETE SET NULL foreign keys; UI handles null gracefully |
| Date in future (paid status) | 🟡 Medium: Inconsistent state | Validate paid transactions cannot have future dates |

## Dependencies

### Upstream
- `users-profile` — Transaction ownership (user_id)
- `accounts` — Account reference (account_id), balance updates
- `categories` — Category reference (category_id)
- `imports-integrations` — CSV import logic
- `ai-insights` — Auto-categorization

### Downstream
- `dashboard` — Aggregates transactions for KPIs
- `reports` — Queries transactions for reports
- `budgets` (future) — Compares transactions to budgets

## Code Map

### Backend
- **Routes:** `backend/routes/transactions.py`
- **Services:** `backend/services/transaction_service.py`
- **Repositories:** `backend/repositories/transaction_repository_supabase.py`

### Frontend
- **Components:** `frontend/src/components/dashboard/TransactionsList.tsx`, `frontend/src/components/transactions/*`
- **Pages:** `frontend/src/pages/Transactions.tsx`

### Database
- **Tables:** `transactions`
- **Migrations:** `backend/database/schema.sql`

## Security Considerations

- All queries filtered by `user_id` from JWT (users can only see own transactions)
- Amount validation to prevent large/negative values
- Input sanitization for description field (prevent XSS)
- Rate limiting on bulk import endpoint

## Observability Plan

### Logs
- Transaction created/updated/deleted (user_id, transaction_id, amount, type)
- Bulk import started/completed (user_id, row_count, success_count, error_count)
- Validation errors (transaction_id, field, error)

### Metrics
- `transactions.created.count` — Total transactions created
- `transactions.import.count` — CSV imports executed
- `transactions.import.rows.count` — Total rows imported
- `transactions.import.errors.count` — Import errors
- `transactions.query.duration.ms` — Query performance

### Traces
- Transaction create flow: Validate → Insert → Update balance
- CSV import flow: Parse → Validate → Detect categories → Batch insert

## Future Evolution

### v1.0 (Current)
- Basic CRUD
- CSV import
- Installment tracking
- Status management

### v2.0 (Planned)
- Recurring transactions (auto-create monthly)
- Transaction attachments (receipts, invoices)
- Transaction splits (shared expenses)
- Transaction rules (auto-categorize based on patterns)

### v3.0 (Vision)
- Real-time sync across devices
- Bank integration (Plaid, Open Banking)
- AI-powered fraud detection
- Transaction disputes/notes

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
