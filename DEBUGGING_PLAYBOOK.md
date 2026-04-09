# DEBUGGING_PLAYBOOK.md - Alça Finanças

**Última atualização:** 2026-04-09  
**Status:** Ativo

---

## Backend (Flask)

### 1. Backend não inicia

**Sintoma:** `docker compose up backend` falha ou container fica reiniciando

**Diagnóstico:**
```bash
# Ver logs
docker compose logs backend

# Ver status
docker compose ps backend

# Testar localmente
cd backend
python app.py
```

**Causas comuns:**
- `.env` ausente ou variáveis faltando
- Supabase credentials inválidas
- Porta 8001 em uso
- Dependencies não instaladas

**Solução:**
```bash
# Validar .env
cat backend/.env | grep -E "SUPABASE|SECRET"

# Instalar dependencies
cd backend
pip install -r requirements.txt

# Testar conexão Supabase
python -c "from supabase import create_client; print('OK')"
```

---

### 2. JWT Auth falha (401/403)

**Sintoma:** Login funciona, mas requests subsequentes falham

**Diagnóstico:**
```bash
# Verificar token no localStorage
# DevTools → Application → Local Storage → token

# Validar token (backend)
curl -H "Authorization: Bearer <token>" http://localhost:8001/api/dashboard

# Ver logs do backend
docker compose logs backend | grep -i "jwt\|auth\|token"
```

**Causas comuns:**
- `SUPABASE_JWT_SECRET` diferente entre serviços (⚠️ P0)
- Token expirado (refresh não funcionando)
- RLS policy bloqueando acesso

**Solução:**
```bash
# Alinhar JWT secrets
grep SUPABASE_JWT_SECRET backend/.env
grep JWT_SECRET services/chatbot/.env  # Deve ser igual

# Regenerar token
# Fazer logout → login novamente

# Validar RLS policy no Supabase Dashboard
```

---

### 3. Backend lento ou timeout

**Sintoma:** Requests demoram >5s ou retornam 504

**Diagnóstico:**
```bash
# Ver tempo de resposta
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8001/api/dashboard

# Ver logs de queries lentas
docker compose logs backend | grep -i "slow\|timeout"

# Monitorar conexões Supabase
# Supabase Dashboard → Database → Connection Pool
```

**Causas comuns:**
- Queries sem índice
- Connection pool esgotado
- Gunicorn workers insuficientes

**Solução:**
```sql
-- Adicionar índices (Supabase SQL Editor)
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_date ON transactions(date);
```

```bash
# Aumentar workers (produção)
# docker-compose.prod.yml
command: gunicorn --bind 0.0.0.0:8001 --workers 8 app:app
```

---

## Frontend (React + Vite)

### 1. Frontend não carrega

**Sintoma:** Tela branca ou erro no console

**Diagnóstico:**
```bash
# Ver logs do Vite
docker compose logs frontend

# Ou dev local
cd frontend
npm run dev

# Ver console do navegador
# DevTools → Console
```

**Causas comuns:**
- `VITE_API_URL` incorreto
- Build antigo (cache)
- Erro de import/TypeScript

**Solução:**
```bash
# Validar .env
cat frontend/.env | grep VITE_API_URL

# Limpar cache e rebuild
rm -rf dist/
npm run build

# Hard refresh no navegador
# Ctrl+Shift+R (Windows) ou Cmd+Shift+R (Mac)
```

---

### 2. API calls falham (401/403/500)

**Sintoma:** Toast de erro "Falha na requisição" ou "Não autorizado"

**Diagnóstico:**
```bash
# DevTools → Network → filtrar por "api"
# Ver status code e response body

# Testar endpoint manualmente
curl http://localhost:8001/api/health
```

**Causas comuns:**
- Token expirado
- CORS bloqueando
- Backend fora do ar

**Solução:**
```typescript
// frontend/src/utils/api.ts - validar interceptor
axios.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      // Refresh token logic
    }
    return Promise.reject(error);
  }
);
```

```bash
# Validar CORS no backend
cat backend/.env | grep CORS_ORIGINS
# Deve incluir: http://localhost:3000,https://alcahub.cloud
```

---

### 3. Chat Widget não conecta

**Sintoma:** Chat fica em "Conectando..." ou erro de WebSocket

**Diagnóstico:**
```bash
# DevTools → Console → ver erro WebSocket
# DevTools → Network → WS → ver status

# Testar WebSocket manualmente
wscat -c ws://localhost:8100/api/chat/ws?token=<token>
```

**Causas comuns:**
- Chatbot fora do ar (⚠️ P0 em produção)
- URL WebSocket incorreta
- JWT inválido no handshake
- Nginx sem config WebSocket (⚠️ P0)

**Solução:**
```typescript
// frontend/src/components/chat/ChatWidget.tsx
// Validar URLs
const CHAT_HTTP_BASE = isDevelopment
  ? 'http://127.0.0.1:8100/api/chat'
  : '/api/chatbot/chat';  // ← Deve apontar para backend Flask

const CHATBOT_WS_URL = isDevelopment
  ? 'ws://127.0.0.1:8100/api/chat/ws'
  : `ws(s)://${loc.host}/api/chatbot/ws`;  // ← Precisa de rota nginx
```

```nginx
# nginx/conf.d/alcahub.conf - adicionar WebSocket
location /api/chatbot/ws {
    proxy_pass http://backend:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## Docker

### 1. Docker Desktop não inicia (Windows)

**Sintoma:** Erro `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`

**Diagnóstico:**
```powershell
# Verificar serviço
Get-Service DockerDesktopService

# Verificar WSL2
wsl -l -v
wsl --status
```

**Solução:**
```powershell
# Resetar Docker Desktop
# 1. Fechar Docker Desktop
# 2. Settings → Resources → WSL Integration → Reset

# Ou reinstalar limpo
winget uninstall Docker.DockerDesktop
winget install Docker.DockerDesktop

# Alternativa: usar WSL2 nativo
wsl -d Ubuntu-24.04
cd /mnt/c/Users/lezin/Downloads/project/alca-financas
docker compose up
```

---

### 2. Container não sobe

**Sintoma:** `docker compose up` falha ou container fica `Exited`

**Diagnóstico:**
```bash
# Ver logs
docker compose logs <serviço>

# Ver por que saiu
docker inspect <container_id> | grep -A 10 "State"

# Testar build
docker compose build --no-cache <serviço>
```

**Causas comuns:**
- Porta em conflito
- Volume mount inválido
- Health check falhando
- Dependencies não prontas

**Solução:**
```bash
# Ver portas em uso
netstat -ano | findstr :8001
netstat -ano | findstr :3000

# Matar processo
taskkill /PID <pid> /F

# Validar volumes
docker compose config  # Ver se paths existem
```

---

### 3. Build frontend falha

**Sintoma:** `npm run build` erro ou `build/frontend/` vazio

**Diagnóstico:**
```bash
cd frontend
npm run build 2>&1 | tee build.log

# Ver último erro
tail -50 build.log
```

**Causas comuns:**
- `node_modules` corrompido
- TypeScript errors
- Variáveis de ambiente faltando

**Solução:**
```bash
# Limpar e reinstall
rm -rf node_modules package-lock.json
npm install

# Build com mais logs
npm run build -- --debug

# Validar .env
cat .env | grep VITE_
```

---

## Chatbot

### 1. Chatbot não responde

**Sintoma:** Mensagem enviada, sem resposta

**Diagnóstico:**
```bash
# Ver se chatbot está rodando
docker compose ps chatbot

# Ver logs
docker compose logs chatbot

# Testar endpoint HTTP
curl -X POST http://localhost:8100/api/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "olá"}'
```

**Causas comuns:**
- Chatbot fora do ar (⚠️ P0 em produção)
- OpenClaw gateway indisponível
- JWT validation falhando

**Solução:**
```bash
# Validar JWT secret alinhado
grep SUPABASE_JWT_SECRET backend/.env
grep JWT_SECRET services/chatbot/.env

# Testar OpenClaw
curl http://localhost:8080/health

# Reiniciar chatbot
docker compose restart chatbot
```

---

### 2. WebSocket desconecta

**Sintoma:** Chat conecta e cai após alguns segundos

**Diagnóstico:**
```bash
# DevTools → Console → ver erro
# DevTools → Network → WS → ver close code
```

**Causas comuns:**
- Nginx timeout (⚠️ P0)
- Token expirado
- Backend não suporta WebSocket

**Solução:**
```nginx
# nginx/conf.d/alcahub.conf
location /api/chat/ws {
    proxy_pass http://chatbot:8100;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    # Timeout para WebSocket
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
}
```

---

## Supabase

### 1. RLS Policy bloqueando

**Sintoma:** Query retorna 0 rows ou erro "permission denied"

**Diagnóstico:**
```sql
-- Supabase SQL Editor
-- Ver policies atuais
SELECT * FROM pg_policies WHERE tablename = 'transactions';

-- Testar como user
SET LOCAL ROLE authenticated;
SET request.jwt.claims = '{"sub": "user-id"}';
SELECT * FROM transactions;
```

**Solução:**
```sql
-- Policy padrão para multi-tenant
CREATE POLICY "Users can view own data"
ON transactions FOR SELECT
USING (user_id = auth.uid());
```

---

### 2. Migration falha

**Sintoma:** `supabase db push` erro ou schema desatualizado

**Diagnóstico:**
```bash
# Ver migrations pendentes
supabase db diff

# Ver último erro
supabase db push --debug
```

**Solução:**
```bash
# Reset local (cuidado: perde dados)
supabase db reset

# Ou aplicar migration específica
supabase migration up --include-all
```

---

## Comandos Úteis

### Logs em Tempo Real
```bash
# Todos os serviços
docker compose logs -f

# Serviço específico
docker compose logs -f backend

# Últimas 50 linhas
docker compose logs --tail=50 backend
```

### Restart Rápido
```bash
# Restart单个服务
docker compose restart backend

# Restart todos
docker compose restart

# Rebuild + restart
docker compose up -d --build
```

### Limpeza
```bash
# Imagens órfãs
docker image prune -f

# Containers parados
docker container prune -f

# Volumes (cuidado!)
docker volume prune -f
```

### Saúde
```bash
# Status geral
docker compose ps

# Health check manual
curl http://localhost:8001/health
curl http://localhost:3000/
curl http://localhost:8100/health
```

---

_Última atualização: 2026-04-09_
