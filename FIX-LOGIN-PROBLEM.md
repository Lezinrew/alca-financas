# 🔧 Corrigindo Problema de Login Travado

## 🔍 Problema Identificado

O login fica travado em "Entrando..." com o erro:
```
Failed to load resource: net::ERR_CONNECTION_TIMED_OUT
api.alcahub.cloud/api/auth/login:1
```

### Causas Identificadas:

1. **CORS mal configurado** - Backend não aceita requisições de `https://alcahub.cloud`
2. **SSL/HTTPS não configurado** - Frontend tenta acessar `https://api.alcahub.cloud` mas nginx só responde HTTP
3. **Backend pode não estar rodando** ou acessível

---

## ✅ Solução Rápida

### Opção 1: Script Automático (RECOMENDADO)

Conecte-se ao servidor e execute o script que corrige tudo:

```bash
# 1. Conectar ao servidor
ssh alcaapp@76.13.239.220

# 2. Ir para o diretório do projeto
cd /home/alcaapp/alca-financas

# 3. Copiar o script (se ainda não estiver lá)
# OU fazer upload do arquivo fix-all-server.sh

# 4. Executar o script com sudo
sudo bash fix-all-server.sh
```

Este script faz automaticamente:
- ✅ Corrige CORS para aceitar `https://alcahub.cloud`
- ✅ Atualiza `FRONTEND_URL` no backend
- ✅ Configura nginx corretamente
- ✅ Oferece configurar SSL se necessário
- ✅ Reinicia os serviços
- ✅ Testa se tudo está funcionando

---

### Opção 2: Diagnóstico Primeiro

Se quiser entender melhor o problema antes de corrigir:

```bash
# 1. Conectar ao servidor
ssh alcaapp@76.13.239.220

# 2. Executar diagnóstico
cd /home/alcaapp/alca-financas
bash diagnose-server.sh
```

O diagnóstico mostrará:
- ✅ Status do backend (rodando ou não)
- ✅ Status do frontend (rodando ou não)
- ✅ Configuração do nginx
- ✅ Certificados SSL
- ✅ Configuração de CORS
- ✅ Conectividade externa

---

### Opção 3: Correção Manual

Se preferir fazer manualmente:

```bash
# 1. Conectar ao servidor
ssh alcaapp@76.13.239.220

# 2. Corrigir CORS no backend
cd /home/alcaapp/alca-financas/backend
cp .env .env.backup
nano .env

# Encontre a linha CORS_ORIGINS e altere para:
# CORS_ORIGINS=https://alcahub.cloud,https://www.alcahub.cloud,http://localhost:3000,http://localhost:5173

# Também verifique FRONTEND_URL:
# FRONTEND_URL=https://alcahub.cloud

# Salve (Ctrl+O) e saia (Ctrl+X)

# 3. Verificar se SSL está configurado
sudo nginx -t
grep "listen 443" /etc/nginx/sites-enabled/alcahub.cloud

# Se não retornar nada, SSL não está configurado
# Configure SSL com:
sudo certbot --nginx -d alcahub.cloud -d www.alcahub.cloud -d api.alcahub.cloud

# 4. Reiniciar serviços
sudo supervisorctl restart alca-backend
sudo supervisorctl restart alca-frontend
sudo systemctl reload nginx

# 5. Verificar status
sudo supervisorctl status
```

---

## 🧪 Testar

Após aplicar as correções:

1. **Limpe o cache do navegador**:
   - Chrome/Edge: `Ctrl+Shift+Delete` → Limpar cache
   - Firefox: `Ctrl+Shift+Delete` → Limpar cache

2. **Acesse**: https://alcahub.cloud/login

3. **Tente fazer login** com suas credenciais

---

## 📋 Verificações Adicionais

Se ainda não funcionar, verifique:

### 1. Backend está rodando?
```bash
curl http://localhost:8001/api/health
# Deve retornar: {"status":"ok"}
```

### 2. Logs do backend
```bash
sudo supervisorctl tail -f alca-backend
# Verifique se há erros
```

### 3. Logs do Nginx
```bash
sudo tail -f /var/log/nginx/error.log
# Verifique se há erros CORS ou SSL
```

### 4. Teste a API externamente
```bash
curl -k https://api.alcahub.cloud/api/health
# Deve retornar: {"status":"ok"}
```

---

## 🆘 Suporte

Se o problema persistir:

1. Execute o diagnóstico completo:
   ```bash
   cd /home/alcaapp/alca-financas
   bash diagnose-server.sh > diagnostico.txt
   ```

2. Envie o arquivo `diagnostico.txt` para análise

3. Inclua também:
   - Prints do erro no navegador (Console do DevTools)
   - Resultado dos comandos de verificação acima

---

## 📝 Arquivos Criados

- `diagnose-server.sh` - Script de diagnóstico
- `fix-all-server.sh` - Script de correção automática
- `fix-cors-remote.sh` - Script específico para CORS
- `deploy-cors-fix.sh` - Deploy automático (requer SSH configurado)
- `FIX-LOGIN-PROBLEM.md` - Este arquivo

---

## ⚡ Resumo Rápido

**Problema**: Login travado em "Entrando..."
**Causa**: CORS e/ou SSL não configurados
**Solução**: Execute `sudo bash fix-all-server.sh` no servidor
**Teste**: Limpe cache e tente login em https://alcahub.cloud/login
