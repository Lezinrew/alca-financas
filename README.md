# Alça Finanças

SaaS multi-tenant de **controle financeiro** com autenticação Supabase, API Flask e frontend React. O repositório inclui integração opcional de **chatbot** (regras e/ou OpenClaw), automação via **n8n** (documentada para VPS) e app **mobile** (Expo) em evolução.

[![CI/CD Pipeline](https://github.com/Lezinrew/alca-financas/actions/workflows/ci.yml/badge.svg)](https://github.com/Lezinrew/alca-financas/actions/workflows/ci.yml)

## Objetivo do sistema

Centralizar receitas, despesas, contas, categorias, planejamento e metas por **organização (tenant)**, com isolamento de dados (RLS no Postgres), relatórios e pontos de extensão para assistentes e automações.

## Stack

| Camada | Tecnologias |
|--------|-------------|
| Frontend web | React 18, TypeScript, Vite, Tailwind, Axios, Recharts, Supabase JS (auth) |
| Backend | Python 3.9, Flask 3, Supabase (client service role), Pydantic, rate limiting |
| Banco / auth | **Supabase** (PostgreSQL, Auth, RLS) |
| Chatbot / IA | Rotas em `backend/routes/chatbot.py`; serviço opcional `services/chatbot/`; OpenClaw em `services/openclaw` + `services/openclaw_bridge` (perfil Docker `openclaw`) |
| Automação | **n8n** em geral fora do repo ou em stack no VPS (ver `n8n/README.md` e `docs/N8N-VPS-SETUP.md`) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |
| Contêineres | `docker-compose.yml` (dev: backend + frontend) |

## Como rodar local

### Pré-requisitos

- Docker e Docker Compose
- Conta Supabase e projeto criado
- Node 18+ e Python 3.9+ (se rodar fora do Docker)

### 1. Variáveis de ambiente

```bash
cp .env.example .env
# Preencha SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, SECRET_KEY (≥32 chars)
```

Detalhes: `docs/ENVIRONMENTS.md`. O backend valida `SECRET_KEY` forte em `backend/app.py`.

### 2. Docker (recomendado)

```bash
# Na raiz do repositório
docker compose up -d
```

- API: `http://localhost:8001` (health: `GET /api/health`)
- Frontend: `http://localhost:3000`

### 3. Script de desenvolvimento (bash)

```bash
./scripts/local-dev.sh start   # sobe compose, checa health
./scripts/local-dev.sh logs
./scripts/local-dev.sh stop
```

### 4. Sem Docker

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env na raiz já carregado por app.py
python app.py

# Frontend (outro terminal)
cd frontend && npm install && npm run dev
```

### 5. OpenClaw (opcional)

```bash
docker compose --profile openclaw up -d
```

Requer variáveis como `OPENCLAW_GATEWAY_TOKEN` no `.env`. Ver `services/openclaw/README.md` e `docs/OPENCLAW-DEPLOY-SEGURO.md`.

### Migrations

Schema versionado em `supabase/migrations/`. Aplicar no projeto Supabase de cada ambiente antes de depender de novas tabelas/policies. Guia: `supabase/README.md`.

## Estrutura de pastas (resumo)

```
alca-financas/
├── backend/              # API Flask, rotas, services, repositórios Supabase
├── frontend/             # SPA React + Vite
├── mobile/               # React Native / Expo
├── services/             # chatbot (FastAPI), openclaw, openclaw_bridge
├── supabase/             # migrations SQL e README de banco
├── scripts/              # dev, deploy, testes, nginx, n8n
├── docs/                 # guias; runbook e decisões em subpastas
├── infra/                # intenção de deploy (VPS, Docker, Nginx) — ver infra/README.md
├── n8n/                  # papel do n8n e links (workflows costumam estar no servidor)
├── system-design.md      # arquitetura e fluxos
└── AGENTS.md             # orientação para agentes/IDE
```

## Comandos principais

| Comando | Descrição |
|--------|------------|
| `docker compose up -d` | Sobe backend + frontend (dev) |
| `docker compose --profile openclaw up -d` | Inclui OpenClaw (opcional) |
| `cd frontend && npm run dev` | Frontend Vite |
| `cd frontend && npm run build` | Build de produção |
| `cd backend && python app.py` | API local |
| `./scripts/local-dev.sh start` | Atalho com health check |
| `./scripts/dev/setup.sh` | Instala deps backend + frontend (ver `scripts/dev/`) |
| `./scripts/dev/up.sh` / `down.sh` | Sobe/para serviços conforme script |
| `./scripts/run-tests.sh` | Testes (via `package.json`: `npm test`, etc.) |

> **Nota:** o `package.json` da raiz referencia `scripts/quick-start.sh` em alguns scripts; se o ficheiro não existir no seu clone, use `docker compose` ou `./scripts/local-dev.sh` como acima.

## Documentação mínima obrigatória para retomar o projeto

1. [system-design.md](system-design.md) — arquitetura e entidades  
2. [docs/runbooks/runbook.md](docs/runbooks/runbook.md) — estado operacional (fonte única para “onde estamos”)  
3. [docs/agents/01-execution-agent.md](docs/agents/01-execution-agent.md) — como agentes devem trabalhar  
4. [AGENTS.md](AGENTS.md) — convenções e agentes por área  

Índice amplo: `docs/INDEX.md` ou `docs/INDICE.md`.

## Licença

MIT (ver repositório).
