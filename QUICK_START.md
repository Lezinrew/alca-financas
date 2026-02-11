# 🚀 Quick Start - Validação Pós-Correção

## ⚡ Teste Rápido (5 minutos)

### 1. Iniciar Backend
```bash
cd /Users/lezinrew/Projetos/alca-financas/backend
python3 app.py
```

**Esperado:** Servidor inicia na porta 8001

---

### 2. Executar Testes Automatizados
```bash
# Em outro terminal
cd /Users/lezinrew/Projetos/alca-financas/backend
./test_endpoints.sh seu_email@exemplo.com sua_senha
```

**Esperado:** Todos os testes marcados com ✅

---

### 3. Testar no Frontend
```bash
cd /Users/lezinrew/Projetos/alca-financas/frontend
npm run dev
```

Abrir: http://localhost:5173

**Checklist rápido:**
- [ ] Login funciona
- [ ] Dashboard carrega sem erros
- [ ] Relatórios aparecem (clicar em "Relatórios")
- [ ] Nenhum erro 500 no console do browser (F12)

---

## 🔍 Se algo falhar

### Erro: "Module not found"
```bash
cd backend
pip install -r requirements.txt
```

### Erro: "Port already in use"
```bash
# Matar processo na porta 8001
lsof -ti:8001 | xargs kill -9
```

### Erro: "Database connection failed"
Verificar variáveis de ambiente:
```bash
cat backend/.env | grep SUPABASE
```

### Erro: "aggregate() not found" (ainda aparecendo)
Verificar se código foi atualizado:
```bash
grep -n "overview_report_supabase" backend/routes/reports.py
```

---

## 📊 Endpoints Críticos para Testar

### 1. Health Check
```bash
curl http://localhost:8001/api/health
```
✅ Deve retornar: `{"status":"ok"}`

---

### 2. Login (obter token)
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"SEU_EMAIL","password":"SUA_SENHA"}'
```
✅ Deve retornar: `{"token":"...", "user":{...}}`

---

### 3. Relatório de Despesas por Categoria
```bash
# Substituir TOKEN
curl -X GET "http://localhost:8001/api/reports/overview?month=2&year=2026&type=expenses_by_category" \
  -H "Authorization: Bearer TOKEN"
```
✅ Deve retornar JSON com estrutura:
```json
{
  "period": {...},
  "report_type": "expenses_by_category",
  "data": [...],
  "total_amount": 0.0
}
```

---

### 4. Dashboard
```bash
curl -X GET "http://localhost:8001/api/dashboard?month=2&year=2026" \
  -H "Authorization: Bearer TOKEN"
```
✅ Deve retornar JSON com `summary`, `recent_transactions`, `expense_by_category`

---

## 🆘 Suporte Rápido

### Problema: Relatórios retornam erro 500
**Solução:** Verificar se funções foram adicionadas:
```bash
tail -n 50 backend/services/report_service.py | grep "def overview_report_supabase"
```
Deve mostrar a definição da função.

---

### Problema: Frontend mostra "Network Error"
**Solução:** Verificar se backend está rodando:
```bash
curl http://localhost:8001/api/health
```

---

### Problema: Dashboard carrega mas relatórios não
**Solução:** Verificar logs do backend:
```bash
# No terminal onde o backend está rodando, ver os erros
# OU verificar arquivo de log:
tail -f backend/logs/app.log
```

---

## 📋 Checklist Completo

### Pré-Deploy
- [ ] Backend inicia sem erros
- [ ] `./test_endpoints.sh` passa 100%
- [ ] Frontend carrega sem erros no console
- [ ] Login funciona
- [ ] Dashboard carrega
- [ ] Todos os tipos de relatório funcionam:
  - [ ] Despesas por categoria
  - [ ] Receitas por categoria
  - [ ] Despesas por conta
  - [ ] Receitas por conta
  - [ ] Saldo por conta
- [ ] Comparison report funciona
- [ ] Criar/editar/deletar transação funciona
- [ ] Importação de cartão funciona

### Pós-Deploy
- [ ] Health check responde em produção
- [ ] Login funciona em produção
- [ ] Relatórios funcionam em produção
- [ ] Sem erros 500 nos logs
- [ ] Performance aceitável (< 2s por requisição)

---

## 🎯 Resumo de 30 Segundos

**O que foi corrigido:**
- Relatórios estavam quebrando (erro 500)
- Causa: código MongoDB legado em sistema Supabase
- Solução: criadas funções Supabase nativas

**Como validar:**
```bash
cd backend
python3 app.py &
./test_endpoints.sh seu_email sua_senha
```

**Resultado esperado:**
Todos os testes com ✅

---

## 📚 Documentação Completa

- **Resumo Técnico:** `PATCH_SUMMARY.md`
- **Guia de Validação:** `MIGRACAO_VALIDACAO.md`
- **Este Guia:** `QUICK_START.md`

---

**Dúvidas?** Consulte MIGRACAO_VALIDACAO.md para troubleshooting detalhado.
