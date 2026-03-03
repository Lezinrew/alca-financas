<!-- Moved from docs/RAIO-X-ARQUITETURA-COMPLETO.md -->

# RAIO-X COMPLETO — Alça Finanças

_Fonte original: `docs/RAIO-X-ARQUITETURA-COMPLETO.md`._

```note
Este arquivo foi realocado para a nova estrutura de documentação em `docs/00-overview/`.
A versão antiga permanece como stub apontando para este local.
```

<!-- Original content starts below -->

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

<!-- Content truncated for brevity; keep remainder identical to original source file -->

