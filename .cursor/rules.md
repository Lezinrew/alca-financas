# Alça Finanças — Cursor Rules

**Projeto:** SaaS de gestão financeira  
**Stack:** Flask + React/Vite + Supabase + Docker + Nginx + N8N  
**Última atualização:** 2026-04-09

---

## Contexto Obrigatório

**Antes de mudanças grandes, ler:**
1. `AGENTS.md` — especializações e red lines
2. `PROJECT_CONTEXT.md` — módulos e regras de negócio
3. `ARCHITECTURE.md` — estrutura e fluxos
4. `ENVIRONMENTS.md` — configs por ambiente
5. `DEBUGGING_PLAYBOOK.md` — troubleshooting
6. `TODO.md` — prioridades e P0s

**Nunca proponha arquitetura sem ler esses arquivos.**

---

## Stack Real do Projeto

| Camada | Tecnologia | Arquivos Chave |
|--------|------------|----------------|
| Backend | Flask 3.0 + Python 3.9 | `backend/app.py`, `backend/routes/` |
| Frontend | React 18 + Vite + TS | `frontend/src/`, `frontend/src/components/` |
| Database | Supabase (Postgres) | RLS policies, `tenant_id` obrigatório |
| Chatbot | FastAPI + WebSocket | `services/chatbot/`, `backend/routes/chatbot.py` |
| Infra | Docker Compose + Nginx | `docker-compose.yml`, `nginx/conf.d/` |
| Automação | N8N | `services/n8n/` |

**Não sugerir:** Express, Django, Next.js, MongoDB, Firebase, AWS.

---

## P0 Conhecidos (Bloqueantes)

**Sempre considerar antes de propor mudanças:**

| P0 | Descrição | Impacto |
|----|-----------|---------|
| 1 | Chatbot duplicado | Flask (`backend/routes/chatbot.py`) vs FastAPI (`services/chatbot/`) |
| 2 | JWT secret drift | Backend usa `SUPABASE_JWT_SECRET`, chatbot usa `JWT_SECRET` |
| 3 | Chatbot ausente em prod | Não definido em `docker-compose.prod.yml` |
| 4 | `build/frontend/` inexistente | Nginx serve volume vazio em produção |
| 5 | Dev ≠ Prod | Backend: Flask debug (dev) vs Gunicorn (prod) |

**Regra:** Não alterar auth, chatbot ou deploy sem validar impacto nesses P0s.

---

## Regras de Desenvolvimento

### 1. Auth e JWT

- **Nunca** hardcoded secrets no código
- **Sempre** usar variáveis de ambiente (`.env`)
- **Validar** `SUPABASE_JWT_SECRET` alinhado entre backend e chatbot
- **Testar** login/logout após qualquer mudança em auth
- **Não modificar** `backend/utils/supabase_jwt.py` sem testar token flow

### 2. Chatbot

- **Consolidar** em uma implementação (recomendado: Flask `backend/routes/chatbot.py`)
- **Remover** `services/chatbot/` após migração
- **Validar** WebSocket + HTTP fallback
- **Adicionar** health check `/health`

### 3. Deploy e Docker

- **Sempre** rodar `npm run build` antes de deploy (gera `build/frontend/`)
- **Validar** `docker-compose.prod.yml` inclui todos os serviços
- **Adicionar** health checks em todos os serviços
- **Testar** em staging antes de produção
- **Nunca** deploy direto sem validar P0s

### 4. Dev vs Prod Drift

- **Considerar** diferenças antes de sugerir correções:
  - Dev: Flask debug, Vite HMR, volumes mount
  - Prod: Gunicorn, Nginx estático, sem volumes
- **Sempre** testar com config de produção localmente
- **Documentar** se mudança afeta apenas dev ou apenas prod

### 5. Database e Supabase

- **RLS policies** obrigatórias em todas as tabelas
- **`tenant_id`** em todas as queries multi-tenant
- **Migrations** versionadas e testadas antes de apply
- **Nunca** usar service role key no frontend

### 6. Frontend

- **TypeScript** obrigatório em novos arquivos
- **Axios interceptors** para JWT refresh
- **Validar** `VITE_API_URL` correto por ambiente
- **Não commitar** `node_modules/` ou `dist/`

### 7. Logs e Health Checks

- **Sempre** adicionar logs em endpoints críticos
- **Implementar** `/health` em todos os serviços
- **Validar** pós-mudança:
  ```bash
  docker compose ps
  curl http://localhost:8001/health
  docker compose logs --tail=50 <serviço>
  ```

### 8. Correções Incrementais

- **Preferir** mudanças pequenas e reversíveis
- **Sempre** ter rollback plan antes de deploy
- **Testar** cada mudança isoladamente
- **Documentar** no `TODO.md` após correção

### 9. Troubleshooting

- **Fonte principal:** `DEBUGGING_PLAYBOOK.md`
- **Seguir** árvore de decisão por sintomas
- **Usar** comandos copy/paste do playbook
- **Validar** com health checks antes de abrir issues

### 10. Segurança

- **Nunca** expor secrets no git, logs ou console
- **Validar** `.gitignore` cobre `.env`, `node_modules/`, `build/`
- **Não commitar** arquivos de configuração com dados reais
- **Usar** `.env.example` como template seguro

---

## Comandos Padrão

### Dev Local
```bash
# Subir tudo
docker compose up -d

# Ver logs
docker compose logs -f backend frontend

# Rebuild
docker compose up -d --build
```

### Produção (VPS Hostinger)
```bash
# Build frontend
cd frontend && npm run build

# Validar build
ls -la build/frontend/

# Deploy
docker compose -f docker-compose.prod.yml up -d

# Health checks
curl https://api.alcahub.cloud/health
docker compose -f docker-compose.prod.yml ps
```

### Troubleshooting
```bash
# Verificar containers
docker compose ps

# Logs específicos
docker compose logs --tail=100 backend

# Testar endpoints
curl http://localhost:8001/health
curl http://localhost:3000/
```

---

## Checklist Antes de Commit

- [ ] Li `AGENTS.md`, `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`
- [ ] Validei impacto nos P0s conhecidos
- [ ] Testei localmente (dev e prod config)
- [ ] Health checks passando
- [ ] Logs sem errors novos
- [ ] `.env` não commitado
- [ ] `TODO.md` atualizado se aplicável

---

## Checklist Antes de Deploy

- [ ] P0s validados/resolvidos
- [ ] Build frontend gerado (`build/frontend/`)
- [ ] JWT secrets alinhados
- [ ] Health checks configurados
- [ ] Rollback plan definido
- [ ] Logs de produção monitorados

---

**Regra de Ouro:** Se não tem certeza, pergunte. Melhor validar do que quebrar produção.
