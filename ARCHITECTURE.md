# ARCHITECTURE.md - Alça Finanças

**Última atualização:** 2026-05-06
**Status:** P0-A, P0-B e P0-C concluídos.

> **Nota:** As definições operacionais canônicas estão em `EXECUTION_BASELINE.md` e `EXECUTION_RUNBOOK.md`.

---

## BLOCO 1 — Visão Geral da Arquitetura

### Componentes Principais

| Componente | Tecnologia | Porta | Status |
|------------|------------|-------|--------|
| Frontend | React + Vite | 3000 | ✅ Estável |
| Backend API | Flask + Supabase | 8001 | ✅ Estável |
| Chatbot | Flask (backend) | 8001 | ✅ Produção |
| Mobile | React Native + Expo | 1900/8081 | 📋 Secundário |
| Nginx | Reverse Proxy + SSL | 80/443 | ✅ Produção |
| Supabase | PostgreSQL (cloud) | — | ✅ Produção |

---

### Integração Chatbot Oficial
O serviço de Chatbot utiliza a rota `/api/chatbot/*` nativa no Flask, sem dependência de serviços externos FastAPI.

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
                    │             │             
                    ▼             ▼             
          ┌─────────────┐ ┌───────────┐ 
          │  Frontend   │ │  Backend  │ 
          │  React/Vite │ │   Flask   │ 
          │   :3000     │ │   :8001   │ 
          └─────────────┘ └─────┬─────┘ 
                                │              
                                ▼              
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
  nginx:      # Reverse proxy 80/443
  openclaw-gateway:  # Bridge OpenClaw
```


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
    
}
```

---

### Ambientes

| Ambiente | Backend | Frontend | Docker |
|----------|---------|----------|--------|
| Dev Local | Flask debug :8001 | Vite :3000 | docker-compose.yml |
| Produção | Gunicorn :8001 | Nginx (build) | docker-compose.prod.yml |

**⚠️ P0:** Inconsistência dev vs prod (build path)

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
| Build path inexistente | Frontend 404 em prod | Certa | Script de build pré-deploy |
| Dev ≠ Prod | Bugs só aparecem em prod | Média | Alinhar configs, testar em staging |

---

### Gargalos Confirmados (P0)

1. **Frontend Build Path Inexistente**
   - `build/frontend/` não existe
   - Nginx monta volume vazio
   - **Ação:** Executar `npm run build` antes de deploy

2. **Docker Mismatch Backend**
   - Dev: `python app.py` (Flask debug)
   - Prod: `gunicorn` (4 workers)
   - **Ação:** Documentar diferença ou alinhar

---

### Diretrizes de Evolução

**Curto Prazo (30 dias):**
- [ ] Corrigir todos os P0s antes de próximo deploy
- [x] Unificar chatbot (Flask `backend/routes/chatbot.py`)
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
