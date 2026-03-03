# ADR 0001: Skills Architecture

**Status:** Accepted
**Date:** 2026-02-27
**Decision Makers:** Architecture Team
**Context:** Need for better discoverability, maintainability, and scalability of the codebase

---

## Context

The Alça Finanças codebase has grown organically, with functionality spread across routes, services, and repositories. As the system evolves, several challenges have emerged:

1. **Discoverability:** New developers struggle to find where specific functionality lives
2. **Boundaries:** Unclear ownership and responsibility boundaries between modules
3. **Dependencies:** Implicit dependencies between modules make refactoring risky
4. **Onboarding:** Long ramp-up time for new team members
5. **Scalability:** No clear path to extract functionality into services when needed
6. **Documentation Drift:** Docs are scattered and often out of date with code

### Current Pain Points
- "Where does CSV import live?" requires grepping the codebase
- Changing one module unexpectedly breaks another
- No single source of truth for API contracts
- Security considerations are not documented per feature
- Observability (logs, metrics) is inconsistent

---

## Decision

We will adopt a **Skills Architecture** where the codebase is organized around cohesive, bounded capabilities called "Skills."

### What is a skill?
A skill is a **logical boundary** representing a cohesive capability of the product. Each skill:
- Has a clear purpose and well-defined boundaries
- Owns specific domain logic, APIs, and database entities
- Documents its contracts (API, DB, events)
- Declares dependencies on other skills explicitly
- Includes security, observability, and testing strategies

### Key Components

1. **Skills Directory (`/skills/`):**
   - Central documentation hub for all skills
   - Each skill has its own folder with structured docs

2. **Skills Registry:**
   - Complete mapping of skills to code locations
   - Dependency declarations
   - Risk assessment
   - Ownership tracking

3. **Dependency Graph:**
   - Visual representation of skill dependencies
   - Helps identify coupling and architectural issues

4. **Per-Skill Documentation:**
   - `skill.md` — Purpose, boundaries, responsibilities
   - `contracts/` — API, DB, events contracts
   - `design/` — Domain model, invariants, threats
   - `runbooks/` — Troubleshooting, observability
   - `tests/` — Test strategy

5. **Conventions:**
   - System-wide standards for naming, APIs, DB, security
   - Ensures consistency across skills

6. **Architecture Overview:**
   - Big picture diagrams (context, container, sequence)
   - Technology decisions and rationale

---

## Alternatives Considered

### Alternative 1: Continue with ad-hoc organization
- **Pros:** No immediate work required
- **Cons:** Pain points worsen as system grows; onboarding stays slow; refactoring stays risky
- **Verdict:** Rejected — technical debt compounds over time

### Alternative 2: Microservices architecture
- **Pros:** Clear boundaries, independent deployment, technology diversity
- **Cons:** High operational overhead, network complexity, distributed transactions, premature optimization
- **Verdict:** Rejected for now — monolith is appropriate for current scale; skills enable future extraction

### Alternative 3: Traditional layered architecture documentation
- **Pros:** Well-understood pattern (presentation → business → data)
- **Cons:** Layers cut across domain boundaries; doesn't capture dependencies well; doesn't enable service extraction
- **Verdict:** Rejected — layers are orthogonal to skills; skills are domain-focused

### Alternative 4: Domain-Driven Design (DDD) with Bounded Contexts
- **Pros:** Mature pattern, strong domain boundaries, rich modeling
- **Cons:** High upfront investment, heavy ceremony, overkill for current team size
- **Verdict:** Partial adoption — skills are inspired by bounded contexts but lighter-weight

---

## Consequences

### Positive

1. **Discoverability:** Engineers can quickly find where functionality lives via registry
2. **Onboarding:** New team members have structured docs to understand the system
3. **Maintainability:** Clear boundaries reduce unintended coupling
4. **Scalability:** Skills can be extracted into services when needed
5. **Documentation:** Living docs kept close to code, easier to maintain
6. **Security:** Threat models documented per skill
7. **Observability:** Consistent logging/metrics strategy per skill
8. **Testing:** Explicit test strategies per skill
9. **Collaboration:** Clear ownership enables parallel work
10. **Refactoring:** Dependency graph makes safe refactoring easier

### Negative

1. **Upfront Cost:** Initial time investment to create skills documentation
2. **Maintenance Overhead:** Docs must be kept in sync with code changes
3. **Learning Curve:** Team must learn new structure and conventions
4. **Discipline Required:** Temptation to skip documentation under pressure
5. **Not Enforced by Code:** Skills are logical, not enforced by compiler/runtime

### Mitigations

- **Upfront Cost:** One-time investment pays dividends over time
- **Maintenance:** Quarterly reviews to keep docs fresh; link docs in PR templates
- **Learning Curve:** Provide playbooks and examples; pair programming
- **Discipline:** Make skills docs part of Definition of Done; review in PRs
- **Enforcement:** Consider linting rules (e.g., no cross-skill imports) in future

---

## Implementation Plan

### Phase 1: Foundation (Week 1) ✅
- [x] Create `/skills/` directory structure
- [x] Write core documentation:
  - [x] README.md
  - [x] SKILLS_REGISTRY.md
  - [x] SKILLS_DEPENDENCY_GRAPH.mmd
  - [x] ADD_A_SKILL_PLAYBOOK.md
  - [x] CONVENTIONS.md
  - [x] ARCHITECTURE_OVERVIEW.md
- [x] Write ADR 0001 (this document)

### Phase 2: Identify Skills (Week 1-2)
- [x] Audit codebase and identify 12 core skills:
  - authentication
  - users-profile
  - accounts
  - categories
  - transactions
  - dashboard
  - reports
  - imports-integrations
  - notifications
  - admin-governance
  - ai-insights
  - infrastructure-platform
- [x] Populate registry with initial mappings

### Phase 3: Document Skills (Week 2-4)
- [ ] Create folder for each skill
- [ ] Write `skill.md` for each skill
- [ ] Document API contracts
- [ ] Document DB contracts
- [ ] Document domain models
- [ ] Document threats (STRIDE-lite)
- [ ] Document observability plans
- [ ] Document test strategies

### Phase 4: Validate (Week 4)
- [ ] Review all docs for completeness
- [ ] Validate all links work
- [ ] Validate Mermaid diagrams render
- [ ] Get team feedback
- [ ] Iterate on conventions based on feedback

### Phase 5: Socialize (Week 5)
- [ ] Team walkthrough session
- [ ] Update onboarding docs to reference skills
- [ ] Add skills docs link to README
- [ ] Update PR template to prompt skills docs updates
- [ ] Add skills review to quarterly planning

### Phase 6: Maintain (Ongoing)
- [ ] Quarterly skills review
- [ ] Update registry when code locations change
- [ ] Update dependency graph when dependencies change
- [ ] Create new ADRs for major architectural decisions
- [ ] Enforce in code reviews

---

## Success Metrics

### Short-Term (3 months)
- [ ] All existing skills documented
- [ ] New team member can find code for any feature in <5 minutes
- [ ] Pull requests include skills docs updates when relevant
- [ ] Zero broken links in skills documentation

### Medium-Term (6 months)
- [ ] Onboarding time reduced by 50%
- [ ] Engineers reference skills docs regularly (survey)
- [ ] Refactoring confidence increased (survey)
- [ ] At least one skill extracted into a service (if needed)

### Long-Term (12 months)
- [ ] Skills architecture becomes "the way we work"
- [ ] Documentation drift near zero
- [ ] Architecture decisions are traceable via ADRs
- [ ] System can scale to 10x users without architectural changes

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docs drift out of sync | High | Medium | Quarterly reviews, PR checks, automation |
| Team doesn't adopt | Medium | High | Training, pair programming, lead by example |
| Overhead slows velocity | Low | Medium | Keep docs concise, iterate on format |
| Skills boundaries wrong | Medium | Medium | Iterate on boundaries, allow refactoring |
| Enforcement is manual | High | Low | Consider linting tools in future |

---

## Related Decisions

- **ADR 0002 (future):** Multi-tenancy architecture
- **ADR 0003 (future):** Event-driven architecture (if adopted)
- **ADR 0004 (future):** Service extraction criteria

---

## References

- [Skills README](../README.md)
- [Skills Registry](../SKILLS_REGISTRY.md)
- [Dependency Graph](../SKILLS_DEPENDENCY_GRAPH.mmd)
- [Conventions](../CONVENTIONS.md)
- [Architecture Overview](../ARCHITECTURE_OVERVIEW.md)

### External Inspiration
- **Domain-Driven Design** (Eric Evans)
- **Building Microservices** (Sam Newman)
- **Team Topologies** (Matthew Skelton, Manuel Pais)
- **The Twelve-Factor App** (Adam Wiggins)

---

## Changelog

- **2026-02-27:** Initial decision, documented all skills
- **[Future]:** Updates as architecture evolves

---

## Review Schedule

- **Next Review:** 2026-05-27 (3 months)
- **Frequency:** Quarterly
- **Reviewers:** Architecture Team + Lead Engineers

---

**Status:** Accepted and implemented.
