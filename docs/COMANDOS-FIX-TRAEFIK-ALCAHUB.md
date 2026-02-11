# Comandos para corrigir Traefik (alcahub.cloud)

Execute no VPS, na ordem. Ajuste `FRONTEND_PORT` e `BACKEND_PORT` se no seu servidor forem diferentes.

---

## 0. Verificar portas do frontend e backend

```bash
ss -tlnp | grep -E ':80|:8080|:8001'
```

Anote:
- **Frontend:** porta onde o nginx/app está (ex.: 8080 se o Traefik usa 80)
- **Backend:** porta 8001 (gunicorn)

---

## 1. Backup do docker-compose

```bash
cp /docker/n8n/docker-compose.yml /docker/n8n/docker-compose.yml.bak.$(date +%Y%m%d)
```

---

## 2. Criar pasta e arquivo de config dinâmica

```bash
mkdir -p /docker/n8n/traefik-dynamic
```

```bash
cat > /docker/n8n/traefik-dynamic/dynamic.yml << 'EOF'
http:
  routers:
    alcahub-frontend:
      rule: "Host(`alcahub.cloud`) || Host(`www.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: alcahub-frontend
      priority: 100
    alcahub-api:
      rule: "Host(`api.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: alcahub-api
      priority: 100
    traefik-dashboard:
      rule: "Host(`traefik.alcahub.cloud`)"
      entryPoints: ["websecure"]
      service: api@internal
      priority: 1
  services:
    alcahub-frontend:
      loadBalancer:
        servers:
          - url: "http://172.17.0.1:8080"
        passHostHeader: true
    alcahub-api:
      loadBalancer:
        servers:
          - url: "http://172.17.0.1:8001"
        passHostHeader: true
EOF
```

Se o frontend estiver em outra porta (ex.: 3000), edite:

```bash
nano /docker/n8n/traefik-dynamic/dynamic.yml
```

Altere `8080` para a porta correta do frontend e `8001` para a do backend.

---

## 3. Editar o docker-compose do Traefik

```bash
nano /docker/n8n/docker-compose.yml
```

No serviço **traefik**, adicione:

**a) No `command` (ou `args`), inclua:**

```yaml
--providers.file.directory=/etc/traefik/dynamic
--providers.file.watch=true
```

**b) Nos `volumes` do traefik, adicione:**

```yaml
- /docker/n8n/traefik-dynamic:/etc/traefik/dynamic:ro
```

**c) Para desativar o dashboard na raiz do domínio (se ainda estiver ativo):**

```yaml
--api.dashboard=false
```

Ou mantenha o dashboard apenas em `traefik.alcahub.cloud` (já configurado no dynamic.yml).

**Exemplo de bloco traefik completo:**

```yaml
traefik:
  image: traefik
  command:
    - "--api.dashboard=true"
    - "--providers.docker=true"
    - "--providers.docker.exposedbydefault=false"
    - "--providers.file.directory=/etc/traefik/dynamic"
    - "--providers.file.watch=true"
    - "--entrypoints.web.address=:80"
    - "--entrypoints.websecure.address=:443"
    - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
    - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
    # ... outros args existentes
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /docker/n8n/traefik-dynamic:/etc/traefik/dynamic:ro
  ports:
    - "80:80"
    - "443:443"
```

Salve e saia (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 4. Reiniciar o Traefik

```bash
cd /docker/n8n
docker compose down
docker compose up -d
```

Ou, se usar docker-compose:

```bash
cd /docker/n8n
docker-compose down
docker-compose up -d
```

---

## 5. Criar DNS para o dashboard do Traefik

No painel DNS (Hostinger ou outro):

- **Tipo:** A  
- **Nome:** `traefik` (ou `traefik.alcahub.cloud` se o painel pedir o FQDN)  
- **Valor:** `76.13.239.220`  
- **TTL:** 300  

---

## 6. Testar

```bash
# Frontend
curl -sk -I https://alcahub.cloud | head -5

# API
curl -sk https://api.alcahub.cloud/api/health

# Dashboard Traefik (após propagar DNS)
curl -sk -I https://traefik.alcahub.cloud | head -5
```

No navegador:

- `https://alcahub.cloud` → deve mostrar o app Alca Finanças (login/dashboard)
- `https://api.alcahub.cloud/api/health` → `{"status":"ok"}`
- `https://traefik.alcahub.cloud` → dashboard do Traefik

---

## Se o frontend ou backend não estiverem rodando

```bash
# Listar processos nas portas
ss -tlnp
```

Se o frontend não estiver em 8080 ou o backend em 8001, edite o `dynamic.yml` e ajuste as URLs. Depois reinicie o Traefik novamente.
