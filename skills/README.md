# Skills Architecture — Alça Finanças

**Last Updated:** 2026-02-27
**Status:** Active
**Purpose:** This directory defines the modular capabilities (Skills) of the Alça Finanças platform.

---

## What are Skills?

**Skills** are cohesive, bounded capabilities of the product. Each skill:
- Has clear ownership boundaries
- Defines its own domain model and invariants
- Exposes well-defined contracts (API, DB, events)
- Can be understood, tested, and evolved independently
- Maps to specific code locations in the repository

Skills are NOT microservices (yet). They are **logical boundaries** within a modular monolith that enable:
- **Discoverability:** Engineers can quickly find where functionality lives
- **Scalability:** Clear boundaries enable future extraction into services
- **Maintainability:** Changes are localized; blast radius is contained
- **Onboarding:** New team members understand the system faster

---

## Skills in This System

| Skill | Purpose | Status |
|-------|---------|--------|
| **authentication** | User authentication (JWT, OAuth, Supabase Auth) | ✅ Active |
| **users-profile** | User profile, settings, preferences | ✅ Active |
| **tenant-core** | Multi-tenant model (tenants, membership, tenant_id on domain tables, RLS helpers) | ⚠️ Planned / in rollout |
| **accounts** | Financial accounts (bank, credit cards, savings) | ✅ Active |
| **categories** | Income/expense categorization | ✅ Active |
| **transactions** | Core financial ledger (transactions, installments, recurring) | ✅ Active |
| **recurring** | Recurring transactions and fixed expenses (logical view over `transactions`) | ⚠️ Planned / embedded in `transactions` |
| **budgets** | Budgets and goals per category/period (planned) | ⚠️ Planned |
| **dashboard** | KPIs, charts, analytics | ✅ Active |
| **reports** | Financial reports (overview, evolution, comparison) | ✅ Active |
| **imports-integrations** | CSV import, external data integration, auto-detection | ✅ Active |
| **notifications** | Email service, alerts, notifications | ✅ Active |
| **admin-governance** | Admin panel, user management, audit logs | ✅ Active |
| **ai-insights** | AI-powered category/account detection | ✅ Active |
| **infrastructure-platform** | RLS, rate limiting, CORS, monitoring, CI/CD | ✅ Active |
| **github-operations** | GitHub workflows, CI/CD, release/deploy runbooks | ✅ Active |

---

## How to Navigate

### Quick Links
- **[Skills Registry](./SKILLS_REGISTRY.md)** — Complete mapping of skills to code locations
- **[Dependency Graph](./SKILLS_DEPENDENCY_GRAPH.mmd)** — Visual dependencies between skills
- **[Add a Skill Playbook](./ADD_A_SKILL_PLAYBOOK.md)** — Step-by-step guide to add new skills
- **[Conventions](./CONVENTIONS.md)** — Naming, API, DB, security standards
- **[Architecture Overview](./ARCHITECTURE_OVERVIEW.md)** — Big picture architecture with diagrams
- **[ADRs](./ADRs/)** — Architecture Decision Records

### Per-Skill Documentation Structure

Each skill has its own folder with:

```
skills/<skill-name>/
├── skill.md                      # Main skill documentation
├── contracts/
│   ├── api.md                    # API routes and contracts
│   ├── db.md                     # Database tables, RLS, indexes
│   └── events.md                 # Domain events (pub/sub)
├── design/
│   ├── domain-model.md           # Entities, relationships, glossary
│   ├── invariants.md             # Business rules that must never break
│   └── threats.md                # Security threat model (STRIDE-lite)
├── runbooks/
│   ├── troubleshooting.md        # Common issues and fixes
│   └── observability.md          # Logs, metrics, traces
└── tests/
    └── test-strategy.md          # Test coverage strategy
```

---

## Code Mapping

Skills map to code in the following patterns:

| Skill | Backend Routes | Backend Services | Frontend Components | Database Tables |
|-------|----------------|------------------|---------------------|-----------------|
| **authentication** | `routes/auth.py`, `routes/auth_supabase.py` | `services/supabase_auth_service.py`, `services/user_service.py` | `components/auth/*` | `users`, `oauth_states` |
| **transactions** | `routes/transactions.py` | `services/transaction_service.py` | `components/dashboard/TransactionsList.tsx` | `transactions` |
| **accounts** | `routes/accounts.py` | `services/account_service.py` | `components/accounts/*` | `accounts` |
| **categories** | `routes/categories.py` | `services/category_service.py` | `components/categories/*` | `categories` |

_See [SKILLS_REGISTRY.md](./SKILLS_REGISTRY.md) for complete mapping._

---

## Design Principles

1. **Single Responsibility:** Each skill owns a cohesive domain area
2. **Explicit Contracts:** APIs, DB schemas, events are documented
3. **Dependency Clarity:** Skills declare dependencies on other skills
4. **Security by Design:** Each skill documents threats and mitigations
5. **Observability First:** Logs, metrics, traces are planned upfront
6. **Test Strategy:** Unit, integration, E2E coverage is explicit
7. **Evolution Mindset:** Skills can be extracted into services when needed

---

## Getting Started

### For Developers
1. Read [CONVENTIONS.md](./CONVENTIONS.md) to understand standards
2. Check [SKILLS_REGISTRY.md](./SKILLS_REGISTRY.md) to find where code lives
3. Read the skill's `skill.md` for context before making changes

### For Architects
1. Review [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) for system design
2. Check [SKILLS_DEPENDENCY_GRAPH.mmd](./SKILLS_DEPENDENCY_GRAPH.mmd) for coupling analysis
3. Read [ADRs](./ADRs/) for historical decisions

### For New Features
1. Follow [ADD_A_SKILL_PLAYBOOK.md](./ADD_A_SKILL_PLAYBOOK.md) to add a new skill
2. Update [SKILLS_REGISTRY.md](./SKILLS_REGISTRY.md) with new mappings
3. Add ADR if architectural decision is needed

---

## Maintenance

- **Review Cycle:** Quarterly review of skills boundaries
- **Ownership:** Each skill should have a designated owner (team or individual)
- **Deprecation:** Mark skills as deprecated in registry before removal
- **Evolution:** Skills can be split, merged, or extracted based on needs

---

## Questions?

- Check existing skill documentation first
- Review [ADRs](./ADRs/) for context on decisions
- Raise issues in the repository for clarifications
- Update docs when you find gaps (PRs welcome!)

---

**Remember:** Skills are living documentation. Keep them updated as the system evolves.
