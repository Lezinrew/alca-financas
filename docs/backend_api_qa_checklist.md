### Checklist de QA – Backend API (Mobills Pro)

Use este checklist para validar os endpoints principais após mudanças/refatorações.

Pré-requisitos
- Backend em execução em `http://localhost:5000`.
- Variável `TOKEN` obtida via login/registro (JWT Bearer).

Como obter TOKEN
```bash
curl -s -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Tester","email":"tester@example.com","password":"secret123"}' | jq -r .token

# ou (se já existir usuário)
curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tester@example.com","password":"secret123"}' | jq -r .token

# exporte o token
export TOKEN="<cole_o_token_aqui>"
```

Saúde da API
```bash
curl -i http://localhost:5000/api/health
# Esperado: 200 OK {"status":"ok"}
```

Autenticação (/api/auth)
```bash
# Registro
curl -i -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"User QA","email":"qa@example.com","password":"secret123"}'

# Login
curl -i -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@example.com","password":"secret123"}'

# Me
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/auth/me

# Settings (GET)
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/auth/settings

# Settings (PUT)
curl -i -X PUT http://localhost:5000/api/auth/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"language":"pt","theme":"light"}'
```

Categorias (/api/categories)
```bash
# Listar
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/categories

# Criar
curl -i -X POST http://localhost:5000/api/categories \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Lazer","type":"expense","color":"#AA00FF","icon":"balloon"}'

# Atualizar
curl -i -X PUT http://localhost:5000/api/categories/<category_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Lazer & Jogos"}'

# Deletar
curl -i -X DELETE http://localhost:5000/api/categories/<category_id> \
  -H "Authorization: Bearer $TOKEN"
```

Contas (/api/accounts)
```bash
# Listar
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/accounts

# Criar
curl -i -X POST http://localhost:5000/api/accounts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Carteira","type":"wallet","initial_balance":100.0}'

# Atualizar
curl -i -X PUT http://localhost:5000/api/accounts/<account_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"color":"#009688"}'

# Deletar
curl -i -X DELETE http://localhost:5000/api/accounts/<account_id> \
  -H "Authorization: Bearer $TOKEN"
```

Transações (/api/transactions)
```bash
# Listar (filtros opcionais: month, year, category_id, type)
curl -i -H "Authorization: Bearer $TOKEN" 'http://localhost:5000/api/transactions?month=1&year=2025'

# Criar simples
curl -i -X POST http://localhost:5000/api/transactions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Almoço","amount":35.5,"type":"expense","category_id":"<category_id>","date":"2025-01-10T12:00:00Z"}'

# Criar parcelada (3x)
curl -i -X POST http://localhost:5000/api/transactions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Notebook","amount":4500,"type":"expense","category_id":"<category_id>","date":"2025-01-10T12:00:00Z","installments":3}'

# Atualizar
curl -i -X PUT http://localhost:5000/api/transactions/<transaction_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"description":"Almoço com equipe"}'

# Deletar
curl -i -X DELETE http://localhost:5000/api/transactions/<transaction_id> \
  -H "Authorization: Bearer $TOKEN"
```

Dashboard (/api/dashboard)
```bash
curl -i -H "Authorization: Bearer $TOKEN" 'http://localhost:5000/api/dashboard?month=1&year=2025'

# Dashboard avançado (opcional)
curl -i -H "Authorization: Bearer $TOKEN" 'http://localhost:5000/api/dashboard-advanced?month=1&year=2025'

# Configurações do dashboard
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/dashboard-settings
curl -i -X PUT http://localhost:5000/api/dashboard-settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"show_accounts_summary":true}'
```

Relatórios (/api/reports)
```bash
# Overview (expenses_by_category | income_by_category | expenses_by_account | income_by_account | balance_by_account)
curl -i -H "Authorization: Bearer $TOKEN" 'http://localhost:5000/api/reports/overview?month=1&year=2025&type=expenses_by_category'

# Comparison
curl -i -H "Authorization: Bearer $TOKEN" 'http://localhost:5000/api/reports/comparison?current_month=1&current_year=2025'
```

Importação CSV (opcional)
```bash
curl -i -X POST http://localhost:5000/api/transactions/import \
  -H "Authorization: Bearer $TOKEN" \
  -F file=@/caminho/para/arquivo.csv
```

Observações
- Substitua `<category_id>`, `<account_id>` e `<transaction_id>` por ids válidos.
- Em produção, ajuste `VITE_API_URL`/CORS conforme o ambiente.

