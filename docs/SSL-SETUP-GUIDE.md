# 🔒 Guia de Configuração SSL/HTTPS - Alça Finanças

Este guia explica como configurar SSL/HTTPS no seu VPS usando Let's Encrypt.

## 📋 Checklist Pré-Deploy

Antes de começar, verifique:

- [ ] DNS configurado (alcahub.cloud, www, api → 76.13.239.220)
- [ ] Aplicação rodando no VPS (frontend porta 3000, backend porta 8001)
- [ ] Acesso SSH ao servidor VPS
- [ ] Docker Compose instalado e containers rodando

## 🚀 Passo a Passo Completo

### 1️⃣ Verificar DNS Localmente (Execute no seu computador)

```bash
cd /Users/lezinrew/Projetos/alca-financas
./scripts/verify-production.sh
```

✅ Certifique-se de que todos os domínios apontam para **76.13.239.220**

### 2️⃣ Conectar ao VPS

```bash
ssh root@76.13.239.220
# ou
ssh seu-usuario@76.13.239.220
```

### 3️⃣ Preparar Arquivos no Servidor

No seu **computador local**, envie os arquivos necessários:

```bash
# Enviar configuração Nginx
scp /Users/lezinrew/Projetos/alca-financas/nginx-vps.conf root@76.13.239.220:/var/www/alca-financas/

# Enviar script de setup SSL
scp /Users/lezinrew/Projetos/alca-financas/scripts/setup-ssl-production.sh root@76.13.239.220:/var/www/alca-financas/scripts/

# Enviar script de verificação
scp /Users/lezinrew/Projetos/alca-financas/scripts/verify-production.sh root@76.13.239.220:/var/www/alca-financas/scripts/
```

**Ou clone o repositório no servidor:**

```bash
# No servidor VPS
cd /var/www/alca-financas
git pull origin main
```

### 4️⃣ Executar Setup SSL (No servidor VPS)

```bash
cd /var/www/alca-financas

# ⚠️  IMPORTANTE: Edite o script e altere o EMAIL!
nano scripts/setup-ssl-production.sh
# Altere: EMAIL="seu-email@exemplo.com" para seu email real

# Tornar executável (se necessário)
chmod +x scripts/setup-ssl-production.sh

# Executar como root
sudo ./scripts/setup-ssl-production.sh
```

O script vai:
1. ✅ Verificar DNS
2. ✅ Verificar se Docker está rodando
3. ✅ Verificar se a aplicação está respondendo
4. ✅ Instalar Certbot
5. ✅ Configurar Nginx
6. ✅ Obter certificado SSL
7. ✅ Configurar renovação automática

### 5️⃣ Atualizar Variáveis de Ambiente

Após o SSL estar configurado, atualize o `.env` no servidor:

```bash
# No servidor VPS
cd /var/www/alca-financas
nano .env
```

Altere para:
```env
FRONTEND_URL=https://alcahub.cloud
API_BASE_URL=https://alcahub.cloud/api
CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud
```

**Reinicie os containers:**

```bash
docker-compose -f docker-compose.prod.yml restart
```

### 6️⃣ Verificar Funcionamento

**No servidor VPS:**

```bash
cd /var/www/alca-financas
./scripts/verify-production.sh
```

**Ou teste manualmente:**

```bash
# Testar frontend
curl -I https://alcahub.cloud

# Testar API
curl https://alcahub.cloud/api/health

# Ver logs Nginx
sudo tail -f /var/log/nginx/error.log

# Ver logs dos containers
docker-compose -f docker-compose.prod.yml logs -f
```

## 🌐 URLs Finais

Após a configuração:

- **Frontend**: https://alcahub.cloud
- **Frontend (www)**: https://www.alcahub.cloud → redireciona para https://alcahub.cloud
- **API**: https://alcahub.cloud/api

## 🔧 Comandos Úteis

### Verificar Certificados SSL

```bash
sudo certbot certificates
```

### Renovar Certificados (manual)

```bash
sudo certbot renew
```

### Testar Renovação Automática

```bash
sudo certbot renew --dry-run
```

### Ver Status do Nginx

```bash
sudo systemctl status nginx
sudo nginx -t  # Testar configuração
sudo systemctl reload nginx  # Recarregar configuração
```

### Ver Logs

```bash
# Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Certbot
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Containers Docker
docker-compose -f docker-compose.prod.yml logs -f
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend
```

## 🆘 Troubleshooting

### Erro 502 Bad Gateway

**Causa**: Backend não está respondendo

```bash
# Verificar se o backend está rodando
docker-compose -f docker-compose.prod.yml ps backend

# Ver logs do backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Reiniciar backend
docker-compose -f docker-compose.prod.yml restart backend
```

### Erro 503 Service Unavailable

**Causa**: Nginx não consegue se conectar ao upstream

```bash
# Verificar portas
sudo ss -lntp | grep -E ':(80|443|3000|8001)'

# Verificar configuração Nginx
sudo nginx -t

# Ver logs
sudo tail -n 100 /var/log/nginx/error.log
```

### DNS não resolve

**Causa**: Propagação DNS ainda não completou ou configuração incorreta

```bash
# Verificar DNS
dig +short alcahub.cloud A
dig +short www.alcahub.cloud A
dig +short api.alcahub.cloud A

# Deve retornar: 76.13.239.220
```

**Solução**: Aguarde até 48h para propagação ou verifique configuração no Hostinger.

### Certificado SSL expirado

**Causa**: Renovação automática falhou

```bash
# Ver certificados
sudo certbot certificates

# Renovar manualmente
sudo certbot renew --force-renewal

# Verificar cron job
sudo systemctl status certbot.timer
```

### CORS Error

**Causa**: Configuração CORS no backend

```bash
# Verificar .env
cat /var/www/alca-financas/.env | grep CORS

# Deve ter:
# CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# Reiniciar backend
docker-compose -f docker-compose.prod.yml restart backend
```

## 📝 Manutenção

### Renovação Automática

O Certbot configura automaticamente um timer systemd para renovar certificados:

```bash
# Ver status do timer
sudo systemctl status certbot.timer

# Ver próximas execuções
sudo systemctl list-timers certbot
```

### Backup da Configuração

```bash
# Backup manual do Nginx
sudo cp /etc/nginx/sites-available/alcahub.cloud /etc/nginx/sites-available/alcahub.cloud.backup.$(date +%Y%m%d)

# Backup dos certificados (opcional)
sudo tar -czf /root/letsencrypt-backup-$(date +%Y%m%d).tar.gz /etc/letsencrypt/
```

## 🎯 Próximos Passos

Após configurar SSL:

1. ✅ Testar login/cadastro no frontend
2. ✅ Verificar se a API está funcionando
3. ✅ Configurar monitoring (uptime, logs)
4. ✅ Configurar backups automáticos do banco de dados
5. ✅ Adicionar Google Analytics (se necessário)
6. ✅ Configurar CI/CD para deploy automático

## 📚 Referências

- [Let's Encrypt](https://letsencrypt.org/)
- [Certbot Documentation](https://certbot.eff.org/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
