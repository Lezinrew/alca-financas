# 🧪 Estrutura de Testes e Automação - Alça Finanças

Documentação completa da infraestrutura de testes e automação do projeto Alça Finanças.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Tipos de Testes](#tipos-de-testes)
- [Configuração de Ambiente](#configuração-de-ambiente)
- [Executando Testes](#executando-testes)
- [CI/CD Pipeline](#cicd-pipeline)
- [Scripts de Deploy](#scripts-de-deploy)
- [Boas Práticas](#boas-práticas)

---

## 🎯 Visão Geral

O projeto possui uma estrutura completa de testes automatizados que cobre:

- **Testes Unitários** (Backend e Frontend)
- **Testes de Integração** (API)
- **Testes E2E** (Fluxos completos)
- **Testes de Segurança** (Vulnerabilidades)
- **Smoke Tests** (Produção)

### 📊 Cobertura de Testes

| Tipo | Tecnologia | Cobertura Mínima |
|------|-----------|------------------|
| Backend Unit | pytest | 70% |
| Frontend Unit | Vitest | 70% |
| Integration | pytest | 60% |
| E2E | Playwright | Principais fluxos |

---

## 🧩 Tipos de Testes

### 1️⃣ Testes Unitários - Backend

**Localização:** `backend/tests/unit/`

**Framework:** pytest

**Executar:**
```bash
cd backend
pytest tests/unit -v --cov=. --cov-report=html
```

**Exemplos:**
- `test_auth_utils.py` - Autenticação e JWT
- `test_transaction_service.py` - Lógica de transações
- `test_validators.py` - Validações de dados

### 2️⃣ Testes de Integração - Backend

**Localização:** `backend/tests/integration/`

**Framework:** pytest + MongoDB test

**Executar:**
```bash
cd backend
pytest tests/integration -v --cov=. --cov-report=html
```

**Exemplos:**
- `test_auth_api.py` - Endpoints de autenticação
- `test_transactions_api.py` - CRUD de transações
- `test_categories_api.py` - Gestão de categorias

### 3️⃣ Testes Unitários - Frontend

**Localização:** `frontend/src/__tests__/`

**Framework:** Vitest + Testing Library

**Executar:**
```bash
cd frontend
npm run test:run -- --coverage
```

**Exemplos:**
- `components/Dashboard.test.tsx` - Componente Dashboard
- `utils/api.test.ts` - Cliente API
- `contexts/AuthContext.test.tsx` - Context de autenticação

### 4️⃣ Testes E2E - Frontend

**Localização:** `frontend/e2e/`

**Framework:** Playwright

**Executar:**
```bash
cd frontend
npx playwright test
```

**Suites:**
- `auth.spec.ts` - Fluxo de autenticação
- `dashboard.spec.ts` - Navegação no dashboard
- `transactions.spec.ts` - Gestão de transações

**Browsers testados:**
- Chromium (Desktop)
- Firefox (Desktop)
- WebKit/Safari (Desktop)
- Chrome Mobile
- Safari Mobile

---

## ⚙️ Configuração de Ambiente

### Variáveis de Ambiente

O projeto usa diferentes configurações para cada ambiente:

**Local (.env):**
```bash
NODE_ENV=local
LOCAL_API_URL=http://localhost:5000
LOCAL_WEB_URL=http://localhost:3000
MONGO_URL=mongodb://localhost:27017/alca_financas
```

**Produção (.env):**
```bash
NODE_ENV=production
PROD_API_URL=https://api.alcahub.com.br
PROD_WEB_URL=https://alcahub.com.br
PROD_MONGO_URL=mongodb+srv://...
```

**Testes (.env.test):**
```bash
NODE_ENV=test
MONGO_URL=mongodb://localhost:27017/alca_financas_test
JWT_SECRET=test-secret-key
```

### Configuração Inicial

1. **Clone e configure:**
```bash
git clone <repo>
cd alca-financas
cp .env.example .env
# Edite .env com suas configurações
```

2. **Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. **Frontend:**
```bash
cd frontend
npm install
npx playwright install --with-deps
```

---

## 🚀 Executando Testes

### Scripts Automatizados

#### Todos os testes (local):
```bash
./scripts/run-tests.sh all local
```

#### Apenas testes unitários:
```bash
./scripts/run-tests.sh unit local
```

#### Apenas testes de integração:
```bash
./scripts/run-tests.sh integration local
```

#### Apenas testes E2E:
```bash
./scripts/run-tests.sh e2e local
```

#### Testes E2E em produção:
```bash
./scripts/run-tests.sh e2e production
```

### Execução Manual

#### Backend - Testes Unitários:
```bash
cd backend
source venv/bin/activate
pytest tests/unit -v
```

#### Backend - Testes de Integração:
```bash
cd backend
source venv/bin/activate
pytest tests/integration -v
```

#### Backend - Com Cobertura:
```bash
pytest tests/ -v --cov=. --cov-report=html
# Abra: backend/htmlcov/index.html
```

#### Frontend - Testes Unitários:
```bash
cd frontend
npm run test:run
```

#### Frontend - Modo Watch:
```bash
npm run test
```

#### Frontend - Com Cobertura:
```bash
npm run test:run -- --coverage
# Abra: frontend/coverage/index.html
```

#### E2E - Todos os Browsers:
```bash
cd frontend
npx playwright test
```

#### E2E - Apenas Chrome:
```bash
npx playwright test --project=chromium
```

#### E2E - Com UI:
```bash
npx playwright test --ui
```

#### E2E - Debug:
```bash
npx playwright test --debug
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions

O projeto possui 2 workflows principais:

#### 1. CI Pipeline (`.github/workflows/ci.yml`)

**Trigger:** Push e PR para `main` e `develop`

**Jobs:**
1. **Backend Tests**
   - Lint (black, flake8, pylint)
   - Security (bandit, safety)
   - Unit tests
   - Integration tests
   - Upload coverage

2. **Frontend Tests**
   - ESLint
   - Unit tests
   - Build
   - Upload coverage

3. **E2E Tests**
   - Playwright (todos browsers)
   - Upload relatórios

4. **Docker Build**
   - Build backend image
   - Build frontend image

5. **Security Scan**
   - Trivy vulnerability scan

#### 2. Deploy Pipeline (`.github/workflows/deploy-production.yml`)

**Trigger:** Push para `main` ou manual

**Jobs:**
1. **Test** - Executa CI completo
2. **Deploy Backend**
   - Build Docker image
   - Push para registry
   - Deploy no servidor
3. **Deploy Frontend**
   - Build production
   - Deploy via SCP
   - Reload Nginx
4. **Smoke Tests**
   - Testes básicos em produção
   - Notificação em caso de falha

### Secrets Necessários

Configure no GitHub:
- `DOCKER_REGISTRY` - URL do registry
- `DOCKER_USERNAME` - Usuário Docker
- `DOCKER_PASSWORD` - Senha Docker
- `PROD_HOST` - Servidor de produção
- `PROD_USER` - Usuário SSH
- `PROD_SSH_KEY` - Chave SSH privada
- `TELEGRAM_CHAT_ID` - ID do chat (notificações)
- `TELEGRAM_BOT_TOKEN` - Token do bot

---

## 📦 Scripts de Deploy

### Deploy Local

Inicia ambiente de desenvolvimento completo:

```bash
./scripts/deploy-local.sh
```

**O que faz:**
- ✅ Verifica Docker
- ✅ Cria .env se não existir
- ✅ Inicia MongoDB
- ✅ Configura venv Python
- ✅ Instala dependências
- ✅ Inicia Backend (porta 5000)
- ✅ Inicia Frontend (porta 3000)

**URLs:**
- Frontend: http://localhost:3000
- Backend: http://localhost:5000
- MongoDB: mongodb://localhost:27017

### Parar Serviços

```bash
./scripts/stop-local.sh
```

### Deploy Produção

Deploy completo para alcahub.com.br:

```bash
./scripts/deploy-production.sh
```

**O que faz:**
1. ✅ Roda todos os testes
2. ✅ Build Docker images
3. ✅ Build frontend
4. ✅ Cria backup
5. ✅ Deploy backend via Docker
6. ✅ Deploy frontend via rsync
7. ✅ Restart Nginx
8. ✅ Health checks
9. ✅ Smoke tests

### Backup

Cria backup do banco e arquivos:

```bash
./scripts/backup.sh
```

**Backup inclui:**
- 🗄️ MongoDB dump
- 📁 Arquivos uploaded
- 🗜️ Compactação tar.gz
- 🧹 Rotação (mantém 7 dias)

---

## 🎯 Boas Práticas

### Escrevendo Testes

#### 1. Nomenclatura
```python
# Backend
def test_user_can_login_with_valid_credentials():
    ...

def test_transaction_creation_fails_without_category():
    ...
```

```typescript
// Frontend
describe('Dashboard Component', () => {
  it('should display KPI cards', () => {
    ...
  })

  it('should show error when API fails', () => {
    ...
  })
})
```

#### 2. Arrange-Act-Assert
```python
def test_create_transaction():
    # Arrange
    user = create_test_user()
    category = create_test_category(user)

    # Act
    transaction = create_transaction(user, category, amount=100)

    # Assert
    assert transaction.amount == 100
    assert transaction.category_id == category.id
```

#### 3. Use Fixtures
```python
@pytest.fixture
def auth_token(test_user):
    return generate_jwt_token(test_user)

def test_protected_endpoint(client, auth_token):
    response = client.get('/api/me', headers={'Authorization': f'Bearer {auth_token}'})
    assert response.status_code == 200
```

#### 4. Mock External Services
```typescript
vi.mock('@/utils/api', () => ({
  api: {
    get: vi.fn(() => Promise.resolve({ data: mockData }))
  }
}))
```

### Cobertura de Testes

**Priorize testar:**
1. ✅ Lógica de negócio crítica
2. ✅ Fluxos de autenticação
3. ✅ Manipulação de dinheiro
4. ✅ Validações de dados
5. ✅ Casos de erro

**Não precisa testar:**
- ❌ Código de terceiros
- ❌ Configurações simples
- ❌ Arquivos de tipo (.d.ts)
- ❌ Mock data

### Testes E2E

**Organize por jornada do usuário:**
```typescript
test.describe('Transaction Management Journey', () => {
  test('user can create, edit and delete transaction', async ({ page }) => {
    // Login
    await loginAsUser(page)

    // Create
    await createTransaction(page, data)

    // Edit
    await editTransaction(page, newData)

    // Delete
    await deleteTransaction(page)
  })
})
```

**Use Page Objects:**
```typescript
class DashboardPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/dashboard')
  }

  async getBalance() {
    return this.page.locator('[data-testid="balance"]').textContent()
  }
}
```

---

## 📊 Monitoramento

### Relatórios de Cobertura

Após executar os testes, verifique os relatórios:

**Backend:**
```bash
open backend/htmlcov/index.html
```

**Frontend:**
```bash
open frontend/coverage/index.html
```

**Playwright:**
```bash
open frontend/playwright-report/index.html
```

### Logs

**Local:**
```bash
# Backend
tail -f logs/backend.log

# Frontend
tail -f logs/frontend.log
```

**Produção:**
```bash
ssh user@alcahub.com.br
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

## 🔧 Troubleshooting

### Testes falhando localmente

1. **MongoDB não está rodando:**
```bash
docker-compose up -d mongo
```

2. **Dependências desatualizadas:**
```bash
# Backend
pip install -r requirements-dev.txt

# Frontend
npm install
```

3. **Playwright não instalado:**
```bash
npx playwright install --with-deps
```

### Testes E2E falhando

1. **Servidor não está rodando:**
```bash
./scripts/deploy-local.sh
```

2. **Timeout issues:**
Aumente timeout no `playwright.config.ts`:
```typescript
timeout: 60 * 1000
```

3. **Headless issues:**
Execute com UI para debug:
```bash
npx playwright test --headed
```

### CI/CD falhando

1. **Secrets não configurados:**
Verifique GitHub Settings → Secrets

2. **Docker build falhando:**
Teste localmente:
```bash
docker build -t test ./backend
docker build -t test ./frontend
```

---

## 📚 Recursos Adicionais

- [Pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [GitHub Actions](https://docs.github.com/actions)

---

**Desenvolvido com ❤️ pela equipe Alça Finanças**
