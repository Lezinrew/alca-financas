## Recipe: open-pr

**Goal:** Abrir um Pull Request com contexto mínimo porém suficiente para revisão rápida.

### Pre-requisitos

- Branch criada a partir de `main`.
- Commits já feitos e empurrados (`git push`).

### Steps

1. **Garanta que está na branch correta:**
   ```bash
   git status
   git branch
   ```

2. **Suba a branch (caso ainda não tenha feito):**
   ```bash
   git push -u origin <sua-branch>
   ```

3. **Abra o PR via GitHub UI ou CLI:**
   - Via navegador: abra o repositório e use o banner “Compare & pull request”.
   - Via CLI (se configurado):
     ```bash
     gh pr create
     ```

4. **Use o template de PR:**
   - Preencha **Resumo** em 2–4 bullet points.
   - Liste **Testes executados** (comandos `make` ou `npm`/`pytest` usados).
   - Referencie o skill principal afetado (ex.: `skills/transactions`).

5. **Marque revisores e labels:**
   - Adicione pelo menos um revisor responsável.
   - Adicione label de tipo: `feature`, `bug`, `chore`, `security` (se aplicável).

### Para agentes de IA

- Leia apenas:
  - `skills/README.md`
  - `skills/SKILLS_REGISTRY.md`
  - `skills/github-operations/skill.md`
  - Arquivos listados em `git diff --name-only origin/main...HEAD`
- Não carregue o repositório inteiro na memória.

