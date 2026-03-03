# Skill: reports

**Status:** Active
**Risk Level:** Low
**Owner:** Analytics Team
**Last Updated:** 2026-02-27

---

## Purpose

Generate comprehensive financial reports with historical comparisons, trends, evolution analysis, and visualizations. Provides deep insights into financial data beyond the dashboard overview.

## Business Value

- **Financial Analysis:** Users can analyze spending patterns over time
- **Historical Comparison:** Compare periods to understand changes
- **Trend Identification:** Spot trends in income and expenses
- **Impact if Failed:** Users lose detailed financial analysis capabilities

## Boundaries

### In Scope
- Financial overview reports (income, expenses, net)
- Evolution reports (trends over time)
- Comparison reports (period vs period)
- Category-based analysis
- Account-based filtering
- Exportable report data (JSON, future: PDF)

### Out of Scope
- Raw data storage → `transactions` owns data
- Real-time dashboard → `dashboard` skill
- Budget reports → `budgets` skill (future)
- Tax reports → Future feature

## Core Responsibilities

1. **Generate overview reports** (total income, expenses, net for period)
2. **Calculate evolution trends** (month-over-month, year-over-year)
3. **Compare periods** (current vs previous, custom ranges)
4. **Aggregate by category** (spending breakdown)
5. **Support filtering** (by account, category, date range)
6. **Export reports** (JSON format, future: PDF)

## User Journeys

### Journey 1: View Overview Report
1. User navigates to Reports page
2. User selects date range (e.g., 2026-01 to 2026-12)
3. Frontend sends GET /api/overview
4. Backend aggregates transactions for period
5. User sees total income, expenses, net, charts

### Journey 2: Evolution Report
1. User clicks "Evolution" tab
2. Frontend sends GET /api/evolution
3. Backend calculates month-over-month trends
4. User sees line chart showing income/expense evolution

### Journey 3: Comparison Report
1. User selects two periods to compare
2. Frontend sends GET /api/comparison
3. Backend calculates differences
4. User sees side-by-side comparison with % changes

### Journey 4: Export Report
1. User clicks "Export Report"
2. Backend generates JSON report
3. User downloads file

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Slow aggregation queries | High: Timeout | Add indexes; optimize queries; use caching |
| Large date ranges | Medium: Performance | Limit max range (e.g., 2 years) |
| Missing data periods | Low: Empty report | Show "No data" message |
| Calculation errors | High: Wrong insights | Add validation; log anomalies |

## Dependencies

### Upstream
- `transactions` — Core data source
- `accounts` — Account filtering
- `categories` — Category filtering

### Downstream
- None (reports is read-only consumer)

## Code Map

### Backend
- **Routes:** `backend/routes/reports.py`
- **Services:** `backend/services/report_service.py`

### Frontend
- **Components:** `frontend/src/components/Reports.tsx`
- **Pages:** `frontend/src/pages/Reports.tsx`

### Database
- No dedicated tables (queries existing tables)

## Security Considerations

- All queries filtered by `user_id` from JWT
- Users can only generate reports for own data
- No sensitive data exposed beyond user scope

## Observability Plan

### Logs
- Report generated (user_id, report_type, date_range)
- Report exported (user_id, format)

### Metrics
- `reports.generated.count` — Report generation frequency
- `reports.query_time.ms` — Query performance
- `reports.export.count` — Export frequency

## Future Evolution

### v1.0 (Current)
- Overview reports
- Evolution reports
- Comparison reports

### v2.0 (Planned)
- PDF export
- Email scheduled reports
- Custom report templates
- Tax reports
- Budget vs actual reports

### v3.0 (Vision)
- AI-powered insights
- Predictive analysis
- Anomaly detection
- Benchmarking (compare to similar users)
- Visual report builder

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
