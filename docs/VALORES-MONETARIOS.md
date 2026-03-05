# Referência: Valores monetários no projeto

Este documento lista onde valores de dinheiro são usados (entrada, saída, exibição e armazenamento) para manter consistência (pt-BR, 2 decimais, mesmo parsing).

---

## Backend

### Utilitário central
- **`backend/utils/money_utils.py`**
  - `parse_money_value(value)` – Converte string (pt-BR ou en) ou número para `float`. Usar em todo valor vindo de request ou arquivo.

### Serviços que recebem valores (input)
| Arquivo | Campo(s) | Uso |
|---------|----------|-----|
| `services/transaction_service.py` | `amount` | Criação e edição de transação; parcelas. Usa `parse_money_value`. Validação: valor > 0. |
| `services/account_service.py` | `initial_balance`, `balance`, `limit`, `current_balance` | Criação e edição de conta/cartão. Usa `parse_money_value`. |
| `services/import_service.py` | Valores em CSV/OFX | Nubank CSV (novo e antigo), CSV padrão, OFX (XML e regex). Todos usam `parse_money_value`. |

### Serviços que apenas leem do banco (já numérico)
| Arquivo | Uso |
|---------|-----|
| `services/report_service.py` | `float(t.get('amount', 0))`, `float(account.get('initial_balance', 0))` – dados já vêm do DB. |
| `routes/admin.py` | `float(trans.get('amount', 0))`, `float(acc.get('balance', 0))` – leitura. |

### Rotas (payload → serviço)
- **POST/PUT `/api/transactions`** – body com `amount` (e opcionalmente outros) → `TransactionService` (já com `parse_money_value`).
- **POST/PUT `/api/accounts`** – body com `initial_balance`, `limit`, `current_balance` → `AccountService` (já com `parse_money_value`).

---

## Frontend

### Parsing (string → número)
- **`frontend/src/lib/utils.ts`**
  - `parseCurrencyString(value)` – Remove R$, espaços, troca ponto (milhar) e vírgula (decimal) para número. **Sempre usar antes de enviar valores para a API.**

### Formatação (número → exibição)
- **`frontend/src/utils/api.ts`**
  - `formatCurrency(value, currency = 'BRL')` – Exibição em pt-BR (R$ 1.234,56).

### Componentes que exibem ou editam valores
| Componente | Campos | Observação |
|------------|--------|------------|
| `AccountForm.tsx` | `initial_balance`, `current_balance` | Usa `parseCurrencyString` no submit; `CurrencyInput` no formulário. |
| `AccountCard.tsx` | `current_balance`, `projected_balance`, `creditLimit` (limit/initial_balance) | Exibe com `formatCurrency`. |
| `TransactionForm.tsx` | `amount` | `parseCurrencyString` no submit; input de valor. |
| `TransactionList.tsx` | `transaction.amount` | `formatCurrency(transaction.amount)`. |
| `CreditCardForm.tsx` | `limit` | `parseCurrencyString(formData.limit)` no submit. |
| `CreditCardDetail.tsx` | `limit`, `totalUsed`, `expense.amount` | `formatCurrency`. |
| `CreditCardExpenseForm.tsx` | `amount` | `parseCurrencyString(formData.amount)`. |
| `CreditCards.tsx` | `limit`, `used`, `available` | Envio: `initial_balance: cardData.limit`; exibição com `formatCurrency`. |
| `Dashboard.tsx` | Saldos, receitas, despesas, `transaction.amount` | `formatCurrency`. |
| `DashboardCard.tsx` | Valores de KPI | `formatCurrency`. |
| `RecentTransactions.tsx` | `transaction.amount` | `formatCurrency`. |
| `Reports.tsx` / `ReportChart.tsx` | `item.total`, `current_balance` | `formatCurrency` ou número direto. |
| `Planning.tsx` / `PlanningForm.tsx` / `PlanningSummary.tsx` | `amount`, `category_budgets[].amount`, totais | `parseCurrencyString` onde há input; `formatCurrency` na exibição. |
| `Accounts.tsx` | `totalBalance`, `projected_balance` | Soma de `current_balance`/`projected_balance`; exibição formatada. |
| `UserDetail.tsx` (admin) | `balance`, `trans.amount`, `account.balance` | `toLocaleString('pt-BR', { minimumFractionDigits: 2 })`. |

### Input reutilizável
- **`frontend/src/components/ui/CurrencyInput.tsx`**
  - `decimalSeparator=','`, `groupSeparator='.'` (pt-BR). Integrado com `react-currency-input-field`; o valor exibido já segue o padrão.

---

## Banco de dados (Supabase/Postgres)

- **Tabela `accounts`**: `balance`, `initial_balance`, `current_balance` → `numeric(15,2)`.
- **Tabela `transactions`**: `amount` → `numeric(15,2) NOT NULL`.

Sempre persistir valores como número (float/decimal), nunca string formatada.

---

## Regras de consistência

1. **API (backend)**  
   - Receber string (ex.: "1.000,50") ou número.  
   - Usar `parse_money_value()` antes de validar ou gravar.

2. **Frontend → API**  
   - Enviar número (ex.: `parseCurrencyString` no submit) ou string já normalizada; o backend aceita os dois via `parse_money_value`.

3. **Exibição**  
   - Usar `formatCurrency(value)` (ou equivalente pt-BR) em todos os valores monetários na UI.

4. **Importação (CSV/OFX)**  
   - Aceitar pt-BR (1.000,50) e en (1000.50).  
   - Todo parsing de valor passa por `parse_money_value` no backend.
