# Relatório de Auditoria de Segurança - Alca Finanças
**Data:** 2026-02-10
**Versão Analisada:** Main branch (commit 134a5191)

---

## Sumário Executivo

Esta auditoria identificou **11 vulnerabilidades** no sistema, sendo **3 CRÍTICAS**, **5 ALTAS**, **2 MÉDIAS** e **1 BAIXA**. As vulnerabilidades críticas envolvem:
- Row Level Security (RLS) ineficaz permitindo escalada de privilégio
- OAuth Google com bypass de verificação de segurança
- Exposição de secrets em ambiente de desenvolvimento

## Classificação de Vulnerabilidades

- **CRÍTICA**: Permite acesso não autorizado a dados ou escalada de privilégio
- **ALTA**: Compromete segurança mas requer condições específicas
- **MÉDIA**: Expõe informações ou degrada serviço
- **BAIXA**: Impacto limitado ou difícil exploração

---

## VULNERABILIDADES CRÍTICAS

### 1. [CRÍTICO] Row Level Security (RLS) Ineficaz - Escalada de Privilégio
**Arquivo:** `backend/database/schema.sql` (linhas 128-163)
**CVSS Score:** 9.8 (Critical)

#### Descrição
As políticas RLS do Supabase estão configuradas com `USING (true)` e `WITH CHECK (true)`, o que significa que **QUALQUER requisição** pode acessar **TODOS os dados** sem verificação de ownership.

```sql
CREATE POLICY "Users can view own categories" ON categories
    FOR SELECT USING (true);  -- ❌ VULNERÁVEL

CREATE POLICY "Users can manage own categories" ON categories
    FOR ALL USING (true);  -- ❌ VULNERÁVEL
```

Adicionalmente, o backend usa `SUPABASE_SERVICE_ROLE_KEY` que **bypassa completamente o RLS**.

#### Impacto
- **Escalada de privilégio total**
- Usuário pode acessar transações, contas e categorias de QUALQUER outro usuário
- Violação total de privacidade e isolamento de dados

#### Exploração
```bash
# Um usuário autenticado pode fazer:
curl -X GET https://api.alcahub.com.br/api/transactions \
  -H "Authorization: Bearer <token_usuario_A>" \
  -d "user_id=<usuario_B>"  # Acessa dados de outro usuário
```

#### Remediação
**URGENTE - Implementar imediatamente:**

```sql
-- Substitui políticas existentes por verificação real de ownership
DROP POLICY IF EXISTS "Users can view own categories" ON categories;
CREATE POLICY "Users can view own categories" ON categories
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can manage own categories" ON categories;
CREATE POLICY "Users can manage own categories" ON categories
    FOR ALL USING (auth.uid() = user_id);

-- Aplicar para todas as tabelas: transactions, accounts, categories
```

**Adicionar validação no backend:**
```python
# Não confiar apenas no RLS - validar no código também
def get_transaction(self, user_id: str, transaction_id: str):
    transaction = self.transaction_repo.find_by_id(transaction_id)
    if not transaction or transaction.get('user_id') != user_id:
        raise NotFoundException('Transação não encontrada')
    return transaction
```

---

### 2. [CRÍTICO] OAuth Google - Bypass de Verificação de Segurança
**Arquivo:** `backend/routes/auth.py` (linhas 340-384)
**CVSS Score:** 8.6 (High/Critical)

#### Descrição
O fluxo OAuth Google possui múltiplas vulnerabilidades:

1. **Bypass de State Verification** (linha 340-364):
```python
except MismatchingStateError:
    # ❌ VULNERÁVEL: Obtém token SEM verificar state
    print("Warning: MismatchingStateError - tentando obter token sem verificação de state")
    code = request.args.get('code')
    # ... obtém token sem validação
```

2. **JWT Sem Verificação de Assinatura** (linha 384):
```python
# ❌ VULNERÁVEL: Decodifica JWT sem verificar assinatura
resp = jwt.decode(id_token, options={"verify_signature": False})
```

#### Impacto
- **CSRF attacks**: Atacante pode forjar requisições OAuth
- **Token forgery**: Tokens maliciosos podem ser aceitos
- Atacante pode fazer login como qualquer usuário via OAuth

#### Exploração
```python
# Atacante cria token malicioso:
import jwt
fake_token = jwt.encode({
    'sub': 'victim_google_id',
    'email': 'victim@gmail.com',
    'name': 'Victim User'
}, 'any_key', algorithm='HS256')

# Como não verifica assinatura, o token é aceito
```

#### Remediação
```python
# Remover fallback inseguro - sempre verificar state
try:
    token = google.authorize_access_token()
    nonce = session.get("__google_oidc_nonce__")
    if not nonce:
        raise Exception('Session expired - please try again')
except MismatchingStateError:
    # NÃO fazer fallback - retornar erro
    return jsonify({'error': 'Session expired. Please try again.'}), 401

# SEMPRE verificar assinatura do JWT
resp = google.parse_id_token(token, nonce=nonce)  # Verifica assinatura automaticamente
```

---

### 3. [CRÍTICO] Secrets Inseguros em Desenvolvimento
**Arquivo:** `backend/app.py` (linha 43), `backend/utils/auth_utils.py` (linha 9)
**CVSS Score:** 7.5 (High)

#### Descrição
Secrets críticos usam valores default inseguros que podem vazar para produção:

```python
# app.py linha 43
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')  # ❌ VULNERÁVEL

# auth_utils.py linha 9
JWT_SECRET = os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'dev-secret-key'))  # ❌ VULNERÁVEL
```

#### Impacto
- Atacante pode forjar tokens JWT válidos
- Sessions podem ser hijacked
- Se default vazar para produção, sistema completamente comprometido

#### Remediação
```python
# Forçar erro se não configurado - NÃO usar default
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY or SECRET_KEY == 'dev-secret-key':
    raise RuntimeError(
        "SECRET_KEY não configurado ou usando valor inseguro.\n"
        "Execute: openssl rand -hex 32\n"
        "E configure no .env: SECRET_KEY=<valor_gerado>"
    )

JWT_SECRET = os.getenv('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET não configurado. Use: openssl rand -hex 32")
```

---

## VULNERABILIDADES ALTAS

### 4. [ALTA] Logs Expõem Informações Sensíveis
**Arquivo:** `backend/routes/auth.py` (linhas 132-147, 485-491)
**CVSS Score:** 6.5 (Medium/High)

#### Descrição
Logs contêm informações sensíveis que podem auxiliar ataques:

```python
# Linha 140 - Expõe tipo da senha no log
password_type = type(user['password']).__name__
current_app.logger.debug(f"Tipo da senha no banco: {password_type}")

# Linha 143 - Expõe resultado de verificação
current_app.logger.debug(f"Resultado da verificação de senha: {password_check_result}")

# Linha 488 - Stack trace completo em produção
print(f"Erro no callback OAuth: {error_msg}")
print(error_trace)  # ❌ Stack trace completo
```

#### Impacto
- Informações sensíveis em logs podem vazar (CloudWatch, Sentry, etc.)
- Stack traces revelam estrutura interna do código
- Facilita reconnaissance para ataques

#### Remediação
```python
# Remover logs sensíveis
# current_app.logger.debug(f"Tipo da senha: {password_type}")  # REMOVER

# Logs genéricos apenas
current_app.logger.warning(f"Login failed for email: {email}")

# Stack trace apenas em development
if app.debug:
    print(traceback.format_exc())
else:
    logger.error(f"OAuth error: {error_msg}")  # Sem stack trace
```

---

### 5. [ALTA] Rate Limiting Insuficiente
**Arquivo:** `backend/routes/auth.py` (linhas 48, 100)
**CVSS Score:** 6.2 (Medium)

#### Descrição
Rate limits permitem brute force attacks:

```python
@bp.route('/auth/register', methods=['POST'])
@limiter.limit("3 per hour")  # ❌ Muito permissivo

@bp.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")  # ❌ Pode ser brute forced
```

Com 5 tentativas/minuto, atacante pode testar 300 senhas/hora.

#### Impacto
- Brute force de senhas viável
- Account enumeration possível
- Abuse de registro (criar múltiplas contas)

#### Remediação
```python
# Rate limit mais agressivo
@limiter.limit("3 per minute")  # Login
@limiter.limit("1 per hour")    # Register (por IP)

# Adicionar bloqueio progressivo
# Após 3 falhas: aguardar 15 min
# Após 5 falhas: aguardar 1 hora
# Após 10 falhas: bloquear conta (require admin unlock)

# Implementar CAPTCHA após 2 falhas
```

---

### 6. [ALTA] Password Reset Sem Rate Limit
**Arquivo:** `backend/routes/auth.py` (linhas 182-200)
**CVSS Score:** 6.0 (Medium)

#### Descrição
Endpoint de forgot password não possui rate limiting:

```python
@bp.route('/auth/forgot-password', methods=['POST'])
# ❌ SEM rate limit
def forgot_password():
```

#### Impacto
- Atacante pode spammar emails para qualquer usuário
- Enumerar emails válidos no sistema
- DoS do serviço de email

#### Remediação
```python
@bp.route('/auth/forgot-password', methods=['POST'])
@limiter.limit("2 per hour per IP")
@limiter.limit("5 per day per email")
def forgot_password():
    # ... código existente
```

---

### 7. [ALTA] Admin Endpoints Sem Auditoria
**Arquivo:** `backend/routes/admin.py` (todo o arquivo)
**CVSS Score:** 5.8 (Medium)

#### Descrição
Ações administrativas críticas não são auditadas:

```python
@bp.route('/admin/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    # ❌ SEM auditoria - quem deletou e quando?
    users_collection.delete_one({'_id': user_id})
```

#### Impacto
- Impossível rastrear quem fez ações administrativas
- Dificulta investigação de incidentes
- Não compliance com LGPD/GDPR

#### Remediação
```python
# Criar tabela de audit logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    admin_user_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_user_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

# Adicionar logging
def delete_user(user_id):
    # Log antes de deletar
    audit_log.create({
        'admin_user_id': request.user_id,
        'action': 'DELETE_USER',
        'target_user_id': user_id,
        'ip_address': request.remote_addr
    })

    users_collection.delete_one({'_id': user_id})
```

---

### 8. [ALTA] Session Cookie Inseguro em Produção
**Arquivo:** `backend/app.py` (linhas 48-50)
**CVSS Score:** 5.5 (Medium)

#### Descrição
```python
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if is_production else 'Lax'
```

`SameSite=None` em produção permite CSRF attacks.

#### Impacto
- Cross-Site Request Forgery (CSRF) viável
- Cookies enviados em requests cross-origin maliciosos

#### Remediação
```python
# Usar Lax ou Strict em produção
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Se precisar de cross-origin, implementar CSRF token
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```

---

## VULNERABILIDADES MÉDIAS

### 9. [MÉDIA] Hardcoded User Data
**Arquivo:** `backend/routes/transactions.py` (linha 265), `backend/routes/accounts.py` (linha 222)
**CVSS Score:** 4.0 (Low/Medium)

#### Descrição
```python
'responsible_person': 'Leandro'  # ❌ Hardcoded
```

#### Impacto
- Revela nome do desenvolvedor
- Dados incorretos em transações importadas

#### Remediação
```python
'responsible_person': data.get('responsible_person') or user.get('name')
```

---

### 10. [MÉDIA] Export de Dados Sem Limite
**Arquivo:** `backend/routes/auth.py` (linhas 524-551)
**CVSS Score:** 4.0 (Low/Medium)

#### Descrição
```python
# ❌ Retorna TODOS os dados sem paginação ou limite
categories = list(categories_collection.find({'user_id': user_id}))
transactions = list(transactions_collection.find({'user_id': user_id}))
```

#### Impacto
- DoS por consumo de memória
- Timeout em contas com muitos dados

#### Remediação
```python
# Adicionar limite e usar streaming
@bp.route('/auth/backup/export', methods=['GET'])
@require_auth
@limiter.limit("1 per hour")  # Rate limit
def export_backup():
    # Usar cursor e streaming para grandes datasets
    def generate():
        yield '{"transactions":['
        # Stream transactions em chunks
        for chunk in get_transactions_chunks(request.user_id):
            yield json.dumps(chunk)
        yield ']}'

    return Response(generate(), mimetype='application/json')
```

---

## VULNERABILIDADES BAIXAS

### 11. [BAIXA] Potential ReDoS em Regex
**Arquivo:** `backend/routes/auth.py` (linhas 129, 193)
**CVSS Score:** 3.1 (Low)

#### Descrição
```python
{'email': {'$regex': f'^{email}$', '$options': 'i'}}
```

Input do usuário usado diretamente em regex pode causar ReDoS.

#### Impacto
- DoS limitado (apenas em queries específicas)
- Baixa exploração prática

#### Remediação
```python
# Usar comparação exata ao invés de regex
{'email': email.lower()}  # Case-insensitive no backend

# Ou escapar input se regex necessário
import re
escaped_email = re.escape(email)
{'email': {'$regex': f'^{escaped_email}$', '$options': 'i'}}
```

---

## Resumo de Priorização

### Ação Imediata (24h)
1. ✅ Corrigir RLS policies (Vulnerabilidade #1)
2. ✅ Remover bypass OAuth Google (Vulnerabilidade #2)
3. ✅ Forçar configuração de secrets (Vulnerabilidade #3)

### Curto Prazo (1 semana)
4. ✅ Remover logs sensíveis (Vulnerabilidade #4)
5. ✅ Implementar rate limiting agressivo (Vulnerabilidades #5, #6)
6. ✅ Corrigir session cookie (Vulnerabilidade #8)

### Médio Prazo (1 mês)
7. ✅ Implementar audit logging (Vulnerabilidade #7)
8. ✅ Adicionar paginação em exports (Vulnerabilidade #10)
9. ✅ Remover hardcoded data (Vulnerabilidade #9)
10. ✅ Escapar regex inputs (Vulnerabilidade #11)

---

## Testes de Segurança Recomendados

### Testes Pendentes
- [ ] Penetration testing completo
- [ ] Fuzzing de inputs
- [ ] OWASP ZAP scan
- [ ] Dependency vulnerability scan (Snyk, Dependabot)
- [ ] SAST (Static Application Security Testing)

### Ferramentas Recomendadas
```bash
# Scan de dependências
pip install safety
safety check

# SAST
pip install bandit
bandit -r backend/

# Secrets scanning
git secrets --scan

# Container scanning (se usar Docker)
docker scan alca-financas:latest
```

---

## Compliance

### LGPD/GDPR
- ⚠️ **Não Conforme**: Sem audit logs para rastreabilidade
- ⚠️ **Não Conforme**: Export de dados sem controle
- ✅ **Conforme**: Direito ao esquecimento implementado (clear_all_data)

### OWASP Top 10 (2021)
- A01:2021 - Broken Access Control: **VULNERÁVEL** (RLS ineficaz)
- A02:2021 - Cryptographic Failures: **VULNERÁVEL** (Secrets default)
- A03:2021 - Injection: **MITIGADO** (Usando ORM, pequeno risco ReDoS)
- A04:2021 - Insecure Design: **VULNERÁVEL** (OAuth bypass)
- A05:2021 - Security Misconfiguration: **VULNERÁVEL** (RLS, Sessions)
- A07:2021 - Identification/Authentication: **VULNERÁVEL** (Rate limiting)
- A09:2021 - Security Logging: **VULNERÁVEL** (Sem audit logs)

---

## Conclusão

O sistema apresenta **vulnerabilidades críticas de segurança** que permitem:
- Acesso não autorizado a dados de outros usuários (RLS)
- Bypass de autenticação (OAuth)
- Potencial comprometimento total (Secrets)

**Recomendação**: Não utilizar em produção até corrigir pelo menos as 3 vulnerabilidades críticas.

**Próximos Passos**:
1. Implementar correções críticas (24h)
2. Testes de segurança completos (1 semana)
3. Code review focado em segurança (ongoing)
4. Implementar DevSecOps pipeline

---

**Auditor:** Claude Sonnet 4.5
**Metodologia:** OWASP Testing Guide, CWE Top 25, CVSS v3.1
