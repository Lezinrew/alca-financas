# 403 Forbidden em https://alcahub.cloud/

## Causa mais comum (Docker + volume)

O container **nginx** corre como utilizador `nginx` (UID típico **101**). Os ficheiros em `build/frontend/` são criados no host como **root** (build com `docker run` + `cp`). Se as permissões forem restritas (`700` / `600`), o Nginx **não lê** `index.html` e responde **403 Forbidden**.

### Corrigir no servidor (imediato)

```bash
cd /var/www/alca-financas
sudo chmod -R a+rX build/frontend
sudo docker compose -f docker-compose.prod.yml exec -T frontend ls -la /usr/share/nginx/html/
curl -sI http://127.0.0.1:3000/   # deve ser 200
```

Se `index.html` não existir em `build/frontend/`, o build falhou ou não correu — volte a fazer o build do frontend (com `VITE_SUPABASE_*` definidos).

### Opcional: dono alinhado ao nginx no container

```bash
sudo chown -R 101:101 build/frontend
```

(UID 101 = `nginx` na imagem `nginx:alpine`; confirme com `docker compose exec frontend id nginx`.)

---

## Outras causas

1. **Nginx do host (443)** — Se usares SSL no host a apontar para `127.0.0.1:3000`, confirma que o `server_name` e `proxy_pass` estão corretos. Testa primeiro **só** o container: `curl -I http://127.0.0.1:3000/`.

2. **Cloudflare / WAF** — Regra, “Bot Fight”, ou IP bloqueado pode devolver 403. Testa com Cloudflare em “Development mode” ou acede ao IP do servidor (se exposto) para isolar.

3. **Porta errada** — O `docker-compose.prod.yml` expõe o frontend em **3000:80**. O host deve fazer proxy para a porta **3000** do sítio principal (como em [`nginx-vps.conf`](../nginx-vps.conf)).

---

## Prevenção nos workflows

O workflow `deploy-production.yml` executa `chmod -R a+rX build/frontend` após copiar o `dist`, para evitar 403 após deploy.
