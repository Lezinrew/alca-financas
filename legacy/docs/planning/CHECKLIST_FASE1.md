# ✅ Checklist - FASE 1 (Correções Críticas)

Marque conforme completa cada item.

---

## 📋 PRÉ-REQUISITOS

- [ ] Tenho acesso ao Supabase Dashboard
- [ ] Tenho acesso ao repositório Git
- [ ] Tenho 3.5 horas disponíveis
- [ ] Fiz backup local do código (`git commit` atual)

---

## 🔴 TASK 1.1: Corrigir RLS (1 hora)

### Preparação
- [ ] Criei branch `security-hotfix-critical`
- [ ] Verifiquei que arquivo `002_fix_rls_policies.sql` existe

### Backup
- [ ] Abri Supabase Dashboard
- [ ] Database → Backups → Create backup
- [ ] Backup criado com sucesso ✅

### Migration
- [ ] Abri SQL Editor no Supabase
- [ ] Copiei conteúdo de `002_fix_rls_policies.sql`
- [ ] Colei no SQL Editor
- [ ] Cliquei RUN
- [ ] Migration executada sem erros ✅

### Validação
- [ ] Executei query de validação (ver policies)
- [ ] Listou ~16 policies
- [ ] Nenhuma policy tem `USING (true)` ✅

### Teste
- [ ] Executei script de teste RLS
- [ ] Teste passou ✅

### Documentação
- [ ] Atualizei `backend/README_SUPABASE.md`

**✅ TASK 1.1 COMPLETA**

---

## 🔴 TASK 1.2: Corrigir OAuth (1 hora)

### Preparação
- [ ] Fiz backup: `cp backend/routes/auth.py backend/routes/auth.py.backup`

### Correção 1: Remover Fallback
- [ ] Abri `backend/routes/auth.py`
- [ ] Encontrei linha ~334 (`except MismatchingStateError:`)
- [ ] DELETEI linhas 334-364 (bloco completo)
- [ ] COLEI novo código (do guia)
- [ ] Salvei arquivo ✅

### Correção 2: Verificar Assinatura
- [ ] Encontrei linha ~384 (`jwt.decode(..., verify_signature: False)`)
- [ ] DELETEI essa linha
- [ ] COLEI novo código (do guia)
- [ ] Salvei arquivo ✅

### Correção 3: Validar Issuer
- [ ] Após `parse_id_token`, ADICIONEI validação de issuer
- [ ] Salvei arquivo ✅

### Teste
- [ ] Iniciei backend: `python backend/app.py`
- [ ] Testei login via Google
- [ ] Login funcionou ✅
- [ ] (Opcional) Testei state mismatch - retornou erro ✅

**✅ TASK 1.2 COMPLETA**

---

## 🔴 TASK 1.3: Forçar Secrets (30 min)

### Gerar Secrets
- [ ] Executei: `openssl rand -hex 32` (SECRET_KEY)
- [ ] Copiei o valor gerado
- [ ] Executei novamente: `openssl rand -hex 32` (JWT_SECRET)
- [ ] Copiei o segundo valor ✅

### Atualizar Código - app.py
- [ ] Abri `backend/app.py`
- [ ] Encontrei linha 43 (`app.secret_key = ...`)
- [ ] SUBSTITUÍ por novo código (do guia)
- [ ] Salvei arquivo ✅

### Atualizar Código - auth_utils.py
- [ ] Abri `backend/utils/auth_utils.py`
- [ ] Encontrei linha 9 (`JWT_SECRET = ...`)
- [ ] SUBSTITUÍ por novo código (do guia)
- [ ] Salvei arquivo ✅

### Configurar .env
- [ ] Abri `.env`
- [ ] ADICIONEI/ATUALIZEI:
  ```
  SECRET_KEY=<valor1_gerado>
  JWT_SECRET=<valor2_gerado>
  ```
- [ ] Salvei arquivo ✅

### Teste
- [ ] Removi `.env` temporariamente
- [ ] Tentei iniciar backend - FALHOU com erro ✅
- [ ] Restaurei `.env`
- [ ] Iniciei backend - FUNCIONOU ✅

**✅ TASK 1.3 COMPLETA**

---

## ✅ VALIDAÇÃO FINAL

- [ ] Backend inicia sem erros
- [ ] Frontend conecta ao backend
- [ ] Login tradicional funciona
- [ ] Login Google funciona (se configurado)
- [ ] Transações são exibidas corretamente
- [ ] Usuários não veem dados de outros usuários

**✅ TODAS AS VALIDAÇÕES PASSARAM**

---

## 🚀 COMMIT E DEPLOY

### Commit
- [ ] Executei: `git add .`
- [ ] Executei: `git status` (revisei mudanças)
- [ ] Executei commit:
  ```bash
  git commit -m "security: CRITICAL fixes - RLS, OAuth, Secrets

  - Fix RLS policies (migration 002) - isolamento de dados
  - Remove OAuth Google insecure fallback
  - Remove JWT decode without signature verification
  - Enforce strong secrets (min 32 chars)

  BREAKING: Requires SECRET_KEY and JWT_SECRET in .env
  Fixes: Vulnerabilities #1, #2, #3 (CRITICAL)"
  ```
- [ ] Commit criado ✅

### Push
- [ ] Executei: `git push origin security-hotfix-critical`
- [ ] Push bem-sucedido ✅

### Pull Request
- [ ] Criei PR no GitHub/GitLab
- [ ] Título: "🔒 SECURITY HOTFIX: Critical vulnerabilities (RLS, OAuth, Secrets)"
- [ ] Descrição: Linkar para `SECURITY_AUDIT_REPORT.md`
- [ ] PR criado ✅

### Deploy (se aplicável)
- [ ] Gerei secrets de produção (diferentes de dev!)
- [ ] Configurei secrets no servidor/hosting
- [ ] Executei migration RLS no Supabase de produção
- [ ] Fiz deploy do código
- [ ] Verifiquei logs - backend iniciou corretamente
- [ ] Testei funcionalidades principais
- [ ] **Deploy em produção concluído** ✅

---

## 🎉 FASE 1 COMPLETA!

**Tempo gasto:** _____ horas (meta: 3.5h)

**Status do sistema:**
- Antes: 🔴 VULNERÁVEL (3 críticas)
- Depois: ✅ SEGURO

**Próximos passos:**
1. ✅ Descanse, você merece!
2. 🟠 FASE 2 (esta semana) - Rate limiting, audit logs
3. 📊 Monitorar logs de segurança
4. 🔄 Agendar revisão de segurança mensal

---

**Data de conclusão:** ____________
**Responsável:** ____________
**Revisado por:** ____________

**Assinatura:** Sistema agora está SEGURO para produção ✅
