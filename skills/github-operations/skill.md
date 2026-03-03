## Skill: github-operations

**Status:** Active  
**Domain:** Developer productivity, GitHub workflows, CI/CD orchestration  

---

### Purpose

Centralizar todo o conhecimento operacional ligado a GitHub (branches, PRs, reviews, releases e deploys) em um único skill, otimizado para uso por agentes de IA com baixo consumo de tokens.

---

### Business Value

- **Fluxo previsível de entrega:** garante que todos os PRs passem por quality gates consistentes.
- **Onboarding rápido:** novos contribuidores seguem receitas claras para branches, commits, PRs e releases.
- **Redução de incidentes:** opera com runbooks explícitos de deploy e rollback.
- **IA-friendly:** instruções curtas e focadas evitam que agentes leiam o repositório inteiro.

---

### Boundaries

**Inclui:**
- Convenções de branch, commit e PR.
- Uso de `Makefile` e comandos de CI locais.
- Interação com workflows em `.github/workflows`.
- Runbooks de deploy e rollback usando scripts em `scripts/prod/`.

**Não inclui:**
- Definição de regras de negócio do produto.
- Modelagem de banco de dados ou RLS.
- Implementação de features em backend/frontend (apenas orquestra entrega).

---

### Code Mapping

#### DevOps / GitHub
- `.github/workflows/ci.yml`
- `.github/workflows/gitleaks.yml`
- `.github/workflows/deploy-production.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/*.yml`
- `CODEOWNERS`
- `CONTRIBUTING.md`
- `Makefile`

#### Production Scripts
- `scripts/prod/build.sh`
- `scripts/prod/run.sh`
- `scripts/prod/migrate.sh`
- `scripts/prod/deploy.sh`
- `scripts/prod/rollback.sh`

---

### AI Token Optimization Strategy

- **Contexto mínimo recomendado para agentes:**
  - `skills/README.md`
  - `skills/SKILLS_REGISTRY.md`
  - `skills/github-operations/skill.md`
  - Apenas os arquivos modificados no diff atual (por exemplo, `git diff --name-only HEAD~1`).
- **Evitar:**
  - Carregar todo o repositório ou toda a pasta `frontend/` ou `backend/`.
  - Ler todos os workflows; foque apenas em `ci.yml` e `deploy-production.yml` quando necessário.
- **Estratégia:**
  - Usar receitas em `skills/github-operations/recipes/` como fonte primária de verdade.
  - Usar prompts em `skills/github-operations/prompts/` para gerar descrições de PR, mensagens de commit e changelogs.

---

### Model Escalation Policy (Tier 0–3)

- **Tier 0 — Tarefas triviais**
  - Atualizar changelog pequeno.
  - Ajustar título/descrição de PR.
  - Gerar mensagem de commit simples.

- **Tier 1 — Tarefas de CI leves**
  - Modificar passo simples em workflow existente (sem alterar lógica de deploy).
  - Ajustar cache, versões de linguagem ou paths.

- **Tier 2 — Entrega e Qualidade**
  - Alterar gates de CI (lint, testes, build).
  - Adicionar novo job (por exemplo, docs-link-check).
  - Atualizar scripts de deploy sem mudar arquitetura de infra.

- **Tier 3 — Mudanças de Infra/Segurança**
  - Alterar estratégia de deploy (novo provider, novo registry).
  - Modificar autenticação de runner, secrets, chaves SSH.
  - Qualquer alteração que possa impactar produção deve ser:
    - Proposta em PR separado.
    - Revisada manualmente por humano com contexto completo do ambiente.

---

### References

- `docs/INDEX.md` (seção DevOps & Operations)
- `docs/06-ops/DADOS-DEPLOY.md`
- `docs/OPENCLAW-DEPLOY-SEGURO.md`
- `docs/MCP-HOSTINGER.md`

