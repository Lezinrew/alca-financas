# Migrations PostgreSQL V2

Estas migrations pertencem ao banco PostgreSQL próprio. Elas não devem ser executadas no Supabase.

## Ordem

1. `0001_core.sql`: identidade, organizações, contas, categorias, transações, contas a pagar, pagamentos e auditoria.
2. `0002_ai_platform.sql`: plataforma de IA (espaços financeiros, grants, execuções, propostas, operações, outbox, orçamento, RAG e RLS). Reversão em `0002_ai_platform.down.sql`. Ver `docs/runbooks/ai-platform.md`.

## Aplicar localmente

```powershell
Get-Content backend/database/migrations_v2/0001_core.sql -Raw |
  docker exec -i alcahub-postgres-v2 psql -v ON_ERROR_STOP=1 -U alcahub -d alcahub_v2
```

## Reverter localmente

```powershell
Get-Content backend/database/migrations_v2/0001_core.down.sql -Raw |
  docker exec -i alcahub-postgres-v2 psql -v ON_ERROR_STOP=1 -U alcahub -d alcahub_v2
```

O rollback remove todas as tabelas V2. Use apenas no banco local de desenvolvimento enquanto ele contém dados fictícios.

