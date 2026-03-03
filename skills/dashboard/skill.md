# Skill: dashboard

**Status:** Active
**Risk Level:** Low
**Owner:** Product Team
**Last Updated:** 2026-02-27

---

## Purpose

High-level financial overview dashboard providing KPIs (current balance, income, expenses), charts (area charts, pie charts), recent transactions, and financial insights at a glance.

## Business Value

- **Quick Overview:** Users see financial status immediately upon login
- **Visual Insights:** Charts help users understand spending patterns
- **Actionable Data:** KPIs highlight important metrics
- **Impact if Failed:** Users lose primary navigation point and financial overview

## Boundaries

### In Scope
- Dashboard KPIs (balance, income, expenses, pending count)
- Financial charts (income vs expenses, category breakdown)
- Recent transactions list
- Dashboard settings/preferences
- Period filtering (current month, year)

### Out of Scope
- Data storage → `transactions`, `accounts`, `categories` own the data
- Detailed reports → `reports` skill
- Budget tracking → `budgets` skill (future)
- Transaction editing → `transactions` skill

## Core Responsibilities

1. **Aggregate financial data** from transactions, accounts, categories
2. **Calculate KPIs** (balance, income, expenses, pending)
3. **Generate chart data** for visualization
4. **Fetch recent transactions** for quick access
5. **Support period filtering** (month, year)
6. **Store dashboard preferences** (widget visibility, layout)

## User Journeys

### Journey 1: View Dashboard
1. User logs in or clicks Dashboard
2. Frontend sends GET /api/dashboard
3. Backend aggregates transactions, accounts
4. Backend calculates KPIs and chart data
5. User sees dashboard with KPIs, charts, recent transactions

### Journey 2: Filter by Period
1. User changes period selector to "Last Month"
2. Frontend sends GET /api/dashboard?month=1&year=2026
3. Backend recalculates KPIs for selected period
4. Dashboard updates with filtered data

### Journey 3: Customize Dashboard
1. User clicks "Customize Dashboard"
2. User toggles widget visibility
3. Frontend sends PUT /api/dashboard-settings
4. Dashboard updates with new layout

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Slow aggregation queries | High: Poor UX | Add database indexes; cache results |
| Missing data (no transactions) | Low: Empty dashboard | Show onboarding prompts |
| Chart rendering errors | Medium: Partial display | Fallback to table view |
| KPI calculation errors | High: Wrong numbers | Add validation; log discrepancies |

## Dependencies

### Upstream
- `transactions` — Transaction data for aggregation
- `accounts` — Account balances
- `categories` — Category breakdown

### Downstream
- None (dashboard is read-only consumer)

## Code Map

### Backend
- **Routes:** `backend/routes/dashboard.py`

### Frontend
- **Components:** `frontend/src/components/dashboard/*`
- **Pages:** `frontend/src/pages/Dashboard.tsx`

### Database
- No dedicated tables (queries existing tables)

## Security Considerations

- All queries filtered by `user_id` from JWT
- Users can only see own dashboard data
- No sensitive data exposed beyond user scope

## Observability Plan

### Logs
- Dashboard viewed (user_id, period)
- Dashboard settings updated (user_id, settings)

### Metrics
- `dashboard.load_time.ms` — Dashboard load time
- `dashboard.views.count` — Dashboard view frequency
- `dashboard.query_time.ms` — Query performance

## Future Evolution

### v1.0 (Current)
- Basic KPIs
- Income vs expenses chart
- Category breakdown chart
- Recent transactions

### v2.0 (Planned)
- Customizable widgets
- Budget progress bars
- Spending goals
- Trend indicators (up/down from last month)
- Net worth tracking

### v3.0 (Vision)
- AI-powered insights ("You spent 20% more on dining this month")
- Forecasting (predicted end-of-month balance)
- Custom dashboard layouts (drag-and-drop)
- Multiple dashboard views (personal, business, shared)

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
