# Schema & Constraints — AlcaHub (alca-financas)

Este documento centraliza a especificação formal de todas as constraints, CHECKs, chaves únicas, restrições relacionais e políticas de isolamento multi-tenant do banco de dados Postgres / Supabase.

---

## 1. Tabela: `transactions` (Movimentações Financeiras Realizadas)

| Coluna | Tipo | Nulo | Default | Descrição / Restrição |
|---|---|---|---|---|
| `id` | `UUID` | Não | `gen_random_uuid()` | Chave primária |
| `user_id` | `UUID` | Não | — | Usuário proprietário (`auth.users(id)`) |
| `tenant_id` | `UUID` | Não | — | Workspace / Tenant (`tenants(id)`) |
| `account_id` | `UUID` | Sim | `NULL` | Conta bancária / Cartão (`accounts(id)`) |
| `account_tenant_id` | `UUID` | Não | — | FK composta: `account_tenant_id = tenant_id` |
| `category_id` | `UUID` | Sim | `NULL` | Categoria (`categories(id)`) |
| `category_tenant_id` | `UUID` | Não | — | FK composta: `category_tenant_id = tenant_id` |
| `description` | `VARCHAR(500)` | Não | — | Descrição da transação |
| `amount` | `NUMERIC(15,2)` | Não | — | Valor financeiro absoluto (`CHECK (amount >= 0)`) |
| `type` | `VARCHAR(20)` | Não | — | `CHECK (type IN ('income', 'expense', 'transfer'))` |
| `status` | `VARCHAR(20)` | Sim | `'pending'` | `CHECK (status IN ('paid', 'pending', 'overdue', 'cancelled'))` |
| `date` | `DATE` | Não | — | Data da ocorrência / liquidação |
| `is_recurring` | `BOOLEAN` | Sim | `false` | Indicador de recorrência |
| `responsible_person`| `VARCHAR(255)` | Sim | `NULL` | Nome do responsável familiar |
| `installment_info` | `JSONB` | Sim | `NULL` | Parcelamento: `{current, total, original_amount}` |
| `entry_source` | `VARCHAR(50)` | Sim | `'manual'` | Origem: `'manual'`, `'ofx'`, `'csv'`, `'api'` |
| `source_file` | `TEXT` | Sim | `NULL` | Nome do arquivo de importação |
| `fitid` | `TEXT` | Sim | `NULL` | Identificador bancário único OFX |
| `dedup_key` | `TEXT` | Sim | `NULL` | Chave determinística de deduplicação universal |
| `import_batch_id` | `UUID` | Sim | `NULL` | Vínculo com lote (`import_batches(id)`) |
| `legacy_id` | `TEXT` | Sim | `NULL` | ID original migrado de outras fontes |
| `created_at` | `TIMESTAMPTZ` | Sim | `now()` | Timestamp de criação |
| `updated_at` | `TIMESTAMPTZ` | Sim | `now()` | Timestamp de atualização |

### Constraints e Índices:
- `CONSTRAINT transactions_type_check CHECK (type IN ('income', 'expense', 'transfer'))`
- `CONSTRAINT transactions_status_check CHECK (status IN ('paid', 'pending', 'overdue', 'cancelled'))`
- `CONSTRAINT transactions_account_tenant_matches CHECK (account_tenant_id = tenant_id)`
- `CONSTRAINT transactions_category_tenant_matches CHECK (category_tenant_id = tenant_id)`
- `UNIQUE (tenant_id, dedup_key)`: Impede inserção de duplicatas no mesmo workspace.
- `INDEX idx_transactions_tenant_date ON transactions(tenant_id, date DESC)`
- `INDEX idx_transactions_import_batch_id ON transactions(import_batch_id)`

---

## 2. Tabela: `financial_expenses` (Contas a Pagar / Projeções Fixas)

> [!IMPORTANT]
> `financial_expenses` gerencia o planejamento e previsão de contas a pagar. Não se confunde com `transactions` (realizado). Lançamentos pendentes **não** afetam o saldo nem os dashboards de transações realizadas.

| Coluna | Tipo | Nulo | Default | Restrição / Valores Válidos |
|---|---|---|---|---|
| `category` | `TEXT` | Não | — | `CHECK (category IN ('alimentação', 'cartões', 'educação', 'moradia', 'serviços', 'utilidades', 'saúde', 'transporte', 'outros', 'impostos'))` |
| `status` | `TEXT` | Não | `'pending'` | `CHECK (status IN ('pending', 'paid', 'overdue', 'cancelled'))` |
| `source_transaction_id` | `UUID` | Sim | `NULL` | FK opcional apontando para a `transactions(id)` que quitou a conta. |

---

## 3. Tabela: `import_batches` (Governança e Auditoria de Importações)

| Coluna | Tipo | Nulo | Default | Descrição |
|---|---|---|---|---|
| `id` | `UUID` | Não | `gen_random_uuid()` | Identificador único do lote |
| `user_id` | `UUID` | Não | — | Usuário que realizou o upload |
| `tenant_id` | `UUID` | Não | — | Workspace do lote |
| `account_id` | `UUID` | Sim | `NULL` | Conta bancária de destino |
| `filename` | `TEXT` | Não | — | Nome do arquivo importado |
| `file_format` | `TEXT` | Não | `'ofx'` | Formato: `'ofx'`, `'csv'` |
| `total_parsed` | `INT` | Não | `0` | Quantidade bruta de linhas lidas |
| `imported_count` | `INT` | Não | `0` | Transações efetivamente inseridas |
| `ignored_count` | `INT` | Não | `0` | Lançamentos descartados com motivo |
| `duplicate_count` | `INT` | Não | `0` | Duplicatas evitadas |
| `unclassified_count`| `INT` | Não | `0` | Lançamentos sem regra de categoria |
| `total_income` | `NUMERIC(15,2)` | Sim | `0.00` | Soma das receitas do lote |
| `total_expense`| `NUMERIC(15,2)` | Sim | `0.00` | Soma das despesas do lote |
| `total_transfer`| `NUMERIC(15,2)`| Sim | `0.00` | Soma das transferências do lote |
| `ledger_balance`| `NUMERIC(15,2)`| Sim | `NULL` | Saldo declarado no LEDGERBAL do OFX |
| `status` | `TEXT` | Não | `'completed'` | `CHECK (status IN ('preview', 'completed', 'rolled_back'))` |
| `metadata` | `JSONB` | Sim | `NULL` | Detalhes de categorias e itens ignorados |
| `created_at` | `TIMESTAMPTZ` | Sim | `now()` | Data de criação |
| `rolled_back_at`| `TIMESTAMPTZ` | Sim | `NULL` | Data de rollback (quando aplicável) |

---

## 4. Tabela de Tradução de Erros Postgres para Mensagens Amigáveis

| Código Postgres | Causa Raiz | Mensagem Retornada ao Usuário / Frontend |
|---|---|---|
| `23514` (Check Violation) | `type` diferente de `income`, `expense`, `transfer` | "Tipo de transação inválido. Valores aceitos: Receita (income), Despesa (expense) ou Transferência (transfer)." |
| `23514` (Check Violation) | `category` inválida em `financial_expenses` | "Categoria de conta a pagar não reconhecida. Categorias válidas: alimentação, cartões, educação, moradia, serviços, utilidades, saúde, transporte, impostos, outros." |
| `23505` (Unique Violation) | `idx_transactions_tenant_dedup_key` | "Esta transação já foi importada anteriormente para esta conta (duplicidade detectada)." |
| `PGRST102` | Chaves heterogêneas no payload PostgREST | "Lote normalizado automaticamente pelo backend. Todas as transações compartilham o conjunto canônico de chaves." |
