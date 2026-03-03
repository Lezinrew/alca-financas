# Skill: ai-insights

**Status:** Active
**Risk Level:** Low
**Owner:** ML Team
**Last Updated:** 2026-02-27

---

## Purpose

AI-powered detection and insights for categories and accounts using pattern matching and machine learning. Automatically suggests categories and accounts during transaction imports based on descriptions.

## Business Value

- **Time Savings:** Users don't have to manually categorize every transaction
- **Consistency:** Automated categorization improves data consistency
- **User Experience:** Smooth import experience with smart suggestions
- **Impact if Failed:** Users must manually assign categories (tedious but functional)

## Boundaries

### In Scope
- Category detection from transaction descriptions
- Account detection from transaction descriptions
- Pattern matching and keyword analysis
- Confidence scoring for suggestions
- Learning from user feedback (future)

### Out of Scope
- Full ML model training pipeline → Future feature
- Deep learning models → Future feature
- Fraud detection → Future feature
- Spending predictions → Future feature

## Core Responsibilities

1. **Detect categories** from transaction descriptions using pattern matching
2. **Detect accounts** from transaction descriptions
3. **Provide confidence scores** for suggestions
4. **Handle edge cases** (ambiguous descriptions)
5. **Learn from corrections** (future ML training)

## User Journeys

### Journey 1: Category Detection During Import
1. User imports CSV with description "UBER *TRIP TO AIRPORT"
2. Import service calls CategoryDetector.detect()
3. Detector finds pattern "UBER" → "Transportation"
4. Returns category suggestion with 0.95 confidence
5. Transaction saved with detected category

### Journey 2: Account Detection
1. User imports transaction "NUBANK *PURCHASE"
2. Import service calls AccountDetector.detect()
3. Detector finds pattern "NUBANK" → "Nubank Credit Card"
4. Returns account suggestion
5. Transaction assigned to detected account

### Journey 3: User Correction (Future)
1. System suggests "Dining" for "STORE ABC"
2. User corrects to "Groceries"
3. System logs correction
4. ML model learns from feedback
5. Future "STORE ABC" transactions auto-categorized as "Groceries"

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Wrong category detected | Low: User can override | Always allow manual correction; track accuracy |
| Low confidence scores | Low: No suggestion | Set threshold (e.g., 0.7); don't suggest if uncertain |
| Pattern conflicts | Low: Ambiguous results | Return multiple suggestions; let user choose |
| Missing patterns | Low: No detection | Expand pattern database; ML-based fallback |

## Dependencies

### Upstream
- `categories` — Read category patterns
- `accounts` — Read account patterns

### Downstream
- `imports-integrations` — Uses detection services
- `transactions` — Applies detected categories

## Code Map

### Backend
- **Services:** `backend/services/category_detector.py`, `backend/services/account_detector.py`

### Frontend
- No frontend components (backend service only)

### Database
- No dedicated tables (reads from categories, accounts)

## Security Considerations

- Read-only service (no writes)
- No sensitive data exposed
- Pattern database not user-modifiable (admin only)

## Observability Plan

### Logs
- Detection request (description, detected_category, confidence)
- User corrections (original, corrected, reason)

### Metrics
- `detection.requests.count` — Total detection requests
- `detection.accuracy` — Accuracy percentage (correct/total)
- `detection.confidence.avg` — Average confidence score
- `detection.corrections.count` — User corrections

## Current Implementation

**Algorithm:** Keyword/regex pattern matching

**Category Patterns:**
```python
patterns = {
    "Transportation": ["uber", "lyft", "taxi", "bus", "metro"],
    "Groceries": ["supermarket", "grocery", "market"],
    "Dining": ["restaurant", "cafe", "food"],
    # ... more patterns
}
```

**Detection Logic:**
```python
def detect_category(description):
    description_lower = description.lower()
    for category, keywords in patterns.items():
        for keyword in keywords:
            if keyword in description_lower:
                return (category_id, confidence=0.85)
    return (None, confidence=0.0)
```

## Future Evolution

### v1.0 (Current)
- Keyword-based pattern matching
- Basic category detection
- Account detection

### v2.0 (Planned)
- Machine learning classifier (scikit-learn)
- User feedback loop
- Confidence scoring improvements
- Multi-language support

### v3.0 (Vision)
- Deep learning (BERT/transformers)
- Merchant recognition
- Spending predictions
- Fraud detection
- Personalized suggestions per user

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
