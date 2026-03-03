# Database Contracts — users-profile

## Table: `users`

**Purpose:** Stores user accounts, authentication credentials, and profile information

**Full Schema:** See `authentication` skill for complete schema.

**Profile-Specific Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `name` | VARCHAR(255) | NOT NULL | User display name |
| `profile_picture` | TEXT | NULL | Profile picture URL |
| `settings` | JSONB | DEFAULT '{"currency": "BRL", "theme": "light", "language": "pt"}'::jsonb | User preferences |

**Settings Schema (JSONB):**
```json
{
  "currency": "BRL",     // ISO 4217 currency code
  "theme": "light",      // "light" | "dark"
  "language": "pt"       // ISO 639-1 language code
}
```

**Valid Values:**
- **Currency:** BRL, USD, EUR, GBP, JPY, etc. (ISO 4217)
- **Theme:** light, dark
- **Language:** pt, en, es (expandable)

---

## Data Integrity Rules

1. **Name Required:** User must have a display name
2. **Valid Settings Schema:** Settings JSONB must contain currency, theme, language
3. **Valid Currency:** Currency must be valid ISO 4217 code
4. **Profile Picture URL:** Must be valid HTTPS URL or NULL
5. **Settings Defaults:** If settings is NULL, use default values

---

## Common Queries

**Get user with settings:**
```sql
SELECT id, email, name, profile_picture, settings
FROM users
WHERE id = :user_id;
```

**Update settings:**
```sql
UPDATE users
SET settings = settings || :new_settings::jsonb,
    updated_at = NOW()
WHERE id = :user_id;
```

**Update profile:**
```sql
UPDATE users
SET name = :name,
    profile_picture = :profile_picture,
    updated_at = NOW()
WHERE id = :user_id;
```

---

## Migrations

**Initial Schema:** `backend/database/schema.sql`

**Future Migrations:**
- Add `phone_number` column
- Add `timezone` column
- Add `notification_preferences` JSONB column
- Add `privacy_settings` JSONB column
