#!/bin/bash
###############################################################################
# COMANDOS PARA SETUP SSL - COPIAR E COLAR NO VPS
# Execute estes comandos no servidor VPS (76.13.239.220)
###############################################################################

# ============================================================================
# 1. VERIFICAÇÃO INICIAL (Execute estes primeiro)
# ============================================================================

# Verificar DNS (do seu computador local OU do servidor)
dig +short alcahub.cloud A
dig +short www.alcahub.cloud A
dig +short api.alcahub.cloud A
# Deve retornar: 76.13.239.220

# Verificar se o Docker está rodando
docker ps

# Verificar se a aplicação está rodando
sudo ss -lntp | grep -E ':(80|443|3000|8001)'
# Deve mostrar portas 3000 (frontend) e 8001 (backend) escutando

# Testar frontend local
curl -I http://localhost:3000

# Testar backend local
curl http://localhost:8001/api/health


# ============================================================================
# 2. INSTALAR CERTBOT (Execute no VPS como root/sudo)
# ============================================================================

sudo apt update
sudo apt install -y certbot python3-certbot-nginx


# ============================================================================
# 3. CRIAR DIRETÓRIO PARA CERTBOT
# ============================================================================

sudo mkdir -p /var/www/certbot


# ============================================================================
# 4. COPIAR CONFIGURAÇÃO NGINX (No VPS)
# ============================================================================

cd /var/www/alca-financas

# Backup da configuração atual (se existir)
sudo cp /etc/nginx/sites-available/alcahub.cloud /etc/nginx/sites-available/alcahub.cloud.backup.$(date +%Y%m%d) 2>/dev/null || true

# Copiar nova configuração
sudo cp nginx-vps.conf /etc/nginx/sites-available/alcahub.cloud

# Criar link simbólico
sudo ln -sf /etc/nginx/sites-available/alcahub.cloud /etc/nginx/sites-enabled/

# Remover configuração padrão
sudo rm -f /etc/nginx/sites-enabled/default

# Testar configuração
sudo nginx -t

# Recarregar Nginx
sudo systemctl reload nginx


# ============================================================================
# 5. OBTER CERTIFICADO SSL (Execute no VPS como root/sudo)
# ============================================================================

# ⚠️  ALTERE o email abaixo para o seu email real!
EMAIL="seu-email@exemplo.com"

sudo certbot --nginx \
    -d alcahub.cloud \
    -d www.alcahub.cloud \
    -d api.alcahub.cloud \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --redirect

# Ou use o script automatizado:
# cd /var/www/alca-financas
# sudo ./scripts/setup-ssl-production.sh


# ============================================================================
# 6. VERIFICAR CERTIFICADO
# ============================================================================

sudo certbot certificates

# Testar renovação automática
sudo certbot renew --dry-run


# ============================================================================
# 7. ATUALIZAR .ENV E REINICIAR CONTAINERS
# ============================================================================

cd /var/www/alca-financas

# Editar .env (use nano ou vi)
sudo nano .env

# Altere para:
# FRONTEND_URL=https://alcahub.cloud
# API_BASE_URL=https://alcahub.cloud/api
# CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# Reiniciar containers
docker-compose -f docker-compose.prod.yml restart


# ============================================================================
# 8. TESTES FINAIS
# ============================================================================

# Testar frontend HTTPS
curl -I https://alcahub.cloud

# Testar API HTTPS
curl https://alcahub.cloud/api/health

# Testar redirecionamento HTTP → HTTPS
curl -I http://alcahub.cloud

# Verificar certificado SSL
echo | openssl s_client -servername alcahub.cloud -connect alcahub.cloud:443 2>/dev/null | openssl x509 -noout -dates


# ============================================================================
# 9. MONITORAMENTO E LOGS
# ============================================================================

# Ver logs Nginx em tempo real
sudo tail -f /var/log/nginx/error.log

# Ver logs dos containers
docker-compose -f docker-compose.prod.yml logs -f

# Ver logs apenas do backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Ver logs apenas do frontend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Ver status dos containers
docker-compose -f docker-compose.prod.yml ps


# ============================================================================
# 10. COMANDOS ÚTEIS PÓS-DEPLOY
# ============================================================================

# Reiniciar Nginx
sudo systemctl restart nginx

# Recarregar configuração Nginx (sem downtime)
sudo systemctl reload nginx

# Ver status Nginx
sudo systemctl status nginx

# Renovar certificado manualmente
sudo certbot renew

# Ver timer de renovação automática
sudo systemctl status certbot.timer

# Reiniciar todos os containers
docker-compose -f docker-compose.prod.yml restart

# Parar todos os containers
docker-compose -f docker-compose.prod.yml down

# Iniciar todos os containers
docker-compose -f docker-compose.prod.yml up -d

# Ver uso de recursos
docker stats

# Limpar imagens não utilizadas
docker system prune -a


# ============================================================================
# 11. TROUBLESHOOTING RÁPIDO
# ============================================================================

# Erro 502 - Backend não responde
docker-compose -f docker-compose.prod.yml restart backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Erro 503 - Nginx não consegue conectar
sudo ss -lntp | grep -E ':(3000|8001)'
sudo nginx -t
sudo systemctl restart nginx

# CORS error
# Verifique CORS_ORIGINS no .env e reinicie o backend
cat .env | grep CORS
docker-compose -f docker-compose.prod.yml restart backend

# DNS não resolve
dig +short alcahub.cloud A
# Se não retornar 76.13.239.220, aguarde propagação DNS

# Certificado SSL expirado
sudo certbot certificates
sudo certbot renew --force-renewal


# ============================================================================
# SCRIPT AUTOMATIZADO - USE ESTE SE PREFERIR
# ============================================================================

# Execute este comando para automatizar todo o processo:
cd /var/www/alca-financas
sudo ./scripts/setup-ssl-production.sh
