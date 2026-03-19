# 🔧 Troubleshooting - Ambiente Local

## 🚨 Problemas Comuns e Soluções

### 1. Frontend: `npm: not found`

**Sintoma:**
```
/docker-entrypoint.sh: exec: line 47: npm: not found
frontend container restarting
```

**Causa:** Dockerfile de produção (nginx) sendo usado em dev

**Solução:** ✅ CORRIGIDO
- Criado `frontend/Dockerfile.dev` com Node.js
- `docker-compose.yml` atualizado para usar Dockerfile.dev

**Validar:**
```bash
docker compose ps | grep frontend
# Deve mostrar: Up (não Restarting)
```

---

### 2. OpenClaw Gateway: `Invalid --bind`

**Sintoma:**
```
openclaw-gateway: Invalid --bind (use loopback, lan, tailnet, auto, or custom)
Container restarting
```

**Causa:** Variável `OPENCLAW_GATEWAY_BIND="0.0.0.0"` (valor inválido)

**Solução:** ✅ CORRIGIDO
- Alterado para `OPENCLAW_GATEWAY_BIND="lan"`
- Valores válidos: `loopback`, `lan`, `tailnet`, `auto`, `custom`

**Validar:**
```bash
docker compose logs openclaw-gateway | tail -20
# Não deve mostrar erro de --bind
```

---

### 3. Backend em Flask Debug Server

**Sintoma:**
```
* Serving Flask app 'app'
* Debug mode: on
WARNING: This is a development server. Do not use it in production.
```

**Status:** ⚠️ **INTENCIONAL em DEV**
- Ambiente local usa Flask debug server para hot-reload
- Produção usa Gunicorn (4 workers)

**Se quiser Gunicorn em DEV:**
```yaml
# docker-compose.yml
command: gunicorn --bind 0.0.0.0:8001 --reload app:app
```

---

### 4. OpenClaw não inicia (token faltando)

**Sintoma:**
```
openclaw-gateway: No OPENCLAW_GATEWAY_TOKEN configured
```

**Solução:**
```bash
# Gerar token
openssl rand -hex 32

# Adicionar ao .env
echo "OPENCLAW_GATEWAY_TOKEN=<seu-token-aqui>" >> .env

# Restart
./scripts/local-dev.sh restart
```

---

### 5. Supabase connection error

**Sintoma:**
```
backend: Error connecting to Supabase
```

**Diagnóstico:**
```bash
# Verificar .env
grep SUPABASE .env

# Deve ter:
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

**Solução:**
1. Copiar credenciais do dashboard Supabase
2. Atualizar `.env`
3. Restart: `./scripts/local-dev.sh restart`

---

## 🔍 Comandos de Diagnóstico

### Status Geral
```bash
docker compose ps
```

### Logs de Erro
```bash
# Todos os serviços
docker compose logs | grep -i error

# Backend apenas
docker compose logs backend | tail -50

# Frontend apenas
docker compose logs frontend | tail -50

# OpenClaw
docker compose logs openclaw-gateway | tail -50
```

### Health Checks
```bash
# Backend
curl http://localhost:8001/api/health

# Frontend
curl -I http://localhost:3000

# Docker health status
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

### Rebuild Completo (limpa tudo)
```bash
# CUIDADO: Remove volumes e dados locais
./scripts/local-dev.sh clean

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

---

## 📋 Checklist Pós-Correção

Após correções aplicadas, validar:

- [ ] ✅ Frontend responde em http://localhost:3000
- [ ] ✅ Backend health OK em http://localhost:8001/api/health
- [ ] ✅ Logs sem erro de `npm not found`
- [ ] ✅ OpenClaw gateway sem erro de `Invalid --bind`
- [ ] ✅ Todos containers `Up` (não `Restarting`)
- [ ] ✅ Hot reload funciona (alterar código e ver mudança)

### Comandos de Validação
```bash
# 1. Status de todos os containers
docker compose ps

# Esperado:
# NAME                STATUS        PORTS
# backend            Up (healthy)  0.0.0.0:8001->8001/tcp
# frontend           Up (healthy)  0.0.0.0:3000->3000/tcp
# openclaw-gateway   Up (healthy)
# openclaw-bridge    Up (healthy)

# 2. Health endpoints
curl http://localhost:8001/api/health
# Esperado: {"status":"healthy",...}

curl -I http://localhost:3000
# Esperado: HTTP/1.1 200 OK

# 3. Logs sem erros críticos
docker compose logs --tail=50 | grep -i "error\|fatal\|crash"
# Esperado: Poucos ou nenhum erro
```

---

## 🚀 Workflow de Desenvolvimento Recomendado

### 1. Primeira execução
```bash
# Copiar .env.example para .env
cp .env.example .env

# Editar .env com suas credenciais
# - SUPABASE_URL
# - SUPABASE_SERVICE_ROLE_KEY
# - OPENCLAW_GATEWAY_TOKEN (opcional)

# Subir ambiente
./scripts/local-dev.sh start
```

### 2. Desenvolvimento diário
```bash
# Iniciar
./scripts/local-dev.sh start

# Fazer mudanças no código...
# Hot reload deve detectar automaticamente

# Ver logs em tempo real
./scripts/local-dev.sh logs

# Parar ao fim do dia
./scripts/local-dev.sh stop
```

### 3. Quando algo quebra
```bash
# Restart rápido
./scripts/local-dev.sh restart

# Se não resolver: rebuild
./scripts/local-dev.sh rebuild

# Se ainda não resolver: limpar tudo
./scripts/local-dev.sh clean
./scripts/local-dev.sh start
```

---

## ⚙️ Configuração de Profiles (Opcional)

### Rodar sem OpenClaw
```bash
# Desabilitar OpenClaw no docker-compose.yml
# Adicionar profiles:
#   openclaw-gateway:
#     profiles: [openclaw]
#   openclaw-bridge:
#     profiles: [openclaw]

# Subir apenas backend + frontend
docker compose up -d

# Subir com OpenClaw
docker compose --profile openclaw up -d
```

---

## 📞 Suporte

- **Documentação Deploy**: `DEPLOY.md`
- **Guia CI/CD**: `CICD-GUIDE.md`
- **Scripts**: `scripts/local-dev.sh`
