# Scripts Legados

Scripts movidos para esta pasta pois foram substituídos, tornaram-se obsoletos ou são específicos de setup já realizado.

## 📋 Lista de Scripts

### Migração e Setup Inicial (já executados)
- `migrate-cicd.sh` - Migração de workflows CI/CD (substituído por novos workflows)
- `setup-ssl-production.sh` - Configuração SSL inicial (já configurado)
- `setup-server-security.sh` - Hardening do servidor (já aplicado)
- `setup-vps.sh` - Setup inicial do VPS (já executado)
- `setup-monitoring.sh` - Setup de monitoramento (já configurado)

### Google OAuth (migrado para Supabase)
- `configurar-google-oauth.sh` - Configuração Google OAuth (projeto migrou para Supabase Auth)

### Deploy (substituídos por CI/CD)
- `deploy-docker-remote.sh` - Deploy via Docker remoto (substituído por `deploy.sh` e CI/CD)
- `deploy-quick-update.sh` - Quick update (substituído por workflow `deploy-production.yml`)

### Fixes Pontuais (já aplicados)
- `fix-502-error.sh` - Fix de erro 502 (problema resolvido)
- `fix-local-dev.sh` - Fix ambiente local (problema resolvido)
- `fix-traefik-alcahub-cloud.sh` - Fix Traefik (não mais usado)

### Hotfix Supabase (duplicado)
- `hotfix-supabase-prod.sh` - Versão antiga (mantido `hotfix-supabase-prod-simple.sh`)

### Utilitários Simples (sem valor agregado)
- `git-commit-push.sh` - Wrapper git simples (desnecessário)
- `test-ssh-connection.sh` - Teste SSH básico (pode usar ssh direto)
- `start-chatbot.sh` - Chatbot antigo (não mais usado)
- `stop-local.sh` - Parar serviços locais (substituído por `local-dev.sh stop`)

---

## 🗑️ Podem ser deletados?

**SIM**, se confirmado que não são mais necessários. Mantidos aqui por cautela durante período de transição.

**Período de retenção sugerido**: 30-60 dias, depois deletar permanentemente.

---

## 📚 Scripts Ativos (em `scripts/`)

### Core
- `deploy.sh` - Deploy principal (local test + production via SSH)
- `local-dev.sh` - Gerenciamento ambiente dev (start/stop/logs/rebuild/clean)
- `run-tests.sh` - Executar testes

### Setup/Configuração
- `setup-env.sh` - Setup ambiente (.env, dependências)
- `setup-github-secrets.sh` - Configurar secrets do GitHub
- `setup-supabase-credentials.sh` - Configurar credenciais Supabase

### Hotfix/Emergência
- `get-supabase-jwt-secret.sh` - Obter JWT secret do Supabase
- `hotfix-supabase-prod-simple.sh` - Hotfix Supabase em prod
- `rebuild-frontend-prod-on-server.sh` - Rebuild frontend no servidor
- `rebuild-prod-now.sh` - Rebuild prod agora (SSH direto)

### Utilitários
- `load-env.sh` - Carregar variáveis de ambiente
- `verify-production.sh` - Verificar status produção

---

**Data de arquivamento**: 2026-03-20
**Razão**: Simplificação de scripts após migração para Supabase e CI/CD automatizado
