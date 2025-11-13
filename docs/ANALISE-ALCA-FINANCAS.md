Vou analisar o projeto Alça Finanças de forma completa.
  Deixe-me explorar a estrutura do código para fornecer uma
  avaliação precisa.

⏺ Bash(find /Users/lezinrew/Projetos/alca-financas/frontend/src
      -type f -name "*.tsx" -o -name "*.ts" -o -name "*.jsx" -o
      -name "*.js" | grep -v node_modules | sort)
  ⎿ /Users/lezinrew/Projetos/alca-financas/frontend/src/App
    .tsx
    /Users/lezinrew/Projetos/alca-financas/frontend/src/__t
    … +63 lines (ctrl+o to expand)



⏺ Read(frontend/package.json)
  ⎿  Read 56 lines

⏺ Read(frontend/vite.config.js)
  ⎿  Read 19 lines

⏺ Read(frontend/src/main.tsx)
  ⎿  Read 11 lines

⏺ Read(frontend/src/App.tsx)
  ⎿  Read 120 lines

⏺ Read(frontend/src/contexts/AuthContext.tsx)
  ⎿  Read 174 lines

⏺ Read(frontend/src/components/dashboard/Dashboard.tsx)
  ⎿  Read 337 lines

⏺ Read(frontend/src/components/transactions/Transactions.tsx)
  ⎿  Read 224 lines

⏺ Read(frontend/src/i18n/config.ts)
  ⎿  Read 26 lines

⏺ Read(frontend/src/utils/api.ts)
  ⎿  Read 116 lines

⏺ Read(frontend/src/mocks/finance.ts)
  ⎿  Read 165 lines

⏺ Bash(ls -la /Users/lezinrew/Projetos/alca-financas/frontend/sr
      c/i18n/locales/ 2>/dev/null || echo "Directory not found")
  ⎿  total 24                                           
     drwxr-xr-x@ 5 lezinrew  staff   160 Sep  8 11:07 .
     drwxr-xr-x@ 4 lezinrew  staff   128 Sep  9 03:21 ..
     … +6 lines (ctrl+o to expand)

⏺ Bash(find /Users/lezinrew/Projetos/alca-financas/backend -type
       f -name "*.py" | grep -E "(routes|services|models)" |
      head -20)
  ⎿ /Users/lezinrew/Projetos/alca-financas/backend/.venv/li
    b/python3.9/site-packages/charset_normalizer/models.py
    /Users/lezinrew/Projetos/alca-financas/backend/.venv/li
    … +52 lines (ctrl+o to expand)



⏺ Read(backend/app.py)
  ⎿  Read 64 lines

⏺ Bash(find /Users/lezinrew/Projetos/alca-financas/backend -type
       f -name "*.py" | grep -v ".venv" | grep -v "__pycache__"
      | sort)
  ⎿ /Users/lezinrew/Projetos/alca-financas/backend/app.py  
    /Users/lezinrew/Projetos/alca-financas/backend/app_run.
    py
    … +30 lines (ctrl+o to expand)


⏺ Read(README.md)
  ⎿  Read 80 lines

⏺ Agora vou analisar alguns componentes chave para entender
  melhor a estrutura:

⏺ Bash(head -50 /Users/lezinrew/Projetos/alca-financas/frontend/
      src/components/reports/Reports.tsx)
  ⎿  import React, { useState, useEffect } from 'react';
     import { useTranslation } from 'react-i18next';
     import { formatCurrency } from '../../utils/api';
     … +57 lines (ctrl+o to expand)

⏺ Bash(head -50 /Users/lezinrew/Projetos/alca-financas/frontend/
      src/components/accounts/Accounts.tsx)
  ⎿  import React, { useState, useEffect } from 'react';
     import { useTranslation } from 'react-i18next';
     import { formatCurrency } from '../../utils/api';
     … +54 lines (ctrl+o to expand)

⏺ Bash(head -50 /Users/lezinrew/Projetos/alca-financas/backend/r
      outes/dashboard.py)
  ⎿ from flask import Blueprint, request, jsonify, current_
    app
    from datetime import datetime
    … +65 lines (ctrl+o to expand)


⏺ Perfeito! Agora tenho informações suficientes para criar
  uma análise completa. Vou gerar o documento em Markdown
  conforme solicitado.

  Project Overview

  Tech Stack Summary

  Frontend:
  - React 18.2 with TypeScript (migrated from JSX)
  - Vite 4.5 as build tool (port 3000)
  - React Router DOM 6.20 for SPA routing
  - Tailwind CSS 3.4 + shadcn/ui for modern design system
  - Bootstrap 5.3 + Bootstrap Icons (legacy, being migrated)
  - Recharts 3.2 + Chart.js 4.5 for data visualization
  - i18next 23.7 + react-i18next for internationalization
  (PT, EN, ES)
  - Axios 1.6 for HTTP client
  - Vitest 3.2 + Testing Library for unit tests
  - Lucide React for modern icons

  Backend:
  - Flask 3.0 (Python 3.9+) running on port 8001
  - MongoDB (PyMongo) for data persistence
  - JWT (PyJWT) for authentication
  - bcrypt for password hashing
  - Flask-CORS for cross-origin support
  - Authlib for OAuth 2.0 (Google, Microsoft, Apple)
  - Modular architecture with Blueprints (routes) and
  Services

  Routing Organization

  Frontend Routing (React Router DOM):
  - Public Routes: /login, /register (redirect to /dashboard
   if authenticated)
  - Protected Routes: All require authentication, redirect
  to /login if not
    - /dashboard - Main overview with KPIs and charts
    - /transactions - Full CRUD for income/expenses
    - /categories - Category management
    - /accounts - Bank accounts management
    - /reports - Analytics and custom reports
    - /settings - User preferences
    - /profile - User profile
    - /import - CSV import for transactions

  Backend API Structure (Flask Blueprints):
  - /api/auth/* - Authentication (login, register, OAuth,
  settings)
  - /api/categories - Category CRUD
  - /api/transactions - Transaction CRUD + CSV import
  - /api/accounts - Account CRUD
  - /api/dashboard - Dashboard data aggregation
  - /api/reports/* - Reporting and analytics

  State and Data Flow

  Authentication State:
  - AuthContext (React Context API) manages user session
  globally
  - Stores JWT token + user data in localStorage
  - Token automatically attached to all API requests via
  Axios interceptor
  - Supports traditional login + "AI Login" (demo mode with
  mock credentials)
  - Auto-logout on 401 responses

  Data Flow:
  - API Layer: Centralized in src/utils/api.ts with typed
  functions
  - Service Layer (Backend): Business logic separated from
  routes
    - user_service.py, category_service.py,
  transaction_service.py, etc.
  - Mock Data: src/mocks/finance.ts provides demo financial
  data for Dashboard
  - No Global State Management: Components use local state +
   Context for auth only
  - Loading/Error States: Handled per component with local
  state

  i18n Configuration

  Setup (src/i18n/config.ts):
  - i18next with react-i18next and LanguageDetector
  - 3 Languages: Portuguese (default/fallback), English,
  Spanish
  - Translation Files: src/i18n/locales/{pt,en,es}.json
  - Auto-detects browser language, falls back to PT-BR
  - Used throughout the app with useTranslation() hook

  ---
  Implemented Features

  Existing Pages and Functionality

  ✅ Authentication & User Management

  - Login Page (src/components/auth/Login.tsx)
    - Traditional email/password login
    - "AI Login" button for instant demo access
    - OAuth 2.0 integration (Google, Microsoft, Apple) via
  backend
    - Modern UI with Tailwind + shadcn/ui components
  - Register Page (src/components/auth/Register.tsx)
    - User registration with name, email, password
    - Form validation and error handling
  - Profile Page (src/components/profile/Profile.tsx)
    - User profile editing
  - Settings Page (src/components/settings/Settings.tsx)
    - User preferences configuration

  ✅ Dashboard

  - Dashboard Page (src/components/dashboard/Dashboard.tsx)
    - 4 KPI Cards: Current Balance, Income, Expenses, Open
  Tickets
    - Area Chart: Income vs Expenses (last 12 months) using
  Recharts
    - Pie Chart: Expense distribution by category
    - Recent Transactions List: Last 5 transactions with
  type indicators
    - Mock Data Integration: Uses generateFinancialData()
  from mocks/finance.ts
    - Responsive Design: Grid layout adapts to
  mobile/tablet/desktop
    - Loading States: Skeleton screens during data load
    - User Greeting: Displays logged-in user name and email

  ✅ Transactions Management

  - Transactions Page
  (src/components/transactions/Transactions.tsx)
    - Full CRUD operations (Create, Read, Update, Delete)
    - Filters: Month, Year, Category, Type (Income/Expense)
    - TransactionForm (modal) for add/edit
    - TransactionList component displays all transactions
    - Integrates with backend API (/api/transactions)
    - Confirmation dialog for delete operations

  ✅ Categories Management

  - Categories Page
  (src/components/categories/Categories.tsx)
    - CRUD for income/expense categories
    - CategoryForm component for add/edit
    - Supports icon and color customization
    - Backend integration via /api/categories

  ✅ Accounts Management

  - Accounts Page (src/components/accounts/Accounts.tsx)
    - Manage bank accounts (wallet, checking, savings,
  credit card, investment)
    - AccountCard displays each account with balance
    - AccountForm for creating/editing accounts
    - Track initial balance and current balance
    - Institution name and custom colors/icons

  ✅ Reports & Analytics

  - Reports Page (src/components/reports/Reports.tsx)
    - Customizable report types:
        - Expenses by category
      - Expenses by account
      - Income by category
      - Income by account
      - Balance by account
    - Multiple chart types: Pie, Doughnut, Bar, Line
    - ReportFilters component for month/year/type selection
    - ReportChart renders Chart.js visualizations
    - Backend integration via /api/reports/overview

  ✅ CSV Import

  - Import Page (src/components/import/Import.tsx)
    - Upload CSV files with transactions
    - Bulk import functionality via /api/transactions/import

  ✅ Backend Services

  - auth.py: Login, register, OAuth flows, JWT generation,
  password reset
  - categories.py: Category CRUD with user isolation
  - transactions.py: Transaction CRUD + CSV import +
  filtering
  - accounts.py: Account management
  - dashboard.py: Aggregated data for dashboard (KPIs,
  charts)
  - reports.py: Custom reporting with various aggregations

  ✅ UI Components (shadcn/ui)

  - Button (src/components/ui/button.tsx)
  - Card (src/components/ui/card.tsx)
  - Input (src/components/ui/input.tsx)
  - Modern, accessible components with variants

  ✅ Testing Setup

  - Vitest configured with jsdom
  - Testing Library for React component tests
  - Example test: src/__tests__/AuthContext.test.tsx
  - Test scripts: npm run test, npm run test:ui, npm run 
  test:run

  ---
  Gaps and Missing Parts

  Missing Screens / Flows

  🔴 Critical Missing Features for Alça Finanças MVP:

  1. Monthly Finance Overview / Checklist (Core Product
  Goal)
    - No dedicated "Monthly View" showing:
        - What has been paid this month
      - What is pending (upcoming bills)
      - What is overdue
      - What must be prioritized
    - Missing "checklist" UI for marking bills as paid
    - No visual distinction between paid/pending/overdue
  items
  2. Fixed Expenses Management
    - No dedicated screen/section for recurring monthly
  expenses
    - Cannot mark expenses as "fixed" vs "variable"
    - No automatic recurrence setup for rent, subscriptions,
   utilities, etc.
  3. Debts & Installments Tracking
    - No debt management feature
    - Cannot track installment payments (e.g., 3/12 paid)
    - No interest calculation or amortization schedule
    - No "remaining installments" indicator
  4. Responsibility Assignment (Leandro/Glenda)
    - Cannot assign transactions/expenses to specific people
    - No "responsible person" field in transactions
    - No filtering by responsible person
    - Missing "Who pays what?" view for couples/households
  5. Budget & Goals
    - No monthly budget setting per category
    - No budget vs actual spending comparison
    - No overspending alerts or indicators
    - No financial goals feature
  6. Pending Payments Queue
    - No prioritized list of upcoming payments
    - No sorting by due date or priority
    - No "pay next" recommendations

  UX Gaps

  7. Cash Flow Projection
    - Dashboard shows historical data but no future
  projections
    - No "expected balance" at end of month
    - No income/expense forecast based on recurring items
  8. Payment Status Indicators
    - Transactions don't have status field
  (paid/pending/overdue/cancelled)
    - No visual badges or color coding for status
    - No "Mark as Paid" quick action
  9. Monthly Summary Card
    - No summary widget showing:
        - Total fixed expenses this month
      - Total variable expenses this month
      - Total income this month
      - Net cash flow (income - expenses)
  10. Category Presets
    - No default categories for Alça Finanças use case:
        - Housing (Moradia), Health (Saúde), Communication
  (Comunicação)
      - Digital, Financial (Financeiro), Transportation,
  Education, etc.
    - Users must manually create all categories

  Technical Gaps

  11. Environment Configuration
    - .env.example exists but no clear documentation
    - REACT_APP_BACKEND_URL hardcoded in some places
    - No env variable validation on startup
  12. Error Handling & User Feedback
    - Generic error messages ("Erro ao carregar transações")
    - No toast/notification system for success/error
  feedback
    - No retry mechanism on failed API calls
    - No offline support or connection status indicator
  13. Loading States Inconsistency
    - Some components have skeleton loaders (Dashboard)
    - Others use generic spinners (Transactions)
    - No unified loading UX pattern
  14. Form Validation
    - Basic validation in forms but no schema validation
  (e.g., Zod, Yup)
    - No real-time validation feedback
    - Error messages not always user-friendly
  15. API Response Types
    - Backend responses not fully typed in frontend
    - Mix of any types in API layer
    - No API contract/schema validation (e.g.,
  OpenAPI/Swagger)
  16. Date Handling
    - Inconsistent date formats across components
    - No timezone handling
    - No date range picker for filtering
  17. Pagination
    - Transactions list loads all at once (no pagination)
    - Performance issue with large datasets
    - No infinite scroll or "Load More" button
  18. Search & Filtering
    - No search bar in Transactions page
    - Cannot search by description or amount range
    - Filters are basic (only month, year, category, type)
  19. Data Export
    - No export to CSV/PDF from Reports or Transactions
    - Cannot generate monthly statements
    - No print-friendly views
  20. Accessibility
    - No keyboard navigation hints
    - Missing ARIA labels in some components
    - No screen reader testing
    - No focus management in modals
  21. Performance Optimization
    - No code splitting (all routes load upfront)
    - No lazy loading for heavy components (Charts)
    - No image optimization
    - No bundle size analysis in build
  22. Security Enhancements
    - No CSRF protection mentioned
    - Password strength indicator missing
    - No rate limiting on API endpoints
    - No input sanitization on backend (SQL/NoSQL injection
  risk)
  23. Testing Coverage
    - Only 1 test file (AuthContext.test.tsx)
    - No tests for components, API layer, or utils
    - No E2E tests (Playwright, Cypress)
    - No backend tests
  24. Documentation
    - No API documentation (OpenAPI/Swagger)
    - No component Storybook
    - No developer onboarding guide
    - No architecture diagrams
  25. Multi-Account Support
    - Transactions don't link to specific accounts
    - No account balance updates on transaction
  create/delete
    - No inter-account transfers
  26. Recurring Transactions
    - No recurrence field in transaction model
    - Cannot set up automatic monthly bills
    - No "clone transaction" feature for recurring items

  ---
  Alça Finanças – MVP Workflow

  1. Foundation & Architecture

  - Add Transaction Status Field (Priority: High)Extend
  transaction model with status: 'paid' | 'pending' | 
  'overdue' | 'cancelled'. Update backend
  (backend/routes/transactions.py,
  backend/services/transaction_service.py) and frontend
  types (src/utils/api.ts).
  - Add Responsible Person Field (Priority: High)Add
  responsible_person: string to transactions and fixed
  expenses (e.g., "Leandro", "Glenda", "Both"). Update DB
  schema, API, and frontend forms.
  - Add Recurrence/Fixed Expense Flag (Priority: High)Add
  is_recurring: boolean, recurrence_type: 'monthly' | 
  'yearly' | 'weekly' | null, recurrence_day: number to
  transactions. Backend service to auto-generate recurring
  transactions monthly.
  - Add Debt & Installments Model (Priority: High)Create new
   debts collection in MongoDB with fields: name,
  total_amount, installments_total, installments_paid,
  monthly_payment, interest_rate, responsible_person,
  due_day. Backend routes: backend/routes/debts.py.
  - Environment Variable Documentation (Priority:
  Medium)Document all required env vars in README.md and
  .env.example. Add validation on app startup (frontend and
  backend) to check for missing vars.
  - Setup OpenAPI/Swagger for API Documentation (Priority:
  Medium)Integrate flask-swagger-ui or flasgger in backend.
  Document all endpoints with request/response schemas.
  Expose at /api/docs.
  - Implement Global Toast Notification System (Priority:
  Medium)Add react-hot-toast or sonner library. Create
  ToastProvider context and useToast() hook. Replace generic
   alerts with toast notifications for success/error
  feedback.
  - Setup Code Splitting & Lazy Loading (Priority: Low)Use
  React.lazy() and Suspense for route-based code splitting.
  Lazy load heavy components (Charts, Reports). Add loading
  fallbacks.

  ---
  2. Core Features – Monthly Overview

  - Create Monthly Overview Page (Priority: High)New page
  /monthly-overview showing:
    - Month selector (current month by default)
    - 3 sections: "Paid", "Pending", "Overdue"
    - Each item is a card with: description, amount,
  category, due date, status badge, "Mark as Paid" button
    - Total summary at top (total paid, total pending, total
   overdue)
    - Files:
  src/components/monthly-overview/MonthlyOverview.tsx,
  src/components/monthly-overview/PaymentCard.tsx
  - Monthly Checklist Component (Priority: High)Create
  interactive checklist UI for pending payments. Checkboxes
  to mark items as paid. Sort by due date and priority. Add
  "Pay" action button that updates transaction status to
  paid.
  - Overdue Indicator & Alerts (Priority: High)Backend
  service to calculate overdue items (status = pending and
  due_date < today). Frontend shows red badge for overdue
  items. Optional: Toast notification on Dashboard if
  overdue items exist.
  - Priority Field for Transactions (Priority: Medium)Add
  priority: 'high' | 'medium' | 'low' field. Update forms to
   allow setting priority. Sort pending payments by priority
   + due date.
  - Monthly Summary Card on Dashboard (Priority: High)Add
  card showing:
    - Fixed expenses this month (sum of recurring expenses)
    - Variable expenses this month (sum of non-recurring
  expenses)
    - Total income this month
    - Net cash flow (income - all expenses)
    - Link to Monthly Overview page

  ---
  3. Income & Fixed Expenses

  - Fixed Expenses Management Screen (Priority: High)New
  page /fixed-expenses listing all recurring monthly
  expenses (rent, subscriptions, utilities, etc.). CRUD
  operations for fixed expenses. Mark as active/inactive.
  Set recurrence day of month.
  - Auto-Generate Recurring Transactions (Priority:
  High)Backend cron job or scheduled task (using
  APScheduler) to auto-create transactions for active
  recurring expenses at start of month. Status = pending by
  default.
  - Recurring Transaction Template (Priority: Medium)Create
  transaction templates for fixed expenses. On template
  edit, ask "Apply to future occurrences only?" or "Update
  all past and future?".
  - Income Recurrence Support (Priority: Medium)Extend
  recurrence model to income transactions (e.g., monthly
  salary). Auto-generate income transactions at start of
  month.

  ---
  4. Variable Expenses & Categories

  - Default Category Presets (Priority: Medium)Backend seed
  script to create default categories on user registration:
    - Moradia (Housing), Saúde (Health), Comunicação
  (Communication), Digital, Financeiro (Financial),
  Transporte (Transportation), Educação (Education),
  Alimentação (Food), Lazer (Entertainment), Outros (Others)
    - Assign default icons and colors per category.
  - Category Budgets (Priority: Medium)Add monthly_budget: 
  number field to categories. Show budget vs actual spending
   in Dashboard and Reports. Visual progress bar for each
  category.
  - Variable Expenses Filter (Priority: Low)In Transactions
  page, add toggle to show only variable expenses
  (is_recurring = false). Helps distinguish one-time
  purchases from fixed costs.

  ---
  5. Debts, Installments & Pending Items

  - Debts Management Page (Priority: High)New page /debts
  listing all debts with:
    - Debt name, total amount, installments (e.g., "3/12
  paid"), monthly payment
    - Progress bar showing paid vs remaining installments
    - Responsible person indicator
    - Interest rate and total interest paid
    - Files: src/components/debts/Debts.tsx,
  src/components/debts/DebtCard.tsx,
  src/components/debts/DebtForm.tsx
  - Installment Tracking (Priority: High)Link debt
  installments to transactions. Auto-create monthly
  installment transactions. Update debt installments_paid
  count when transaction marked as paid.
  - Debt Amortization Schedule (Priority: Medium)Show
  detailed payment schedule (month-by-month) with principal
  + interest breakdown. Calculate total interest over life
  of debt.
  - Next Payment Reminder (Priority: Medium)Dashboard widget
   showing "Next Payments" (debts + fixed expenses due in
  next 7 days). Sort by due date.
  - Debt Payoff Calculator (Priority: Low)Tool to simulate
  early payoff scenarios. "If I pay X extra per month, how
  many months earlier will I be debt-free?"

  ---
  6. Charts & Analytics (Chart.js + Recharts)

  - Monthly Evolution Line Chart (Priority: Medium)Add to
  Dashboard: line chart showing month-over-month balance
  evolution. X-axis: last 12 months, Y-axis: account
  balance. Use Recharts LineChart.
  - Cash Flow Projection Chart (Priority: Medium)Show
  projected balance for next 3 months based on recurring
  income/expenses. Dotted line for future data, solid line
  for historical data.
  - Budget vs Actual Comparison Chart (Priority: Medium)Bar
  chart comparing budgeted amount vs actual spending per
  category. Green if under budget, red if over budget.
  - Expense Trend Analysis (Priority: Low)Line chart showing
   trend of specific category over last 12 months. Identify
  spending patterns and anomalies.
  - Income vs Expenses Area Chart (Priority: Low)Currently
  in Dashboard with mock data. Connect to real backend API
  (/api/dashboard-advanced). Show historical data with
  smooth transitions.

  ---
  7. Responsible Person & Multi-User Support

  - Filter by Responsible Person (Priority: High)Add
  dropdown filter in Transactions, Fixed Expenses, and Debts
   pages to show only items for specific person ("Leandro",
  "Glenda", "Both", "All").
  - Responsible Person Dashboard Widget (Priority:
  Medium)Show breakdown on Dashboard: "Leandro's expenses
  this month", "Glenda's expenses this month", "Shared
  expenses this month". Pie chart or simple cards.
  - Expense Split Calculator (Priority: Low)For shared
  expenses, calculate "Who owes whom?" based on responsible
  person assignments. Show net balance: "Leandro owes Glenda
   R$ 350" or vice versa.

  ---
  8. UX Enhancements

  - Transaction Search Bar (Priority: High)Add search input
  in Transactions page header. Search by description,
  category name, or amount. Real-time filtering as user
  types.
  - Date Range Picker for Filters (Priority:
  *Medium-)Replace month/year dropdowns with date range
  picker (e.g., react-day-picker). Allow custom date ranges
  like "Last 30 days", "This quarter", "Custom range".
  - Quick Add Transaction FAB (Priority: Medium)Floating
  Action Button (FAB) on Dashboard for quick transaction
  entry. Opens modal with minimal form (amount, type,
  category).
  - Transaction Quick Actions (Priority: Medium)Add action
  buttons to transaction cards: "Duplicate", "Mark as Paid",
   "Edit", "Delete". Swipe actions on mobile.
  - Pagination for Transactions (Priority: Medium)Implement
  server-side pagination in backend
  (/api/transactions?page=1&limit=50). Frontend shows "Load
  More" button or infinite scroll.
  - Loading State Unification (Priority: Low)Create reusable
   LoadingSpinner and SkeletonLoader components. Apply
  consistent loading patterns across all pages.
  - Empty States (Priority: Low)Design empty state screens
  for pages with no data (e.g., "No transactions yet. Add
  your first transaction!"). Include illustration and CTA
  button.
  - Onboarding Tour (Priority: Low)First-time user tour
  (using react-joyride) explaining key features: Dashboard,
  Transactions, Monthly Overview, Fixed Expenses, Debts.

  ---
  9. Reports & Data Export

  - Export Transactions to CSV (Priority: Medium)Add "Export
   CSV" button in Transactions page. Backend endpoint
  /api/transactions/export returns CSV file with all
  filtered transactions.
  - Monthly Statement PDF (Priority: Medium)Generate PDF
  report for selected month with summary, charts, and
  transaction list. Use jsPDF or backend library (reportlab
  in Python).
  - Print-Friendly Views (Priority: Low)Add print CSS styles
   (@media print) for Reports and Monthly Overview pages.
  Remove unnecessary UI elements (sidebar, buttons) when
  printing.
  - Custom Report Builder (Priority: Low)Advanced UI to
  build custom reports: select date range, categories,
  accounts, grouping, chart type. Save report
  configurations.

  ---
  10. i18n & UX Polish

  - Complete Translation Coverage (Priority: Medium)Audit
  all hardcoded strings in components. Replace with t('key')
   from useTranslation(). Update pt.json, en.json, es.json
  with missing keys.
  - Language Switcher in Settings (Priority: Medium)Add
  language dropdown in Settings page. Save preference to
  user profile (backend). Apply on login.
  - Date/Currency Localization (Priority: Low)Use
  Intl.DateTimeFormat and Intl.NumberFormat with user's
  locale. Respect regional date/currency formats (DD/MM vs
  MM/DD, R$ vs $).
  - Dark Mode Support (Priority: Low)Implement dark mode
  toggle in Settings. Use Tailwind's dark: classes. Save
  preference to localStorage and user profile.
  - Animations & Transitions (Priority: Low)Add
  micro-interactions: button hover effects, card
  transitions, page enter/exit animations (using
  framer-motion). Smooth chart animations.

  ---
  11. Testing & Quality

  - Unit Tests for Core Components (Priority: High)Write
  tests for:
    - Dashboard.tsx (KPI rendering, chart data)
    - Transactions.tsx (CRUD operations, filtering)
    - MonthlyOverview.tsx (payment status logic)
    - api.ts (API functions mocking)
    - Minimum 70% code coverage
  - Integration Tests for API (Priority: High)Backend tests
  using pytest and pytest-flask:
    - Auth endpoints (login, register, JWT)
    - Transaction CRUD
    - Dashboard aggregations
    - Test database fixtures
  - E2E Tests for Critical Flows (Priority: Medium)Use
  Playwright or Cypress:
    - Login flow
    - Create transaction
    - Mark payment as paid
    - Generate report
    - CSV import
  - Accessibility Audit (Priority: Medium)Use axe-core or
  Lighthouse to identify a11y issues. Fix WCAG Level AA
  violations (keyboard navigation, ARIA labels, contrast
  ratios).
  - Performance Testing (Priority: Low)Test with 1000+
  transactions. Optimize database queries (add indexes on
  user_id, date, category_id). Profile frontend bundle size
  with vite-bundle-visualizer.
  - CI/CD Pipeline (Priority: Low)Setup GitHub Actions:
    - Run tests on PR
    - Lint code with ESLint
    - Type-check with TypeScript
    - Build frontend and backend
    - Deploy to staging on merge to main

  ---
  12. Security & Error Handling

  - Input Sanitization on Backend (Priority: High)Sanitize
  all user inputs to prevent NoSQL injection. Use PyMongo's
  query builders, avoid eval() or direct string
  concatenation.
  - CSRF Protection (Priority: High)Implement CSRF tokens
  for state-changing requests (POST, PUT, DELETE). Use
  flask-wtf or custom middleware.
  - Rate Limiting (Priority: Medium)Add rate limiting to API
   endpoints using flask-limiter. Prevent brute-force
  attacks on /api/auth/login.
  - Password Strength Indicator (Priority: Medium)Add visual
   indicator in Register form. Require minimum 8 characters,
   1 uppercase, 1 number, 1 special char.
  - Error Boundary in React (Priority: Medium)Wrap app in
  <ErrorBoundary> to catch React errors. Show friendly error
   page instead of blank screen.
  - Retry Logic for Failed API Calls (Priority: Low)Add
  retry mechanism (3 attempts) for network errors using
  Axios interceptors. Show "Retrying..." toast.

  ---
  Current Completion Estimate

  Overall MVP Completion: ~45%

  What's Done (45%):

  - ✅ Authentication & JWT (login, register, OAuth setup)
  - ✅ Dashboard with mock KPIs and charts
  - ✅ Transaction CRUD (full backend + frontend)
  - ✅ Category management
  - ✅ Account management
  - ✅ Basic reports and analytics
  - ✅ CSV import
  - ✅ i18n setup (3 languages)
  - ✅ Modern UI with Tailwind + shadcn/ui
  - ✅ TypeScript migration started
  - ✅ Testing infrastructure (Vitest)

  What's Missing (55%):

  - ❌ Monthly Overview / Checklist (Core product goal!)
  - ❌ Payment status tracking (paid/pending/overdue)
  - ❌ Responsible person assignment (Leandro/Glenda)
  - ❌ Fixed expenses & recurrence
  - ❌ Debts & installments tracking
  - ❌ Budget management
  - ❌ Cash flow projection
  - ❌ Pagination, search, advanced filters
  - ❌ Data export (CSV/PDF)
  - ❌ Comprehensive testing
  - ❌ API documentation
  - ❌ Performance optimization

  ---
  Recommended Next Focus (Top 5 Tasks)

  🎯 Priority 1: Add Transaction Status Field

  Why: Foundational for payment tracking. Enables
  paid/pending/overdue logic, which is core to monthly
  overview.Files: backend/services/transaction_service.py,
  backend/routes/transactions.py, src/utils/api.ts,
  transaction forms.

  🎯 Priority 2: Create Monthly Overview Page

  Why: This is the primary user need for Alça Finanças.
  Users need a clear view of what's paid, pending, and
  overdue each month.Files: Create
  src/components/monthly-overview/MonthlyOverview.tsx,
  PaymentCard.tsx. Backend: /api/transactions with status
  filtering.

  🎯 Priority 3: Add Responsible Person Field

  Why: Critical for couples/households to split financial
  responsibility. Enables "Who pays what?" filtering.Files:
  Extend transaction model, update forms
  (TransactionForm.tsx), add filter dropdown.

  🎯 Priority 4: Fixed Expenses Management Screen

  Why: Users need to separate recurring (fixed) from
  one-time (variable) expenses. Foundation for
  auto-generating monthly bills.Files: Create
  /fixed-expenses page, add is_recurring flag to
  transactions, backend recurrence service.

  🎯 Priority 5: Debts & Installments Tracking

  Why: Core feature for managing loans, credit cards, and
  installment purchases. High user value.Files: Create debts
   collection, new routes (backend/routes/debts.py),
  frontend page (src/components/debts/Debts.tsx).

  ---
  Next Steps: Start with Priority 1-3 to unlock the core
  monthly finance overview workflow. Then build out fixed
  expenses and debts tracking. This will take the MVP from
  ~45% to ~80% completion for a solid v1.0 launch. 🚀

