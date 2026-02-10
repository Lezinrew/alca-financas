# TODO - Correções de Segurança

**Status:** 🔴 CRÍTICO - Sistema não deve estar em produção até completar Fase 1
**Última atualização:** 2026-02-10

---

## 📋 Progresso Geral

- [ ] **Fase 1 - CRÍTICO** (0/3) - Prazo: 24h
- [ ] **Fase 2 - ALTA** (0/5) - Prazo: 1 semana
- [ ] **Fase 3 - MÉDIA** (0/2) - Prazo: 1 mês
- [ ] **Fase 4 - BAIXA** (0/1) - Prazo: 1 mês
- [ ] **Fase 5 - TESTES** (0/5) - Após todas as correções

---

## 🔴 FASE 1 - VULNERABILIDADES CRÍTICAS (24 HORAS)

### ✅ Task 1.1: Corrigir Row Level Security (RLS)
**Prioridade:** 🔴 CRÍTICA | **Tempo estimado:** 2h | **Arquivo:** `backend/database/schema.sql`

**Subtarefas:**
- [ ] 1.1.1 - Backup do banco de dados antes de modificar
  ```bash
  # Via Supabase Dashboard: Database > Backups > Create backup
  ```

- [ ] 1.1.2 - Criar novo arquivo de migration para RLS
  ```bash
  touch backend/database/migrations/002_fix_rls_policies.sql
  ```

- [ ] 1.1.3 - Adicionar policies corretas ao arquivo de migration
  ```sql
  -- backend/database/migrations/002_fix_rls_policies.sql

  -- Remove policies antigas (inseguras)
  DROP POLICY IF EXISTS "Users can view own data" ON users;
  DROP POLICY IF EXISTS "Users can insert own data" ON users;
  DROP POLICY IF EXISTS "Users can update own data" ON users;
  DROP POLICY IF EXISTS "Users can view own categories" ON categories;
  DROP POLICY IF EXISTS "Users can manage own categories" ON categories;
  DROP POLICY IF EXISTS "Users can view own accounts" ON accounts;
  DROP POLICY IF EXISTS "Users can manage own accounts" ON accounts;
  DROP POLICY IF EXISTS "Users can view own transactions" ON transactions;
  DROP POLICY IF EXISTS "Users can manage own transactions" ON transactions;

  -- Policies corretas para USERS
  CREATE POLICY "users_select_own" ON users
      FOR SELECT USING (auth.uid() = id);

  CREATE POLICY "users_insert_own" ON users
      FOR INSERT WITH CHECK (auth.uid() = id);

  CREATE POLICY "users_update_own" ON users
      FOR UPDATE USING (auth.uid() = id);

  -- Policies corretas para CATEGORIES
  CREATE POLICY "categories_select_own" ON categories
      FOR SELECT USING (auth.uid()::text = user_id::text);

  CREATE POLICY "categories_insert_own" ON categories
      FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

  CREATE POLICY "categories_update_own" ON categories
      FOR UPDATE USING (auth.uid()::text = user_id::text);

  CREATE POLICY "categories_delete_own" ON categories
      FOR DELETE USING (auth.uid()::text = user_id::text);

  -- Policies corretas para ACCOUNTS
  CREATE POLICY "accounts_select_own" ON accounts
      FOR SELECT USING (auth.uid()::text = user_id::text);

  CREATE POLICY "accounts_insert_own" ON accounts
      FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

  CREATE POLICY "accounts_update_own" ON accounts
      FOR UPDATE USING (auth.uid()::text = user_id::text);

  CREATE POLICY "accounts_delete_own" ON accounts
      FOR DELETE USING (auth.uid()::text = user_id::text);

  -- Policies corretas para TRANSACTIONS
  CREATE POLICY "transactions_select_own" ON transactions
      FOR SELECT USING (auth.uid()::text = user_id::text);

  CREATE POLICY "transactions_insert_own" ON transactions
      FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

  CREATE POLICY "transactions_update_own" ON transactions
      FOR UPDATE USING (auth.uid()::text = user_id::text);

  CREATE POLICY "transactions_delete_own" ON transactions
      FOR DELETE USING (auth.uid()::text = user_id::text);
  ```

- [ ] 1.1.4 - Executar migration no Supabase
  ```bash
  # Via Supabase Dashboard: SQL Editor > New query
  # Cole o conteúdo de 002_fix_rls_policies.sql e execute
  ```

- [ ] 1.1.5 - Testar que RLS está funcionando
  ```bash
  # Criar script de teste
  python backend/tests/test_rls_enforcement.py
  ```

- [ ] 1.1.6 - Atualizar documentação
  ```bash
  # Atualizar backend/README_SUPABASE.md com as novas policies
  ```

**Validação:**
```bash
# Teste manual: tentar acessar dados de outro usuário deve falhar
curl -X GET "https://api.alcahub.com.br/api/transactions" \
  -H "Authorization: Bearer <token_usuario_A>"
# Deve retornar APENAS transações do usuário A
```

---

### ✅ Task 1.2: Corrigir OAuth Google - Remover Bypass
**Prioridade:** 🔴 CRÍTICA | **Tempo estimado:** 1h | **Arquivo:** `backend/routes/auth.py`

**Subtarefas:**
- [ ] 1.2.1 - Backup do arquivo auth.py
  ```bash
  cp backend/routes/auth.py backend/routes/auth.py.backup
  ```

- [ ] 1.2.2 - Remover fallback inseguro (linhas 334-364)
  ```python
  # REMOVER este bloco completo:
  except MismatchingStateError:
      print("Warning: MismatchingStateError - tentando obter token sem verificação de state")
      code = request.args.get('code')
      if not code:
          raise Exception('Código de autorização não encontrado')
      # ... TODO O BLOCO ATÉ LINHA 364
  ```

- [ ] 1.2.3 - Modificar tratamento de erro para ser seguro
  ```python
  # Substituir por:
  except MismatchingStateError as e:
      error_msg = "Sessão OAuth expirou. Por favor, tente fazer login novamente."
      logger.warning(f"OAuth state mismatch: {e}")

      error_html = f"""<!DOCTYPE html>
  <html>
  <head>
      <title>Erro de Autenticação</title>
      <meta charset="UTF-8">
  </head>
  <body>
      <p style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; color: red;">
          {error_msg}
      </p>
      <script>
          setTimeout(function() {{
              window.location.href = {json.dumps(frontend_url + '/login?error=session_expired')};
          }}, 3000);
      </script>
  </body>
  </html>"""
      return error_html, 401, {'Content-Type': 'text/html; charset=utf-8'}
  ```

- [ ] 1.2.4 - Remover decodificação JWT sem verificação (linha 384)
  ```python
  # REMOVER:
  # resp = jwt.decode(id_token, options={"verify_signature": False})

  # SUBSTITUIR POR:
  # Sempre usar parse_id_token que verifica assinatura
  if not nonce:
      raise Exception('Nonce inválido - session expirada')
  resp = google.parse_id_token(token, nonce=nonce)
  ```

- [ ] 1.2.5 - Adicionar validação adicional de issuer
  ```python
  # Após parse_id_token, adicionar:
  if resp.get('iss') not in ['https://accounts.google.com', 'accounts.google.com']:
      raise Exception('Token issuer inválido')
  if resp.get('aud') != GOOGLE_CLIENT_ID:
      raise Exception('Token audience inválido')
  ```

- [ ] 1.2.6 - Testar fluxo OAuth
  ```bash
  # Teste manual: fazer login via Google
  # Verificar que funciona e que MismatchingStateError retorna erro
  ```

**Validação:**
```bash
# OAuth deve funcionar normalmente
# Tentar forge de token deve falhar
# State mismatch deve retornar erro 401
```

---

### ✅ Task 1.3: Forçar Configuração de Secrets
**Prioridade:** 🔴 CRÍTICA | **Tempo estimado:** 30min | **Arquivos:** `backend/app.py`, `backend/utils/auth_utils.py`

**Subtarefas:**
- [ ] 1.3.1 - Atualizar app.py para validar SECRET_KEY
  ```python
  # backend/app.py (linha 43)
  # REMOVER:
  # app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

  # ADICIONAR:
  SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
  if not SECRET_KEY or SECRET_KEY == 'dev-secret-key' or len(SECRET_KEY) < 32:
      raise RuntimeError(
          "❌ SECRET_KEY não configurado ou inseguro!\n"
          "Execute: openssl rand -hex 32\n"
          "Configure no .env: SECRET_KEY=<valor_gerado>\n"
          "NUNCA use 'dev-secret-key' em produção!"
      )
  app.secret_key = SECRET_KEY
  ```

- [ ] 1.3.2 - Atualizar auth_utils.py para validar JWT_SECRET
  ```python
  # backend/utils/auth_utils.py (linha 9)
  # REMOVER:
  # JWT_SECRET = os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'dev-secret-key'))

  # ADICIONAR:
  JWT_SECRET = os.getenv('JWT_SECRET', '').strip()
  if not JWT_SECRET or JWT_SECRET == 'dev-secret-key' or len(JWT_SECRET) < 32:
      raise RuntimeError(
          "❌ JWT_SECRET não configurado ou inseguro!\n"
          "Execute: openssl rand -hex 32\n"
          "Configure no .env: JWT_SECRET=<valor_gerado>\n"
          "DEVE ser diferente de SECRET_KEY!"
      )
  ```

- [ ] 1.3.3 - Gerar secrets fortes
  ```bash
  # Gerar SECRET_KEY
  openssl rand -hex 32

  # Gerar JWT_SECRET (diferente!)
  openssl rand -hex 32
  ```

- [ ] 1.3.4 - Atualizar .env.example com instruções
  ```bash
  # .env.example
  # CRITICAL: Generate strong secrets (NEVER use defaults!)
  # Generate with: openssl rand -hex 32
  SECRET_KEY=your-secret-key-here-minimum-32-chars
  JWT_SECRET=your-jwt-secret-here-different-from-secret-key
  ```

- [ ] 1.3.5 - Atualizar .env local e produção
  ```bash
  # Adicionar secrets gerados ao .env
  # NUNCA commitar .env ao git
  ```

- [ ] 1.3.6 - Testar que aplicação não inicia sem secrets
  ```bash
  # Remover temporariamente secrets do .env
  # Tentar iniciar backend - deve falhar com erro claro
  python backend/app.py  # Deve mostrar RuntimeError
  ```

**Validação:**
```bash
# Aplicação não deve iniciar sem secrets configurados
# Deve rejeitar secrets inseguros (curtos ou defaults)
```

---

## 🟠 FASE 2 - VULNERABILIDADES ALTAS (1 SEMANA)

### ✅ Task 2.1: Remover Logs Sensíveis
**Prioridade:** 🟠 ALTA | **Tempo estimado:** 1h | **Arquivo:** `backend/routes/auth.py`

**Subtarefas:**
- [ ] 2.1.1 - Remover logs de debug de senha (linhas 138-143)
  ```python
  # REMOVER:
  # password_type = type(user['password']).__name__
  # current_app.logger.debug(f"Tentativa de login para {email}: tipo da senha no banco: {password_type}")
  # password_check_result = check_password(data.password, user['password'])
  # current_app.logger.debug(f"Resultado da verificação de senha: {password_check_result}")

  # SUBSTITUIR POR:
  password_check_result = check_password(data.password, user['password'])
  ```

- [ ] 2.1.2 - Modificar logs de erro para não expor stack trace (linhas 485-491)
  ```python
  # REMOVER:
  # print(f"Erro no callback OAuth: {error_msg}")
  # print(error_trace)

  # SUBSTITUIR POR:
  logger.error(f"OAuth callback error: {error_msg}")
  if current_app.debug:
      logger.debug(f"Stack trace: {error_trace}")
  # Em produção, stack trace vai apenas para logs estruturados, não para console
  ```

- [ ] 2.1.3 - Adicionar log estruturado (opcional mas recomendado)
  ```python
  # Adicionar no início de app.py
  import logging.config

  LOGGING_CONFIG = {
      'version': 1,
      'formatters': {
          'default': {
              'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
          }
      },
      'handlers': {
          'console': {
              'class': 'logging.StreamHandler',
              'formatter': 'default'
          },
          'file': {
              'class': 'logging.FileHandler',
              'filename': 'logs/app.log',
              'formatter': 'default'
          }
      },
      'root': {
          'level': 'INFO' if is_production else 'DEBUG',
          'handlers': ['console', 'file']
      }
  }

  logging.config.dictConfig(LOGGING_CONFIG)
  ```

- [ ] 2.1.4 - Revisar TODOS os print() e substituir por logger
  ```bash
  # Buscar todos os prints
  grep -rn "print(" backend/ --include="*.py"

  # Substituir por logger apropriado:
  # logger.debug() - informações de debug
  # logger.info() - informações gerais
  # logger.warning() - avisos
  # logger.error() - erros
  ```

**Validação:**
```bash
# Logs não devem conter:
# - Senhas ou hashes
# - Stack traces em produção
# - Dados pessoais identificáveis
```

---

### ✅ Task 2.2: Implementar Rate Limiting Agressivo
**Prioridade:** 🟠 ALTA | **Tempo estimado:** 2h | **Arquivo:** `backend/routes/auth.py`

**Subtarefas:**
- [ ] 2.2.1 - Atualizar rate limits existentes
  ```python
  # backend/routes/auth.py

  # Login (linha 100)
  @bp.route('/auth/login', methods=['POST'])
  @limiter.limit("3 per minute")  # Era 5, reduzir para 3
  @limiter.limit("10 per hour")   # Adicionar limite por hora
  def login():

  # Register (linha 48)
  @bp.route('/auth/register', methods=['POST'])
  @limiter.limit("1 per hour")    # Era 3, reduzir para 1
  @limiter.limit("5 per day")     # Adicionar limite por dia
  def register():
  ```

- [ ] 2.2.2 - Adicionar rate limit para forgot-password
  ```python
  # backend/routes/auth.py (linha 182)
  @bp.route('/auth/forgot-password', methods=['POST'])
  @limiter.limit("2 per hour")     # Por IP
  @limiter.limit("5 per day")      # Por IP
  def forgot_password():
  ```

- [ ] 2.2.3 - Adicionar rate limit para reset-password
  ```python
  # backend/routes/auth.py (linha 203)
  @bp.route('/auth/reset-password', methods=['POST'])
  @limiter.limit("3 per hour")     # Por IP
  def reset_password():
  ```

- [ ] 2.2.4 - Implementar bloqueio progressivo de conta
  ```python
  # Criar novo arquivo: backend/services/account_lockout_service.py
  from datetime import datetime, timedelta
  from typing import Optional

  class AccountLockoutService:
      """Gerencia bloqueios progressivos de conta"""

      def __init__(self, db):
          self.db = db
          # Usar Redis para melhor performance, ou tabela no DB

      def record_failed_login(self, email: str) -> dict:
          """Registra tentativa falha e retorna status de bloqueio"""
          # Buscar tentativas recentes (última hora)
          attempts = self._get_recent_attempts(email)
          attempts.append({
              'timestamp': datetime.utcnow(),
              'ip': request.remote_addr
          })

          # Lógica de bloqueio progressivo
          if len(attempts) >= 10:
              lockout_until = datetime.utcnow() + timedelta(hours=24)
              return {'locked': True, 'until': lockout_until, 'reason': 'Muitas tentativas'}
          elif len(attempts) >= 5:
              lockout_until = datetime.utcnow() + timedelta(hours=1)
              return {'locked': True, 'until': lockout_until, 'reason': 'Múltiplas tentativas'}
          elif len(attempts) >= 3:
              lockout_until = datetime.utcnow() + timedelta(minutes=15)
              return {'locked': True, 'until': lockout_until, 'reason': 'Tentativas suspeitas'}

          self._save_attempts(email, attempts)
          return {'locked': False, 'attempts': len(attempts)}

      def clear_failed_attempts(self, email: str):
          """Limpa tentativas após login bem-sucedido"""
          self._save_attempts(email, [])

      def is_locked(self, email: str) -> Optional[datetime]:
          """Verifica se conta está bloqueada"""
          # Implementar verificação de lockout
          pass
  ```

- [ ] 2.2.5 - Integrar lockout service no login
  ```python
  # backend/routes/auth.py no endpoint /auth/login

  @bp.route('/auth/login', methods=['POST'])
  @limiter.limit("3 per minute")
  def login():
      data = UserLoginSchema(**request.get_json())
      email = data.email.strip().lower()

      # Verificar se conta está bloqueada
      lockout_service = AccountLockoutService(current_app.config['DB'])
      lockout_until = lockout_service.is_locked(email)
      if lockout_until:
          return jsonify({
              'error': f'Conta temporariamente bloqueada até {lockout_until.isoformat()}'
          }), 429

      # ... código existente de verificação ...

      if not password_check_result:
          # Registrar falha
          lockout_info = lockout_service.record_failed_login(email)
          if lockout_info['locked']:
              return jsonify({
                  'error': f"Muitas tentativas falhas. Conta bloqueada até {lockout_info['until'].isoformat()}"
              }), 429

          return jsonify({'error': 'Email ou senha incorretos'}), 401

      # Login bem-sucedido - limpar tentativas
      lockout_service.clear_failed_attempts(email)
      # ... resto do código
  ```

- [ ] 2.2.6 - Criar tabela para armazenar lockouts
  ```sql
  -- backend/database/migrations/003_account_lockouts.sql
  CREATE TABLE IF NOT EXISTS account_lockouts (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      email VARCHAR(255) NOT NULL,
      attempts JSONB DEFAULT '[]'::jsonb,
      locked_until TIMESTAMP WITH TIME ZONE,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
  );

  CREATE INDEX idx_lockouts_email ON account_lockouts(email);
  CREATE INDEX idx_lockouts_locked_until ON account_lockouts(locked_until);
  ```

- [ ] 2.2.7 - Testar rate limiting
  ```bash
  # Script de teste
  for i in {1..10}; do
      curl -X POST http://localhost:8001/api/auth/login \
          -H "Content-Type: application/json" \
          -d '{"email":"test@test.com","password":"wrong"}'
      echo "Tentativa $i"
  done
  # Após 3 tentativas deve retornar 429
  ```

**Validação:**
```bash
# Rate limits devem bloquear após limites atingidos
# Conta deve ser bloqueada após múltiplas falhas
# Bloqueio progressivo funcionando: 3 falhas = 15min, 5 falhas = 1h, 10 falhas = 24h
```

---

### ✅ Task 2.3: Corrigir Session Cookie
**Prioridade:** 🟠 ALTA | **Tempo estimado:** 30min | **Arquivo:** `backend/app.py`

**Subtarefas:**
- [ ] 2.3.1 - Atualizar configuração de session cookie
  ```python
  # backend/app.py (linhas 48-50)

  # REMOVER:
  # app.config['SESSION_COOKIE_SAMESITE'] = 'None' if is_production else 'Lax'

  # SUBSTITUIR POR:
  app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Sempre Lax (mais seguro)
  app.config['SESSION_COOKIE_SECURE'] = is_production  # True apenas em HTTPS
  app.config['SESSION_COOKIE_HTTPONLY'] = True
  ```

- [ ] 2.3.2 - Se OAuth cross-origin for necessário, implementar CSRF token
  ```python
  # Instalar Flask-WTF
  # pip install Flask-WTF

  # backend/app.py
  from flask_wtf.csrf import CSRFProtect

  csrf = CSRFProtect()
  csrf.init_app(app)

  # Excluir apenas endpoints OAuth do CSRF (eles têm state)
  @csrf.exempt
  @bp.route('/auth/google/callback')
  def google_callback():
      # ... código existente
  ```

- [ ] 2.3.3 - Atualizar frontend para incluir CSRF token
  ```typescript
  // frontend/src/utils/api.ts

  // Adicionar CSRF token em requests
  const getCsrfToken = () => {
      const cookies = document.cookie.split(';');
      const csrfCookie = cookies.find(c => c.trim().startsWith('csrf_token='));
      return csrfCookie ? csrfCookie.split('=')[1] : '';
  };

  api.interceptors.request.use(config => {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
          config.headers['X-CSRFToken'] = csrfToken;
      }
      return config;
  });
  ```

- [ ] 2.3.4 - Testar que cookies são enviados corretamente
  ```bash
  # Verificar que SameSite=Lax funciona
  # Verificar que Secure=true em produção
  ```

**Validação:**
```bash
# Cookie deve ter SameSite=Lax
# Cookie deve ter Secure=true em produção
# CSRF token deve proteger mutations
```

---

### ✅ Task 2.4: Implementar Audit Logging
**Prioridade:** 🟠 ALTA | **Tempo estimado:** 3h | **Arquivo:** `backend/routes/admin.py`

**Subtarefas:**
- [ ] 2.4.1 - Criar tabela de audit logs
  ```sql
  -- backend/database/migrations/004_audit_logs.sql
  CREATE TABLE IF NOT EXISTS audit_logs (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      admin_user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
      action VARCHAR(100) NOT NULL,
      target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      target_resource_type VARCHAR(50),  -- 'user', 'transaction', 'account', etc.
      target_resource_id UUID,
      details JSONB,
      ip_address VARCHAR(45),
      user_agent TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
  );

  CREATE INDEX idx_audit_admin_user ON audit_logs(admin_user_id);
  CREATE INDEX idx_audit_action ON audit_logs(action);
  CREATE INDEX idx_audit_target_user ON audit_logs(target_user_id);
  CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);

  -- RLS para audit logs
  ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

  CREATE POLICY "admins_view_audit_logs" ON audit_logs
      FOR SELECT USING (
          EXISTS (
              SELECT 1 FROM users
              WHERE users.id = auth.uid()::text::uuid
              AND users.is_admin = true
          )
      );
  ```

- [ ] 2.4.2 - Criar serviço de audit logging
  ```python
  # backend/services/audit_service.py
  from datetime import datetime
  from typing import Dict, Any, Optional
  from flask import request
  import uuid

  class AuditService:
      """Serviço para registrar ações administrativas"""

      def __init__(self, db):
          self.db = db

      def log_action(
          self,
          admin_user_id: str,
          action: str,
          target_user_id: Optional[str] = None,
          target_resource_type: Optional[str] = None,
          target_resource_id: Optional[str] = None,
          details: Optional[Dict[str, Any]] = None
      ):
          """Registra uma ação administrativa"""
          log_entry = {
              'id': str(uuid.uuid4()),
              'admin_user_id': admin_user_id,
              'action': action,
              'target_user_id': target_user_id,
              'target_resource_type': target_resource_type,
              'target_resource_id': target_resource_id,
              'details': details or {},
              'ip_address': request.remote_addr,
              'user_agent': request.headers.get('User-Agent', '')[:500],
              'created_at': datetime.utcnow().isoformat()
          }

          try:
              self.db.table('audit_logs').insert(log_entry).execute()
          except Exception as e:
              # Não falhar ação principal se log falhar
              import logging
              logging.error(f"Falha ao criar audit log: {e}")

      def get_logs(
          self,
          admin_user_id: Optional[str] = None,
          action: Optional[str] = None,
          page: int = 1,
          per_page: int = 50
      ) -> Dict[str, Any]:
          """Busca audit logs com filtros"""
          query = self.db.table('audit_logs').select('*', count='exact')

          if admin_user_id:
              query = query.eq('admin_user_id', admin_user_id)
          if action:
              query = query.eq('action', action)

          query = query.order('created_at', desc=True)
          offset = (page - 1) * per_page
          query = query.range(offset, offset + per_page - 1)

          response = query.execute()

          return {
              'logs': response.data or [],
              'total': response.count if hasattr(response, 'count') else 0,
              'page': page,
              'per_page': per_page
          }
  ```

- [ ] 2.4.3 - Adicionar audit logging em endpoints admin
  ```python
  # backend/routes/admin.py
  from services.audit_service import AuditService

  @bp.route('/users/<user_id>', methods=['DELETE'])
  @require_auth
  @admin_required
  def delete_user(user_id):
      if user_id == request.user_id:
          return jsonify({'error': 'Não é possível deletar a si mesmo'}), 400

      users_collection = current_app.config['USERS']
      user = users_collection.find_one({'_id': user_id})
      if not user:
          return jsonify({'error': 'Usuário não encontrado'}), 404

      # ✅ ADICIONAR: Audit log ANTES de deletar
      audit = AuditService(current_app.config['DB'])
      audit.log_action(
          admin_user_id=request.user_id,
          action='DELETE_USER',
          target_user_id=user_id,
          details={
              'user_email': user.get('email'),
              'user_name': user.get('name')
          }
      )

      # Delete everything
      users_collection.delete_one({'_id': user_id})
      categories_collection.delete_many({'user_id': user_id})
      transactions_collection.delete_many({'user_id': user_id})
      accounts_collection.delete_many({'user_id': user_id})

      return jsonify({'message': 'Usuário e dados deletados com sucesso'})

  # Repetir para outros endpoints admin:
  # - create_user_admin (action: 'CREATE_USER')
  # - update_user_status (action: 'UPDATE_USER_STATUS')
  ```

- [ ] 2.4.4 - Criar endpoint para visualizar audit logs
  ```python
  # backend/routes/admin.py

  @bp.route('/audit-logs', methods=['GET'])
  @require_auth
  @admin_required
  def get_audit_logs():
      """Lista audit logs (apenas para admins)"""
      audit = AuditService(current_app.config['DB'])

      page = int(request.args.get('page', 1))
      per_page = int(request.args.get('per_page', 50))
      action = request.args.get('action')

      result = audit.get_logs(
          action=action,
          page=page,
          per_page=per_page
      )

      return jsonify(result)
  ```

- [ ] 2.4.5 - Testar audit logging
  ```bash
  # Executar ação admin (ex: deletar usuário)
  # Verificar que log foi criado em audit_logs
  # Verificar que pode consultar logs via /api/admin/audit-logs
  ```

**Validação:**
```bash
# Todas as ações admin devem gerar audit log
# Logs devem conter: quem, o que, quando, IP
# Apenas admins podem ver audit logs
```

---

### ✅ Task 2.5: Adicionar CAPTCHA após Falhas
**Prioridade:** 🟠 ALTA | **Tempo estimado:** 2h | **Arquivo:** `backend/routes/auth.py`, `frontend/src/components/auth/Login.tsx`

**Subtarefas:**
- [ ] 2.5.1 - Criar conta no hCaptcha ou reCAPTCHA
  ```bash
  # Opção 1: hCaptcha (recomendado - mais privado)
  # https://www.hcaptcha.com/

  # Opção 2: Google reCAPTCHA v3
  # https://www.google.com/recaptcha/admin/create
  ```

- [ ] 2.5.2 - Adicionar keys ao .env
  ```bash
  # .env
  HCAPTCHA_SITE_KEY=your-site-key
  HCAPTCHA_SECRET_KEY=your-secret-key
  ```

- [ ] 2.5.3 - Instalar dependências
  ```bash
  # Backend
  pip install requests

  # Frontend
  cd frontend
  npm install @hcaptcha/react-hcaptcha
  ```

- [ ] 2.5.4 - Criar serviço de verificação de CAPTCHA
  ```python
  # backend/services/captcha_service.py
  import requests
  import os

  class CaptchaService:
      """Verifica CAPTCHA (hCaptcha ou reCAPTCHA)"""

      @staticmethod
      def verify_hcaptcha(token: str, remote_ip: str) -> bool:
          """Verifica token hCaptcha"""
          secret = os.getenv('HCAPTCHA_SECRET_KEY')
          if not secret:
              return True  # Permitir se não configurado (dev)

          response = requests.post(
              'https://hcaptcha.com/siteverify',
              data={
                  'secret': secret,
                  'response': token,
                  'remoteip': remote_ip
              },
              timeout=5
          )

          result = response.json()
          return result.get('success', False)
  ```

- [ ] 2.5.5 - Integrar CAPTCHA no login após falhas
  ```python
  # backend/routes/auth.py
  from services.captcha_service import CaptchaService

  @bp.route('/auth/login', methods=['POST'])
  @limiter.limit("3 per minute")
  def login():
      data = request.get_json()
      email = data.get('email', '').strip().lower()

      # Verificar se precisa de CAPTCHA (após 2 falhas)
      lockout_service = AccountLockoutService(current_app.config['DB'])
      attempts = lockout_service.get_recent_attempts(email)

      if len(attempts) >= 2:
          # Exigir CAPTCHA
          captcha_token = data.get('captcha_token')
          if not captcha_token:
              return jsonify({
                  'error': 'CAPTCHA obrigatório após múltiplas tentativas',
                  'requires_captcha': True
              }), 400

          # Verificar CAPTCHA
          if not CaptchaService.verify_hcaptcha(captcha_token, request.remote_addr):
              return jsonify({
                  'error': 'CAPTCHA inválido',
                  'requires_captcha': True
              }), 400

      # ... resto do código de login
  ```

- [ ] 2.5.6 - Adicionar CAPTCHA no frontend
  ```tsx
  // frontend/src/components/auth/Login.tsx
  import HCaptcha from '@hcaptcha/react-hcaptcha';
  import { useState } from 'react';

  export function Login() {
      const [requiresCaptcha, setRequiresCaptcha] = useState(false);
      const [captchaToken, setCaptchaToken] = useState<string | null>(null);

      const handleLogin = async (e: React.FormEvent) => {
          e.preventDefault();

          const payload = {
              email,
              password,
              ...(requiresCaptcha && captchaToken ? { captcha_token: captchaToken } : {})
          };

          try {
              const response = await api.post('/auth/login', payload);
              // ... success
          } catch (error: any) {
              if (error.response?.data?.requires_captcha) {
                  setRequiresCaptcha(true);
              }
              // ... error handling
          }
      };

      return (
          <form onSubmit={handleLogin}>
              {/* ... existing fields */}

              {requiresCaptcha && (
                  <HCaptcha
                      sitekey={import.meta.env.VITE_HCAPTCHA_SITE_KEY}
                      onVerify={(token) => setCaptchaToken(token)}
                      onExpire={() => setCaptchaToken(null)}
                  />
              )}

              {/* ... submit button */}
          </form>
      );
  }
  ```

- [ ] 2.5.7 - Adicionar HCAPTCHA_SITE_KEY ao .env do frontend
  ```bash
  # frontend/.env
  VITE_HCAPTCHA_SITE_KEY=your-site-key
  ```

- [ ] 2.5.8 - Testar CAPTCHA
  ```bash
  # Fazer 2 tentativas de login com senha errada
  # Na 3ª tentativa, CAPTCHA deve aparecer
  # Login só deve funcionar após resolver CAPTCHA
  ```

**Validação:**
```bash
# Após 2 falhas, CAPTCHA deve ser exigido
# Login com CAPTCHA inválido deve falhar
# CAPTCHA resolvido corretamente permite login
```

---

## 🟡 FASE 3 - VULNERABILIDADES MÉDIAS (1 MÊS)

### ✅ Task 3.1: Remover Hardcoded User Data
**Prioridade:** 🟡 MÉDIA | **Tempo estimado:** 30min | **Arquivos:** `backend/routes/transactions.py`, `backend/routes/accounts.py`

**Subtarefas:**
- [ ] 3.1.1 - Atualizar transactions.py (linha 265)
  ```python
  # backend/routes/transactions.py

  # REMOVER:
  # 'responsible_person': 'Leandro',

  # SUBSTITUIR POR:
  'responsible_person': data.get('responsible_person') or user.get('name'),
  ```

- [ ] 3.1.2 - Atualizar accounts.py (linha 222)
  ```python
  # backend/routes/accounts.py

  # Mesmo padrão - usar dados do usuário ou do form
  'responsible_person': tx.get('responsible_person') or user.get('name'),
  ```

- [ ] 3.1.3 - Buscar todos os hardcoded values
  ```bash
  grep -rn "Leandro" backend/ --include="*.py"
  grep -rn "hardcoded" backend/ --include="*.py"
  # Substituir todos por valores dinâmicos
  ```

**Validação:**
```bash
# Nenhum valor hardcoded no código
# Transações usam nome do usuário logado
```

---

### ✅ Task 3.2: Adicionar Paginação em Exports
**Prioridade:** 🟡 MÉDIA | **Tempo estimado:** 2h | **Arquivo:** `backend/routes/auth.py`

**Subtarefas:**
- [ ] 3.2.1 - Refatorar export para usar streaming
  ```python
  # backend/routes/auth.py (linha 524)
  from flask import Response, stream_with_context
  import json

  @bp.route('/auth/backup/export', methods=['GET'])
  @require_auth
  @limiter.limit("1 per hour")  # Adicionar rate limit
  def export_backup():
      """Exporta dados do usuário em formato JSON com streaming"""
      user_id = request.user_id

      def generate():
          """Generator para streaming de dados"""
          yield '{\n'
          yield '  "version": "1.0",\n'
          yield f'  "exported_at": "{datetime.utcnow().isoformat()}",\n'
          yield f'  "user_id": "{user_id}",\n'

          # Stream categories
          yield '  "categories": [\n'
          categories = current_app.config['CATEGORIES'].find_by_user(user_id)
          for i, cat in enumerate(categories):
              cat_json = json.dumps(cat, default=str)
              yield '    ' + cat_json
              if i < len(categories) - 1:
                  yield ','
              yield '\n'
          yield '  ],\n'

          # Stream transactions em chunks
          yield '  "transactions": [\n'
          transactions_repo = current_app.config['TRANSACTIONS']
          page = 1
          per_page = 100
          first = True

          while True:
              result = transactions_repo.find_by_filter(
                  user_id, {}, page=page, per_page=per_page
              )
              transactions = result.get('data', [])

              if not transactions:
                  break

              for tx in transactions:
                  if not first:
                      yield ',\n'
                  first = False
                  tx_json = json.dumps(tx, default=str)
                  yield '    ' + tx_json

              if len(transactions) < per_page:
                  break
              page += 1

          yield '\n  ],\n'

          # Stream accounts
          yield '  "accounts": [\n'
          accounts = current_app.config['ACCOUNTS'].find_by_user(user_id)
          for i, acc in enumerate(accounts):
              acc_json = json.dumps(acc, default=str)
              yield '    ' + acc_json
              if i < len(accounts) - 1:
                  yield ','
              yield '\n'
          yield '  ]\n'

          yield '}\n'

      return Response(
          stream_with_context(generate()),
          mimetype='application/json',
          headers={
              'Content-Disposition': f'attachment; filename=alca_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
          }
      )
  ```

- [ ] 3.2.2 - Adicionar limite de tamanho de export
  ```python
  # Adicionar verificação antes do export
  @bp.route('/auth/backup/export', methods=['GET'])
  @require_auth
  @limiter.limit("1 per hour")
  def export_backup():
      # Verificar tamanho estimado
      transactions_count = current_app.config['TRANSACTIONS'].count({'user_id': request.user_id})

      if transactions_count > 10000:
          return jsonify({
              'error': 'Export muito grande. Entre em contato com suporte.',
              'transactions_count': transactions_count
          }), 413  # Payload Too Large

      # ... resto do código de streaming
  ```

- [ ] 3.2.3 - Testar export com muitos dados
  ```bash
  # Criar usuário de teste com 1000+ transações
  # Fazer export
  # Verificar que streaming funciona sem timeout
  ```

**Validação:**
```bash
# Export deve usar streaming
# Não deve carregar tudo em memória
# Deve ter rate limit e limite de tamanho
```

---

## 🟢 FASE 4 - VULNERABILIDADES BAIXAS (1 MÊS)

### ✅ Task 4.1: Escapar Regex Inputs
**Prioridade:** 🟢 BAIXA | **Tempo estimado:** 30min | **Arquivo:** `backend/routes/auth.py`

**Subtarefas:**
- [ ] 4.1.1 - Substituir regex por comparação exata
  ```python
  # backend/routes/auth.py (linhas 129, 193)

  # REMOVER:
  # user = users_collection.find_one({'email': {'$regex': f'^{email}$', '$options': 'i'}})

  # SUBSTITUIR POR (se Supabase):
  user = users_collection.find_by_email(email)  # Usa .eq() internamente

  # OU se MongoDB:
  user = users_collection.find_one({'email': email.lower()})
  # E garantir que email é sempre salvo em lowercase
  ```

- [ ] 4.1.2 - Criar helper para queries case-insensitive
  ```python
  # backend/utils/db_utils.py
  def find_by_email_case_insensitive(collection, email: str):
      """Busca email case-insensitive de forma segura"""
      normalized_email = email.strip().lower()

      # Supabase
      if hasattr(collection, 'find_by_email'):
          return collection.find_by_email(normalized_email)

      # MongoDB - comparação exata (email já deve estar lowercase)
      return collection.find_one({'email': normalized_email})
  ```

- [ ] 4.1.3 - Usar helper em todos os lugares
  ```bash
  # Buscar todas as queries de email
  grep -rn "email.*regex" backend/ --include="*.py"

  # Substituir por helper seguro
  ```

**Validação:**
```bash
# Nenhuma query deve usar regex com input do usuário
# Emails devem ser normalizados (lowercase) no registro
```

---

## 🧪 FASE 5 - TESTES DE SEGURANÇA

### ✅ Task 5.1: Configurar Ferramentas de Segurança
**Tempo estimado:** 2h

**Subtarefas:**
- [ ] 5.1.1 - Instalar e configurar safety (dependency check)
  ```bash
  pip install safety
  safety check --json > security-reports/dependencies.json

  # Adicionar ao CI
  # .github/workflows/security.yml
  name: Security Scan
  on: [push, pull_request]
  jobs:
    security:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v2
        - name: Safety Check
          run: |
            pip install safety
            safety check
  ```

- [ ] 5.1.2 - Instalar e configurar bandit (SAST)
  ```bash
  pip install bandit
  bandit -r backend/ -f json -o security-reports/bandit.json

  # Adicionar ao CI
  - name: Bandit Check
    run: |
      pip install bandit
      bandit -r backend/ -ll  # Apenas medium e high severity
  ```

- [ ] 5.1.3 - Configurar git-secrets
  ```bash
  # macOS
  brew install git-secrets

  # Linux
  git clone https://github.com/awslabs/git-secrets.git
  cd git-secrets && make install

  # Configurar no repo
  cd /path/to/alca-financas
  git secrets --install
  git secrets --register-aws
  git secrets --add 'SUPABASE_SERVICE_ROLE_KEY.*'
  git secrets --add 'JWT_SECRET.*'
  git secrets --add 'SECRET_KEY.*'

  # Scan histórico
  git secrets --scan-history
  ```

- [ ] 5.1.4 - Configurar Snyk ou Dependabot
  ```bash
  # GitHub: Settings > Security > Dependabot alerts > Enable
  # OU criar conta no Snyk.io e conectar repo
  ```

- [ ] 5.1.5 - Criar script de scan completo
  ```bash
  # scripts/security-scan.sh
  #!/bin/bash
  set -e

  echo "=== Security Scan ==="
  mkdir -p security-reports

  echo "1. Dependency scan (safety)..."
  safety check --json > security-reports/dependencies.json || true

  echo "2. SAST (bandit)..."
  bandit -r backend/ -f json -o security-reports/bandit.json || true

  echo "3. Secrets scan (git-secrets)..."
  git secrets --scan || true

  echo "4. OWASP ZAP scan (if running)..."
  # docker run -t owasp/zap2docker-stable zap-baseline.py \
  #   -t http://localhost:8001 \
  #   -r security-reports/zap-report.html || true

  echo "=== Scan completo. Ver security-reports/ ==="
  ```

**Validação:**
```bash
./scripts/security-scan.sh
# Deve executar todos os scans sem erros críticos
```

---

### ✅ Task 5.2: Testes Manuais de Penetração
**Tempo estimado:** 4h

**Subtarefas:**
- [ ] 5.2.1 - Testar RLS (escalada de privilégio)
  ```bash
  # Script: tests/security/test_rls.py
  import requests

  # Criar 2 usuários
  # Login como user A
  # Tentar acessar transações do user B
  # Deve retornar 403 ou dados vazios
  ```

- [ ] 5.2.2 - Testar rate limiting
  ```bash
  # Fazer 10 tentativas de login com senha errada
  # Verificar que bloqueio progressivo funciona
  # Verificar que CAPTCHA aparece após 2 falhas
  ```

- [ ] 5.2.3 - Testar OAuth
  ```bash
  # Tentar forge de token OAuth
  # Verificar que state mismatch retorna erro
  # Verificar que JWT sem assinatura é rejeitado
  ```

- [ ] 5.2.4 - Testar secrets
  ```bash
  # Remover SECRET_KEY do .env
  # Tentar iniciar backend
  # Deve falhar com erro claro
  ```

- [ ] 5.2.5 - Testar CSRF
  ```bash
  # Criar página maliciosa que tenta fazer POST
  # Verificar que SameSite=Lax bloqueia
  ```

- [ ] 5.2.6 - Testar injection
  ```bash
  # Tentar SQL injection em campos de texto
  # Tentar XSS em descriptions
  # Tentar NoSQL injection (se MongoDB)
  ```

**Validação:**
```bash
# Todos os testes de penetração devem falhar (sistema bloqueou ataque)
```

---

### ✅ Task 5.3: OWASP ZAP Scan
**Tempo estimado:** 2h

**Subtarefas:**
- [ ] 5.3.1 - Instalar OWASP ZAP
  ```bash
  # Docker
  docker pull owasp/zap2docker-stable

  # OU download: https://www.zaproxy.org/download/
  ```

- [ ] 5.3.2 - Executar baseline scan
  ```bash
  docker run -t owasp/zap2docker-stable zap-baseline.py \
    -t http://localhost:8001 \
    -r security-reports/zap-baseline.html
  ```

- [ ] 5.3.3 - Executar full scan (demora mais)
  ```bash
  docker run -t owasp/zap2docker-stable zap-full-scan.py \
    -t http://localhost:8001 \
    -r security-reports/zap-full.html
  ```

- [ ] 5.3.4 - Analisar relatório e corrigir issues
  ```bash
  # Abrir security-reports/zap-full.html
  # Corrigir vulnerabilidades encontradas
  ```

**Validação:**
```bash
# ZAP report não deve ter vulnerabilidades críticas ou altas
```

---

### ✅ Task 5.4: Code Review Focado em Segurança
**Tempo estimado:** 4h

**Checklist:**
- [ ] 5.4.1 - Revisar todos os endpoints de autenticação
  - [ ] Token validation
  - [ ] Password hashing
  - [ ] Session management

- [ ] 5.4.2 - Revisar autorização em todos os endpoints
  - [ ] Verificação de ownership
  - [ ] Admin checks
  - [ ] RLS enforcement

- [ ] 5.4.3 - Revisar input validation
  - [ ] Todos os inputs validados
  - [ ] Sanitização apropriada
  - [ ] Type checking

- [ ] 5.4.4 - Revisar secrets e configurações
  - [ ] Nenhum secret hardcoded
  - [ ] .env.example atualizado
  - [ ] .gitignore correto

- [ ] 5.4.5 - Revisar logging
  - [ ] Sem dados sensíveis
  - [ ] Audit logs implementados
  - [ ] Error handling seguro

**Validação:**
```bash
# Code review completo sem issues de segurança
```

---

### ✅ Task 5.5: Documentar Práticas de Segurança
**Tempo estimado:** 2h

**Subtarefas:**
- [ ] 5.5.1 - Criar SECURITY.md
  ```markdown
  # Security Policy

  ## Reporting Vulnerabilities
  Email: security@alcahub.com.br

  ## Security Measures
  - Row Level Security (RLS)
  - JWT authentication
  - Rate limiting
  - CAPTCHA after failed attempts
  - Audit logging
  - HTTPS only in production

  ## Secure Deployment
  - Use strong secrets (32+ chars)
  - Enable HTTPS
  - Configure CORS appropriately
  - Regular dependency updates
  ```

- [ ] 5.5.2 - Atualizar README com security badges
  ```markdown
  # Alca Finanças

  ![Security Scan](https://github.com/user/repo/workflows/Security%20Scan/badge.svg)
  ![Dependencies](https://img.shields.io/badge/dependencies-up%20to%20date-brightgreen)
  ```

- [ ] 5.5.3 - Criar guia de deployment seguro
  ```bash
  touch docs/SECURE_DEPLOYMENT.md
  # Documentar:
  # - Como gerar secrets
  # - Como configurar HTTPS
  # - Como configurar firewall
  # - Como monitorar logs
  ```

**Validação:**
```bash
# Documentação de segurança completa e atualizada
```

---

## 📊 Tracking de Progresso

### Como Usar Este TODO
1. Trabalhe de cima para baixo (Fase 1 → Fase 5)
2. Marque checkboxes conforme completa: `- [x]`
3. Commit após cada fase completada
4. Não pule fases críticas

### Comandos Úteis
```bash
# Ver progresso
grep -c "\- \[x\]" SECURITY_FIXES_TODO.md
grep -c "\- \[ \]" SECURITY_FIXES_TODO.md

# Criar branch para fixes
git checkout -b security-fixes

# Commit após cada task
git add .
git commit -m "security: [Task X.Y] Descrição"

# Após FASE 1 completa, fazer PR urgente
git push origin security-fixes
```

---

## ⚠️ AVISOS IMPORTANTES

### CRÍTICO
- **NÃO** deploy em produção até FASE 1 estar 100% completa
- **NÃO** commitar secrets ou .env ao git
- **NÃO** pular validações de cada task

### Após Cada Fase
1. ✅ Executar testes automatizados
2. ✅ Executar security scan
3. ✅ Code review
4. ✅ Deploy em staging
5. ✅ Testes manuais de segurança
6. ✅ Deploy em produção (apenas após FASE 1)

### Contatos de Emergência
- Lead Dev: [seu-email]
- Security Team: security@alcahub.com.br
- Supabase Support: https://supabase.com/support

---

**Última atualização:** 2026-02-10
**Próxima revisão:** Após completar cada fase
