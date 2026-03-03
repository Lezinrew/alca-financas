# Add a New Skill — Playbook

**Purpose:** Step-by-step guide to add a new skill to the Alça Finanças system.

**Time Estimate:** 2-4 hours for complete skill documentation

---

## Prerequisites

Before adding a new skill, ensure:
- [ ] You've read [CONVENTIONS.md](./CONVENTIONS.md)
- [ ] You've reviewed [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [ ] You understand existing skills in [SKILLS_REGISTRY.md](./SKILLS_REGISTRY.md)
- [ ] The skill has clear, cohesive boundaries (not overlapping with existing skills)

---

## Step 1: Plan the Skill

### 1.1 Define Skill Scope

Answer these questions:
- **What problem does this skill solve?**
- **What is in scope?** (features, responsibilities)
- **What is out of scope?** (explicit boundaries)
- **Which existing skills does it depend on?**
- **Which skills will depend on it?**

### 1.2 Choose Skill Name

Follow naming conventions from [CONVENTIONS.md](./CONVENTIONS.md):
- Use lowercase with hyphens (e.g., `payment-processing`)
- Be descriptive but concise (2-3 words max)
- Avoid technical jargon; use domain language
- Examples: `authentication`, `transactions`, `reports`

### 1.3 Assess Risk Level

Determine risk level based on:
- **🔴 High:** Handles authentication, payments, critical business logic, admin access
- **🟡 Medium:** Handles user data, integrations, imports/exports
- **🟢 Low:** Read-only, analytics, UI-only features

---

## Step 2: Create Skill Folder Structure

Run the following commands:

```bash
# Navigate to skills directory
cd skills/

# Create skill folder and subdirectories
mkdir -p <skill-name>/{contracts,design,runbooks,tests}

# Create placeholder files
touch <skill-name>/skill.md
touch <skill-name>/contracts/{api.md,db.md,events.md}
touch <skill-name>/design/{domain-model.md,invariants.md,threats.md}
touch <skill-name>/runbooks/{troubleshooting.md,observability.md}
touch <skill-name>/tests/test-strategy.md
```

Your skill folder should look like:

```
skills/<skill-name>/
├── skill.md
├── contracts/
│   ├── api.md
│   ├── db.md
│   └── events.md
├── design/
│   ├── domain-model.md
│   ├── invariants.md
│   └── threats.md
├── runbooks/
│   ├── troubleshooting.md
│   └── observability.md
└── tests/
    └── test-strategy.md
```

---

## Step 3: Document the Skill

### 3.1 Write `skill.md`

Use this template:

```markdown
# Skill: <skill-name>

**Status:** Active | In Development | Deprecated
**Risk Level:** 🔴 High | 🟡 Medium | 🟢 Low
**Owner:** [Team/Individual]
**Last Updated:** YYYY-MM-DD

---

## Purpose

[1-2 sentences describing what this skill does and why it exists]

## Business Value

- [What business problem does this solve?]
- [What user need does it address?]
- [What is the impact if this skill fails?]

## Boundaries

### In Scope
- [Feature 1]
- [Feature 2]
- [Responsibility 1]

### Out of Scope
- [What this skill does NOT do]
- [Responsibilities that belong to other skills]

## Core Responsibilities

1. [Primary responsibility]
2. [Secondary responsibility]
3. [Additional responsibility]

## User Journeys

### Journey 1: [Name]
1. User does X
2. System validates Y
3. Skill processes Z
4. Result is returned

### Journey 2: [Name]
...

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| [What can fail] | [User/business impact] | [How we prevent/recover] |

## Dependencies

### Upstream (Skills this depends on)
- `skill-name` — [Why we depend on it]

### Downstream (Skills that depend on this)
- `skill-name` — [How they use this skill]

## Code Map

### Backend
- Routes: `backend/routes/<file>.py`
- Services: `backend/services/<file>.py`
- Repositories: `backend/repositories/<file>.py`
- Utils: `backend/utils/<file>.py`

### Frontend
- Components: `frontend/src/components/<dir>/`
- Pages: `frontend/src/pages/<file>.tsx`
- Utils: `frontend/src/utils/<file>.ts`

### Database
- Tables: `table_name` (see contracts/db.md)
- Migrations: `backend/database/migrations/<file>.sql`

## Security Considerations

- [Authentication requirements]
- [Authorization rules]
- [Data sensitivity]
- [Threat mitigations]

## Observability Plan

### Logs
- [What to log]
- [Log levels]
- [PII handling]

### Metrics
- [Key performance indicators]
- [Success/failure rates]
- [Latency targets]

### Traces
- [Distributed trace requirements]
- [Correlation IDs]

## Future Evolution

### v1.0 (Current)
- [Current capabilities]

### v2.0 (Planned)
- [Planned enhancements]
- [Breaking changes]

### v3.0 (Vision)
- [Long-term vision]
- [Potential service extraction]

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
- [Domain Model](./design/domain-model.md)
- [Threat Model](./design/threats.md)
- [Test Strategy](./tests/test-strategy.md)
```

### 3.2 Write API Contracts (`contracts/api.md`)

```markdown
# API Contracts — <skill-name>

## Routes

### Endpoint: [Method] /api/path

**Description:** [What this endpoint does]

**Auth Required:** Yes | No

**Rate Limit:** [e.g., 100 req/min per user]

**Request:**
\`\`\`json
{
  "field": "value",
  "another_field": 123
}
\`\`\`

**Response (200 OK):**
\`\`\`json
{
  "id": "uuid",
  "data": "value"
}
\`\`\`

**Errors:**
- `400 Bad Request` — Invalid input
- `401 Unauthorized` — Missing/invalid auth token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Resource not found
- `422 Unprocessable Entity` — Validation error
- `500 Internal Server Error` — Server error

**Example cURL:**
\`\`\`bash
curl -X POST https://api.alcahub.cloud/api/path \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"field": "value"}'
\`\`\`

---

[Repeat for each endpoint]
```

### 3.3 Write Database Contracts (`contracts/db.md`)

```markdown
# Database Contracts — <skill-name>

## Tables

### Table: `table_name`

**Purpose:** [What this table stores]

**Schema:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `user_id` | UUID | NOT NULL, FK(users.id) | Owner |
| `field` | VARCHAR(255) | NOT NULL | Description |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |

**Indexes:**
- `idx_table_user_id` on `user_id`
- `idx_table_created_at` on `created_at`

**RLS Policies:**
- Users can SELECT/INSERT/UPDATE/DELETE own rows (`user_id = auth.uid()`)
- Service role bypasses RLS

**Triggers:**
- `update_updated_at_trigger` — Auto-updates `updated_at` on row change

---

[Repeat for each table]
```

### 3.4 Write Domain Events (`contracts/events.md`)

```markdown
# Domain Events — <skill-name>

## Events Emitted

### Event: `skill.action.happened`

**When:** [Trigger condition]

**Payload:**
\`\`\`json
{
  "event_id": "uuid",
  "event_type": "skill.action.happened",
  "timestamp": "2026-02-27T12:00:00Z",
  "user_id": "uuid",
  "data": {
    "field": "value"
  }
}
\`\`\`

**Consumers:**
- `other-skill` — [How it uses this event]

**Idempotency:** Event can be replayed safely (use `event_id` for deduplication)

---

## Events Consumed

### Event: `other-skill.event.name`

**Handler:** `service/handler.py:handle_event()`

**Processing:**
1. Validate event
2. Process business logic
3. Update state
4. Emit own event (if needed)

**Failure Handling:** Retry 3 times with exponential backoff, then DLQ
```

### 3.5 Write Domain Model (`design/domain-model.md`)

Include:
- Entity definitions
- Relationships (Mermaid ER diagram)
- Glossary of domain terms
- Lifecycle states (if applicable)

### 3.6 Write Invariants (`design/invariants.md`)

List business rules that must NEVER be violated:
- "Transaction amount sign must match transaction type"
- "Account balance must equal sum of transaction amounts"
- "Installment current must be <= installment total"

### 3.7 Write Threat Model (`design/threats.md`)

Use STRIDE framework:
- **Spoofing:** Authentication threats
- **Tampering:** Data integrity threats
- **Repudiation:** Audit logging gaps
- **Information Disclosure:** Data leak risks
- **Denial of Service:** Rate limiting needs
- **Elevation of Privilege:** Authorization gaps

### 3.8 Write Runbooks

- `troubleshooting.md` — Common issues and fixes
- `observability.md` — What to log/monitor/trace

### 3.9 Write Test Strategy (`tests/test-strategy.md`)

Define:
- Unit test scope
- Integration test scope
- E2E test scenarios
- Test fixtures and mocks
- Edge cases to cover
- Contract tests (if API consumed by other systems)

---

## Step 4: Update Registry

Add your skill to [SKILLS_REGISTRY.md](./SKILLS_REGISTRY.md):

1. Add row to main registry table
2. Add detailed section with:
   - Purpose
   - Code locations
   - API routes
   - Database tables
   - Observability plan
   - Dependencies
   - Test coverage status

---

## Step 5: Update Dependency Graph

Edit [SKILLS_DEPENDENCY_GRAPH.mmd](./SKILLS_DEPENDENCY_GRAPH.mmd):

1. Add your skill node to appropriate subgraph
2. Add dependency edges to/from other skills
3. Apply correct risk color class (highRisk, mediumRisk, lowRisk)

Example:
```mermaid
newskill[new-skill<br/>🟡 Description]
existingskill --> newskill
```

---

## Step 6: Update README

Add your skill to [README.md](./README.md) skills table:

```markdown
| **new-skill** | Short description | ✅ Active |
```

---

## Step 7: (Optional) Create ADR

If the skill involves an architectural decision, create an ADR in `ADRs/`:

```bash
cd skills/ADRs/
# Use next available number
touch XXXX-skill-name-decision.md
```

Follow ADR template from [0001-skills-architecture.md](./ADRs/0001-skills-architecture.md).

---

## Step 8: Validate

Run through this checklist:

### Documentation Checklist
- [ ] `skill.md` is complete and clear
- [ ] All API endpoints documented in `contracts/api.md`
- [ ] Database schema documented in `contracts/db.md`
- [ ] Domain events documented in `contracts/events.md` (if applicable)
- [ ] Domain model includes Mermaid diagram
- [ ] Invariants are explicit and testable
- [ ] Threat model covers STRIDE
- [ ] Troubleshooting runbook has common issues
- [ ] Observability plan defines logs/metrics/traces
- [ ] Test strategy covers unit/integration/E2E

### Registry Checklist
- [ ] Added to SKILLS_REGISTRY.md registry table
- [ ] Added detailed section in SKILLS_REGISTRY.md
- [ ] Code locations are accurate
- [ ] Dependencies are correct

### Graph Checklist
- [ ] Added to SKILLS_DEPENDENCY_GRAPH.mmd
- [ ] Edges point in correct direction (dependency flow)
- [ ] Risk color is appropriate
- [ ] Placed in correct subgraph

### Cross-Reference Checklist
- [ ] Updated README.md skills table
- [ ] All internal links work (use relative paths)
- [ ] Mermaid diagrams render correctly
- [ ] No broken links to code files

---

## Step 9: Implement the Skill

Now that documentation is done, implement the skill:

1. **Backend:**
   - Create routes in `backend/routes/<skill>.py`
   - Create services in `backend/services/<skill>_service.py`
   - Create repositories in `backend/repositories/<skill>_repository_supabase.py`
   - Register blueprint in `backend/app.py`

2. **Frontend:**
   - Create components in `frontend/src/components/<skill>/`
   - Add routes in `frontend/src/App.tsx`
   - Create pages in `frontend/src/pages/`

3. **Database:**
   - Create migration in `backend/database/migrations/`
   - Update `backend/database/schema.sql` if needed
   - Apply RLS policies

4. **Tests:**
   - Write unit tests: `backend/tests/test_<skill>.py`
   - Write frontend tests: `frontend/src/__tests__/<skill>.test.tsx`
   - Write E2E tests: `frontend/e2e/<skill>.spec.ts`

---

## Step 10: Review and Iterate

1. **Self-Review:**
   - Read your skill docs as if you're a new team member
   - Check for clarity, completeness, accuracy
   - Validate all links and code references

2. **Peer Review:**
   - Share with team for feedback
   - Update docs based on feedback

3. **Update as You Go:**
   - Documentation is living; update it when implementation reveals gaps
   - Keep registry, graph, and skill docs in sync

---

## Done Checklist

- [ ] Skill folder created with all required files
- [ ] All documentation sections complete
- [ ] SKILLS_REGISTRY.md updated
- [ ] SKILLS_DEPENDENCY_GRAPH.mmd updated
- [ ] README.md updated
- [ ] ADR created (if needed)
- [ ] All links validated
- [ ] Mermaid diagrams render correctly
- [ ] Code implementation started/completed
- [ ] Tests written
- [ ] Documentation reviewed by peer

---

## Tips

- **Start with skill.md:** It forces you to think through the skill's purpose and boundaries
- **Iterate on contracts:** API and DB contracts may evolve as you implement
- **Don't skip threat modeling:** Security issues are expensive to fix later
- **Keep it concise:** Documentation should be helpful, not exhaustive
- **Link liberally:** Use relative links to connect related docs
- **Validate early:** Check Mermaid syntax and links before moving on

---

## Need Help?

- Check existing skills for examples: `authentication`, `transactions`, `accounts`
- Review [CONVENTIONS.md](./CONVENTIONS.md) for standards
- Ask in team chat or open an issue

---

**Remember:** Good documentation makes the system understandable, maintainable, and scalable. Invest the time upfront!
