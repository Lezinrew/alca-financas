# ENVIRONMENTS.md - Alça Finanças

**Última atualização:** 2026-04-09  
**Status:** Em validação (P0 críticos identificados)

---

## Visão Geral

O projeto possui 3 ambientes principais:

| Ambiente | Finalidade | Docker Compose | Backend | Frontend |
|----------|------------|----------------|---------|----------|
| Dev Local | Desenvolvimento | `docker-compose.yml` + `docker-compose.dev.yml` | Flask debug | Vite HMR |
| Staging | Testes pré-produção | `docker-compose.prod.yml` | Gunicorn | Nginx estático |
| Produção | VPS Hostinger | `docker-compose.prod.yml` | Gunicorn | Nginx estático |

---

## Variáveis de Ambiente Críticas

### Backend (.env)

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# JWT (⚠️ P0: deve ser igual em todos os serviços)
SUPABASE_JWT_SECRET=your-jwt-secret-min-32-chars

# Flask
FLASK_ENV=development  # ou production
SECRET_KEY=your-flask-secret-key
CORS_ORIGINS=http://localhost:3000,https://alcahub.cloud

# Rate Limiting
RATELIMIT_ENABLED=true

# OpenClaw (chatbot)
OPENCLAW_GATEWAY_URL=http://localhost:8080
```

### Frontend (.env)

```bash
# API URL
VITE_API_URL=http://localhost:8001  # dev
# VITE_API_URL=https://api.alcahub.cloud  # prod

# WebSocket Chat
VITE_CHAT_WS_URL=ws://localhost:8100/api/chat/ws  # dev
# VITE_CHAT_WS_URL=wss://chat.alcahub.com.br/api/chat/ws  # prod

# Feature Flags
VITE_ENABLE_CHATBOT=true
VITE_ENABLE_IMPORT_CSV=true
```

### Chatbot (.env)

```bash
# JWT (⚠️ P0: deve bater com SUPABASE_JWT_SECRET)
JWT_SECRET=your-jwt-secret-min-32-chars
# ou
SUPABASE_JWT_SECRET=your-jwt-secret-min-32-chars

# OpenClaw
OPENCLAW_GATEWAY_URL=http://localhost:8080
OPENCLAW_API_KEY=your-openclaw-key

# FastAPI
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8100
```

---

## Docker Compose por Ambiente

### Dev Local

**Arquivo:** `docker-compose.yml`

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python app.py  # Flask debug
    volumes:
      - ./backend:/app  # Hot-reload
    ports:
      - "8001:8001"
    env_file:
      - backend/.env
  
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    command: npm run dev
    volumes:
      - ./frontend/src:/app/src  # Hot-reload
    ports:
      - "3000:3000"
  
  chatbot:
    build:
      context: ./services/chatbot
      dockerfile: Dockerfile
    command: uvicorn app:app --reload --host 0.0.0.0 --port 8100
    volumes:
      - ./services/chatbot:/app
    ports:
      - "8100:8100"
```

**Override Dev:** `docker-compose.dev.yml`

```yaml
services:
  backend:
    environment:
      - FLASK_ENV=development
      - FLASK_DEBUG=1
  
  frontend:
    environment:
      - VITE_API_URL=http://localhost:8001
```

---

### Produção (VPS Hostinger)

**Arquivo:** `docker-compose.prod.yml`

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile.prod
    command: gunicorn --bind 0.0.0.0:8001 --workers 4 app:app
    # ⚠️ Sem volumes (código imutável)
    env_file:
      - backend/.env.prod
    depends_on:
      - openclaw-bridge
  
  frontend:
    image: nginx:alpine
    volumes:
      - ./build/frontend:/usr/share/nginx/html:ro  # ⚠️ P0: deve existir
    # ⚠️ P0: chatbot ausente
  
  openclaw-gateway:
    image: openclaw/gateway:latest
    ports:
      - "8080:8080"
  
  openclaw-bridge:
    image: openclaw/bridge:latest
```

**⚠️ P0 Confirmados:**
1. Serviço `chatbot` não definido
2. `build/frontend/` pode não existir
3. Sem health checks

---

## Nginx (VPS Hostinger)

**Config:** `/etc/nginx/conf.d/alcahub.conf` ou `nginx/conf.d/alcahub.conf`

```nginx
upstream backend {
    server backend:8001;
}

upstream frontend {
    server frontend:80;
}

# ⚠️ P0: Falta upstream para chatbot
# upstream chatbot {
#     server chatbot:8100;
# }

server {
    listen 80;
    server_name alcahub.cloud www.alcahub.cloud;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name alcahub.cloud www.alcahub.cloud;
    
    ssl_certificate /etc/letsencrypt/live/alcahub.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/alcahub.cloud/privkey.pem;
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # ⚠️ P0: Falta location para WebSocket do chatbot
    # location /api/chat/ws {
    #     proxy_pass http://chatbot:8100;
    #     proxy_http_version 1.1;
    #     proxy_set_header Upgrade $http_upgrade;
    #     proxy_set_header Connection "upgrade";
    # }
}

# Chatbot subdomínio
server {
    listen 443 ssl http2;
    server_name chat.alcahub.com.br;
    
    ssl_certificate /etc/letsencrypt/live/chat.alcahub.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.alcahub.com.br/privkey.pem;
    
    location / {
        proxy_pass http://chatbot:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## Fluxo de Deploy Real (VPS Hostinger)

### Pré-requisitos

```bash
# SSH na VPS
ssh root@srv1353242.hostinger.com

# Navegar para projeto
cd /var/www/alca-financas
```

### Deploy Passo a Passo

```bash
# 1. Pull das mudanças
git pull origin main

# 2. Build do frontend
cd frontend
npm install
npm run build
cd ..

# 3. Validar build
ls -la build/frontend/  # Deve existir index.html

# 4. Parar containers atuais
docker compose -f docker-compose.prod.yml down

# 5. Build/rebuild dos serviços
docker compose -f docker-compose.prod.yml build --no-cache

# 6. Subir produção
docker compose -f docker-compose.prod.yml up -d

# 7. Validar saúde
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs frontend

# 8. Testar endpoints
curl -I https://alcahub.cloud
curl -I https://api.alcahub.cloud/health
curl -I https://chat.alcahub.com.br

# 9. Limpar imagens antigas
docker image prune -f
```

### Rollback (se necessário)

```bash
# Voltar commit anterior
git checkout HEAD~1

# Re-deploy
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

---

## Health Checks

### Endpoints de Saúde

```bash
# Backend
GET /health
# Response: {"status": "ok", "timestamp": "..."}

# Frontend
GET /
# Response: 200 OK (index.html)

# Chatbot (⚠️ P0: ausente em prod)
GET /health
# Response: {"status": "ok"}
```

### Docker Health Check (recomendado adicionar)

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
  
  frontend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  chatbot:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Riscos de Inconsistência Dev vs Prod

| Risco | Dev | Prod | Impacto | Mitigação |
|-------|-----|------|---------|-----------|
| **Backend command** | `python app.py` | `gunicorn` | Bugs de concorrência só aparecem em prod | Testar com gunicorn localmente |
| **Chatbot** | ✅ Presente | ❌ Ausente | Feature não funciona em prod | Adicionar ao docker-compose.prod.yml |
| **Frontend** | Vite HMR | Nginx estático | Build necessário | Script automatizado pré-deploy |
| **Volumes** | Hot-reload | Read-only | Debug difícil em prod | Logs detalhados + staging |
| **JWT Secret** | `.env` local | `.env` VPS | Auth falha se dessincronizar | Documentar + validar no deploy |
| **CORS** | localhost:3000 | alcahub.cloud | Requests bloqueados | Validar CORS_ORIGINS |
| **SSL** | HTTP | HTTPS | Mixed content errors | Usar URLs relativas |

---

## Checklist Pré-Deploy

```bash
# [ ] Git limpo (sem mudanças locais)
git status

# [ ] .env.prod atualizado na VPS
cat backend/.env.prod

# [ ] Build frontend gerado
ls -la build/frontend/

# [ ] JWT secrets alinhados
grep SUPABASE_JWT_SECRET backend/.env.prod
grep JWT_SECRET services/chatbot/.env.prod

# [ ] Docker compose válido
docker compose -f docker-compose.prod.yml config

# [ ] Health checks funcionando
curl https://api.alcahub.cloud/health

# [ ] Logs limpos
docker compose -f docker-compose.prod.yml logs --tail=10
```

---

_Última atualização: 2026-04-09_
