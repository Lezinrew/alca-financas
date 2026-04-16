# ARCHITECTURE.md - Alça Finanças

**Última atualização:** 2026-04-13  
**Status:** P0 #1 em validação — Frontend migrado para Flask

---

## BLOCO 1 — Visão Geral da Arquitetura

### Componentes Principais

| Componente | Tecnologia | Porta | Status |
|------------|------------|-------|--------|
| Frontend | React + Vite | 3000 | ✅ Estável |
| Backend API | Flask + Supabase | 8001 | ✅ Estável |
| Chatbot | Flask (backend) | 8001 | 🟡 Migrando (P0 #1) |
| Chatbot (FastAPI) | FastAPI | 8100 | ⚠️ Arquivar após validação |
| Mobile | React Native + Expo | 1900/8081 | 📋 Secundário |
| Nginx | Reverse Proxy + SSL | 80/443 | ✅ Produção |
| Supabase | PostgreSQL (cloud) | — | ✅ Produção |

---

### ⚠️ P0 #1 — Migração do Chatbot (2026-04-13)

**Status:** Frontend migrado para backend Flask, aguardando validação.

**Mudanças:**
- Frontend agora usa `/api/chatbot/chat` (Flask) em vez de `/api/chat` (FastAPI)
- WebSocket desativado temporariamente (Flask ainda não implementou)
- `services/chatbot/` será arquivado após testes

**Próximos passos:**
1. Testar health: `curl http://localhost:8001/api/chatbot/health`
2. Testar login + chat no frontend
3. Validar logs do backend
4. Arquivar `services/chatbot/`

**Rollback:** `git checkout frontend/src/components/chat/ChatWidget.tsx frontend/src/utils/api.ts .env.example`

---

### Diagrama de Arquitetura

```
                                    INTERNET
                                        │
                                        ▼
                              ┌─────────────────────┐
                              │   Nginx (VPS)       │
                              │   SSL + Reverse     │
                              └─────────────────────┘
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
          ┌─────────────┐ ┌───────────┐ ┌─────────────┐
          │  Frontend   │ │  Backend  │ │   Chatbot   │
          │  React/Vite │ │   Flask   │ │   FastAPI   │
          │   :3000     │ │   :8001   │ │    :8100    │
          └─────────────┘ └─────┬─────┘ └──────┬──────┘
                                │              │
                                ▼              ▼
                         ┌──────────┐   ┌────────────┐
                         │ Supabase │   │ OpenClaw   │
                         │ Postgres │   │   (LLM)    │
                         └──────────┘   └────────────┘
```

---

### Padrões Arquiteturais

- **Backend:** Service/Repository pattern, Blueprints Flask, Pydantic
- **Frontend:** Context API, Axios interceptors, shadcn/ui
- **Database:** Row Level Security (RLS), `tenant_id` obrigatório
- **Auth:** JWT via Supabase, rotação automática de token

---

## BLOCO 2 — Detalhamento por Componente

### Backend (Flask)

**Entrypoint:** `backend/app.py`

```
backend/
├── app.py              # Flask app, registra blueprints
├── routes/             # Endpoints API
│   ├── auth_supabase.py
│   ├── transactions.py
│   ├── dashboard.py
│   └── chatbot.py
├── services/           # Regras de negócio
├── repositories/       # Acesso a dados (Supabase)
├── utils/              # Helpers (JWT, money, tenant)
└── database/           # Conexão + migrations
```

**Endpoints principais:**
- `POST /api/auth/login` — autenticação
- `GET /api/dashboard` — KPIs e gráficos
- `GET /api/transactions` — lista transações
- `POST /api/chatbot/chat` — chat com LLM

---

### Frontend (React + Vite)

**Entrypoint:** `frontend/src/main.tsx`

```
frontend/src/
├── main.tsx            # Bootstrap React
├── App.tsx             # Componente raiz
├── components/         # UI components
│   ├── dashboard/
│   ├── transactions/
│   ├── chat/
│   └── ui/            # shadcn/ui base
├── contexts/           # AuthContext, ThemeContext
├── utils/              # API client, tokenStorage
└── hooks/              # Custom hooks
```

**Comunicação:**
- Axios com interceptor de JWT
- Refresh token automático
- WebSocket para chat (fallback HTTP)

---

### Mobile (React Native + Expo)

**Entrypoint:** `mobile/App.tsx`

```
mobile/src/
├── screens/
│   ├── DashboardScreen.tsx
│   ├── TransactionsScreen.tsx
│   └── AccountsScreen.tsx
├── navigation/AppNavigator.tsx
└── api/client.ts
```

**Status:** Secundário, mesma API do web.

---

### Chatbot (FastAPI)

**Entrypoint:** `services/chatbot/app.py`

```
services/chatbot/
├── app.py              # FastAPI + WebSocket
├── requirements.txt
└── __init__.py
```

**Protocolos:**
- HTTP: `POST /api/chat`
- WebSocket: `WS /api/chat/ws?token=<JWT>`

**⚠️ P0:** Duplicado com `backend/routes/chatbot.py`

---

### Integrações

| Integração | Tipo | Status |
|------------|------|--------|
| Supabase | Database + Auth | ✅ Produção |
| OpenClaw | LLM (chatbot) | ✅ Produção |
| N8N | Automações | 📋 Planejado |
| WhatsApp | Notificações | 📋 Planejado |

---

## BLOCO 3 — Infraestrutura e Deploy

### Docker Compose

**Arquivos:**
- `docker-compose.yml` — Desenvolvimento local
- `docker-compose.dev.yml` — Overrides dev (hot-reload)
- `docker-compose.prod.yml` — Produção (Gunicorn, sem volumes)

**Serviços:**
```yaml
services:
  backend:    # Flask + Gunicorn :8001
  frontend:   # React + Vite :3000 (dev) ou Nginx (prod)
  chatbot:    # FastAPI :8100 (⚠️ ausente em prod)
  nginx:      # Reverse proxy 80/443
  openclaw-gateway:  # Bridge OpenClaw
```

**⚠️ P0:** `docker-compose.prod.yml` não define serviço `chatbot`

---

### Nginx (Produção)

**Config:** `nginx/conf.d/alcahub.conf`

```nginx
upstream backend {
    server backend:8001;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 443 ssl;
    server_name alcahub.cloud;
    
    location / {
        proxy_pass http://frontend;
    }
    
    location /api/ {
        proxy_pass http://backend;
    }
    
    # ⚠️ P0: Falta location para /api/chat/ws (WebSocket)
}
```

---

### Ambientes

| Ambiente | Backend | Frontend | Chatbot | Docker |
|----------|---------|----------|---------|--------|
| Dev Local | Flask debug :8001 | Vite :3000 | FastAPI :8100 | docker-compose.yml |
| Produção | Gunicorn :8001 | Nginx (build) | ❌ Ausente | docker-compose.prod.yml |

**⚠️ P0:** Inconsistência dev vs prod (chatbot, build path)

---

### Entrypoints

**Backend:**
```bash
# Dev
python app.py

# Produção
gunicorn --bind 0.0.0.0:8001 --workers 4 app:app
```

**Frontend:**
```bash
# Dev
npm run dev

# Build
npm run build

# Produção (Nginx serve build/)
```

**Chatbot:**
```bash
# Dev e Prod (mesmo comando)
uvicorn app:app --host 0.0.0.0 --port 8100
```

---

### Fluxo de Deploy

```bash
# 1. Build do frontend
cd frontend && npm run build

# 2. Validar build gerado
ls -la build/frontend/  # ⚠️ P0: deve existir

# 3. Subir produção
docker compose -f docker-compose.prod.yml up -d

# 4. Validar saúde
docker compose ps
curl https://api.alcahub.cloud/health
```

**⚠️ P0:** `build/frontend/` não existe (script não rodado)

---

## BLOCO 4 — Riscos e Gargalos Confirmados

### Riscos Arquiteturais Atuais

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Chatbot duplicado | Confusão, manutenção 2x | Alta | Consolidar em 1 implementação |
| JWT secrets diferentes | Auth falha em prod | Alta | Unificar variáveis de ambiente |
| Chatbot ausente em prod | Feature indisponível | Certa | Adicionar serviço ao compose |
| Build path inexistente | Frontend 404 em prod | Certa | Script de build pré-deploy |
| Dev ≠ Prod | Bugs só aparecem em prod | Média | Alinhar configs, testar em staging |

---

### Gargalos Confirmados (P0)

1. **Chatbot Duplicado**
   - `backend/routes/chatbot.py` (Flask)
   - `services/chatbot/app.py` (FastAPI)
   - **Ação:** Escolher 1, remover outro

2. **JWT Secrets Dessincronizados**
   - Backend: `SUPABASE_JWT_SECRET`
   - Chatbot: `JWT_SECRET` ou `SECRET_KEY`
   - **Ação:** Unificar para `SUPABASE_JWT_SECRET`

3. **Chatbot Ausente em Produção**
   - Serviço não definido em `docker-compose.prod.yml`
   - Nginx sem rota WebSocket
   - **Ação:** Adicionar serviço + config nginx

4. **Frontend Build Path Inexistente**
   - `build/frontend/` não existe
   - Nginx monta volume vazio
   - **Ação:** Executar `npm run build` antes de deploy

5. **Docker Mismatch Backend**
   - Dev: `python app.py` (Flask debug)
   - Prod: `gunicorn` (4 workers)
   - **Ação:** Documentar diferença ou alinhar

---

### Diretrizes de Evolução

**Curto Prazo (30 dias):**
- [ ] Corrigir todos os P0s antes de próximo deploy
- [ ] Unificar chatbot (recomendado: Flask `backend/routes/chatbot.py`)
- [ ] Adicionar health checks em todos os serviços
- [ ] Criar script `scripts/prod/deploy.sh` automatizado

**Médio Prazo (90 dias):**
- [ ] Implementar staging environment
- [ ] CI/CD com GitHub Actions
- [ ] Monitoramento (Prometheus + Grafana)
- [ ] Centralizar logs (ELK ou similar)

**Longo Prazo (6+ meses):**
- [ ] Kubernetes para orquestração
- [ ] Multi-region deployment
- [ ] Feature flags para rollout gradual
- [ ] A/B testing infrastructure

---

_Última atualização: 2026-04-09_
