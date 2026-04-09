# PROJECT_CONTEXT.md - Alça Finanças

**Visão Geral:** SaaS de gestão financeira pessoal e familiar

---

## Produto

**Nome:** Alça Finanças  
**Domínio:** `alcahub.cloud`  
**Subdomínios:**
- `www.alcahub.cloud` → Frontend principal
- `api.alcahub.cloud` → Backend API
- `chat.alcahub.com.br` → Chatbot (planejado)

**Objetivo:** Entregar clareza financeira, planejamento, automação e inteligência de gastos.

**Público-alvo:**
- Pessoas físicas buscando organização financeira
- Famílias gerenciando orçamento doméstico
- Futuro: multi-empresa, white-label por nicho

---

## Módulos Principais

| Módulo | Status | Descrição |
|--------|--------|-----------|
| Dashboard | ✅ Produção | KPIs, gráficos, transações recentes |
| Contas Bancárias | ✅ Produção | CRUD de contas, saldo por conta |
| Cartões de Crédito | ✅ Produção | Importação de fatura, parcelas |
| Categorias | ✅ Produção | Personalização, ícones, cores |
| Transações | ✅ Produção | Receitas, despesas, parcelamento |
| Relatórios | ✅ Produção | Gráficos por categoria/conta/período |
| Importação CSV | ✅ Produção | Upload de extratos bancários |
| Planejamento | 🚧 Em desenvolvimento | Orçamento mensal, metas de gastos |
| Metas (Goals) | 🚧 Em desenvolvimento | Economia para objetivos |
| Chatbot Financeiro | ⚠️ Bloqueado (P0) | Assistente virtual com LLM |
| Automações N8N | 📋 Planejado | Notificações, categorização automática |
| Multi-tenant | ✅ Base | RLS policies, tenant_id |
| Admin Dashboard | 🚧 Em desenvolvimento | Gestão de usuários, logs |

---

## Stack Tecnológico

### Frontend
```
React 18 + TypeScript + Vite
Tailwind CSS + shadcn/ui
Recharts (gráficos)
React Router DOM
Axios (API client)
React Hot Toast (notificações)
Lucide React (ícones)
```

### Backend
```
Flask 3.0 + Python 3.9
Supabase (PostgreSQL)
Pydantic (validação)
Flask-CORS
Flask-Limiter (rate limiting)
Gunicorn (produção)
```

### Mobile
```
React Native + Expo SDK ~54
React Navigation
Axios
AsyncStorage
```

### Chatbot
```
FastAPI (serviço separado)
WebSocket
PyJWT
OpenClaw (LLM integration)
```

### Infraestrutura
```
Docker + Docker Compose
Nginx (reverse proxy + SSL)
Let's Encrypt (certbot)
VPS Hostinger Ubuntu 24.04
N8N (automações)
```

### Database
```
Supabase (PostgreSQL 15+)
Row Level Security (RLS)
JWT authentication
Migrations versionadas
```

---

## Arquitetura Resumida

```
┌─────────────────────────────────────────────────────────┐
│                    USUÁRIO                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Nginx (alcahub.cloud)                      │
│         SSL + Reverse Proxy + Rate Limiting             │
└─────────────────────────────────────────────────────────┘
                    │                    │
                    ▼                    ▼
        ┌─────────────────┐    ┌─────────────────┐
        │   Frontend      │    │   Backend API   │
        │   (React/Vite)  │    │   (Flask)       │
        │   Porta 3000    │    │   Porta 8001    │
        └─────────────────┘    └─────────────────┘
                    │                    │
                    │                    ▼
                    │          ┌─────────────────┐
                    │          │   Supabase      │
                    │          │   (Postgres)    │
                    │          └─────────────────┘
                    │
                    ▼
        ┌─────────────────┐
        │   Chatbot       │
        │   (FastAPI/WS)  │
        │   Porta 8100    │
        └─────────────────┘
```

---

## Regras de Negócio Críticas

### Autenticação
- Supabase Auth nativo (email/senha)
- JWT com rotação de token
- Refresh token automático (7 dias)
- Recuperação de senha via email
- **P0:** JWT secret deve ser único (`SUPABASE_JWT_SECRET`)

### Multi-tenant
- Cada usuário = um tenant
- RLS policies garantem isolamento
- `tenant_id` em todas as tabelas
- **P0:** Migrations devem preservar RLS

### Transações
- Valores em centavos (evitar float)
- Parcelas geram transações filhas
- Importação CSV com auto-detecção de conta
- **P1:** Validar `money_utils.py` para decimals

### Categorias
- Padrão criadas no onboarding
- Usuário pode personalizar
- Cores e ícones por categoria
- **P1:** Conflito de categorias em importação

### Relatórios
- Agrupamento por categoria/conta
- Período: mês atual, último mês, personalizado
- KPIs: saldo, receitas, despesas, ticket médio
- **P1:** Performance em meses com muitas transações

---

## KPIs Desejados

| KPI | Meta | Como medir |
|-----|------|------------|
| Retenção mensal | >60% | Usuários ativos 30d |
| Onboarding completo | >80% | Usuários com 1ª transação |
| Frequência semanal | >3x | Logins por semana |
| Uso de relatórios | >50% | Usuários que acessam relatórios |
| Conversão free→premium | >5% | Upgrade para plano pago |

---

## Roadmap (Próximos Objetivos)

### Curto Prazo (30 dias)
- [ ] Corrigir P0s do chatbot
- [ ] Estabilizar planejamento mensal
- [ ] Implementar metas (goals)
- [ ] Analytics (PostHog ou similar)

### Médio Prazo (90 dias)
- [ ] Escalar Casa Boaz como vertical
- [ ] Replicar engine para Autlarme
- [ ] Evoluir chatbot premium
- [ ] Dashboards comparativos antes/depois

### Longo Prazo (6+ meses)
- [ ] Multi-empresa
- [ ] White-label por nicho
- [ ] Growth loops automatizados
- [ ] Monetização recorrente

---

## Lições Aprendidas

### O que funcionou
- ✅ Supabase migração (de MongoDB)
- ✅ RLS policies para multi-tenant
- ✅ Docker compose para dev/prod
- ✅ Scripts organizados (`scripts/dev/`, `scripts/prod/`)

### O que evitar
- ❌ Migrations fora de ordem (quebra schema)
- ❌ Chatbot duplicado (2 implementações)
- ❌ JWT secrets diferentes entre serviços
- ❌ Frontend dist no git (poluição)
- ❌ Python 3.9 + urllib3 warning (atualizar para 3.11+)

### Padrões estabelecidos
- ✅ Service/repository pattern
- ✅ JWT com rotação automática
- ✅ Docker compose override (dev vs prod)
- ✅ SSL via certbot em produção
- ✅ Websocket para chat realtime

---

## Links Importantes

| Recurso | URL |
|---------|-----|
| Repositório | `C:\Users\lezin\Downloads\project\alca-financas` |
| Produção | https://alcahub.cloud |
| API | https://api.alcahub.cloud |
| Supabase Dashboard | https://app.supabase.com |
| VPS Hostinger | srv1353242 |
| N8N | http://localhost:5678 (dev) |

---

_Última atualização: 2026-04-09_
