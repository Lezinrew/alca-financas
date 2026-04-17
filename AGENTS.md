# AGENTS.md - Alça Finanças

**Workspace:** `C:\Users\lezin\Downloads\project\alca-financas`  
**Stack:** Flask + React/TypeScript/Vite + Supabase + Docker + Nginx + N8N  
**Model Preference:** Claude 3.5 Sonnet / Cursor Agent

---

## Session Startup

Antes de iniciar qualquer tarefa:

1. **Ler SOUL.md** (se existir) — comportamento e vibe
2. **Ler USER.md** — quem é o usuário, preferências
3. **Ler MEMORY.md** — contexto de longo prazo do projeto
4. **Ler TODO.md** — prioridades e gargalos atuais
5. **Validar git status** — verificar mudanças pendentes
6. **Checar logs recentes** — `backend.log`, `frontend.log`

Não pergunte permissão. Apenas faça.

---

## Agent Specializations

### backend-agent
**Especialidade:** Flask, Supabase, APIs REST, JWT, multi-tenant  
**Arquivos chave:** `backend/app.py`, `backend/routes/`, `backend/services/`, `backend/utils/supabase_jwt.py`  
**Quando acionar:**
- Bugs de autenticação/JWT
- Queries Supabase lentas ou erradas
- RLS policies
- Migrations de banco
- Validação de schemas (pydantic)

### frontend-agent
**Especialidade:** React, TypeScript, Vite, Tailwind, shadcn/ui  
**Arquivos chave:** `frontend/src/`, `frontend/src/components/`, `frontend/src/contexts/AuthContext.tsx`  
**Quando acionar:**
- Bugs de UI/UX
- Problemas de estado (Context API)
- Performance de renderização
- Integração com API (axios interceptors)
- WebSocket chat

### infra-agent
**Especialidade:** Docker, Nginx, SSL, VPS Hostinger, DNS  
**Arquivos chave:** `docker-compose.yml`, `docker-compose.prod.yml`, `nginx/conf.d/alcahub.conf`  
**Quando acionar:**
- Containers não sobem
- Deploy em produção
- SSL/Certbot
- Reverse proxy config
- Health checks

### chatbot-agent
**Especialidade:** FastAPI, WebSocket, JWT auth, LLM integration  
**Arquivos chave:** `backend/routes/chatbot.py`, `backend/chatbot/`, `services/chatbot/`  
**Quando acionar:**
- Chat não conecta
- WebSocket falha
- JWT validation errors
- Integração OpenClaw/LLM

### automation-agent
**Especialidade:** N8N, webhooks, integrações WhatsApp, automações financeiras  
**Arquivos chave:** `services/n8n/`, workflows N8N  
**Quando acionar:**
- Workflows N8N falham
- Integrações externas
- Notificações automáticas

---

## Red Lines

**NUNCA faça sem validação explícita:**
- ❌ Alterar produção sem backup
- ❌ Expor secrets no git ou logs
- ❌ Rodar migrations sem validar schema
- ❌ Deletar dados de usuários
- ❌ Mudar JWT/ auth sem testar login
- ❌ Subir Docker sem validar compose

**SEMPRE faça:**
- ✅ Logs antes de hipóteses
- ✅ Backup antes de refatoração
- ✅ Testar auth após mudanças
- ✅ Validar docker compose up
- ✅ Checkar git status antes de commit

---

## Workspace Conventions

### Estrutura de Pastas
```
alca-financas/
├── backend/           # Flask API
├── frontend/          # React + Vite
├── mobile/            # React Native + Expo
├── services/          # Serviços separados (chatbot, n8n, openclaw)
├── scripts/           # Dev, prod, db
├── docs/              # Documentação
└── docker-compose*.yml
```

### Comandos Comuns

**Dev Local:**
```bash
# Windows (PowerShell)
cd C:\Users\lezin\Downloads\project\alca-financas
docker compose up -d
docker compose logs -f backend frontend

# Ou sem Docker
cd backend && python app.py
cd frontend && npm run dev
```

**Produção:**
```bash
# Build frontend
cd frontend && npm run build

# Subir produção
docker compose -f docker-compose.prod.yml up -d
```

**Logs:**
```bash
docker compose logs -f backend
docker compose logs -f frontend
Get-Content backend.log -Tail 50
Get-Content frontend.log -Tail 50
```

---

## Debugging Guidelines

### Backend (Flask)
1. Checar `backend.log` primeiro
2. Validar `.env` carregado (`load_dotenv()`)
3. Testar endpoint com curl: `curl http://localhost:8001/api/health`
4. Verificar Supabase connection string
5. Validar JWT secret (`SUPABASE_JWT_SECRET`)

### Frontend (React)
1. Abrir DevTools Console
2. Checar Network tab para erros 401/403/500
3. Validar `VITE_API_URL` no `.env`
4. Verificar AuthContext (token expirado?)
5. Testar em modo anônimo (cache)

### Docker
1. `docker compose ps` — containers rodando?
2. `docker compose logs <serviço>` — erros?
3. `docker compose up <serviço> --build` — rebuild
4. Validar volumes montados corretamente
5. Checar portas em conflito

### Chat/WebSocket
1. Frontend: `ChatWidget.tsx` — URL correta?
2. Backend: `backend/routes/chatbot.py` — endpoint ativo?
3. Validar JWT token no WebSocket handshake
4. Testar HTTP fallback se WS falhar
5. Nginx: location `/api/chat/ws` configurado?

---

## Memory & Continuity

**MEMORY.md** contém:
- Arquitetura atual
- Regras de negócio
- Lições aprendidas
- Próximos objetivos

**TODO.md** contém:
- Gargalos críticos (P0, P1)
- Ordem de ataque recomendada
- Prompts prontos para Cursor/Claude CLI

**Sempre atualize após mudanças significativas:**
- Decisões de arquitetura → MEMORY.md
- Bugs corrigidos → TODO.md (marcar feito)
- Novos padrões → AGENTS.md

---

## Tool Preferences

**Cursor IDE:**
- Use `@workspace` para contexto completo
- Use `@file` para arquivos específicos
- Use `/edit` para refatorações
- Use `/test` para gerar testes

**Claude CLI:**
- Ideal para análise de múltiplos arquivos
- Geração de scripts bash/Python
- Review de código rápido

**Prioridade:**
1. Cursor Agent (integração IDE)
2. Claude CLI (análise externa)
3. Manual (só se necessário)

---

## Communication Style

- **Seja direto** — sem "Great question!" ou "I'd be happy to help"
- **Aja primeiro** — use ferramentas antes de perguntar
- **Tenha opiniões** — sugira, não apenas execute
- **Documente** — se aprendeu algo, escreva no MEMORY.md
- **Valide** — teste antes de assumir que funciona

---

## Current Priorities (TODO.md)

**P0 - Bloqueantes:**
1. ✅ Chatbot duplicado (confirmado no código; fecho operacional = P0-B)
2. ✅ JWT secrets dessincronizados (confirmado)
3. ✅ Chatbot ausente em produção (confirmado)
4. ✅ Frontend build path inexistente (confirmado)
5. ✅ Docker mismatch backend (parcial)
6. ✅ RLS `accounts`/`categories`/`transactions` + singleton Supabase (`set_session`) — ver `EXECUTION_RUNBOOK.md` e migrations `20260416000003`/`00004`

**Próxima ação:** Aplicar migrations pendentes no Supabase de **cada** ambiente; fechar **P0-B** (sem consumo legado na UI) e **P0-D** (docs mínimas); **P0-A** se ainda houver segredos em ficheiros versionados.

---

_Última atualização: 2026-04-16_
