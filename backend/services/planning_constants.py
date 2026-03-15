"""
Constantes e regras de negócio do módulo Planejamento.
Separação: FACTS = transactions, PLANS = budget_plans.
"""

# Expense category status (progress = spent / planned * 100)
EXPENSE_STATUS_SAFE = "safe"           # progress <= 70%
EXPENSE_STATUS_WARNING = "warning"     # progress > 70% and <= 100%
EXPENSE_STATUS_EXCEEDED = "exceeded"   # progress > 100%
EXPENSE_STATUS_UNPLANNED = "unplanned" # planned = 0 and spent > 0

EXPENSE_SAFE_THRESHOLD_PERCENT = 70.0
EXPENSE_WARNING_MAX_PERCENT = 100.0

# Income category status
INCOME_STATUS_ON_TRACK = "on_track"         # received >= planned (or close)
INCOME_STATUS_BELOW_TARGET = "below_target" # received < planned
INCOME_STATUS_EXCEEDED_TARGET = "exceeded_target"  # received > planned

# Alert types
ALERT_UNPLANNED_EXPENSE = "unplanned_expense"
ALERT_ABOVE_BUDGET = "above_budget"
ALERT_CLOSE_TO_LIMIT = "close_to_limit"
