# Observabilidade — transações

## Campos de rastreio (2026-04-17)

- **`entry_source`:** `manual` (formulário/API de criação), `csv` ou `ofx` (importação em `POST /api/transactions/import`). Útil para distinguir movimentos digitados de ficheiros.
- **`fitid`:** presente quando o parser OFX expõe FITID; usado para deduplicação na importação.

## Contas a pagar ligadas

- **`financial_expenses.source_transaction_id`:** quando a conta foi criada a partir do livro (`POST /api/financial-expenses/from-transactions`). Índice único parcial evita duplicar a mesma transação.

## Referência operacional

Ver `EXECUTION_RUNBOOK.md` secção «Contas a pagar ↔ transações».
