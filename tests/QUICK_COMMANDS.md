# ⚡ COMANDOS RÁPIDOS - QA

Cheat sheet de comandos úteis para QA do Alca Finanças.

## 🎯 EXECUÇÃO RÁPIDA

```bash
# Teste completo em 1 comando
cd ~/Projetos/alca-financas
./tests/scripts/quick-test.sh

# Teste Python completo
python3 tests/scripts/full-test.py

# Performance test
k6 run tests/performance/load-test.js
```

---

## 🔍 TESTES MANUAIS (CURL)

### Auth

```bash
API="http://localhost:8001/api"

# Registro
curl -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","password":"senha123","name":"Teste"}'

# Login
curl -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","password":"senha123"}'

# Salvar token
TOKEN="seu_token_aqui"

# Get Me
curl -X GET "$API/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

### Accounts

```bash
# Listar contas
curl -X GET "$API/accounts" \
  -H "Authorization: Bearer $TOKEN"

# Criar conta
curl -X POST "$API/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Conta Corrente",
    "type":"checking",
    "initial_balance":1000.00,
    "currency":"BRL"
  }'

# Atualizar conta
curl -X PUT "$API/accounts/ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Conta Atualizada"}'

# Deletar conta
curl -X DELETE "$API/accounts/ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### Categories

```bash
# Listar categorias
curl -X GET "$API/categories" \
  -H "Authorization: Bearer $TOKEN"

# Criar categoria
curl -X POST "$API/categories" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Alimentação",
    "type":"expense",
    "color":"#6366f1",
    "icon":"utensils"
  }'
```

### Transactions

```bash
# Listar transações
curl -X GET "$API/transactions?page=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Filtrar por mês
curl -X GET "$API/transactions?month=3&year=2024" \
  -H "Authorization: Bearer $TOKEN"

# Criar transação
curl -X POST "$API/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description":"Almoço",
    "amount":35.50,
    "type":"expense",
    "category_id":"CATEGORY_ID",
    "account_id":"ACCOUNT_ID",
    "date":"2024-03-04",
    "status":"paid"
  }'
```

### Dashboard

```bash
# Dashboard básico
curl -X GET "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN"

# Dashboard específico
curl -X GET "$API/dashboard?month=3&year=2024" \
  -H "Authorization: Bearer $TOKEN"

# Dashboard avançado
curl -X GET "$API/dashboard-advanced" \
  -H "Authorization: Bearer $TOKEN"
```

### Reports

```bash
# Despesas por categoria
curl -X GET "$API/reports/overview?type=expenses_by_category" \
  -H "Authorization: Bearer $TOKEN"

# Receitas por categoria
curl -X GET "$API/reports/overview?type=income_by_category" \
  -H "Authorization: Bearer $TOKEN"

# Comparação de períodos
curl -X GET "$API/reports/comparison" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔐 TESTES DE SEGURANÇA

```bash
# Tentar acesso sem token (deve retornar 401)
curl -X GET "$API/accounts"

# Token inválido (deve retornar 401)
curl -X GET "$API/accounts" \
  -H "Authorization: Bearer invalid_token"

# SQL Injection (deve ser sanitizado)
curl -X POST "$API/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description":"'\'' OR '\''1'\''='\''1",
    "amount":10.00,
    "type":"expense",
    "date":"2024-03-04"
  }'

# XSS (deve ser sanitizado)
curl -X POST "$API/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description":"<script>alert(1)</script>",
    "amount":10.00,
    "type":"expense",
    "date":"2024-03-04"
  }'
```

---

## 📊 PERFORMANCE TESTS

```bash
# Quick load test (10 users, 30s)
k6 run --vus 10 --duration 30s tests/performance/load-test.js

# Medium load test (50 users, 2min)
k6 run --vus 50 --duration 2m tests/performance/load-test.js

# High load test (100 users, 5min)
k6 run --vus 100 --duration 5m tests/performance/load-test.js

# Stress test (ramp até falhar)
k6 run --vus 200 --duration 3m tests/performance/load-test.js

# Spike test (0 to 100 in 10s)
k6 run tests/performance/load-test.js --stage "10s:100,1m:100,10s:0"
```

---

## 🐛 DEBUG

```bash
# Ver logs do backend
tail -f backend/logs/app.log

# Ver requisições em tempo real
watch -n 1 "curl -s $API/health"

# Testar conectividade
nc -zv localhost 8001

# Ver portas em uso
lsof -i :8001

# Monitorar performance do servidor
htop

# Ver uso de memória
free -h  # Linux
vm_stat  # macOS

# Testar latência
time curl -X GET "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN"

# Fazer múltiplas requisições
for i in {1..100}; do
  curl -s -X GET "$API/dashboard" \
    -H "Authorization: Bearer $TOKEN" &
done
wait
```

---

## 🧪 PYTEST (TESTES BACKEND)

```bash
# Rodar todos os testes
cd backend
pytest -v

# Testes de integração
pytest tests/integration/ -v

# Testes de uma rota específica
pytest tests/integration/test_auth_api.py -v

# Com coverage
pytest --cov=. --cov-report=html

# Ver coverage
open htmlcov/index.html
```

---

## 📦 NEWMAN (POSTMAN CLI)

```bash
# Instalar Newman
npm install -g newman

# Rodar collection
newman run tests/postman/alca-financas.json

# Com environment
newman run tests/postman/alca-financas.json \
  -e tests/postman/environment.json

# Com relatório HTML
newman run tests/postman/alca-financas.json \
  -r html --reporter-html-export report.html
```

---

## 🔄 CI/CD CHECKS

```bash
# Simular CI localmente
cd ~/Projetos/alca-financas

# Backend checks
cd backend
python -m pip install -r requirements.txt
pytest tests/unit -v
black --check .
flake8 .

# Frontend checks
cd ../frontend
npm ci
npx tsc --noEmit
npm run test:run
npm run build

# Full CI simulation
cd ..
make ci
```

---

## 🚀 DEPLOY VALIDATION

```bash
# Smoke tests pós-deploy
API="https://alcahub.cloud/api"

# Health check
curl -f "$API/health" || echo "Health check FAILED"

# Auth check (criar usuário temporário)
TEMP_EMAIL="smoke-test-$(date +%s)@example.com"
curl -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEMP_EMAIL\",\"password\":\"senha123\",\"name\":\"Smoke Test\"}"

# Dashboard check
# (use token do registro acima)
curl -X GET "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📈 MONITORING

```bash
# Ver métricas em tempo real
watch -n 1 'curl -s "$API/health"'

# Contar requisições por segundo
while true; do
  date
  curl -s "$API/health" &
  sleep 0.1
done | uniq -c

# Load test rápido com Apache Bench
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  "$API/dashboard"

# Load test com wrk
wrk -t 12 -c 400 -d 30s \
  -H "Authorization: Bearer $TOKEN" \
  "$API/dashboard"
```

---

## 🎨 FORMATAÇÃO DE OUTPUT

```bash
# Pretty print JSON
curl -s "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# Extrair campo específico
curl -s "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN" | jq '.balance'

# Salvar response em arquivo
curl -s "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN" > dashboard.json

# Ver apenas HTTP status
curl -s -o /dev/null -w "%{http_code}\n" "$API/health"

# Ver headers e body
curl -i "$API/health"

# Ver tempo de resposta
curl -w "@-" -o /dev/null -s "$API/dashboard" \
  -H "Authorization: Bearer $TOKEN" <<'EOF'
  time_total: %{time_total}
  time_connect: %{time_connect}
  time_starttransfer: %{time_starttransfer}
EOF
```

---

## 💡 DICAS

### Salvar Token em Variável
```bash
# Registrar e extrair token automaticamente
RESPONSE=$(curl -s -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@example.com","password":"senha123","name":"Teste"}')

TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
echo "Token: $TOKEN"

# Agora pode usar $TOKEN em outros comandos
```

### Loop de Testes
```bash
# Testar endpoint 10 vezes
for i in {1..10}; do
  echo "Teste $i:"
  curl -s "$API/health" | jq '.status'
done

# Com delay
for i in {1..10}; do
  curl -s "$API/dashboard" -H "Authorization: Bearer $TOKEN"
  sleep 1
done
```

### Parallel Requests
```bash
# 10 requisições paralelas
for i in {1..10}; do
  curl -s "$API/health" &
done
wait
```

---

**Autor**: Claude Sonnet 4.5
**Última Atualização**: 2024-03-04
