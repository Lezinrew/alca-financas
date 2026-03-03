## Contribuindo para Alça Finanças

Obrigado por contribuir! Este projeto utiliza uma arquitetura baseada em **Skills**.

Antes de abrir PRs grandes, familiarize-se com:

- `skills/README.md` — visão geral do sistema de Skills.
- `skills/SKILLS_REGISTRY.md` — mapeamento de skills para código.
- `skills/ARCHITECTURE_OVERVIEW.md` — visão arquitetural.
- `skills/ADD_A_SKILL_PLAYBOOK.md` — como adicionar/alterar skills.

---

### Fluxo de trabalho básico

1. **Crie uma branch:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/minha-feature
   ```

2. **Use o Makefile para qualidade local:**
   ```bash
   make lint
   make test
   make typecheck
   make build
   ```

3. **Faça commits pequenos e descritivos:**
   - Siga `skills/github-operations/recipes/commit-conventional.md`.

4. **Abra um Pull Request:**
   - Use o template em `.github/PULL_REQUEST_TEMPLATE.md`.
   - Cite o(s) skill(s) afetado(s) (`skills/SKILLS_REGISTRY.md`).

---

### Onde fazer mudanças

- **Backend (Flask/Supabase):**
  - `backend/routes/*`
  - `backend/services/*`
  - `backend/repositories/*`

- **Frontend (React/Vite):**
  - `frontend/src/components/*`
  - `frontend/src/contexts/*`
  - `frontend/src/utils/*`

- **Docs:**
  - Use a estrutura em `docs/00-overview` a `docs/07-contributing`.
  - Atualize sempre `docs/INDEX.md` quando criar novos docs relevantes.

---

### Skills e governança

Ao alterar uma parte significativa do sistema:

- Verifique qual skill é o dono da área (`skills/SKILLS_REGISTRY.md`).
- Atualize:
  - `skills/<skill>/skill.md` (se o contexto mudou).
  - Contratos em `skills/<skill>/contracts/*.md` (API/DB/events).
  - Invariantes em `skills/<skill>/design/invariants.md`, se necessário.

---

### Perguntas e melhorias

- Use os templates de issue em `.github/ISSUE_TEMPLATE/*.yml`.
- Para mudanças em CI/CD e GitHub, consulte:
  - `skills/github-operations/skill.md`
  - `skills/github-operations/recipes/*`

