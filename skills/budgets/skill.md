## Skill: budgets

**Status:** Planned  
**Domain:** Budgets, metas financeiras e comparação orçamento vs realizado.

---

### Purpose

Definir e acompanhar orçamentos por categoria/período e metas de gastos, possibilitando visualizações de “budget vs actual”.

---

### Code Mapping (to confirm)

Atualmente não há módulos claramente dedicados apenas a budgets; o tema aparece como lacuna em análises e TODOs.

- **Backend (pontos de partida):**
  - `backend/services/report_service.py` — TODO: procurar agregações que possam servir de base para budgets.
  - `backend/routes/reports.py` — TODO: checar endpoints que poderiam expor comparações planejado vs realizado.
- **Frontend (pontos de partida):**
  - `frontend/src/components/reports/Reports.tsx` — TODO: avaliar se já há gráficos de budget vs actual planejados.

**TODO (DB):**  
- Procurar em `scripts/db/` e `backend/database/` se há tabelas/colunas candidatas (ex.: `monthly_budget`, `goal_amount`).  
- Se não houver, budgets permanecem como visão derivada em cima de `transactions` + `categories`.

---

### API Routes (to confirm)

Nenhum endpoint específico identificado ainda.

- TODO: quando budgets forem implementados, documentar aqui:
  - rota para definir/atualizar orçamentos;
  - rota para recuperar comparações por categoria/período.

---

### References

- `docs/RAIO-X-ARQUITETURA-COMPLETO.md` — lacunas identificadas em metas e budgets.
- `skills/reports/skill.md` — relatórios que provavelmente consumirão dados de budgets.
- `skills/categories/skill.md` — categorias como eixo principal de orçamento.

