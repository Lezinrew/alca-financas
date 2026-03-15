# Planejamento (Budget Planning) — System Design

Separação clara entre **planejado** (budget_*) e **real** (transactions). Um único endpoint agrega todas as métricas.

---

## 1. Data Model

### Tabelas

**budget_monthly** (uma linha por tenant/mês)

| Coluna              | Tipo     | Descrição                    |
|---------------------|----------|------------------------------|
| id                  | uuid     | PK                           |
| tenant_id           | uuid     | FK tenants                   |
| month               | smallint | 1–12                         |
| year                | smallint | 2020–2100                    |
| planned_income      | numeric  | Receita planejada do mês     |
| savings_percentage  | numeric  | % meta de economia (0–100)   |
| created_at, updated_at | timestamptz | |

**budget_plans** (valor planejado por categoria por mês)

| Coluna         | Tipo    | Descrição              |
|----------------|---------|------------------------|
| id             | uuid    | PK                     |
| tenant_id      | uuid    | FK tenants             |
| month, year    | smallint| Período                |
| category_id    | uuid    | FK categories          |
| planned_amount | numeric | Limite/orça da categoria |
| created_at, updated_at | timestamptz | |

- UNIQUE(tenant_id, month, year) em budget_monthly.
- UNIQUE(tenant_id, month, year, category_id) em budget_plans.

---

## 2. API Contract

### GET /api/planning/month

**Query:** `month` (1–12), `year` (opcional; default atual).

**Resposta 200:**

```json
{
  "period": { "month": 3, "year": 2026 },
  "planned_income": 5600,
  "planned_expenses": 2222,
  "real_income": 5600,
  "real_expenses": 300,
  "balance_real": 5300,
  "balance_planned": 3378,
  "savings_rate": 94.64,
  "savings_percentage_planned": 20,
  "categories": [
    {
      "category_id": "uuid",
      "category_name": "Transporte",
      "category_color": "#3B82F6",
      "category_icon": "car",
      "planned": 1111,
      "spent": 300,
      "remaining": 811,
      "progress_percent": 27
    }
  ]
}
```

- **planned_income** → `budget_monthly.planned_income`
- **planned_expenses** → soma de `budget_plans.planned_amount` (só categorias de despesa, se no futuro houver tipo)
- **real_income / real_expenses** → soma de `transactions` no mês por `type`
- **balance_real** = real_income - real_expenses
- **balance_planned** = planned_income - planned_expenses
- **savings_rate** = (balance_real / real_income) * 100
- **categories[].spent** = soma de transações `type = 'expense'` por `category_id`
- **categories[].remaining** = planned - spent
- **categories[].progress_percent** = (spent / planned) * 100 quando planned > 0

### PUT /api/planning/month

**Body:**

```json
{
  "month": 3,
  "year": 2026,
  "planned_income": 5600,
  "savings_percentage": 20,
  "category_plans": [
    { "category_id": "uuid-1", "planned_amount": 500 },
    { "category_id": "uuid-2", "planned_amount": 1111 }
  ]
}
```

**Resposta 200:** `{ "message": "Planejamento salvo com sucesso", "month": 3, "year": 2026 }`

Requer `tenant_id` (ex.: `@require_tenant`).

---

## 3. SQL Examples (agregação)

Transações reais no mês (receita/despesa):

```sql
SELECT type, SUM(amount) AS total
FROM transactions
WHERE user_id = :user_id
  AND tenant_id = :tenant_id
  AND date >= :start_date
  AND date < :end_date
GROUP BY type;
```

Gasto real por categoria (despesas):

```sql
SELECT category_id, SUM(amount) AS spent
FROM transactions
WHERE user_id = :user_id
  AND tenant_id = :tenant_id
  AND type = 'expense'
  AND date >= :start_date
  AND date < :end_date
GROUP BY category_id;
```

Planejado por categoria:

```sql
SELECT category_id, planned_amount
FROM budget_plans
WHERE tenant_id = :tenant_id AND month = :month AND year = :year;
```

Receita planejada do mês:

```sql
SELECT planned_income, savings_percentage
FROM budget_monthly
WHERE tenant_id = :tenant_id AND month = :month AND year = :year;
```

### Índices recomendados (já na migration)

- **transactions:** `(tenant_id, user_id, date DESC)`, `(type)`, `(category_id)`
- **budget_plans:** `(tenant_id, year, month)`, `(category_id)`
- **budget_monthly:** `(tenant_id, year, month)`

---

## 4. Frontend — Estrutura de componentes

```
Planning/
├── index.ts
├── Planning.tsx                 # Página: layout 3 seções, um GET /api/planning/month
├── PlanningMonthOverview.tsx    # Seção 1: cards (Planned Income, Real Income, …)
├── PlanningCategoryProgress.tsx # Seção 2: tabela/cards por categoria (Planned, Spent, Remaining, barra %)
├── PlanningHealth.tsx           # Seção 3: over/under budget, previsão economia
├── PlanningForm.tsx             # Modal: definir/copiar orçamento → PUT /api/planning/month
└── PlanningSummary.tsx          # (opcional) resumo lateral reutilizável
```

- **Uma chamada:** ao abrir a tela ou mudar mês/ano, apenas `GET /api/planning/month?month=&year=`.
- Estado: `planningPayload | null`, `month`, `year`; loading/error.
- Cores de progresso: verde (&lt; 75%), amarelo (75–100%), vermelho (&gt; 100%).

---

## 5. UI Layout (proposta)

**Seção 1 — Monthly Overview (grid de cards)**

| Card              | Fonte no payload     |
|-------------------|----------------------|
| Planned Income    | planned_income       |
| Planned Expenses  | planned_expenses     |
| Real Income       | real_income          |
| Real Expenses     | real_expenses        |
| Real Balance      | balance_real         |
| Savings Rate      | savings_rate %       |

**Seção 2 — Budget Progress by Category**

Tabela: Categoria | Planejado | Gasto | Restante | Barra (progress_percent).

- Barra: verde &lt; 75%, amarelo 75–100%, vermelho &gt; 100%.

**Seção 3 — Budget Health**

- Lista “Acima do orço” (progress_percent &gt; 100).
- Lista “Dentro do orço” (progress_percent ≤ 100).
- Previsão de economia do mês com base em balance_real.

---

## 6. Evolução futura (apenas desenho)

- **Orçamento recorrente:** repetir budget_plans por mês (job ou regra “copiar mês anterior”).
- **Rollover:** coluna `rollover_amount` em budget_plans ou tabela de “sobra por categoria”.
- **Alertas:** tabela `budget_alerts` (category_id, threshold_percent, notificar quando progress_percent &gt; threshold).
- **Insights / multi-mês:** endpoint opcional `GET /api/planning/compare?months=3` agregando N meses; preparar payload para gráficos.

Nenhuma dessas alterações quebra o contrato atual de GET/PUT /api/planning/month.
