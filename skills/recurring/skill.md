## Skill: recurring

**Status:** Planned / embedded inside `transactions`  
**Domain:** Recurring transactions and fixed monthly expenses.

---

### Purpose

Representar despesas e receitas recorrentes (ex.: aluguel, assinaturas, salário), bem como regras para geração automática de lançamentos futuros.

---

### Code Mapping (to confirm)

> Este skill hoje está principalmente embutido em `transactions`. Os pontos abaixo são hipóteses guiadas pelo código e devem ser verificados antes de evoluções maiores.

- **Backend (suspeito):**
  - `backend/services/transaction_service.py` — TODO: verificar campos `is_recurring`, `installment_info` ou similares.
  - `backend/routes/transactions.py` — TODO: conferir filtros por recorrência e parcelas.
- **Frontend (suspeito):**
  - `frontend/src/components/transactions/*` — TODO: inspecionar campos ligados a recorrência ou despesas fixas.

**TODO (tables/migrations):**  
- Verificar em `backend/database/migrations/` ou `scripts/db/` se há colunas como `is_recurring`, `recurrence_type`, `installment_info` na tabela `transactions`.

---

### API Routes (to confirm)

> Não definir novos endpoints sem validar no código.

- TODO: inspecionar `backend/routes/transactions.py` para rotas que lidam com:
  - criação/edição de transações recorrentes;
  - replicação automática mensal;
  - cancelamento/atualização de séries recorrentes.

---

### References

- `docs/INDEX.md` — visão geral de documentação.
- `docs/RAIO-X-ARQUITETURA-COMPLETO.md` — visão macro da arquitetura.
- `skills/transactions/skill.md` — skill pai lógico onde recorrência está embutida.

