# RAIO-X COMPLETO — Alça Finanças

**Data:** 2026-02-20  
**Arquiteto:** Análise Técnica DevOps/Segurança/Escalabilidade

---

# ETAPA 1 — MAPEAMENTO ESTRUTURAL

## 1.1 Estrutura de Pastas Principais

| Pasta | Papel |
|-------|-------|
| `backend/` | API REST Flask + Supabase. Contém routes, services, repositories, database, utils, schemas, tests |
| `frontend/` | SPA React + TypeScript + Vite. Componentes por feature, contexts, i18n, E2E |
| `mobile/` | App React Native/Expo (em desenvolvimento) |
| `services/chatbot/` | Serviço FastAPI/Uvicorn separado para chatbot |
| `scripts/` | Automação: deploy, setup, dev, prod, db, legacy (MongoDB) |
| `docs/` | Documentação técnica e guias |
| `.github/workflows/` | CI/CD (ci.yml, deploy-production.yml) |

## 1.2 Componentes por Camada

| Camada | Localização | Responsabilidade |
|--------|-------------|------------------|
| **Backend** | `backend/app.py` | Entrypoint Flask, registra blueprints, CORS, OAuth |
| **Routes** | `backend/routes/*.py` | auth, transactions, accounts, categories, dashboard, reports, admin |
| **Services** | `backend/services/*.py` | Lógica de negócio (TransactionService, AccountService, etc.) |
| **Repositories** | `backend/repositories/*_supabase.py` | Acesso a dados Supabase (PostgreSQL) |
| **Frontend** | `frontend/src/main.tsx` → `App.tsx` | Entrypoint React, rotas, layout |
| **Components** | `frontend/src/components/` | Auth, Dashboard, Transactions, Accounts, Categories, CreditCards, Reports, Settings, Profile, Chat |

## 1.3 Entrypoints

| Componente | Entrypoint | Inicialização |
|------------|------------|---------------|
| Backend | `backend/app.py` | `load_dotenv()` → `init_db()` → registra blueprints → `app.run()` ou Gunicorn |
| Frontend | `frontend/src/main.tsx` | ReactDOM.render → App → AuthProvider, ThemeContext, rotas |
| Mobile | `mobile/App.tsx` | Expo entry |
| Chatbot | `services/chatbot/app.py` | FastAPI/Uvicorn |

---

# ETAPA 2 — STACK TECNOLÓGICA

## 2.1 Linguagens

| Linguagem | Uso |
|-----------|-----|
| Python 3.9+ | Backend, scripts, testes |
| TypeScript | Frontend, mobile |
| SQL | Schema Supabase, migrações |

## 2.2 Frameworks e Bibliotecas

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| Flask | 3.0.0 | API REST |
| React | 18.2.0 | Frontend |
| Vite | 4.x | Build frontend |
| Supabase | 2.0.0 | PostgreSQL + Auth |
| Pydantic | 2.5.2 | Validação |
| Tailwind CSS | - | Estilos |
| shadcn/ui | - | Componentes UI |

## 2.3 Banco de Dados

- **PostgreSQL** via Supabase
- **ORM:** Supabase Python Client (não ORM tradicional)
- **Tabelas:** users, categories, accounts, transactions, oauth_states

## 2.4 Autenticação

- JWT (PyJWT) com access + refresh token
- OAuth (Authlib): Google, Microsoft, Apple
- Supabase Auth (alternativo)
- bcrypt para hash de senhas

## 2.5 Dependências Críticas

- `supabase==2.0.0`, `psycopg2-binary==2.9.9`
- `PyJWT==2.8.0`, `bcrypt==4.1.2`
- `Flask-Limiter==3.5.0` (rate limiting)

---

# ETAPA 3 — FLUXO DE EXECUÇÃO

## 3.1 Requisição Típica

```
Cliente → Nginx/Traefik → Backend (Flask:8001)
         → @require_auth (JWT) → Route → Service → Repository → Supabase
         → JSON Response
```

## 3.2 Regras de Negócio

- **Services:** `transaction_service.py`, `account_service.py`, `category_service.py`, `report_service.py`, `import_service.py`
- **Validação:** Pydantic em `schemas/auth_schemas.py`; validação manual em services

## 3.3 Persistência

- Supabase Client → PostgreSQL
- Repositories usam `.select()`, `.insert()`, `.update()`, `.delete()` com filtros parametrizados
- Sem raw SQL concatenado (baixo risco de SQL injection)

## 3.4 Integrações Externas

- **Supabase:** DB, Auth
- **Google OAuth:** Login social
- **Email:** SMTP (reset de senha)
- **Chatbot:** Serviço separado (FastAPI)

---

# ETAPA 4 — SEGURANÇA

## 4.1 Uso de .env

| Arquivo | Status | Observação |
|---------|--------|------------|
| `.env` | ✅ Gitignore | Raiz |
| `backend/.env` | ✅ Gitignore | Contém SECRET_KEY, JWT_SECRET, SUPABASE_KEY |
| `frontend/.env` | ✅ Gitignore | VITE_* |
| `.env.vps.production` | ✅ Gitignore | Dados produção |

## 4.2 Secrets Hardcoded — RISCOS

| Local | Risco | Detalhe |
|-------|-------|---------|
| `scripts/deploy-frontend-only.sh` | 🔴 **CRÍTICO** | `SERVER_PASS="4203434@Mudar"` hardcoded |
| `.cursor/mcp.json` | 🟢 Baixo | API_TOKEN; está em .gitignore |
| `.claude/settings.local.json` | 🔴 **CRÍTICO** | SSH password, JWT, SUPABASE_SERVICE_ROLE_KEY; ignorado por git global |
| `backend/.env` | 🟡 Médio | Se commitado acidentalmente, expõe secrets |

## 4.3 API Keys no Código

- Nenhuma API key hardcoded em código fonte
- OAuth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` via env
- CI: `SUPABASE_SERVICE_ROLE_KEY: eyJ...test.fake` (valor fake para testes)

## 4.4 Logs e Dados Sensíveis

- `current_app.logger.debug` com tipo de senha (não o valor)
- Evitar logar tokens, passwords, PII

## 4.5 Validação de Input

- Pydantic em auth (UserRegisterSchema, UserLoginSchema)
- Validação em services (ValidationException)
- Filtros em transactions: `int(month)`, `int(year)` com try/except

## 4.6 SQL Injection

- 🟢 **Baixo risco:** Supabase client usa queries parametrizadas (`.eq()`, `.gte()`, etc.)
- Nenhum `format()` ou concatenação de SQL com input do usuário encontrado

## 4.7 Autenticação nas Rotas

- `@require_auth` em rotas protegidas
- `@admin_required` em rotas admin
- Health check (`/api/health`) público

## 4.8 RLS (Row Level Security)

- 🔴 **CRÍTICO:** RLS habilitado mas políticas usam `USING (true)` — **não restringe por user_id**
- Backend usa **service_role** que bypassa RLS
- Segurança depende 100% do filtro `user_id` na aplicação
- **Recomendação:** Ajustar RLS para `USING (auth.uid() = user_id)` se usar Supabase Auth, ou manter filtro rigoroso em todas as queries

## 4.9 Service Role Key

- Usada apenas no backend (nunca no frontend)
- Variável: `SUPABASE_KEY` ou `SUPABASE_SERVICE_ROLE_KEY`
- Não exposta em bundle frontend

---

# ETAPA 5 — DEVOPS E PRODUÇÃO

## 5.1 Docker

| Arquivo | Uso |
|---------|-----|
| `backend/Dockerfile` | Build backend (contexto raiz) |
| `frontend/Dockerfile` | Build frontend multi-stage |
| `docker-compose.yml` | Dev (backend + frontend) |
| `docker-compose.prod.yml` | Prod (backend + nginx) |

## 5.2 CI/CD

| Workflow | Trigger | Jobs |
|----------|---------|------|
| `ci.yml` | push/PR main, develop | Lint, testes backend/frontend, Docker build, Security scan (Trivy) |
| `deploy-production.yml` | workflow_run (após CI) | Deploy backend (docker save/scp/load), Deploy frontend (scp), Smoke tests |

## 5.3 Versionamento

- Git com branches main, develop
- Sem versionamento semântico explícito em package.json (0.0.0)

## 5.4 Testes Automatizados

- Backend: pytest (unit + integration), conftest com mocks
- Frontend: Vitest, Testing Library
- E2E: Playwright (desabilitado por padrão: `if: false`)

## 5.5 Logs

- `logging.basicConfig(level=logging.INFO)`
- Sem formato estruturado (JSON)
- Sem integração com APM (Sentry, etc.)

## 5.6 Monitoramento

- Nenhum APM ou métricas configurado
- Health check: `GET /api/health`

## 5.7 Healthcheck

- `GET /api/health` retorna status básico
- Sem verificação de conectividade com DB no health

## 5.8 Ambientes

- `.env`, `.env.production`, `.env.vps.production`
- `VITE_API_URL` para frontend
- `CORS_ORIGINS` configurável

## 5.9 Maturidade DevOps

**Avaliação: Intermediário / Produção Parcial**

- ✅ Docker, CI/CD, testes
- ⚠️ Deploy depende de secrets manuais (PROD_SSH_KEY)
- ❌ Sem monitoramento, logs estruturados, APM
- ❌ E2E desabilitado

---

# ETAPA 6 — PERFORMANCE E ESCALABILIDADE

## 6.1 Gargalos Potenciais

| Área | Risco | Detalhe |
|------|-------|---------|
| Transações | 🟡 Médio | `per_page` default 100; sem limite máximo rígido |
| Relatórios | 🟡 Médio | Agregações em memória (pandas) para períodos longos |
| Listagens | 🟢 Baixo | Paginação implementada |
| Conexões DB | 🟢 Baixo | Supabase client gerencia pool |

## 6.2 Queries

- Índices em `user_id`, `date`, `category_id`, `account_id`
- `find_by_filter` usa range e ordenação
- Sem N+1 explícito (queries por batch)

## 6.3 Código Síncrono

- Flask síncrono; Gunicorn com workers
- Sem async/await no backend
- Adequado para carga moderada

## 6.4 Cache

- Nenhum cache (Redis, in-memory) para sessões ou dados
- Cada request vai ao Supabase

## 6.5 Paginação

- Transações: `page`, `per_page` (default 100)
- Sem limite máximo explícito (ex.: 500)

## 6.6 Conexões

- Supabase client singleton
- Sem pool explícito configurado

---

# ETAPA 7 — QUALIDADE DE CÓDIGO

## 7.1 Organização

- ✅ Separação routes / services / repositories
- ✅ Blueprints por domínio
- ⚠️ Alguns arquivos grandes (report_service.py, transaction_service.py)

## 7.2 Separação de Responsabilidades

- ✅ Repository → Service → Route
- ⚠️ Routes às vezes acessam `current_app.config` diretamente

## 7.3 Duplicação

- Repositories MongoDB vs Supabase (legado)
- Dois fluxos de auth (auth.py e auth_supabase.py)

## 7.4 Complexidade

- Services com múltiplas responsabilidades
- report_service.py com muitas funções de agregação

## 7.5 Tipagem

- Frontend: TypeScript com tipos em `types/`
- Backend: type hints parciais
- Schemas Pydantic para validação

## 7.6 Arquivos Grandes

- `report_service.py`: ~700 linhas
- `transaction_service.py`: ~250 linhas
- `auth.py`: ~500 linhas

---

# ETAPA 8 — ARQUITETURA IDEAL SUGERIDA

## 8.1 Melhorias Estruturais

1. **Remover código legado MongoDB** — manter apenas Supabase
2. **Unificar auth** — escolher auth.py ou auth_supabase.py
3. **Quebrar report_service** — módulos por tipo de relatório

## 8.2 Modularização

```
backend/
├── api/
│   ├── v1/
│   │   ├── auth/
│   │   ├── transactions/
│   │   └── ...
├── core/
│   ├── config.py
│   └── security.py
├── domain/
│   ├── transactions/
│   └── accounts/
└── infrastructure/
    └── supabase/
```

## 8.3 DevOps Ideal

- Secrets em GitHub Secrets ou Vault
- Deploy via registry Docker (GHCR) em vez de save/scp
- Logs estruturados (JSON)
- Sentry ou similar para erros
- E2E habilitado com Supabase de teste

## 8.4 Segurança Ideal

- RLS com políticas por `user_id` (se usar Supabase Auth)
- Rotação de secrets documentada
- Nenhum secret em scripts (usar env ou secrets manager)
- Scan de secrets no CI (gitleaks, trufflehog)

---

# ETAPA 9 — CHECKLIST FINAL

## 9.1 10 Prioridades Críticas

1. 🔴 **Remover `SERVER_PASS` hardcoded** de `deploy-frontend-only.sh`
2. 🔴 **Corrigir RLS** — políticas com `USING (true)` não protegem dados
3. 🔴 **Garantir `.claude/` e `.cursor/mcp.json`** nunca commitados
4. 🟡 Adicionar `.claude/` ao `.gitignore` do projeto
5. 🟡 Limitar `per_page` máximo (ex.: 500) em transações
6. 🟡 Incluir verificação de DB no health check
7. 🟡 Habilitar E2E ou remover do CI
8. 🟢 Padronizar logs em JSON
9. 🟢 Adicionar monitoramento (Sentry)
10. 🟢 Documentar rotação de secrets

## 9.2 5 Melhorias Rápidas de Alto Impacto

1. Substituir `SERVER_PASS` por `PROD_SSH_KEY` em deploy-frontend-only.sh
2. Adicionar `per_page = min(per_page, 500)` em transactions
3. Health check: `init_db()` ou query simples ao Supabase
4. Adicionar `.claude/` ao .gitignore
5. Executar `gitleaks` ou `trufflehog` no CI

## 9.3 3 Riscos que Podem Quebrar Produção

1. **Secrets em repositório** — deploy-frontend-only.sh com senha; .claude com credenciais
2. **RLS ineficaz** — se service_role vazar, todos os dados ficam expostos
3. **Deploy sem rollback** — não há estratégia de rollback automático no workflow

## 9.4 Plano de Evolução em 30 Dias

| Semana | Foco |
|--------|------|
| 1 | Remover secrets hardcoded; adicionar .claude ao gitignore; scan de secrets no CI |
| 2 | Revisar e corrigir RLS; limitar paginação; melhorar health check |
| 3 | Logs estruturados; configurar Sentry; habilitar E2E ou remover |
| 4 | Documentar runbook de deploy; definir estratégia de rollback; revisar permissões |

---

*Documento gerado por análise automatizada do codebase. Validar premissas com a equipe.*
