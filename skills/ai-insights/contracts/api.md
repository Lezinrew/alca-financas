# API Contracts — ai-insights

## No Public API Endpoints

The ai-insights skill is an internal service called by other backend skills. It does not expose public HTTP endpoints.

---

## Internal Service API

### CategoryDetector.detect(description, transaction_type, user_id)

**Description:** Detect category from transaction description

**Parameters:**
- `description` (string) — Transaction description
- `transaction_type` (string) — "income" or "expense"
- `user_id` (uuid) — User ID for personalized suggestions (future)

**Returns:** `tuple` — `(category_id: uuid | None, confidence: float)`

**Example:**
```python
from backend.services.category_detector import CategoryDetector

category_id, confidence = CategoryDetector.detect(
    description="UBER *TRIP",
    transaction_type="expense",
    user_id="user-uuid"
)

if confidence > 0.7:
    print(f"Suggested category: {category_id} (confidence: {confidence})")
else:
    print("No confident suggestion")
```

---

### AccountDetector.detect(description, user_id)

**Description:** Detect account from transaction description

**Parameters:**
- `description` (string) — Transaction description
- `user_id` (uuid) — User ID for account matching

**Returns:** `tuple` — `(account_id: uuid | None, confidence: float)`

**Example:**
```python
from backend.services.account_detector import AccountDetector

account_id, confidence = AccountDetector.detect(
    description="NUBANK *PURCHASE",
    user_id="user-uuid"
)

if account_id:
    print(f"Suggested account: {account_id}")
```

---

## Detection Patterns

### Category Patterns (Current Implementation)

**Pattern Matching:**
```json
{
  "Transportation": {
    "keywords": ["uber", "lyft", "taxi", "bus", "metro", "parking"],
    "weight": 1.0
  },
  "Groceries": {
    "keywords": ["supermarket", "grocery", "market", "mercado"],
    "weight": 1.0
  },
  "Dining": {
    "keywords": ["restaurant", "cafe", "food", "pizza", "burger"],
    "weight": 0.8
  },
  "Utilities": {
    "keywords": ["electricity", "water", "gas", "internet"],
    "weight": 1.0
  },
  "Salary": {
    "keywords": ["salary", "salario", "payroll", "wage"],
    "weight": 1.0
  }
}
```

**Confidence Calculation:**
```python
confidence = (
    exact_match_weight * 1.0 +
    partial_match_weight * 0.5 +
    pattern_weight
) / max_possible_score
```

---

### Account Patterns (Current Implementation)

**Pattern Matching:**
```json
{
  "Nubank": ["nubank", "nu pagamentos"],
  "Itaú": ["itau", "itaú"],
  "Bradesco": ["bradesco"],
  "Santander": ["santander"],
  "Inter": ["banco inter", "inter"]
}
```

---

## Error Handling

**No Match Found:**
- Returns `(None, 0.0)`
- Caller should handle by prompting user or using default

**Low Confidence:**
- Returns suggestion but with low confidence score
- Caller decides threshold (typically 0.7)

**Multiple Matches:**
- Returns highest confidence match
- Future: Return top N suggestions
