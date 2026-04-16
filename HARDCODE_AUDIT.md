# HARDCODE_AUDIT.md

Data: 2026-04-14  
Escopo: varredura de hardcodes de CORS, `localhost`/`127.0.0.1`, JWT/secrets, portas, URLs de API e configurações duplicadas.

## Resumo Executivo

- Foram identificados hardcodes críticos de segredo real versionado e múltiplos pontos de drift de configuração entre backend/frontend/scripts.
- O principal risco imediato é **exposição de token sensível** em arquivo versionado.
- Há também risco operacional por **duplicação de configuração** (CORS, URL de API, JWT legado) em vários pontos de entrada.

## Prioridade P0 (Crítico - corrigir imediatamente)

### 1) Secret/token real versionado em arquivo de configuração recomendado
- **Arquivo:** `.cursor/mcp.json.recommended`
- **Evidência:**
  - `API_TOKEN` preenchido com valor real em `hostinger-mcp`.
- **Risco:** comprometimento de infraestrutura externa (Hostinger MCP/API).
- **Ação recomendada:**
  - Revogar/rotacionar token imediatamente.
  - Substituir no repositório por placeholder.
  - Garantir que arquivo final com segredo real fique fora de versionamento.

### 2) Chave Supabase (anon) hardcoded em script de hotfix
- **Arquivo:** `scripts/hotfix-supabase-prod-simple.sh`
- **Evidência:**
  - `SUPABASE_URL="https://blutjlzyvhdvnkvrzdcm.supabase.co"`
  - `SUPABASE_KEY="eyJ..."`
  - `VITE_API_URL="http://localhost:8001"` em contexto de rebuild remoto.
- **Risco:** vazamento de credencial e deploy com endpoint incorreto para produção.
- **Ação recomendada:**
  - Remover chave hardcoded e ler de variáveis de ambiente/secrets manager.
  - Bloquear execução sem variáveis obrigatórias.
  - Ajustar `VITE_API_URL` para domínio/API de produção no pipeline de produção.

## Prioridade P1 (Alta - segurança e confiabilidade)

### 3) Fallback de CORS permissivo para localhost no backend principal
- **Arquivo:** `backend/app.py`
- **Evidência:**
  - Se `CORS_ORIGINS == '*'`, aplica fallback com `localhost` e `127.0.0.1` em múltiplas portas.
- **Risco:** comportamento inesperado entre ambientes; produção pode subir com origem incorreta se env faltar.
- **Ação recomendada:**
  - Em produção, falhar startup se `CORS_ORIGINS` não estiver definido explicitamente.
  - Manter fallback apenas em modo dev explícito.

### 4) Drift de JWT legado ainda presente em scripts
- **Arquivos:** `scripts/dev/up.sh`, `scripts/setup-env.sh`
- **Evidência:**
  - `scripts/dev/up.sh`: `JWT_SECRET="${JWT_SECRET:-dev-jwt-secret}"`.
  - `scripts/setup-env.sh`: fluxo ainda gera/preenche `JWT_SECRET` como obrigatório.
- **Risco:** confusão operacional e divergência com estratégia Supabase-only (`SUPABASE_JWT_SECRET` como fonte única).
- **Ação recomendada:**
  - Remover exigência de `JWT_SECRET` dos scripts.
  - Padronizar validação e documentação para apenas `SUPABASE_JWT_SECRET` + `SECRET_KEY`.

### 5) URLs de API locais hardcoded em clientes
- **Arquivos:** `frontend/src/utils/api.ts`, `frontend/src/components/chat/ChatWidget.tsx`, `mobile/src/api/client.ts`, `frontend/Dockerfile`
- **Evidência:**
  - Frontend web default: `http://localhost:8001`.
  - Chat widget default DEV: `http://localhost:8001/api/chatbot`.
  - Mobile fallback: `http://localhost:8001`.
  - Docker ARG default: `VITE_API_URL=http://localhost:8001`.
- **Risco:** build/deploy com endpoint local por engano; inconsistência entre canais (web/mobile/chat).
- **Ação recomendada:**
  - Definir matriz única por ambiente (dev/staging/prod).
  - Falhar build de produção se `VITE_API_URL` estiver em localhost.

## Prioridade P2 (Média - dívida técnica com impacto frequente)

### 6) Configuração duplicada de CORS e portas em múltiplos entrypoints de execução
- **Arquivos:** `docker-compose.yml`, `alca_start_mac.sh`, `scripts/dev/up.sh`, `.env.example`, `backend/.env.example`
- **Evidência:**
  - Múltiplas listas de `CORS_ORIGINS` com combinações diferentes.
  - Portas e hosts repetidos em scripts (`3000`, `5173`, `8001`, `5000`, `0.0.0.0`).
- **Risco:** ambientes sobem com comportamento diferente; regressões difíceis de reproduzir.
- **Ação recomendada:**
  - Centralizar defaults em um único arquivo fonte (ex.: `.env.example` + loader único).
  - Fazer scripts apenas consumirem variáveis já definidas (sem redefinir defaults sensíveis).

### 7) Serviço chatbot legado com CORS e base URL hardcoded
- **Arquivo:** `services/chatbot/app.py`
- **Evidência:**
  - `API_BASE_URL` default para `http://127.0.0.1:8001`.
  - `allow_origins` fixo com domínios e localhost.
  - Bind local `host="127.0.0.1"`.
- **Risco:** configuração divergente do backend Flask atual; comportamento inconsistente se serviço legado voltar a ser usado.
- **Ação recomendada:**
  - Se legado: arquivar/remover de execução.
  - Se mantido: externalizar CORS/API URL para env e alinhar com padrão principal.

## Prioridade P3 (Baixa - higiene de repositório/documentação)

### 8) Grande volume de referências hardcoded em docs/legacy/scripts de apoio
- **Escopo afetado:** `legacy/`, `docs/`, guias e playbooks com `localhost`, portas fixas, domínios antigos e exemplos repetidos.
- **Evidência:**
  - Alta recorrência de `localhost`/`127.0.0.1` e exemplos de CORS em documentação histórica.
- **Risco:** ruído para onboarding e chance de copiar configuração desatualizada.
- **Ação recomendada:**
  - Marcar claramente docs legacy.
  - Manter apenas um guia fonte de verdade por ambiente.

## Mapa de Duplicações Relevantes

- **CORS_ORIGINS** aparece em backend, compose, scripts de dev/prod, `.env.example` e docs.
- **VITE_API_URL** aparece em frontend runtime, Dockerfiles, compose e scripts de hotfix/deploy.
- **JWT/Secrets** coexistem entre padrão novo (Supabase JWT) e legado (`JWT_SECRET`) em scripts e documentação.
- **Portas/hosts** (`3000`, `5173`, `8001`, `5000`, `0.0.0.0`, `127.0.0.1`) estão espalhados em diversos pontos sem governança central.

## Ordem Recomendada de Correção

1. **P0:** rotacionar tokens expostos e remover hardcode de segredo.
2. **P1:** eliminar `JWT_SECRET` legado de scripts e reforçar validações de produção.
3. **P1/P2:** unificar origem de `VITE_API_URL` e `CORS_ORIGINS`.
4. **P2:** consolidar scripts de bootstrap para não sobrescrever env com defaults inseguros.
5. **P3:** limpar documentação legacy e apontar para fonte única.

## Checklist de Fechamento (após correções)

- [ ] Nenhum secret real versionado (`rg` por tokens/chaves retorna apenas placeholders).
- [ ] Build de produção falha se detectar `localhost` em `VITE_API_URL`.
- [ ] Backend falha em produção sem `CORS_ORIGINS` explícito.
- [ ] Scripts não dependem mais de `JWT_SECRET` legado.
- [ ] Documentação centralizada por ambiente (dev/prod) com versão única.

