#!/usr/bin/env bash
#
# Configuração automática no VPS: Nginx (proxy → n8n) + Certbot + ficheiro .env de exemplo.
#
# PRÉ-REQUISITOS NO SERVIDOR:
#   - DNS: A/AAAA de N8N_DOMAIN já aponta para este servidor
#   - n8n a escutar em 127.0.0.1:5678 (recomendado) antes ou depois do Nginx
#   - Debian/Ubuntu com nginx instalado
#
# USO (copiar o script para o servidor ou git pull e):
#
#   sudo bash scripts/setup-n8n-nginx-ssl.sh seu@email.com
#
# Variáveis opcionais (antes do comando):
#   export N8N_DOMAIN=n8n.alcahub.cloud
#   export N8N_PORT=5678
#   export CERTBOT_EMAIL=seu@email.com
#   export SKIP_CERTBOT=1          # só Nginx + .env, sem TLS
#   export WEBROOT=/var/www/certbot # para desafio ACME (criado se não existir)
#
set -euo pipefail

N8N_DOMAIN="${N8N_DOMAIN:-n8n.alcahub.cloud}"
N8N_PORT="${N8N_PORT:-5678}"
WEBROOT="${WEBROOT:-/var/www/certbot}"
SKIP_CERTBOT="${SKIP_CERTBOT:-0}"

# E-mail Let's Encrypt: 1º arg ou variável
CERTBOT_EMAIL="${CERTBOT_EMAIL:-${1:-}}"

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Execute como root: sudo bash $0 seu@email.com"
  exit 1
fi

if [[ -z "$CERTBOT_EMAIL" && "$SKIP_CERTBOT" != "1" ]]; then
  echo "Uso:   sudo bash $0 seu@email.com"
  echo "   ou: SKIP_CERTBOT=1 sudo bash $0"
  exit 1
fi

SITE_PATH="/etc/nginx/sites-available/${N8N_DOMAIN}.conf"
ENABLED="/etc/nginx/sites-enabled/${N8N_DOMAIN}.conf"

echo "==> Domínio: $N8N_DOMAIN  |  upstream: 127.0.0.1:${N8N_PORT}"

echo "==> Instalando nginx e certbot (se necessário)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx >/dev/null 2>&1 || true

mkdir -p "$WEBROOT"
chown -R www-data:www-data "$WEBROOT" 2>/dev/null || chown -R nginx:nginx "$WEBROOT" 2>/dev/null || true

if [[ -f "$SITE_PATH" ]]; then
  echo "==> Backup de $SITE_PATH"
  cp -a "$SITE_PATH" "${SITE_PATH}.bak.$(date +%Y%m%d%H%M%S)"
fi

echo "==> Escrevendo virtual host Nginx"
cat >"$SITE_PATH" <<NGINX
# n8n — gerado por setup-n8n-nginx-ssl.sh
server {
    listen 80;
    listen [::]:80;
    server_name ${N8N_DOMAIN};

    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
        try_files \$uri =404;
    }

    location / {
        proxy_pass http://127.0.0.1:${N8N_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX

ln -sf "$SITE_PATH" "$ENABLED"

echo "==> Testando e recarregando Nginx"
nginx -t
systemctl reload nginx

echo "==> HTTP local (Host header):"
curl -sI -H "Host: ${N8N_DOMAIN}" "http://127.0.0.1/" | head -5 || true

if [[ "$SKIP_CERTBOT" == "1" ]]; then
  echo "==> SKIP_CERTBOT=1 — não foi pedido certificado. Configure TLS manualmente."
else
  echo "==> Emitindo certificado Let's Encrypt (certbot --nginx)..."
  certbot --nginx \
    -d "$N8N_DOMAIN" \
    --non-interactive \
    --agree-tos \
    -m "$CERTBOT_EMAIL" \
    --redirect \
    || { echo "AVISO: certbot falhou (DNS ainda não propagou? firewall 80/443?). Nginx HTTP já está ativo."; }
fi

# Password aleatório para basic auth (utilizador pode alterar no .env do n8n)
N8N_BASIC_AUTH_USER="${N8N_BASIC_AUTH_USER:-admin}"
N8N_BASIC_AUTH_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"

ENV_OUT="${N8N_ENV_OUT:-/root/n8n.${N8N_DOMAIN}.env}"

echo "==> Escrevendo variáveis sugeridas em: $ENV_OUT"
cat >"$ENV_OUT" <<ENV
# Copie estas linhas para o .env do n8n (docker-compose ou serviço).
# NUNCA commite este ficheiro.

N8N_HOST=${N8N_DOMAIN}
N8N_PROTOCOL=https
WEBHOOK_URL=https://${N8N_DOMAIN}/
N8N_EDITOR_BASE_URL=https://${N8N_DOMAIN}/
N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER}
N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD}
ENV
chmod 600 "$ENV_OUT"

echo ""
echo "=========================================="
echo "  Nginx: $ENABLED"
echo "  URL:   https://${N8N_DOMAIN}/ (após DNS + certbot OK)"
echo ""
echo "  Credenciais basic auth (GUARDE EM LOCAL SEGURO):"
echo "    Utilizador: ${N8N_BASIC_AUTH_USER}"
echo "    Password:   ${N8N_BASIC_AUTH_PASSWORD}"
echo ""
echo "  Ficheiro completo: $ENV_OUT"
echo "=========================================="
