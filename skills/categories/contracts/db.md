# Database Contracts — categories

## Table: `categories`

**Purpose:** Stores user-defined income and expense categories

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY DEFAULT uuid_generate_v4() | Category ID |
| `user_id` | UUID | NOT NULL, FK(users.id) ON DELETE CASCADE | Owner |
| `name` | VARCHAR(255) | NOT NULL | Category name |
| `type` | VARCHAR(20) | NOT NULL, CHECK(type IN ('income', 'expense')) | Category type |
| `color` | VARCHAR(20) | DEFAULT '#10B981' | Display color (hex) |
| `icon` | VARCHAR(50) | DEFAULT 'tag' | Icon identifier |
| `description` | TEXT | NULL | Category description |
| `active` | BOOLEAN | DEFAULT TRUE | Active status |
| `essential` | BOOLEAN | DEFAULT FALSE | Essential expense flag (for budgeting) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_categories_user_id` on `user_id` — Fast user category lookups
- `idx_categories_type` on `type` — Filter by category type
- `idx_categories_active` on `active` — Filter active categories
- `idx_categories_user_type` on `(user_id, type)` — Common query pattern

**RLS Policies:**
```sql
-- Users can view own categories
CREATE POLICY "categories_read_policy" ON categories
    FOR SELECT USING (user_id = auth.uid());

-- Users can manage own categories
CREATE POLICY "categories_write_policy" ON categories
    FOR ALL USING (user_id = auth.uid());
```

**Triggers:**
```sql
CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Data Integrity Rules

1. **Category Name Required:** Name cannot be empty
2. **Valid Category Type:** Must be either `income` or `expense`
3. **Essential Only for Expenses:** Essential flag only meaningful for expense categories
4. **User Ownership:** All categories must belong to a user (cascading delete)
5. **Duplicate Names Allowed:** Users can have multiple categories with same name (different types)

---

## Common Queries

**Get categories by type:**
```sql
SELECT * FROM categories
WHERE user_id = :user_id AND type = :type AND active = true
ORDER BY name;
```

**Most used categories:**
```sql
SELECT c.*, COUNT(t.id) as transaction_count
FROM categories c
LEFT JOIN transactions t ON c.id = t.category_id
WHERE c.user_id = :user_id
GROUP BY c.id
ORDER BY transaction_count DESC
LIMIT 10;
```

---

## Migrations

**Initial Schema:** `backend/database/schema.sql`

**Future Migrations:**
- Add `parent_id` column for category hierarchy
- Add `order` column for custom sorting
- Add `is_system` flag for pre-defined categories
- Add `rules` JSONB column for auto-categorization patterns
