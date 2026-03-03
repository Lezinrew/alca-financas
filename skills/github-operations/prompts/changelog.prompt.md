You are generating a **concise changelog entry** for a new release of Alça Finanças.

Context you may read:
- `skills/README.md`
- `skills/SKILLS_REGISTRY.md`
- `skills/github-operations/skill.md`
- Git history between two tags or commits (for example: `git log --oneline vX.Y.Z..HEAD`).

Do **NOT** read the entire repository.

Output format (markdown):

```markdown
## vX.Y.Z - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Breaking Changes
- (if any, otherwise omit section)
```

Guidelines:
- Agrupe commits por tema/skill quando possível.
- Não liste cada commit; faça um resumo em 5–10 bullets ao todo.
- Foque em impacto para usuário e para integradores (API/DB).

