# 🚀 Guia de Deploy - Alça Finanças

## 📋 Índice

1. [Scripts Disponíveis](#scripts-disponíveis)
2. [Deploy do Zero (servidor novo)](#deploy-do-zero-servidor-novo)
3. [Deploy Completo (Primeira Vez)](#deploy-completo-primeira-vez)
4. [Update Rápido](#update-rápido)
5. [Troubleshooting](#troubleshooting)

**Servidor novo?** Use o guia **[Deploy do Zero](DEPLOY-DO-ZERO.md)** (comandos em sequência + envio do `.env` com pscp/scp).

---

## Scripts Disponíveis

### ✅ Scripts Atualizados (Usar)

| Script | Uso | Quando Usar |
|--------|-----|-------------|
| **`scripts/deploy-docker-remote.sh`** | Deploy completo com Docker | Primeira instalação, mudanças na infra, rebuild necessário |
| **`scripts/deploy-quick-update.sh`** | Update rápido (git pull + restart) | Mudanças simples no código, hotfixes |

### ⚠️ Scripts Legados (NÃO Usar)

Scripts e docs antigos foram movidos para a pasta **`legacy/`** (ignorada pelo Git). Não use: `deploy-vps.sh`, `deploy-remote.sh`, `deploy-remote.py`, `deploy-cors-fix.sh`, `deploy-hostinger.sh`, etc.

---

## Deploy do Zero (servidor novo)

Servidor novo e primeiro deploy em sequência (inclui envio do `.env` com **pscp** ou **scp**, sem depender do GitHub):

→ **[docs/DEPLOY-DO-ZERO.md](DEPLOY-DO-ZERO.md)**

---

## Deploy Completo (Primeira Vez)

### Pré-requisitos

1. **Servidor VPS com:**
   - Ubuntu/Debian (recomendado)
   - Acesso SSH (root ou sudo)
   - Portas 80 e 443 abertas

2. **Credenciais Supabase:**
   - SUPABASE_URL
   - SUPABASE_SERVICE_ROLE_KEY
   - SUPABASE_ANON_KEY

3. **Domínio configurado:**
   - DNS apontando para IP do servidor
   - Subdomínio opcional para API

### Passo 1: Configurar Variáveis de Ambiente

```bash
export SERVER_HOST="76.13.239.220"           # Seu IP VPS
export SERVER_USER="root"                     # Seu usuário SSH
export SERVER_SSH_KEY="~/.ssh/id_rsa"        # Chave SSH (opcional)
export PROJECT_DIR="/var/www/alca-financas"  # Diretório no servidor
export DOMAIN="alcahub.cloud"                 # Seu domínio
```

### Passo 2: Executar Deploy

```bash
./scripts/deploy-docker-remote.sh
```

### Passo 3: Configurar .env no Servidor

O script criará um `.env.example`. Você precisa editá-lo com suas credenciais:

```bash
ssh root@76.13.239.220

cd /var/www/alca-financas
nano .env
```

**Configuração necessária:**

```env
# Supabase (OBRIGATÓRIO)
SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend
SECRET_KEY=<gerado_automaticamente>
JWT_SECRET=<gerado_automaticamente>
BACKEND_PORT=8001
FLASK_ENV=production

# CORS
CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# Frontend Build
VITE_API_URL=https://alcahub.cloud
VITE_SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Passo 4: Restart Após Configurar .env

```bash
cd /var/www/alca-financas
docker-compose -f docker-compose.prod.yml restart
```

### Passo 5: Verificar Status

```bash
# Ver containers rodando
docker-compose -f docker-compose.prod.yml ps

# Ver logs do backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Ver logs do frontend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Testar API
curl http://localhost:8001/api/health
```

---

## Update Rápido

Use quando fizer mudanças simples no código (Python, JavaScript, CSS):

### Método 1: Script Automático

```bash
export SERVER_HOST="76.13.239.220"
export SERVER_USER="root"

./scripts/deploy-quick-update.sh
```

### Método 2: Manual via SSH

```bash
ssh root@76.13.239.220

cd /var/www/alca-financas
git pull origin main
docker-compose -f docker-compose.prod.yml restart
```

**⚠️ Quando NÃO usar update rápido:**
- Mudanças em Dockerfile
- Novas dependências (requirements.txt, package.json)
- Mudanças no docker-compose.yml
- Mudanças no nginx.conf

**Nesses casos, use o deploy completo.**

---

## Troubleshooting

### 1. Erro 404 ao Recarregar Página

**Causa:** Frontend não está copiando nginx.conf

**Solução:**
```bash
# Já corrigido no commit 11fa4f26
# Fazer rebuild do frontend:
ssh root@76.13.239.220
cd /var/www/alca-financas
docker-compose -f docker-compose.prod.yml build frontend
docker-compose -f docker-compose.prod.yml up -d frontend
```

### 2. Backend Não Inicia

**Verificar logs:**
```bash
ssh root@76.13.239.220
cd /var/www/alca-financas
docker-compose -f docker-compose.prod.yml logs backend
```

**Causas comuns:**
- `.env` não configurado corretamente
- SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY inválidos
- Porta 8001 já em uso

**Solução:**
```bash
# Verificar .env
cat /var/www/alca-financas/.env

# Verificar porta
netstat -tulpn | grep 8001

# Restart
docker-compose -f docker-compose.prod.yml restart backend
```

### 3. Erro de Conexão SSH

**Causas comuns:**
- IP/hostname errado
- Porta SSH não é 22
- Chave SSH não configurada
- Firewall bloqueando

**Solução:**
```bash
# Testar conexão
ssh -v root@76.13.239.220

# Se porta diferente
ssh -p 2222 root@76.13.239.220

# Usar senha ao invés de chave
ssh -o PreferredAuthentications=password root@76.13.239.220
```

### 4. Containers Não Iniciam

**Verificar status Docker:**
```bash
ssh root@76.13.239.220

# Status do Docker daemon
systemctl status docker

# Verificar se há erros
docker ps -a
docker logs <container_id>
```

**Rebuild completo:**
```bash
cd /var/www/alca-financas
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Frontend Mostra Página Branca

**Causas comuns:**
- Build falhou
- Variáveis de ambiente incorretas
- Arquivos não copiados

**Solução:**
```bash
ssh root@76.13.239.220
cd /var/www/alca-financas

# Rebuild frontend
docker-compose -f docker-compose.prod.yml build frontend
docker-compose -f docker-compose.prod.yml up -d frontend

# Verificar logs
docker-compose -f docker-compose.prod.yml logs frontend

# Verificar se arquivos foram gerados
ls -la build/frontend/
```

### 6. CORS Errors no Browser

**Causa:** CORS_ORIGINS não configurado corretamente

**Solução:**
```bash
# Editar .env
nano /var/www/alca-financas/.env

# Adicionar domínio correto
CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud

# Restart
docker-compose -f docker-compose.prod.yml restart backend
```

---

## Comandos Úteis

### Monitoramento

```bash
# Ver todos os logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f

# Ver apenas backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Ver apenas frontend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Ver últimas 100 linhas
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Manutenção

```bash
# Restart todos os containers
docker-compose -f docker-compose.prod.yml restart

# Restart apenas backend
docker-compose -f docker-compose.prod.yml restart backend

# Parar tudo
docker-compose -f docker-compose.prod.yml down

# Iniciar tudo
docker-compose -f docker-compose.prod.yml up -d

# Ver uso de recursos
docker stats
```

### Limpeza

```bash
# Remover containers parados
docker container prune -f

# Remover imagens não usadas
docker image prune -a -f

# Remover volumes não usados
docker volume prune -f

# Limpeza completa (CUIDADO!)
docker system prune -a -f --volumes
```

---

## Checklist de Deploy

- [ ] DNS configurado apontando para servidor
- [ ] Servidor tem portas 80 e 443 abertas
- [ ] Acesso SSH funcionando
- [ ] Credenciais Supabase obtidas
- [ ] `.env` configurado no servidor
- [ ] Docker e Docker Compose instalados
- [ ] SSL/HTTPS configurado (Certbot)
- [ ] Backup do banco de dados (se aplicável)
- [ ] Testes locais passando
- [ ] Git push realizado
- [ ] Deploy executado com sucesso
- [ ] Smoke tests na produção
- [ ] Monitoramento ativo

---

## Suporte

Se encontrar problemas:

1. **Verifique os logs** primeiro
2. **Consulte esta documentação**
3. **Verifique issues no GitHub**
4. **Abra uma issue** com logs detalhados

**Logs importantes:**
- Backend: `docker-compose logs backend`
- Frontend: `docker-compose logs frontend`
- Nginx: `docker-compose logs frontend` (nginx está no container frontend)
- System: `journalctl -xe`
