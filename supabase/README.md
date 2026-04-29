# Supabase — migrations e banco (Alça Finanças)

O **Postgres** do produto vive no **Supabase** (cloud ou local se usares `supabase start`). O schema reprodutível está em **`migrations/`** nesta pasta. O **backend** (`backend/`) acede com `SUPABASE_SERVICE_ROLE_KEY` para operações que exigem bypass controlado; o cliente no browser usa a **anon key** e fica sujeito ao RLS.

## Relação com o backend

- Conexão e clientes: `backend/database/`, repositórios `*_supabase.py`.  
- Autenticação: Supabase Auth + validação de JWT no Flask (`backend/utils/supabase_jwt.py` e afins).  
- **RLS:** policies e funções de contexto (tenant) estão em migrations; alterações de segurança **sempre** passam por novo ficheiro SQL versionado, não alterações ad hoc em produção.

## Estrutura (visão geral)

```
supabase/
├── README.md                 ← este ficheiro
├── MIGRATION_AUDIT.md        ← auditoria / histórico (se existir)
└── migrations/
    ├── 20260303_000001_init.sql           # Base (tabelas, constraints, indexes)
    ├── 20260303_000002_functions.sql
    ├── 20260303_000003_rls_policies.sql
    ├── 20260303_000004_triggers.sql
    ├── 20260315… 20260417… (budget, planning, goals, RLS, financial_expenses, admin, transações, …)
    └── _backup_before_fix/                 # Cópias de segurança; não aplicar como pipeline principal
```

A sequência exata e dependências estão no cabeçalho de cada ficheiro. Migrations com prefixo `20260416` e `20260417` reforçam **membership** em RLS e extensões (despesas, admin, audit).

## Como aplicar migrations

### Supabase Cloud (SQL Editor) — comum

1. Project → **SQL Editor**.  
2. Executar **em ordem cronológica** (por nome de ficheiro), do schema base até as mais recentes.  
3. Não saltar ficheiros que criem `functions` / `policies` de que o próximo dependa.

### Supabase CLI (recomendado para projetos alinhados ao CLI)

```bash
supabase link   # liga ao projeto remoto, quando configurado
supabase db push
```

O projeto pode já ter `supabase/config` — se existir, seguir a documentação oficial. `supabase db reset` **apaga** o estado local; usar só em dev.

### Postgres local (psql) — avançado

Podes encadear `psql` com `$DATABASE_URL` se tiveres URL direta; o fluxo canónico de equipa continua a ser o **Editor** ou **CLI** contra o mesmo projeto.

## Validação

- Ver `MIGRATION_AUDIT.md` (se presente) e scripts em `scripts/db/` como `validate-migrations.sh` (quando existir).  
- Após RLS, testar com utilizador autenticado: só dados do **tenant** esperado.

## Regras

- **Fazer:** migration com `BEGIN`/`COMMIT` quando aplicável, nome com timestamp, testar em dev.  
- **Não fazer:** mudar produção só pelo dashboard sem replicar no git; comitar secrets; aplicar ficheiros de `_backup_before_fix` como se fossem a linha actual sem revisão.

## Recursos

- [Supabase CLI](https://supabase.com/docs/guides/cli)  
- Documentação do repo: `docs/SUPABASE-RLS-SECURITY.md`, `docs/04-database/tenancy.md`

**Última atualização deste README:** 2026-04-23 (reestruturação para alinhar com o monorepo actual).
