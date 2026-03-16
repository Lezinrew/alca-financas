# 🧪 TESTES QA - ALCA FINANÇAS

Suíte completa de testes para validação da API do Alca Finanças.

## 📁 Estrutura

```
tests/
├── README.md                 # Este arquivo
├── scripts/
│   ├── quick-test.sh        # Teste rápido (bash/curl)
│   └── full-test.py         # Suite completa (Python)
├── postman/
│   └── alca-financas.json   # Postman Collection (a criar)
└── performance/
    └── load-test.js         # Teste de carga (k6)
```

---

## 🚀 QUICK START

### 1. Teste Rápido (Bash)

**Pré-requisitos**: curl, jq

```bash
# Tornar executável
chmod +x tests/scripts/quick-test.sh

# Executar (localhost)
./tests/scripts/quick-test.sh

# Executar (outro servidor)
./tests/scripts/quick-test.sh https://alcahub.cloud/api
```

**Saída esperada**:
```
🧪 ALCA FINANÇAS - QUICK API TEST
==================================
Testing Health Check... ✅ PASSED (HTTP 200)
Testing Register... ✅ PASSED
Testing Get /auth/me... ✅ PASSED (HTTP 200)
...
================================
📊 TEST SUMMARY
================================
Total Tests: 15
Passed: 15
Failed: 0

🎉 ALL TESTS PASSED!
```

---

### 2. Suite Completa (Python)

**Pré-requisitos**: Python 3.9+, requests

```bash
# Instalar dependências
pip3 install requests

# Tornar executável
chmod +x tests/scripts/full-test.py

# Executar (localhost)
python3 tests/scripts/full-test.py

# Executar (outro servidor)
python3 tests/scripts/full-test.py https://alcahub.cloud/api
```

**Saída esperada**:
```
==================================================
🧪 ALCA FINANÇAS - FULL API TEST SUITE
==================================================
API URL: http://localhost:8001/api

📝 AUTHENTICATION TESTS
  Testing: Register... ✅ PASSED (HTTP 201)
  Testing: Login... ✅ PASSED (HTTP 200)
  Testing: Get /auth/me... ✅ PASSED (HTTP 200)
  ...

🏷️  CATEGORIES TESTS
  Testing: List Categories... ✅ PASSED (HTTP 200)
  Testing: Create Category... ✅ PASSED (HTTP 201)
  ...

💳 ACCOUNTS TESTS
  Testing: List Accounts... ✅ PASSED (HTTP 200)
  ...

💸 TRANSACTIONS TESTS
  Testing: List Transactions... ✅ PASSED (HTTP 200)
  ...

📊 DASHBOARD TESTS
  Testing: Get Dashboard... ✅ PASSED (HTTP 200)
  ...

📈 REPORTS TESTS
  Testing: Expenses by Category... ✅ PASSED (HTTP 200)
  ...

💾 BACKUP TESTS
  Testing: Export Backup... ✅ PASSED (HTTP 200)

🔒 SECURITY TESTS
  Testing: No Token... ✅ PASSED (HTTP 401)
  Testing: Invalid Token... ✅ PASSED (HTTP 401)
  ...

🧹 CLEANUP
  Testing: Delete Transaction... ✅ PASSED (HTTP 200)
  Testing: Clear All Data... ✅ PASSED (HTTP 200)

==================================================
📊 TEST SUMMARY
==================================================
Total Tests: 45
✅ Passed: 45
❌ Failed: 0
⏱️  Duration: 12.34s
📈 Success Rate: 100.0%

🎉 ALL TESTS PASSED!
```

---

### 3. Teste de Performance (k6)

**Pré-requisitos**: k6 instalado

```bash
# Instalar k6 (macOS)
brew install k6

# Instalar k6 (Linux)
wget https://github.com/grafana/k6/releases/download/v0.46.0/k6-v0.46.0-linux-amd64.tar.gz
tar -xzf k6-v0.46.0-linux-amd64.tar.gz
sudo cp k6-v0.46.0-linux-amd64/k6 /usr/local/bin/

# Executar teste de carga
cd tests/performance
k6 run load-test.js

# Executar com configuração customizada
k6 run --vus 50 --duration 2m load-test.js

# Executar contra servidor externo
API_URL=https://alcahub.cloud/api k6 run load-test.js
```

**Saída esperada**:
```
🚀 Starting load test against http://localhost:8001/api
✅ Setup complete - test data created

          /\      |‾‾| /‾‾/   /‾‾/
     /\  /  \     |  |/  /   /  /
    /  \/    \    |     (   /   ‾‾\
   /          \   |  |\  \ |  (‾)  |
  / __________ \  |__| \__\ \_____/ .io

  execution: local
     script: load-test.js
     output: -

  scenarios: (100.00%) 1 scenario, 100 max VUs, 6m0s max duration
           * default: Up to 100 looping VUs for 5m30s over 6 stages

running (5m30.0s), 000/100 VUs, 15234 complete and 0 interrupted iterations
default ✓ [======================================] 000/100 VUs  5m30s

     ✓ dashboard status 200
     ✓ dashboard has balance
     ✓ transaction created
     ✓ transactions listed
     ✓ transactions has data
     ✓ report status 200
     ✓ report has data
     ✓ accounts listed
     ✓ categories listed

     checks.........................: 99.95% ✓ 137106      ✗ 68
     data_received..................: 45 MB  137 kB/s
     data_sent......................: 12 MB  36 kB/s
     http_req_duration..............: avg=145.23ms min=45ms   med=120ms   max=1.2s   p(95)=280ms p(99)=450ms
     http_req_failed................: 0.10%  ✓ 15          ✗ 15219
     http_reqs......................: 15234  46.3/s
     iteration_duration.............: avg=7.1s     min=5s     med=7s      max=12s
     iterations.....................: 15234  46.3/s
     vus............................: 1      min=1         max=100
     vus_max........................: 100    min=100       max=100

🧹 Cleaning up test data...
✅ Teardown complete

📊 LOAD TEST SUMMARY
====================
Duration: 330s
Requests: 15234
Failed Requests: 15
Avg Response Time: 145.23ms
P95 Response Time: 280.00ms
P99 Response Time: 450.00ms
```

---

## 📋 CHECKLIST DE EXECUÇÃO

### Antes de Rodar os Testes

- [ ] Backend está rodando (`python backend/app.py`)
- [ ] Database está acessível (Supabase)
- [ ] `.env` está configurado corretamente
- [ ] Portas não estão em conflito (8001 para backend)

### Ordem Recomendada

1. **Quick Test** - Validação rápida de funcionamento básico
2. **Full Test** - Validação completa de todos os endpoints
3. **Performance Test** - Validação de carga e performance

### Após os Testes

- [ ] Revisar relatório de falhas (se houver)
- [ ] Documentar bugs encontrados
- [ ] Criar issues no GitHub
- [ ] Atualizar documentação se necessário

---

## 🐛 REPORT DE BUGS

Quando encontrar um bug, documente usando o template:

```markdown
## BUG-XXX: Título do Bug

**Prioridade**: P0/P1/P2/P3
**Endpoint**: POST /api/xxx
**Status Esperado**: 200
**Status Recebido**: 500

### Passos para Reproduzir
1. Criar usuário
2. Fazer login
3. Chamar endpoint X

### Resultado Esperado
Retornar objeto Y

### Resultado Atual
Retornar erro Z

### Evidências
```json
{
  "error": "..."
}
```

### Logs do Backend
```
[ERROR] ...
```
```

---

## 🔧 TROUBLESHOOTING

### Erro: "Connection refused"
- Verifique se o backend está rodando
- Verifique se a porta 8001 está correta
- Use `netstat -an | grep 8001` para verificar

### Erro: "401 Unauthorized"
- Token pode estar expirado
- Verifique se SECRET_KEY está configurado
- Tente registrar novo usuário

### Erro: "Database connection failed"
- Verifique se Supabase está acessível
- Verifique SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env
- Teste conexão manual com `psql` ou Supabase Dashboard

### Testes falhando intermitentemente
- Pode ser issue de rate limiting
- Adicione sleep entre requests
- Reduza número de VUs no k6

---

## 📚 REFERÊNCIAS

- [Plano Completo de Testes](../docs/QA_TEST_PLAN.md)
- [Mapeamento de Endpoints](../docs/QA_TEST_PLAN.md#mapeamento-completo)
- [k6 Documentation](https://k6.io/docs/)
- [Postman Documentation](https://learning.postman.com/)

---

## 🤝 CONTRIBUINDO

Para adicionar novos testes:

1. Adicione o teste no script apropriado
2. Documente no QA_TEST_PLAN.md
3. Teste localmente
4. Crie PR com descrição do teste

---

**Autor**: Claude Sonnet 4.5
**Última Atualização**: 2024-03-04
