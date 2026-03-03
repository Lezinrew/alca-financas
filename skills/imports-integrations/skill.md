# Skill: imports-integrations

**Status:** Active
**Risk Level:** Medium
**Owner:** Integration Team
**Last Updated:** 2026-02-27

---

## Purpose

Import transactions from external sources (CSV files), with AI-powered auto-detection of accounts and categories. Enables users to quickly populate the system with existing financial data.

## Business Value

- **Quick Onboarding:** Users can import years of transaction history
- **Data Migration:** Easy switch from other finance tools
- **Bulk Operations:** Process hundreds of transactions at once
- **Impact if Failed:** Users must manually enter all transactions

## Boundaries

### In Scope
- CSV file parsing and validation
- Transaction bulk import
- Account auto-detection (AI-powered)
- Category auto-detection (AI-powered)
- Import error handling and reporting
- Account-specific imports

### Out of Scope
- Bank API integrations → Future feature
- Real-time sync → Future feature
- PDF/OFX file formats → Future feature
- Transaction storage → `transactions` skill

## Core Responsibilities

1. **Parse CSV files** with various formats (flexible column mapping)
2. **Validate import data** (required fields, data types)
3. **Auto-detect accounts** based on transaction descriptions
4. **Auto-detect categories** using AI pattern matching
5. **Batch insert transactions** efficiently
6. **Report import results** (success count, errors)
7. **Handle partial failures** gracefully

## User Journeys

### Journey 1: Import Transactions from CSV
1. User clicks "Import Transactions"
2. User uploads CSV file
3. Frontend sends file to backend
4. Backend parses CSV rows
5. Backend validates each row
6. Backend auto-detects accounts and categories
7. Backend inserts valid transactions
8. User sees import summary (150 imported, 5 errors)

### Journey 2: Import to Specific Account
1. User navigates to Account page
2. User clicks "Import Transactions"
3. User uploads CSV file
4. Backend imports all transactions to that account
5. User sees transactions added to account

### Journey 3: Auto-Detection
1. System reads transaction description "UBER *RIDE"
2. AI service detects category: "Transportation"
3. System suggests category to user
4. User confirms or overrides
5. Transaction saved with detected category

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Invalid CSV format | High: Import fails | Provide CSV template; show format hints |
| Partial import failure | Medium: Some data lost | Transactional import or detailed error log |
| Detection errors | Low: Wrong categories | Always allow manual override; learn from corrections |
| Large files timeout | High: Import fails | Async processing; progress indicators |
| Duplicate transactions | Medium: Data duplication | Deduplication logic (description + amount + date) |

## Dependencies

### Upstream
- `transactions` — Creates transactions
- `accounts` — References/creates accounts
- `categories` — References/creates categories
- `ai-insights` — Uses detection services

### Downstream
- None (import is a data ingestion service)

## Code Map

### Backend
- **Routes:** `backend/routes/transactions.py:import`, `backend/routes/accounts.py:import`, `backend/routes/categories.py:import`
- **Services:** `backend/services/import_service.py`, `backend/services/account_detector.py`, `backend/services/category_detector.py`

### Frontend
- **Components:** Import modal in transactions/accounts pages

### Database
- No dedicated tables (creates records in transactions, accounts, categories)

## Security Considerations

- File size limits (max 10MB)
- Rate limiting (5 imports per hour)
- Validate file type (CSV only)
- Sanitize input data (prevent SQL injection)
- User can only import to own account

## Observability Plan

### Logs
- Import started (user_id, file_size, row_count)
- Import completed (user_id, success_count, error_count)
- Detection hits (description, detected_category, confidence)

### Metrics
- `imports.count` — Total import operations
- `imports.rows.count` — Total rows processed
- `imports.success_rate` — Success percentage
- `imports.detection.accuracy` — Detection accuracy
- `imports.duration.ms` — Import processing time

## Future Evolution

### v1.0 (Current)
- CSV import
- AI-powered detection
- Basic error handling

### v2.0 (Planned)
- OFX/QFX format support
- Bank API integrations (Plaid, Open Banking)
- Scheduled imports
- Import templates (save column mappings)
- Duplicate detection

### v3.0 (Vision)
- Real-time bank sync
- Email receipt parsing
- Mobile app photo import (scan receipts)
- Machine learning from user corrections

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
