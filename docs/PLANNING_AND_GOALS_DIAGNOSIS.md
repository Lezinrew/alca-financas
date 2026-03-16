# Diagnóstico: Planejamento e Metas (Alça Finanças)

## 1. Estado atual do módulo Planejamento

### Frontend
- **Página:** `frontend/src/components/planning/Planning.tsx`
- **Fonte de dados:** Uma única chamada `GET /api/planning/month?month=&year=` (e `GET /api/planning/month/categories` para o formulário).
- **Estrutura em 4 zonas:**
  - **Zona 1 — Resumo mensal:** `PlanningMonthOverview.tsx` — cards com receita/despesa planejada e real, saldo, taxa de economia.
  - **Zona 2 — Despesas:** `PlanningExpenseProgress.tsx` — tabela só de categorias de despesa (planejado, gasto, restante, progresso, status: safe/warning/exceeded/unplanned).
  - **Zona 3 — Receitas:** `PlanningIncomeTracking.tsx` — tabela só de categorias de receita (meta, recebido, diferença, progresso, status: on_track/below_target/exceeded_target).
  - **Zona 4 — Insights:** `PlanningAlerts.tsx` — alertas (acima do orçamento, perto do limite, gasto sem orçamento, boa economia).
- **Modal de edição:** `PlanningForm.tsx` — envia `PUT /api/planning/month` com `planned_income`, `savings_percentage`, `category_plans`.

### API (backend)
- **GET /api/planning/month** — Payload agregado: `period`, `summary` (planned_income, planned_expenses, planned_balance, real_income, real_expenses, real_balance, savings_rate), `expense_categories`, `income_categories`, `alerts`.
- **PUT /api/planning/month** — Salva planejamento completo (body: month, year, planned_income, savings_percentage, category_plans).
- **POST /api/planning/month** — Cria/atualiza linhas de orçamento (body: month, year, lines).
- **GET /api/planning/month/categories** — Categorias para planejamento (expense / income).
- **DELETE /api/planning/month/<id>** — Remove uma linha de orçamento.

### Backend (serviços e repositório)
- **Serviço:** `backend/services/planning_service.py` — Agrega transações (fatos) e budget_plans/budget_monthly (planos). Separa receita e despesa por categoria; calcula status e alertas.
- **Repositório:** `backend/repositories/budget_repository_supabase.py` — Acesso a `budget_monthly` e `budget_plans`.
- **Constantes:** `backend/services/planning_constants.py` — Status de despesa/receita e tipos de alerta.

### Banco de dados
- **budget_monthly:** Uma linha por (tenant_id, month, year): planned_income, savings_percentage.
- **budget_plans:** Uma linha por (tenant_id, user_id, month, year, category_id): planned_amount, notes. UNIQUE(tenant_id, user_id, month, year, category_id).

### Agregação e regras
- **Fatos:** Totais e valores por categoria vêm de `transactions` (filtro por user_id, tenant_id, intervalo do mês).
- **Planos:** Totais e valores por categoria vêm de `budget_plans` e `budget_monthly`.
- Receita e despesa **não** são misturadas: listas separadas `income_categories` e `expense_categories`.

### Conclusão Planejamento
O módulo Planejamento já está refatorado com separação clara receita/despesa, 4 zonas e uma API única. Foi adicionado o insight “Mês com boa economia” (strong_savings_month) quando savings_rate >= 20%.

---

## 2. Novo módulo: Metas (Goals)

- **Conceito:** Objetivos financeiros de longo prazo (viagem, reserva de emergência, carro, quitar dívida, etc.).
- **Separação de domínio:** transactions = realidade; planning = intenção mensal; **goals = propósito de longo prazo**.
- **Implementação:** Tabelas `goals` e `goal_contributions`; backend (repo, service, routes); frontend (lista em cards, detalhe com histórico de aportes, imagem inspiracional via `image_url`).

### 2.1 Banco de dados (goals)

- `goals`: id, tenant_id, user_id, title, description, target_amount, current_amount, target_date, image_url, status (active|completed|paused), created_at, updated_at.
- `goal_contributions`: id, goal_id, tenant_id, user_id, amount, date, source_type, source_reference_id, notes, created_at.
- RLS e triggers `updated_at` aplicados.

### 2.2 API (Metas)

- **GET /api/goals** — Lista metas do usuário (query `status` opcional: active, completed, paused). Resposta: array de metas com `progress_percent`, `remaining_amount`, `months_remaining`, `monthly_needed`.
- **POST /api/goals** — Cria meta. Body: title, description?, target_amount, current_amount?, target_date?, image_url?, status?.
- **GET /api/goals/:id** — Detalhe da meta (com campos calculados).
- **PUT /api/goals/:id** — Atualiza meta.
- **DELETE /api/goals/:id** — Remove meta (contribuições em cascata).
- **GET /api/goals/:id/contributions** — Lista aportes.
- **POST /api/goals/:id/contributions** — Adiciona aporte. Body: amount, date?, source_type?, source_reference_id?, notes?. Atualiza `current_amount` da meta.

### 2.3 Frontend (Metas)

- **Lista:** `/goals` — grid de cards (imagem, título, meta, guardado, progresso, status); filtro por status; botão "Nova meta".
- **Nova meta:** `/goals/new` — formulário (título, descrição, valor, data alvo, URL da imagem).
- **Detalhe:** `/goals/:id` — banner imagem, progresso, restante, prazo, valor/mês necessário, botão "Adicionar aporte", histórico de aportes.
- **Editar:** `/goals/:id/edit` — mesmo formulário com dados da meta.
- Imagem: suportada via `image_url` (upload pode ser adicionado depois com storage).

---

## 3. Checklist de testes manuais

### Planejamento
- [ ] GET /api/planning/month retorna summary, expense_categories, income_categories e alerts.
- [ ] Receita e despesa não aparecem na mesma tabela (zonas 2 e 3 separadas).
- [ ] Transações do mês atualizam receita/despesa real e totais por categoria.
- [ ] Alertas: acima do orçamento, perto do limite, gasto sem orçamento, boa economia (quando savings_rate >= 20%).
- [ ] Isolamento por tenant: trocar workspace altera dados do planejamento.

### Metas
- [ ] Criar meta: título, valor, data alvo, URL de imagem (opcional).
- [ ] Lista de metas: cards com imagem, progresso, status; filtro por status.
- [ ] Detalhe da meta: progresso, restante, valor/mês necessário, histórico de aportes.
- [ ] Adicionar aporte: valor e observação; current_amount da meta atualiza.
- [ ] Editar meta: alterar título, valor, data, imagem, status.
- [ ] Isolamento por tenant: metas de um workspace não aparecem em outro.
