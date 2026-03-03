# Database Contracts — ai-insights

## No Dedicated Tables (Current)

AI-insights is a read-only service that queries existing tables for pattern matching.

---

## Tables Read

### `categories`
**Purpose:** Read category names and patterns for matching

**Query:**
```sql
SELECT id, name, type FROM categories
WHERE user_id = :user_id AND active = true;
```

### `accounts`
**Purpose:** Read account names for matching

**Query:**
```sql
SELECT id, name FROM accounts
WHERE user_id = :user_id AND active = true;
```

---

## Future Tables

### Table: `detection_patterns` (Planned)

**Purpose:** Store learned detection patterns and rules

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Pattern ID |
| `entity_type` | VARCHAR(50) | NOT NULL | "category" or "account" |
| `entity_id` | UUID | NOT NULL | Category/account ID |
| `pattern` | VARCHAR(255) | NOT NULL | Keyword/regex pattern |
| `weight` | DECIMAL(3, 2) | DEFAULT 1.0 | Pattern weight (0.0-1.0) |
| `language` | VARCHAR(5) | DEFAULT 'en' | Language code |
| `created_by` | VARCHAR(20) | DEFAULT 'system' | "system" or "user" |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |

**Indexes:**
- `idx_detection_patterns_entity` on `(entity_type, entity_id)`
- `idx_detection_patterns_pattern` on `pattern`

**Example Data:**
```sql
INSERT INTO detection_patterns VALUES
  (uuid, 'category', :transport_id, 'uber', 1.0, 'en', 'system', NOW()),
  (uuid, 'category', :transport_id, 'lyft', 1.0, 'en', 'system', NOW()),
  (uuid, 'category', :groceries_id, 'supermarket', 1.0, 'en', 'system', NOW());
```

---

### Table: `detection_feedback` (Planned)

**Purpose:** Store user corrections for ML training

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Feedback ID |
| `user_id` | UUID | NOT NULL, FK(users.id) | User who corrected |
| `transaction_id` | UUID | FK(transactions.id) | Transaction corrected |
| `description` | VARCHAR(500) | NOT NULL | Transaction description |
| `detected_category_id` | UUID | NULL | AI-suggested category |
| `actual_category_id` | UUID | NOT NULL | User-selected category |
| `confidence` | DECIMAL(3, 2) | NULL | AI confidence score |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Correction time |

**Indexes:**
- `idx_detection_feedback_user_id` on `user_id`
- `idx_detection_feedback_description` on `description`

**Usage:**
- Train ML model on (description, actual_category_id) pairs
- Evaluate model accuracy (detected vs actual)
- Personalize suggestions per user

---

### Table: `ml_models` (Future)

**Purpose:** Store trained ML models

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Model ID |
| `name` | VARCHAR(100) | NOT NULL | Model name |
| `version` | VARCHAR(20) | NOT NULL | Model version |
| `type` | VARCHAR(50) | NOT NULL | "category_classifier", "fraud_detector", etc. |
| `model_binary` | BYTEA | NOT NULL | Serialized model (pickle/joblib) |
| `accuracy` | DECIMAL(5, 2) | NULL | Model accuracy percentage |
| `trained_on` | TIMESTAMPTZ | NOT NULL | Training date |
| `active` | BOOLEAN | DEFAULT FALSE | Currently active model |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |

**Note:** For production, consider storing models in object storage (S3, GCS) instead of database

---

## ML Training Pipeline (Future)

**Training Data Query:**
```sql
SELECT
  description,
  category_id,
  type
FROM detection_feedback
WHERE created_at >= NOW() - INTERVAL '90 days'
ORDER BY created_at DESC;
```

**Model Evaluation:**
```sql
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN detected_category_id = actual_category_id THEN 1 ELSE 0 END) as correct,
  (SUM(CASE WHEN detected_category_id = actual_category_id THEN 1 ELSE 0 END)::float / COUNT(*) * 100) as accuracy
FROM detection_feedback
WHERE created_at >= NOW() - INTERVAL '30 days';
```
