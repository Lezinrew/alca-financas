# 🔧 Fix: Problema de CORS Resolvido

## ❌ Problema

Frontend em `http://localhost:3000` não conseguia acessar Backend em `http://192.168.15.4:8001`:

```
Access to XMLHttpRequest at 'http://192.168.15.4:8001/api/...'
from origin 'http://localhost:3000' has been blocked by CORS policy
```

## ✅ Solução Implementada

### 1. Atualizado `backend/app.py`

**Antes:**
```python
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))
```

**Depois:**
```python
# CORS configuration - permite localhost e IPs locais
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    # Se não especificado, permite localhost em portas comuns
    cors_origins = 'http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000'

CORS(app,
     origins=cors_origins.split(','),
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
```

### 2. Criado `backend/.env`

```bash
# CORS - Permite localhost e IP local
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://192.168.15.4:3000,http://192.168.15.4:5173,http://192.168.15.4:8001
```

### 3. Atualizado `alca_start_mac.sh`

O script agora configura CORS automaticamente incluindo o IP local:

```bash
# Ampliar CORS para IP local
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,http://localhost:3001,http://localhost:3002}"
if [ -n "$HOST_IP" ]; then
  export CORS_ORIGINS="$CORS_ORIGINS,http://$HOST_IP:3000,http://$HOST_IP:3001,http://$HOST_IP:3002"
fi
```

## 🔄 Como Aplicar o Fix

### Opção 1: Reiniciar com o script

```bash
# Parar tudo
kill $(lsof -ti:3000 :8001)

# Reiniciar
./alca_start_mac.sh
```

### Opção 2: Atualizar e reiniciar backend

```bash
# Parar backend
kill $(lsof -ti:8001)

# Editar .env se necessário
nano backend/.env

# Adicionar seu IP local ao CORS_ORIGINS
# CORS_ORIGINS=http://localhost:3000,...,http://SEU_IP:3000

# Reiniciar backend
cd backend
source .venv/bin/activate
python app.py
```

## 🎯 Teste

Após aplicar o fix:

```bash
# 1. Verificar health
curl http://localhost:8001/api/health

# 2. Testar CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     http://localhost:8001/api/health

# Deve retornar headers:
# Access-Control-Allow-Origin: http://localhost:3000
# Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
```

## 📝 Explicação Técnica

### Por que aconteceu?

O backend estava configurado com:
```python
CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))
```

E o `.env` tinha:
```
CORS_ORIGINS=http://localhost:5173,http://localhost
```

Isso **não incluía**:
- ❌ `http://localhost:3000` (porta do frontend)
- ❌ `http://192.168.15.4:*` (IP local)

### Solução

Agora o CORS permite:
- ✅ `http://localhost:3000` - Frontend dev
- ✅ `http://localhost:5173` - Vite padrão
- ✅ `http://localhost:3001` - Portas alternativas
- ✅ `http://127.0.0.1:3000` - Localhost IP
- ✅ `http://192.168.15.4:*` - IP local da rede

E adiciona headers necessários:
- ✅ `supports_credentials=True` - Cookies/Auth
- ✅ `allow_headers=['Content-Type', 'Authorization']` - Headers necessários
- ✅ `methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']` - Métodos HTTP

## 🔒 Segurança

### Desenvolvimento (Local)

```python
# Permite múltiplos origins
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,...
```

### Produção (alcahub.com.br)

```python
# Permite apenas domínio oficial
CORS_ORIGINS=https://alcahub.com.br,https://www.alcahub.com.br
```

**Nunca use `*` em produção!**

## ✅ Checklist de Verificação

Após o fix, verifique:

- [ ] Backend inicia sem erros
- [ ] `curl http://localhost:8001/api/health` retorna `{"status":"ok"}`
- [ ] Frontend carrega sem erros CORS
- [ ] Dashboard mostra dados
- [ ] Transações carregam
- [ ] Categorias carregam
- [ ] Contas carregam

## 🐛 Ainda com Problemas?

### Limpar cache do browser

```bash
# Chrome/Edge
CMD+SHIFT+R (Mac) ou CTRL+SHIFT+R (Win/Linux)

# Ou abrir DevTools > Network > Disable cache
```

### Verificar logs do backend

```bash
tail -f logs/backend-*.log | grep -i cors
```

### Verificar console do browser

Procure por:
- ✅ Sem erros CORS
- ✅ Requisições retornam 200 OK
- ✅ Headers `Access-Control-Allow-Origin` presentes

## 📚 Referências

- [Flask-CORS Documentation](https://flask-cors.readthedocs.io/)
- [MDN - CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [CORS Preflight](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request)

---

**Status:** ✅ Resolvido
**Data:** 15/11/2025
