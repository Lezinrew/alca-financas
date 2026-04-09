# TODO.md - Alça Finanças

**Última atualização:** 2026-04-09  
**Status:** 🔴 Crítico - Docker fora do ar

---

## 🔥 PRIORIDADE 1 - SISTEMA SOBROU OU NÃO SOBRE

### 1.1 Docker Desktop não inicia no Windows
- **Hipótese:** Docker Desktop corrompido ou serviço parado
- **Arquivos:** `docker-compose.yml`, `docker-compose.prod.yml`
- **Impacto:** Sem containers = sem sistema em dev local
- **Ferramenta:** Cursor (debug Docker Desktop)
- **Prompt:**
  ```
  Docker Desktop no Windows está com erro:
  "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified"
  
  Analise:
  1. Verifique se o serviço DockerDesktopService está rodando
  2. Valide configurações do Docker Desktop (WSL2 backend?)
  3. Sugira comandos de reset/restart
  4. Se necessário, gere script de reinstalação limpa
  
  Contexto: Workspace Alça Finanças, preciso subir containers localmente.
  ```

### 1.2 Unificar docker-compose (dev vs prod)
- **Hipótese:** 3 arquivos docker-compose causam confusão deploy
- **Arquivos:** `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Impacto:** Deploy errado, variáveis de ambiente confusas
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Temos 3 arquivos docker-compose no Alça Finanças:
  - docker-compose.yml (base?)
  - docker-compose.dev.yml
  - docker-compose.prod.yml
  
  Analise os 3 arquivos e:
  1. Identifique sobreposições e conflitos
  2. Sugira estrutura unificada com override (compose override pattern)
  3. Mantenha segredos fora do git (.env)
  4. Garanta que dev espelhe produção em estrutura
  
  Gere novo docker-compose.yml base + docker-compose.override.yml exemplo.
  ```

---

## 🎯 PRIORIDADE 2 - FLUXO PRINCIPAL

### 2.1 Consolidar chatbot (backend vs services)
- **Hipótese:** Chatbot tem implementação duplicada
- **Arquivos:** `backend/routes/chatbot.py`, `backend/chatbot/`, `services/chatbot/app.py`
- **Impacto:** WebSocket pode estar em serviço errado, autenticação falha
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  O Alça tem chatbot em 2 lugares:
  1. backend/chatbot/ + backend/routes/chatbot.py
  2. services/chatbot/app.py (FastAPI separado)
  
  MEMORY.md diz: "websocket para chat realtime"
  
  Analise:
  1. Qual está em produção hoje?
  2. Qual tem websocket real vs HTTP polling?
  3. Qual tem autenticação Supabase integrada?
  4. Sugira consolidação em um único serviço
  
  Gere plano de migração se necessário.
  ```

### 2.2 Validar autenticação Supabase JWT
- **Hipótese:** JWT expirando ou RLs policies bloqueando
- **Arquivos:** `backend/utils/supabase_jwt.py`, `backend/routes/auth_supabase.py`, `backend/utils/auth_utils_supabase.py`
- **Impacto:** Usuários não logam, loop infinito
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Auth do Alça usa Supabase JWT.
  
  Verifique:
  1. backend/utils/supabase_jwt.py - validação do token
  2. backend/routes/auth_supabase.py - fluxo login
  3. backend/utils/auth_utils_supabase.py - helpers
  
  Teste mentalmente o fluxo:
  Login → JWT → RLS policies → Query
  
  Identifique pontos de falha e gere fix.
  ```

---

## 📊 PRIORIDADE 3 - DADOS E CÁLCULOS

### 3.1 Unificar migrations do Supabase
- **Hipótese:** Migrations em 3 pastas diferentes, ordem desconhecida
- **Arquivos:** `backend/database/migrations/`, `backend/migrations/`, `supabase/migrations/`
- **Impacto:** Produção com schema errado, queries falham
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Temos migrations em 3 lugares:
  1. backend/database/migrations/ (002-015, tenant RLS)
  2. backend/migrations/ (chatbot)
  3. supabase/migrations/ (20260303_*, schema base)
  
  Analise:
  1. Qual a ordem correta de aplicação?
  2. Há duplicações?
  3. Há conflitos de tabelas/colunas?
  
  Gere:
  - migration_master.md com ordem exata
  - Script único de migração
  - Rollback script
  ```

### 3.2 Validar cálculos financeiros (money_utils)
- **Hipótese:** Decimais/rounding causando erros de centavos
- **Arquivos:** `backend/utils/money_utils.py`
- **Impacto:** Relatórios errados, usuário perde confiança
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Analise backend/utils/money_utils.py
  
  Verifique:
  1. Usa Decimal ou float?
  2. Round em que ponto (banco ou app)?
  3. Soma/subtração de transações
  4. Cálculo de saldo de cartões
  
  Gere testes unitários para:
  - Transação de R$ 0,01
  - Soma de 1000 transações
  - Juros de cartão
  ```

---

## 🎨 PRIORIDADE 4 - UX E DASHBOARD

### 4.1 Dashboard performance (queries N+1)
- **Hipótese:** Dashboard faz queries em loop por categoria/conta
- **Arquivos:** `backend/routes/dashboard.py`, `backend/services/report_service.py`
- **Impacto:** Dashboard lento (>5s), usuário abandona
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Dashboard do Alça está lento.
  
  Analise:
  1. backend/routes/dashboard.py - endpoints
  2. backend/services/report_service.py - queries
  
  Identifique:
  - Queries N+1 (loop por categoria/conta)
  - Falta de indexes
  - Dados não agregados no banco
  
  Sugira otimizações com:
  - JOINs adequados
  - Materialized views se necessário
  - Cache de KPIs
  ```

### 4.2 Frontend dist no git (poluição)
- **Hipótese:** Build do frontend commitado acidentalmente
- **Arquivos:** `.gitignore`, `frontend/dist/`
- **Impacto:** Repo inchado, deploy confuso
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Verifique se frontend/dist/ está no .gitignore.
  
  Se não estiver:
  1. Adicione ao .gitignore
  2. Gere comando git para remover do histórico (git rm --cached -r frontend/dist)
  3. Gere .gitignore completo para React+Vite
  
  Isso é crítico pra não poluir o repo.
  ```

---

## 🛠️ PRIORIDADE 5 - DÉBITO TÉCNICO

### 5.1 Python 3.9 obsoleto (urllib3 warning)
- **Hipótese:** Backend em Python 3.9, urllib3 v2 incompatível
- **Arquivos:** `backend/requirements.txt`, `backend/Dockerfile`, `backend/Dockerfile.prod`
- **Impacto:** Warnings em produção, possível vulnerabilidade
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Backend log mostra:
  "urllib3 v2 only supports OpenSSL 1.1.1+, currently compiled with LibreSSL 2.8.3"
  
  Backend usa Python 3.9 (backend/Dockerfile).
  
  Plano:
  1. Atualizar para Python 3.11 ou 3.12
  2. Atualizar requirements.txt compatível
  3. Testar migrations
  4. Atualizar Dockerfile.prod
  
  Gere diff completo.
  ```

### 5.2 Scripts de deploy duplicados
- **Hipótese:** 15+ scripts de deploy em `scripts/`, `legacy/scripts/`, raiz
- **Arquivos:** `scripts/*.sh`, `legacy/scripts/*.sh`, `alca_*.sh`
- **Impacto:** Deploy errado, ninguém sabe qual script usar
- **Ferramenta:** Claude CLI
- **Prompt:**
  ```
  Temos scripts em:
  - scripts/ (30+ arquivos)
  - legacy/scripts/ (15+ arquivos)
  - Raiz: alca_*.sh (10+ arquivos)
  
  Analise e:
  1. Identifique scripts obsoletos (legacy/)
  2. Unifique scripts ativos em scripts/dev/ e scripts/prod/
  3. Gere scripts/README.md com uso de cada
  4. Delete ou archive obsoletos
  
  Foque em: deploy, migrate, rebuild, setup.
  ```

### 5.3 Documentação fragmentada
- **Hipótese:** 50+ arquivos .md em `docs/`, `legacy/docs/`, raiz
- **Arquivos:** `docs/*.md`, `legacy/docs/*.md`, `DEPLOY*.md`, `README*.md`
- **Impacto:** Ninguém acha docs certa, repeating work
- **Ferramenta:** Cursor
- **Prompt:**
  ```
  Documentação do Alça está em:
  - docs/ (40+ arquivos)
  - legacy/docs/ (20+ arquivos)
  - Raiz: DEPLOY*.md, README*.md, QUICKSTART*.md
  
  Crie:
  1. docs/INDEX.md organizado por categoria
  2. Mova obsoletos para docs/archive/
  3. Mantenha apenas 3-5 na raiz (README, DEPLOY, QUICKSTART)
  4. Gere mapa mental da docs
  
  Categorias: Deploy, Auth, Database, Features, Troubleshooting.
  ```

---

## 📋 ORDEM DE ATAQUE RECOMENDADA

| Semana | Foco | Entregas |
|--------|------|----------|
| **Semana 1** | Prioridade 1 | Docker rodando, compose unificado |
| **Semana 2** | Prioridade 2 | Chatbot consolidado, auth validada |
| **Semana 3** | Prioridade 3 | Migrations unificadas, cálculos testados |
| **Semana 4** | Prioridade 4 | Dashboard rápido, frontend limpo |
| **Semana 5** | Prioridade 5 | Python atualizado, scripts organizados |

---

## 🚨 RISCOS IMEDIATOS

1. **Docker parado** = dev travado
2. **Chatbot duplicado** = auth pode falhar em produção
3. **Migrations bagunçadas** = próxima deploy quebra schema
4. **Python 3.9** = urllib3 pode quebrar em update

---

## 📝 NOTAS

- Backend está rodando no Mac (192.168.1.60), workspace no Windows
- Validar qual máquina é "produção local" antes de deploy
- MEMORY.md atualizado em 2026-04-09 com arquitetura alvo
