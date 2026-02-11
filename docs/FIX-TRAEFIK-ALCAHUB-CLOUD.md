# Correção: alcahub.cloud mostra Traefik em vez do frontend

> **Comandos prontos:** veja [COMANDOS-FIX-TRAEFIK-ALCAHUB.md](./COMANDOS-FIX-TRAEFIK-ALCAHUB.md) para copiar e colar no terminal.

## Problema

- Acessar `https://alcahub.cloud` exibe o **dashboard do Traefik** em vez do **frontend do Alca Finanças**
- O Traefik está capturando o domínio principal antes do router do frontend

## Causa

O router do Traefik dashboard está com prioridade ou regra que pega `alcahub.cloud` antes do frontend.

## Solução

### 1. SSH no VPS

```bash
ssh root@76.13.239.220
```

### 2. Localizar a configuração do Traefik

O Traefik pode estar em:
- `docker-compose.yml` na raiz ou em `/opt/traefik/`
- Labels nos containers
- Arquivos estáticos em `/etc/traefik/` ou similar

```bash
# Procurar docker-compose com Traefik
find / -name "docker-compose*.yml" 2>/dev/null | xargs grep -l traefik 2>/dev/null

# Procurar config do Traefik
find / -name "traefik*.yml" -o -name "traefik*.toml" 2>/dev/null
```

### 3. Ajustar o roteamento

**Objetivo:**
- `alcahub.cloud` e `www.alcahub.cloud` → **frontend** (porta 8080 ou 80 do container/serviço do frontend)
- `api.alcahub.cloud` → **backend** (porta 8001)
- `traefik.alcahub.cloud` ou `alcahub.cloud:8081` → **dashboard do Traefik** (evitar conflito)

**Opção A – Traefik em subdomínio**

Mover o dashboard do Traefik para `traefik.alcahub.cloud`:

```yaml
# Exemplo de labels no Traefik (se usar Docker)
labels:
  # Dashboard apenas em subdomínio separado
  - "traefik.http.routers.traefik-dashboard.rule=Host(`traefik.alcahub.cloud`)"
  - "traefik.http.routers.traefik-dashboard.service=api@internal"
```

**Opção B – Definir prioridade dos routers**

Garantir que o frontend tenha prioridade maior que o dashboard:

```yaml
# Router do frontend (ALTA prioridade)
- "traefik.http.routers.alcahub-frontend.rule=Host(`alcahub.cloud`) || Host(`www.alcahub.cloud`)"
- "traefik.http.routers.alcahub-frontend.priority=100"

# Router do dashboard (BAIXA prioridade, ou path específico)
- "traefik.http.routers.traefik-dashboard.rule=Host(`alcahub.cloud`) && PathPrefix(`/traefik`)"
- "traefik.http.routers.traefik-dashboard.priority=1"
```

### 4. Verificar em qual porta o frontend está

```bash
# Serviços na porta 80
ss -tlnp | grep ':80'

# Serviços na porta 8080
ss -tlnp | grep ':8080'

# Containers Docker
docker ps
```

O frontend do Alca Finanças deve estar em alguma porta (ex.: 8080). O Traefik deve encaminhar `alcahub.cloud` para essa porta.

### 5. Exemplo de configuração do frontend no Traefik

```yaml
# Docker Compose - serviço frontend
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.alcahub-frontend.rule=Host(`alcahub.cloud`) || Host(`www.alcahub.cloud`)"
  - "traefik.http.routers.alcahub-frontend.entrypoints=websecure"
  - "traefik.http.routers.alcahub-frontend.tls.certresolver=letsencrypt"
  - "traefik.http.services.alcahub-frontend.loadbalancer.server.port=80"
```

Se o frontend estiver em outro host (ex.: `host.docker.internal:8080`), ajuste o `loadbalancer.server.port` e o host conforme o cenário.

### 6. Reiniciar o Traefik

```bash
cd /caminho/do/docker-compose
docker compose down
docker compose up -d
# ou
docker-compose restart traefik
```

### 7. Testar

```bash
# Frontend
curl -k -I https://alcahub.cloud

# API
curl -k https://api.alcahub.cloud/api/health
```

No navegador: `https://alcahub.cloud` deve mostrar o app Alca Finanças (login/dashboard), não o Traefik.

---

## Checklist rápido

- [ ] Frontend ouvindo em alguma porta (80 ou 8080)
- [ ] Router do Traefik para `alcahub.cloud` apontando para o serviço do frontend
- [ ] Dashboard do Traefik em subdomínio (`traefik.alcahub.cloud`) ou em path diferente (`/traefik`)
- [ ] Prioridade do router do frontend maior que a do dashboard
- [ ] DNS: `traefik.alcahub.cloud` → 76.13.239.220 (se usar subdomínio para o dashboard)
