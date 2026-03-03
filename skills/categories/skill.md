# Skill: categories

**Status:** Active
**Risk Level:** Low
**Owner:** Core Finance Team
**Last Updated:** 2026-02-27

---

## Purpose

Categorization of income and expenses with support for custom categories, icons, colors, and essential/non-essential flagging. Enables users to organize and analyze their financial transactions by meaningful categories.

## Business Value

- **Financial Insight:** Users can understand spending patterns by category
- **Organization:** Clear categorization improves transaction management
- **Budget Foundation:** Categories are the basis for future budgeting features
- **Impact if Failed:** Users cannot effectively analyze or organize transactions

## Boundaries

### In Scope
- Category CRUD operations (create, read, update, delete)
- Category types: income, expense
- Category metadata: name, color, icon, description
- Essential vs non-essential flagging (for expense prioritization)
- Active/inactive category status
- Category import/export

### Out of Scope
- Transaction categorization logic → `transactions` skill
- AI-powered category suggestion → `ai-insights` skill
- Budget limits per category → `budgets` skill (future)
- Category analytics → `reports` skill

## Core Responsibilities

1. **Store category records** with name, type, metadata
2. **Validate category data** (name required, valid type)
3. **Support category filtering** by type (income/expense)
4. **Manage category lifecycle** (active/inactive)
5. **Provide category list** for transaction assignment
6. **Auto-detect categories** during CSV import (AI-powered)

## User Journeys

### Journey 1: Create Category
1. User clicks "New Category"
2. User fills form: name, type, color, icon, essential flag
3. Frontend validates input
4. Backend creates category record
5. User sees category in list

### Journey 2: Categorize Transaction
1. User creates/edits transaction
2. User selects category from dropdown
3. Frontend shows categories filtered by transaction type
4. Backend validates category exists and matches type
5. Transaction saved with category_id

### Journey 3: View Categories
1. User navigates to Categories page
2. Backend fetches all user categories
3. Frontend displays categories grouped by type
4. User can filter by income/expense

### Journey 4: Auto-Detect Category
1. User imports CSV with transaction descriptions
2. AI service analyzes descriptions
3. System suggests matching categories
4. User reviews and confirms suggestions
5. Transactions saved with detected categories

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Duplicate category names | Low: User confusion | Allow duplicates; display type + name together |
| Category deletion with transactions | Medium: Orphaned transactions | ON DELETE SET NULL; UI handles null gracefully |
| Essential flag misuse | Low: Budget analysis inaccurate | Provide clear UI guidance on essential vs non-essential |
| AI detection errors | Low: Wrong categories | Always allow manual override; learn from corrections |

## Dependencies

### Upstream
- `users-profile` — Category ownership (user_id)
- `ai-insights` — Category detection during import

### Downstream
- `transactions` — References category_id
- `dashboard` — Category breakdown charts
- `reports` — Category-based reports

## Code Map

### Backend
- **Routes:** `backend/routes/categories.py`
- **Services:** `backend/services/category_service.py`, `backend/services/category_detector.py`
- **Repositories:** `backend/repositories/category_repository_supabase.py`

### Frontend
- **Components:** `frontend/src/components/categories/*`

### Database
- **Tables:** `categories`
- **Migrations:** `backend/database/schema.sql`

## Security Considerations

- All queries filtered by `user_id` from JWT
- Users can only access own categories
- Category deletion requires checking transaction references
- No sensitive data stored in categories

## Observability Plan

### Logs
- Category created/updated/deleted (user_id, category_id, name, type)
- Category detection hits (import_id, description, detected_category)

### Metrics
- `categories.total.count` — Total categories per user
- `categories.by_type.count` — Categories by type
- `categories.detection.accuracy` — AI detection accuracy
- `categories.most_used.count` — Most frequently used categories

## Future Evolution

### v1.0 (Current)
- Basic CRUD
- Essential flagging
- AI-powered detection

### v2.0 (Planned)
- Category hierarchy (subcategories)
- Category rules (auto-assign based on patterns)
- Category templates (pre-defined sets)
- Category sharing (public category library)

### v3.0 (Vision)
- Smart category suggestions based on merchant
- Category merge/split tools
- Category analytics dashboard
- Category-based alerts

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
