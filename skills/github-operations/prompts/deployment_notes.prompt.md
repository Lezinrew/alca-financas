You are writing **deployment notes** for a change in production for Alça Finanças.

Context you may read:
- `skills/README.md`
- `skills/SKILLS_REGISTRY.md`
- `skills/github-operations/skill.md`
- The diff and list of changed files relevant to this deploy.

Do **NOT** read the entire repository.

Output format (markdown):

```markdown
## Deployment Notes

### Scope
- Skills / areas touched: ...

### Migrations
- DB or config changes: ...
- Rollback plan: ... (reference `scripts/prod/rollback.sh` or relevant strategy)

### Verifications
- Post-deploy checks:
  - [ ] Login
  - [ ] Dashboard carrega dados
  - [ ] Transações CRUD
  - [ ] Funcionalidade específica alterada

### Known Risks
- ...
```

Keep it short and actionable for operators. Focus on what to verify and como reverter em caso de problema.

