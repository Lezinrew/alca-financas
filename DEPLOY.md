# 🚀 Guia de Deploy - Alça Finanças

## 📋 Sumário

1. [Desenvolvimento Local](#desenvolvimento-local)
2. [Testes Locais](#testes-locais)
3. [Deploy Automático (CI/CD)](#deploy-automático-cicd)
4. [Deploy Manual](#deploy-manual)
5. [Troubleshooting](#troubleshooting)

---

## 🔧 Desenvolvimento Local

### Pré-requisitos

- Docker e Docker Compose v2+
- Node.js 20+ (opcional, para desenvolvimento sem Docker)
- Python 3.9+ (opcional, para desenvolvimento sem Docker)
- Arquivo `.env` configurado

### 1. Configurar Ambiente

```bash
# Clone o repositório (se ainda não fez)
git clone https://github.com/Lezinrew/alca-financas.git
cd alca-financas

# Copie o .env de exemplo e configure
cp .env.example .env
# Edite .env com suas credenciais (Supabase, secrets, etc)
```

### 2. Iniciar Ambiente de Desenvolvimento

**Opção A: Docker (Recomendado)**

```bash
# Inicia todos os serviços em modo desenvolvimento
docker compose up -d

# Logs em tempo real
docker compose logs -f

# Verificar status
docker compose ps
```

**Opção B: Local (sem Docker)**

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

### 3. Acessar Aplicação

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs (se habilitado)

### 4. Hot Reload

O ambiente de desenvolvimento suporta **hot reload automático**:

- **Backend**: Python recarrega automaticamente ao modificar arquivos `.py`
- **Frontend**: Vite recarrega automaticamente ao modificar arquivos `.tsx/.ts/.css`

### 5. Parar Ambiente

```bash
# Parar serviços
docker compose down

# Parar e remover volumes (CUIDADO: apaga dados locais)
docker compose down -v
```

---

## 🧪 Testes Locais

### Testes Unitários

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Testes E2E

```bash
cd frontend
npx playwright test
```

### Testes Manuais (QA)

1. Criar conta nova
2. Criar categorias
3. Criar contas bancárias
4. Criar transações (income/expense)
5. Importar OFX/CSV
6. Verificar dashboard atualizado
7. Testar multi-tenant (criar workspace)

---

## 🚀 Deploy Automático (CI/CD)

### Como Funciona

**O deploy é 100% automático ao fazer push para `main`:**

```bash
# 1. Faça suas mudanças localmente
git add .
git commit -m "feat: nova funcionalidade"

# 2. Push para main
git push origin main

# 3. CI/CD faz automaticamente:
#    - ✅ Roda testes
#    - ✅ Build backend Docker image
#    - ✅ Build frontend (npm run build)
#    - ✅ Deploy no servidor de produção
#    - ✅ Smoke tests
#    - ✅ Notifica sucesso/erro
```

### Workflow CI/CD

**Arquivo**: `.github/workflows/deploy-production.yml`

**Etapas**:
1. **CI**: Testes unitários + linting + build
2. **Deploy Backend**: Build Docker image → SCP para servidor → docker compose up
3. **Deploy Frontend**: Build no servidor → Nginx serve arquivos estáticos
4. **Smoke Tests**: Testa login, dashboard, transações

### Monitorar Deploy

```bash
# Via GitHub Actions
https://github.com/Lezinrew/alca-financas/actions

# Via SSH no servidor
ssh user@servidor
cd /var/www/alca-financas
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### Rollback Rápido

Se algo der errado após deploy:

```bash
# No servidor
cd /var/www/alca-financas
git log --oneline -5  # Ver últimos commits
git reset --hard <commit-anterior>
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

---

## 🛠️ Deploy Manual

### Quando Usar

- Hotfix urgente
- Deploy de teste antes do CI/CD
- Servidor sem acesso ao GitHub Actions

### Script Automatizado

```bash
# No seu computador local
./scripts/deploy.sh production
```

### Passo a Passo Manual

```bash
# 1. SSH no servidor
ssh user@servidor

# 2. Navegar para o diretório
cd /var/www/alca-financas

# 3. Pull últimas mudanças
git fetch origin
git reset --hard origin/main

# 4. Rebuild e restart backend
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend

# 5. Build frontend
rm -rf frontend/dist build/frontend
mkdir -p build/frontend
docker run --rm \
  -v $(pwd)/frontend:/app \
  -w /app \
  node:22-alpine \
  sh -c "npm ci && npm run build"
cp -a frontend/dist/. build/frontend/

# 6. Restart frontend
docker compose -f docker-compose.prod.yml up -d --force-recreate frontend

# 7. Verificar status
docker compose -f docker-compose.prod.yml ps
curl -I http://localhost:3000
curl http://localhost:8001/health
```

---

## 🔍 Troubleshooting

### Backend não inicia

```bash
# Ver logs
docker compose logs backend

# Problemas comuns:
# 1. .env faltando ou incompleto
# 2. Supabase credenciais inválidas
# 3. Porta 8001 já em uso

# Solução:
docker compose down
# Verificar .env
docker compose up -d backend
docker compose logs -f backend
```

### Frontend retorna 404

```bash
# Verificar se build existe
ls -la build/frontend/

# Rebuild frontend
rm -rf build/frontend frontend/dist
mkdir -p build/frontend
cd frontend && npm run build
cp -a dist/. ../build/frontend/
docker compose -f docker-compose.prod.yml restart frontend
```

### CI/CD falha

```bash
# 1. Verificar GitHub Actions logs
https://github.com/Lezinrew/alca-financas/actions

# 2. Problemas comuns:
# - Testes falhando: Rodar localmente `pytest` e `npm test`
# - Secrets faltando: Verificar GitHub Settings → Secrets
# - Servidor inacessível: Verificar SSH keys e firewall

# 3. Re-run workflow manualmente:
# GitHub Actions → Deploy to Production → Re-run all jobs
```

### Import OFX/CSV não funciona

```bash
# Verificar logs do backend
docker compose logs backend | grep -i "import\|ofx\|csv"

# Testar manualmente:
curl -X POST http://localhost:8001/api/transactions/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.ofx"
```

### Dashboard mostra dados errados

```bash
# Verificar se backend está usando Supabase correto
docker compose exec backend env | grep SUPABASE

# Verificar logs do report_service
docker compose logs backend | grep "report_service\|dashboard"

# Validar que apenas paid transactions são contadas
# (Ver Phase 1.3 do MEMORY.md)
```

---

## 📚 Referências

- **CI/CD**: `.github/workflows/deploy-production.yml`
- **Docker Compose**: `docker-compose.yml` (dev), `docker-compose.prod.yml` (prod)
- **Knowledge Base**: `memory/MEMORY.md`
- **Scripts**: `scripts/deploy.sh`, `scripts/local-dev.sh`

---

## 🆘 Suporte

**Issues**: https://github.com/Lezinrew/alca-financas/issues
**Docs**: Este arquivo (DEPLOY.md)
**Logs**: `docker compose logs -f`
