# 📋 PLANO COMPLETO DE TESTES QA - ALCA FINANÇAS

## 📊 Resumo Executivo

- **Endpoints Totais**: 60+
- **Módulos**: 8 (Auth, Accounts, Transactions, Categories, Dashboard, Reports, Admin, Tenants)
- **Tipos de Teste**: Funcionais, Integração, Segurança, Performance
- **Ferramentas**: Postman/Newman, Pytest, k6

---

## 🎯 ESTRATÉGIA DE TESTES

### Pirâmide de Testes

```
           ┌──────────────┐
          │   E2E Tests   │  10%
         └────────────────┘
       ┌──────────────────────┐
      │  Integration Tests   │  30%
     └────────────────────────┘
   ┌──────────────────────────────┐
  │      Unit Tests               │  60%
 └────────────────────────────────┘
```

### Níveis de Prioridade

**P0 - Crítico** (Bloqueador)
- Login/Registro
- Criação de transações
- Dashboard principal

**P1 - Alto** (Funcionalidade Core)
- CRUD de contas/categorias
- Importação de dados
- Relatórios

**P2 - Médio** (Funcionalidades secundárias)
- OAuth
- Admin panel
- Configurações

**P3 - Baixo** (Nice to have)
- Exportação CSV
- Logs de admin

---

## 🛠️ FERRAMENTAS RECOMENDADAS

### 1. Postman/Insomnia (Testes Manuais)
- Interface visual para testar endpoints
- Collections organizadas por módulo
- Environments (dev, staging, prod)

### 2. Newman (Testes Automatizados CLI)
```bash
npm install -g newman
newman run postman_collection.json -e environment.json
```

### 3. Pytest (Testes de Integração Python)
```bash
cd backend
pytest tests/integration/ -v
```

### 4. k6 (Testes de Performance)
```bash
k6 run performance-tests/load-test.js
```

### 5. OWASP ZAP (Testes de Segurança)
- Scan automatizado de vulnerabilidades
- Teste de autenticação

---

## 📝 CHECKLIST DE TESTES POR MÓDULO

### ✅ MÓDULO AUTH (20 testes)

#### Registro
- [ ] Registro com dados válidos (201)
- [ ] Registro com email duplicado (400)
- [ ] Registro sem senha (400)
- [ ] Registro com senha < 6 caracteres (400)
- [ ] Registro com email inválido (400)
- [ ] Verificar rate limit (3/hora) (429)

#### Login
- [ ] Login com credenciais válidas (200)
- [ ] Login com senha incorreta (401)
- [ ] Login com email inexistente (401)
- [ ] Login com conta Google (não permite senha) (400)
- [ ] Verificar rate limit (5/min) (429)

#### Refresh Token
- [ ] Refresh com token válido (200)
- [ ] Refresh com token expirado (401)
- [ ] Refresh com token inválido (401)
- [ ] Verificar rate limit (10/min) (429)

#### Recuperação de Senha
- [ ] Forgot password com email válido (200)
- [ ] Forgot password com email inexistente (200 - não revela)
- [ ] Reset password com token válido (200)
- [ ] Reset password com token expirado (400)
- [ ] Reset password com senha < 6 chars (400)

#### OAuth Google
- [ ] Iniciar fluxo OAuth (redirect para Google)
- [ ] Callback com código válido (200)
- [ ] Callback sem OAuth configurado (400)

---

### ✅ MÓDULO ACCOUNTS (15 testes)

#### Listar/Criar
- [ ] GET /api/accounts sem autenticação (401)
- [ ] GET /api/accounts com token válido (200)
- [ ] POST /api/accounts com dados válidos (201)
- [ ] POST /api/accounts sem nome (400)
- [ ] POST /api/accounts com tipo inválido (400)

#### Atualizar/Deletar
- [ ] GET /api/accounts/<id> com ID válido (200)
- [ ] GET /api/accounts/<id> com ID inexistente (404)
- [ ] PUT /api/accounts/<id> com dados válidos (200)
- [ ] DELETE /api/accounts/<id> com ID válido (200)
- [ ] DELETE /api/accounts/<id> de outro usuário (403)

#### Importação
- [ ] POST /api/accounts/<id>/import com OFX válido (201)
- [ ] POST /api/accounts/<id>/import com CSV válido (201)
- [ ] POST /api/accounts/<id>/import sem arquivo (400)
- [ ] POST /api/accounts/<id>/import com PDF (400 - não suportado)
- [ ] POST /api/accounts/<id>/import em conta não credit_card (400)

---

### ✅ MÓDULO TRANSACTIONS (20 testes)

#### Listar/Criar
- [ ] GET /api/transactions sem autenticação (401)
- [ ] GET /api/transactions com paginação (200)
- [ ] GET /api/transactions filtrando por mês/ano (200)
- [ ] GET /api/transactions filtrando por categoria (200)
- [ ] GET /api/transactions filtrando por tipo (200)
- [ ] POST /api/transactions com dados válidos (201)
- [ ] POST /api/transactions sem descrição (400)
- [ ] POST /api/transactions com amount negativo (400)
- [ ] POST /api/transactions com tipo inválido (400)

#### Atualizar/Deletar
- [ ] GET /api/transactions/<id> com ID válido (200)
- [ ] PUT /api/transactions/<id> com dados válidos (200)
- [ ] DELETE /api/transactions/<id> com ID válido (200)
- [ ] DELETE /api/transactions/<id> de outro usuário (403)

#### Importação
- [ ] POST /api/transactions/import com CSV válido (201)
- [ ] POST /api/transactions/import com OFX válido (201)
- [ ] POST /api/transactions/import sem arquivo (400)
- [ ] POST /api/transactions/import com formato inválido (400)

#### Paginação
- [ ] Verificar limite padrão (100)
- [ ] Verificar total de páginas
- [ ] Testar última página

---

### ✅ MÓDULO CATEGORIES (12 testes)

#### Listar/Criar
- [ ] GET /api/categories com token válido (200)
- [ ] POST /api/categories com dados válidos (201)
- [ ] POST /api/categories sem nome (400)
- [ ] POST /api/categories com nome duplicado (400)
- [ ] POST /api/categories com tipo inválido (400)

#### Atualizar/Deletar
- [ ] GET /api/categories/<id> com ID válido (200)
- [ ] PUT /api/categories/<id> com dados válidos (200)
- [ ] DELETE /api/categories/<id> com ID válido (200)

#### Importação
- [ ] POST /api/categories/import com JSON válido (200)
- [ ] POST /api/categories/import com CSV válido (200)
- [ ] POST /api/categories/import com JSON inválido (400)
- [ ] POST /api/categories/import sem arquivo (400)

---

### ✅ MÓDULO DASHBOARD (8 testes)

- [ ] GET /api/dashboard com token válido (200)
- [ ] GET /api/dashboard sem mês/ano (usa atual) (200)
- [ ] GET /api/dashboard com mês inválido (400)
- [ ] GET /api/dashboard-advanced (200)
- [ ] GET /api/dashboard-advanced com show_evolution=false (200)
- [ ] GET/PUT /api/dashboard-settings (200)
- [ ] PUT /api/dashboard-settings com dados válidos (200)
- [ ] Verificar cálculos de total_income/expense/balance

---

### ✅ MÓDULO REPORTS (10 testes)

- [ ] GET /api/reports/overview tipo=expenses_by_category (200)
- [ ] GET /api/reports/overview tipo=expenses_by_account (200)
- [ ] GET /api/reports/overview tipo=income_by_category (200)
- [ ] GET /api/reports/overview tipo=income_by_account (200)
- [ ] GET /api/reports/overview tipo=balance_by_account (200)
- [ ] GET /api/reports/overview com tipo inválido (400)
- [ ] GET /api/reports/overview com account_id válido (200)
- [ ] GET /api/reports/overview com account_id inexistente (404)
- [ ] GET /api/reports/comparison (200)
- [ ] GET /api/reports/evolution (200)

---

### ✅ MÓDULO ADMIN (18 testes)

#### Stats e Usuários
- [ ] GET /api/admin/stats como admin (200)
- [ ] GET /api/admin/stats como usuário comum (403)
- [ ] GET /api/admin/users com paginação (200)
- [ ] GET /api/admin/users com busca (200)
- [ ] GET /api/admin/users/<id>/details (200)

#### CRUD Usuários
- [ ] POST /api/admin/users com dados válidos (201)
- [ ] POST /api/admin/users com email duplicado (400)
- [ ] PUT /api/admin/users/<id> bloqueando usuário (200)
- [ ] PUT /api/admin/users/<id> promovendo a admin (200)
- [ ] DELETE /api/admin/users/<id> como admin (200)
- [ ] DELETE /api/admin/users/<id> (self) deve falhar (400)

#### Logs e Export
- [ ] GET /api/admin/logs (200)
- [ ] GET /api/admin/logs filtrando por action (200)
- [ ] GET /api/admin/logs filtrando por admin_id (200)
- [ ] GET /api/admin/users/<id>/export (200 CSV)

#### Autorização
- [ ] Verificar que usuário comum NÃO acessa admin (403)
- [ ] Verificar que sem token não acessa (401)
- [ ] Verificar logs de ações são criados

---

### ✅ MÓDULO TENANTS (6 testes)

- [ ] GET /api/tenants com token válido (200)
- [ ] POST /api/tenants/switch com tenant válido (200)
- [ ] POST /api/tenants/switch com tenant inválido (403)
- [ ] POST /api/tenants/switch sem tenant_id (400)
- [ ] Verificar isolamento de dados entre tenants
- [ ] Verificar que novo token contém tenant_id correto

---

### ✅ TESTES DE SEGURANÇA (15 testes)

#### Autenticação
- [ ] Acesso sem token (401)
- [ ] Acesso com token inválido (401)
- [ ] Acesso com token expirado (401)
- [ ] Verificar JWT signature

#### Autorização
- [ ] Usuário A não acessa dados de usuário B
- [ ] Usuário comum não acessa rotas /admin
- [ ] Verificar CORS headers
- [ ] Verificar rate limiting funciona

#### Injeção
- [ ] SQL Injection em campos text
- [ ] XSS em campos text (description, name)
- [ ] Path traversal em uploads

#### Dados Sensíveis
- [ ] Password não retorna em GET /api/auth/me
- [ ] Tokens não aparecem em logs
- [ ] Verificar HTTPS only cookies (produção)

#### OWASP Top 10
- [ ] A01 - Broken Access Control
- [ ] A02 - Cryptographic Failures

---

### ✅ TESTES DE PERFORMANCE (10 testes)

#### Carga
- [ ] 10 usuários simultâneos (GET /api/transactions)
- [ ] 50 usuários simultâneos (GET /api/dashboard)
- [ ] 100 usuários simultâneos (POST /api/auth/login)

#### Stress
- [ ] Aumentar usuários até falha
- [ ] Verificar recovery após stress

#### Spike
- [ ] Spike de 0 para 100 usuários em 10s

#### Soak (Durabilidade)
- [ ] Teste de 1 hora com carga constante

#### Limites
- [ ] Upload de arquivo grande (>10MB)
- [ ] Transação com descrição muito longa
- [ ] Query com paginação extrema (page=999999)

---

## 🧪 SCRIPTS DE TESTE PRONTOS

### Script 1: Teste Básico de Auth (curl)

```bash
#!/bin/bash
API_URL="http://localhost:8001/api"

# Registro
echo "==> Testando Registro"
REGISTER_RESP=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@example.com",
    "password": "senha123",
    "name": "Usuario Teste"
  }')
echo "$REGISTER_RESP"

# Extrair token
ACCESS_TOKEN=$(echo "$REGISTER_RESP" | jq -r '.access_token')

# Login
echo -e "\n==> Testando Login"
LOGIN_RESP=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@example.com",
    "password": "senha123"
  }')
echo "$LOGIN_RESP"

# Me
echo -e "\n==> Testando GET /auth/me"
ME_RESP=$(curl -s -X GET "$API_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$ME_RESP"
```

### Script 2: Teste de CRUD Completo (Python + Requests)

```python
#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8001/api"

# 1. Registrar
print("==> Registrando usuário")
register_data = {
    "email": "qa@example.com",
    "password": "senha123",
    "name": "QA Tester"
}
resp = requests.post(f"{BASE_URL}/auth/register", json=register_data)
assert resp.status_code == 201, f"Erro no registro: {resp.text}"
tokens = resp.json()
access_token = tokens['access_token']
headers = {"Authorization": f"Bearer {access_token}"}

# 2. Criar Categoria
print("==> Criando categoria")
category_data = {
    "name": "Alimentação",
    "type": "expense",
    "color": "#6366f1",
    "icon": "utensils"
}
resp = requests.post(f"{BASE_URL}/categories", json=category_data, headers=headers)
assert resp.status_code == 201
category_id = resp.json()['id']

# 3. Criar Conta
print("==> Criando conta")
account_data = {
    "name": "Conta Corrente",
    "type": "checking",
    "initial_balance": 1000.00,
    "currency": "BRL"
}
resp = requests.post(f"{BASE_URL}/accounts", json=account_data, headers=headers)
assert resp.status_code == 201
account_id = resp.json()['id']

# 4. Criar Transação
print("==> Criando transação")
transaction_data = {
    "description": "Almoço",
    "amount": 35.50,
    "type": "expense",
    "category_id": category_id,
    "account_id": account_id,
    "date": "2024-03-04",
    "status": "paid"
}
resp = requests.post(f"{BASE_URL}/transactions", json=transaction_data, headers=headers)
assert resp.status_code == 201
transaction_id = resp.json()['id'] if 'id' in resp.json() else None

# 5. Listar Transações
print("==> Listando transações")
resp = requests.get(f"{BASE_URL}/transactions", headers=headers)
assert resp.status_code == 200
transactions = resp.json()
print(f"Total de transações: {len(transactions['transactions'])}")

# 6. Dashboard
print("==> Verificando dashboard")
resp = requests.get(f"{BASE_URL}/dashboard", headers=headers)
assert resp.status_code == 200
dashboard = resp.json()
print(f"Total de gastos: {dashboard['total_expense']}")
print(f"Saldo: {dashboard['balance']}")

print("\n✅ Todos os testes passaram!")
```

### Script 3: Teste de Performance (k6)

```javascript
// performance-tests/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },  // Warm-up
    { duration: '1m', target: 50 },   // Carga normal
    { duration: '30s', target: 100 }, // Pico
    { duration: '1m', target: 50 },   // Volta ao normal
    { duration: '30s', target: 0 },   // Cool-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% das requests < 500ms
    http_req_failed: ['rate<0.01'],   // < 1% de falhas
  },
};

const BASE_URL = 'http://localhost:8001/api';

export function setup() {
  // Registrar usuário de teste
  const res = http.post(`${BASE_URL}/auth/register`, JSON.stringify({
    email: `qa-${Date.now()}@example.com`,
    password: 'senha123',
    name: 'K6 Tester'
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  return { token: res.json('access_token') };
}

export default function (data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Teste de leitura
  let res = http.get(`${BASE_URL}/dashboard`, { headers });
  check(res, {
    'dashboard status 200': (r) => r.status === 200,
    'dashboard response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);

  // Teste de escrita
  res = http.post(`${BASE_URL}/transactions`, JSON.stringify({
    description: 'Teste K6',
    amount: 10.00,
    type: 'expense',
    date: '2024-03-04',
  }), { headers });

  check(res, {
    'transaction created': (r) => r.status === 201,
  });

  sleep(1);
}
```

---

## 📊 TEMPLATES DE REPORT

### Template de Bug Report

```markdown
## Bug ID: BUG-001

### Título
[CRITICAL] Login falha com email válido

### Descrição
Ao tentar fazer login com credenciais válidas, o sistema retorna erro 500.

### Prioridade
P0 - Crítico

### Endpoint
POST /api/auth/login

### Passos para Reproduzir
1. Registrar usuário com email teste@example.com
2. Tentar fazer login com mesmo email e senha
3. Observar erro 500

### Resultado Esperado
Status 200 com access_token

### Resultado Atual
Status 500 com erro "Internal Server Error"

### Evidências
```json
{
  "error": "Internal Server Error",
  "message": "Database connection failed"
}
```

### Ambiente
- API: http://localhost:8001
- Browser: N/A (API)
- OS: macOS
- Data: 2024-03-04

### Log do Backend
```
[ERROR] Database connection timeout at auth.py:45
```
```

---

## 🚀 EXECUÇÃO DO PLANO

### Fase 1: Setup (Dia 1)
- [ ] Configurar ambiente de testes (dev/staging)
- [ ] Instalar ferramentas (Postman, Newman, k6)
- [ ] Criar collection no Postman
- [ ] Configurar CI/CD para testes automatizados

### Fase 2: Testes Funcionais (Dias 2-5)
- [ ] Executar checklist de Auth
- [ ] Executar checklist de Accounts
- [ ] Executar checklist de Transactions
- [ ] Executar checklist de Categories
- [ ] Executar checklist de Dashboard/Reports

### Fase 3: Testes de Segurança (Dia 6)
- [ ] Executar checklist de segurança
- [ ] Run OWASP ZAP scan
- [ ] Validar rate limiting

### Fase 4: Testes de Performance (Dia 7)
- [ ] Executar k6 load tests
- [ ] Executar stress tests
- [ ] Documentar bottlenecks

### Fase 5: Report (Dia 8)
- [ ] Compilar todos os bugs encontrados
- [ ] Priorizar bugs
- [ ] Criar tickets no GitHub Issues
- [ ] Apresentar relatório final

---

## 📈 MÉTRICAS DE SUCESSO

### Cobertura de Testes
- Target: 90%+ dos endpoints testados
- Atual: ____%

### Taxa de Bugs
- Critical (P0): 0
- High (P1): < 5
- Medium (P2): < 10
- Low (P3): < 20

### Performance
- 95% requests < 500ms ✅
- 99% requests < 1s ✅
- 0.1% error rate ✅

---

## 🔗 RECURSOS

- Postman Collection: `/tests/postman/alca-financas.json`
- Newman Scripts: `/tests/scripts/`
- k6 Tests: `/tests/performance/`
- Bug Reports: GitHub Issues

---

**Criado por**: Claude Sonnet 4.5
**Data**: 2024-03-04
**Versão**: 1.0
