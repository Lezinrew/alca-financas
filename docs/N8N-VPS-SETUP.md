# n8n no VPS (Nginx + SSL + variáveis)

## Script automático (recomendado)

No repositório: [`scripts/setup-n8n-nginx-ssl.sh`](../scripts/setup-n8n-nginx-ssl.sh)

**No servidor** (com o repo em `/var/www/...` ou após copiar o ficheiro):

```bash
cd /caminho/do/alca-financas   # ou só faça scp do .sh para o VPS
sudo bash scripts/setup-n8n-nginx-ssl.sh seu@email.com
```

- Cria o virtual host Nginx para `n8n.alcahub.cloud` (ou `N8N_DOMAIN=...`) com proxy para `127.0.0.1:5678`.
- Instala `nginx` e `certbot` se faltarem (Debian/Ubuntu).
- Corre `certbot --nginx` com o e-mail indicado (renovação automática via systemd timer do certbot).
- Gera `/root/n8n.<domínio>.env` com `N8N_HOST`, `WEBHOOK_URL`, `N8N_EDITOR_BASE_URL`, basic auth e **password aleatório** — guarde o output do terminal.

**Só Nginx (sem TLS ainda):**

```bash
sudo SKIP_CERTBOT=1 bash scripts/setup-n8n-nginx-ssl.sh
```

**Personalizar:**

```bash
export N8N_DOMAIN=n8n.alcahub.cloud
export N8N_PORT=5678
sudo -E bash scripts/setup-n8n-nginx-ssl.sh seu@email.com
```

## Pré-requisitos

1. **DNS**: registo `A` (e `AAAA` se usar IPv6) para o domínio → IP público do VPS.
2. **Firewall**: portas **80** e **443** abertas para o Certbot e HTTPS.
3. **n8n** a servir em `127.0.0.1:5678` (bind local), por exemplo no `docker-compose` do n8n com `N8N_LISTEN_ADDRESS=127.0.0.1` ou equivalente.

## Depois do script

- Copie as variáveis de `/root/n8n.*.env` para o `.env` / compose do **n8n** e reinicie o container/serviço.
- No Telegram (ou outro webhook), use URL **`https://n8n.alcahub.cloud/...`** conforme o path do workflow.

## Copiar só o script (sem git)

No teu Mac:

```bash
scp scripts/setup-n8n-nginx-ssl.sh root@SEU_VPS:/root/
```

No VPS:

```bash
chmod +x /root/setup-n8n-nginx-ssl.sh
sudo /root/setup-n8n-nginx-ssl.sh seu@email.com
```
