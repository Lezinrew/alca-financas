# Database Contracts — transactions

## Table: `transactions`

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Transaction ID |
| `user_id` | UUID | NOT NULL, FK(users.id) ON DELETE CASCADE | Owner |
| `category_id` | UUID | FK(categories.id) ON DELETE SET NULL | Category (nullable) |
| `account_id` | UUID | FK(accounts.id) ON DELETE SET NULL | Account (nullable) |
| `description` | VARCHAR(500) | NOT NULL | Transaction description |
| `amount` | DECIMAL(15, 2) | NOT NULL | Amount (negative for expense, positive for income) |
| `type` | VARCHAR(20) | NOT NULL, CHECK(type IN ('income', 'expense')) | Transaction type |
| `date` | DATE | NOT NULL | Transaction date |
| `status` | VARCHAR(20) | DEFAULT 'pending', CHECK(status IN ('paid', 'pending', 'overdue', 'cancelled')) | Payment status |
| `responsible_person` | VARCHAR(255) | NULL | Payee/payer |
| `is_recurring` | BOOLEAN | DEFAULT FALSE | Recurring flag |
| `installment_info` | JSONB | NULL | `{current: 3, total: 12, parent_id: "uuid"}` |
| `tags` | TEXT[] | NULL | Array of tags |
| `notes` | TEXT | NULL | Additional notes |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update |

**Indexes:**
- `idx_transactions_user_id` on `user_id`
- `idx_transactions_category_id` on `category_id`
- `idx_transactions_account_id` on `account_id`
- `idx_transactions_date` on `date`
- `idx_transactions_type` on `type`
- `idx_transactions_status` on `status`
- `idx_transactions_user_date` on `(user_id, date DESC)` — Most common query pattern

**RLS:** Users can only SELECT/INSERT/UPDATE/DELETE own transactions (filtered by user_id in application)

**Invariants:**
- Amount sign must match type: expense → negative, income → positive
- Paid status with future date is invalid
- Installment current <= total
