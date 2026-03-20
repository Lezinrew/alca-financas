# 🚀 Guia Operacional CI/CD - Alça Finanças

## 📋 Estrutura Final (2 Workflows Principais)

```
.github/workflows/
├── deploy-dev.yml          ✅ CI/CD para branch develop
├── deploy-production.yml   ✅ Deploy automático para produção (dispara após CI)
├── validate-migrations.yml ✅ Validação de migrations (mantido)
└── gitleaks.yml            ✅ Security scan (mantido)
```

---

## 🔄 WORKFLOW DE DESENVOLVIMENTO

### Como deployar DEV

#### 1. Trabalhar em feature branch
```bash
git checkout -b feature/minha-feature
# ... fazer mudanças ...
git add .
git commit -m "feat: minha feature"
git push origin feature/minha-feature
```

#### 2. Criar Pull Request para `develop`
```bash
# GitHub UI: Create Pull Request
# Base: develop ← Compare: feature/minha-feature
```

**O que acontece automaticamente:**
- ✅ TypeScript check
- ✅ Python lint
- ✅ Backend tests
- ✅ Frontend tests
- ✅ Security scan
- ⏭️ **NÃO faz deploy** (apenas validação)

#### 3. Após merge para `develop`
```bash
git checkout develop
git pull origin develop
```

**O que acontece automaticamente:**
- ✅ Todas validações acima
- ✅ Build de Docker images
- ✅ Cache de builds para acelerar próximos deploys

---

## 🚀 WORKFLOW DE PRODUÇÃO

### Como deployar PROD

#### 1. Merge develop → main
```bash
# Após testes em develop
git checkout main
git pull origin main
git merge develop
git push origin main
```

**O que acontece automaticamente:**
1. **Pre-flight checks** (~2min)
   - TypeScript validation
   - Python critical lint

2. **Deploy Backend** (~5min)
   - Build Docker image
   - Upload para servidor
   - Deploy via SSH
   - Wait for health

3. **Deploy Frontend** (~3min)
   - Build frontend no servidor
   - Deploy nginx
   - Force recreate

4. **Health Checks** (~1min)
   - Backend API health
   - Frontend accessibility

5. **Smoke Tests** (~2min)
   - Auth flow (login/logout)
   - Dashboard load
   - API endpoints

6. **Notificação** (Telegram)
   - ✅ Success: Deploy OK
   - ❌ Failure: Instruções de rollback

**Total:** ~13 minutos (deploy completo + validação)

---

## 🔍 VERIFICAR SAÚDE PÓS-DEPLOY

### Backend Health Check

```bash
# Via curl (local)
curl http://localhost:8001/api/health

# Via curl (produção)
curl http://<PROD_HOST>:8001/api/health

# Resposta esperada:
# {"status": "healthy", "timestamp": "2026-03-18T..."}
```

### Frontend Health Check

```bash
# Via curl (local)
curl -I http://localhost:3000

# Via curl (produção)
curl -I http://<PROD_HOST>:3000

# Resposta esperada:
# HTTP/1.1 200 OK
# Content-Type: text/html
```

### Docker Services Status

```bash
# DESENVOLVIMENTO (local)
docker compose ps

# PRODUÇÃO (via SSH)
ssh user@servidor
cd /var/www/alca-financas
docker compose -f docker-compose.prod.yml ps

# Saída esperada:
# NAME       STATUS    PORTS
# backend    Up        0.0.0.0:8001->8001/tcp
# frontend   Up        0.0.0.0:3000->80/tcp
```

### Logs em Tempo Real

```bash
# DESENVOLVIMENTO
docker compose logs -f

# Backend apenas
docker compose logs -f backend

# Frontend apenas
docker compose logs -f frontend

# PRODUÇÃO
ssh user@servidor
cd /var/www/alca-financas
docker compose -f docker-compose.prod.yml logs -f backend frontend
```

---

## 🐛 TROUBLESHOOTING

### Deploy falhou - Como fazer rollback?

#### Método 1: Via GitHub Actions (Re-run anterior)
```
1. Ir para: Actions → Deploy to Production
2. Selecionar último deploy bem-sucedido
3. Clicar "Re-run all jobs"
```

#### Método 2: Manual via SSH
```bash
ssh user@servidor
cd /var/www/alca-financas

# Ver últimos commits
git log --oneline -5

# Rollback para commit anterior
git reset --hard <commit-hash-anterior>

# Rebuild e restart
docker compose -f docker-compose.prod.yml up -d --force-recreate

# Verificar
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8001/api/health
```

### Smoke tests falhando

**Sintoma:** Deploy completo mas smoke tests falham

**Diagnóstico:**
```bash
# Verificar se serviços estão rodando
docker compose -f docker-compose.prod.yml ps

# Verificar logs de erro
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# Testar manualmente
curl http://localhost:8001/api/health
curl -I http://localhost:3000
```

**Soluções:**
1. Backend não respondendo → Verificar variáveis `.env`
2. Frontend 404 → Verificar se `build/frontend/index.html` existe
3. Database errors → Verificar Supabase credentials

---

## ⚙️ COMANDOS ÚTEIS

### Validação Local (antes de commit)

```bash
# TypeScript check
cd frontend && npx tsc --noEmit

# Python lint
cd backend && flake8 . --max-line-length=120

# Backend tests
cd backend && pytest tests/unit -v

# Frontend tests
cd frontend && npm run test:run

# Build local de produção
./scripts/deploy.sh local
```

### Gerenciar Ambiente Local

```bash
# Iniciar dev
./scripts/local-dev.sh start

# Ver logs
./scripts/local-dev.sh logs

# Rebuild completo
./scripts/local-dev.sh rebuild

# Parar tudo
./scripts/local-dev.sh stop

# Limpar volumes (CUIDADO!)
./scripts/local-dev.sh clean
```

### Deploy Manual (emergência)

```bash
# Deploy produção via script
./scripts/deploy.sh production

# Vai pedir confirmação antes de deployar
```

---

## 🔐 SECRETS NECESSÁRIOS

### GitHub Secrets (Settings → Secrets → Actions)

| Secret | Descrição | Exemplo |
|--------|-----------|---------|
| `PROD_HOST` | IP/hostname do servidor | `123.45.67.89` |
| `PROD_USER` | Usuário SSH | `deploy` |
| `PROD_PASSWORD` | Senha SSH (ou use SSH key) | `***` |
| `TELEGRAM_BOT_TOKEN` | Bot do Telegram para notificações | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Chat ID para receber notificações | `-1001234567890` |

---

## 📊 MÉTRICAS DE PERFORMANCE

### Tempos Esperados

| Workflow | Duração Média | Máximo Aceitável |
|----------|---------------|------------------|
| **deploy-dev.yml** | 5-8 min | 12 min |
| **deploy-production.yml** | 10-15 min | 20 min |
| **validate-migrations.yml** | 1-2 min | 5 min |
| **gitleaks.yml** | 30s | 2 min |

### Frequência de Deploys

- **Develop**: Múltiplos por dia (OK)
- **Production**: 1-3 por dia (recomendado)
- **Hotfix**: Imediato (use workflow_dispatch)

---

## 🎯 BOAS PRÁTICAS

### ✅ DO (Faça)

1. **Sempre testar em develop** antes de mergear para main
2. **Criar feature branches** para novas funcionalidades
3. **Commits pequenos e frequentes** com mensagens claras
4. **Aguardar smoke tests** passarem antes de considerar deploy completo
5. **Monitorar logs** após deploy de produção (primeiros 5min)

### ❌ DON'T (Não faça)

1. **Push direto para main** (sempre via develop)
2. **Skip smoke tests** em produção (apenas em emergência)
3. **Deployar sem validar em local** primeiro
4. **Múltiplos deploys simultâneos** (concurrency está configurado)
5. **Ignorar falhas de health check**

---

## 🆘 SUPORTE

- **Logs de workflow**: [GitHub Actions](https://github.com/Lezinrew/alca-financas/actions)
- **Documentação deployment**: `DEPLOY.md`
- **Scripts**: `scripts/deploy.sh`, `scripts/local-dev.sh`
- **Issues**: https://github.com/Lezinrew/alca-financas/issues

---

## 📝 CHANGELOG

### 2026-03-20 - Workflow único de produção
- ✅ Removido `deploy-prod.yml` (redundante)
- ✅ Mantido apenas `deploy-production.yml` (mais completo, com smoke tests)
- ✅ Secrets configurados no ambiente `production`

### 2026-03-18 - Simplificação CI/CD
- ✅ Criado `deploy-dev.yml` (CI para develop)
- ✅ Atualizado `deploy-production.yml` (deploy produção otimizado)
- ✅ Removido `ci.yml` (substituído por deploy-dev)
- ✅ Removido `docker-compose.dev.yml` (redundante)
- ✅ OpenClaw isolado do fluxo principal
- ✅ Rollback automático em caso de falha
