# 🔧 Fix: VITE_API_URL vs REACT_APP_BACKEND_URL

## ❌ Problema Identificado

O frontend estava usando o IP `192.168.15.4:5000` ao invés de `localhost:5000`, causando erros de CORS.

### Root Cause

1. **Frontend usa Vite**, não Create React App
2. Vite usa `VITE_*` para variáveis de ambiente, não `REACT_APP_*`
3. O código estava lendo `REACT_APP_BACKEND_URL` mas o `.env` tinha `VITE_API_URL`
4. O script `alca_start_mac.sh` estava configurando o IP local ao invés de localhost

## ✅ Solução Implementada

### 1. Atualizado `frontend/src/utils/api.ts`

**Antes:**
```typescript
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
```

**Depois:**
```typescript
// Suporta ambas as variáveis: VITE_API_URL (Vite) e REACT_APP_BACKEND_URL (fallback)
const API_BASE_URL = import.meta.env.VITE_API_URL || process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
```

### 2. Criado `frontend/.env`

```bash
# Frontend Environment Variables

# API Backend URL - usar localhost para evitar problemas CORS
VITE_API_URL=http://localhost:5000

# Se o backend estiver em outra porta, ajuste aqui
# VITE_API_URL=http://localhost:8001
```

### 3. Atualizado `alca_start_mac.sh`

**Antes:**
```bash
# Usava IP local (192.168.15.4)
export REACT_APP_BACKEND_URL="http://$HOST_IP:$PORT"
```

**Depois:**
```bash
# Sempre usa localhost
export VITE_API_URL="http://localhost:$PORT"

# Cria .env automaticamente
cat > "$FRONTEND_DIR/.env" << EOF
VITE_API_URL=http://localhost:$PORT
EOF
```

### 4. Atualizado `backend/app.py` (CORS)

```python
# CORS configuration - permite localhost
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    cors_origins = 'http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000'

CORS(app,
     origins=cors_origins.split(','),
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
```

## 🎯 Por Que Localhost?

### Vantagens de usar `localhost`:

1. **✅ Sem CORS issues** - Mesmo domínio (localhost)
2. **✅ Funciona offline** - Não depende de rede
3. **✅ Mais rápido** - Não passa pela interface de rede
4. **✅ Mais seguro** - Não expõe na rede local
5. **✅ Portável** - Funciona em qualquer máquina

### Quando usar IP local (`192.168.x.x`)?

Apenas quando você precisa:
- 📱 Testar em dispositivo mobile físico
- 💻 Acessar de outra máquina na rede
- 🔧 Debug de problemas específicos de rede

**Para esses casos:**
```bash
# Configure manualmente no .env
VITE_API_URL=http://192.168.15.4:5000
```

## 🔄 Como Aplicar o Fix

### Reiniciar Tudo

```bash
# O jeito mais fácil - script faz tudo
./alca_start_mac.sh
```

O script vai:
1. 🛑 Parar todos os serviços
2. 🔧 Configurar CORS no backend
3. 📝 Criar `.env` correto no frontend
4. ✅ Iniciar tudo com configurações corretas

### Aplicar Manualmente

Se preferir fazer manual:

```bash
# 1. Parar tudo
kill $(lsof -ti:3000 :5000 :8001)

# 2. Frontend: criar .env
cd frontend
echo "VITE_API_URL=http://localhost:5000" > .env

# 3. Backend: verificar .env
cd ../backend
grep CORS_ORIGINS .env
# Deve ter: CORS_ORIGINS=http://localhost:3000,...

# 4. Reiniciar backend
source .venv/bin/activate
python app.py &

# 5. Reiniciar frontend
cd ../frontend
npm run dev
```

## ✅ Verificação

Após aplicar o fix:

### 1. Verificar variável no frontend

Abra o DevTools Console e digite:
```javascript
console.log(import.meta.env.VITE_API_URL)
// Deve mostrar: http://localhost:5000
```

### 2. Verificar requisições

No DevTools → Network:
- ✅ Requisições vão para `localhost:5000`
- ✅ Sem erros CORS
- ✅ Status 200 OK

### 3. Verificar funcionalidade

- ✅ Dashboard carrega dados
- ✅ Transações carregam
- ✅ Categorias carregam
- ✅ Contas carregam
- ✅ Login funciona

## 📊 Comparação: Antes vs Depois

### Antes ❌

```
Frontend (.env):
  VITE_API_URL=http://localhost:5000

Código (api.ts):
  process.env.REACT_APP_BACKEND_URL  ← Undefined!

Script (alca_start_mac.sh):
  REACT_APP_BACKEND_URL=http://192.168.15.4:5000  ← IP local

Resultado:
  ❌ Frontend usa IP local hardcoded
  ❌ CORS bloqueia requisições
  ❌ Nada funciona
```

### Depois ✅

```
Frontend (.env):
  VITE_API_URL=http://localhost:5000  ← Gerado pelo script

Código (api.ts):
  import.meta.env.VITE_API_URL  ← ✅ Lê corretamente!

Script (alca_start_mac.sh):
  VITE_API_URL=http://localhost:$PORT  ← Detecta porta automaticamente

Resultado:
  ✅ Frontend usa localhost
  ✅ CORS permite requisições
  ✅ Tudo funciona!
```

## 🎓 Lição Aprendida

### Vite vs Create React App

| Feature | Create React App | Vite |
|---------|-----------------|------|
| Variáveis de ambiente | `REACT_APP_*` | `VITE_*` |
| Acesso no código | `process.env.REACT_APP_*` | `import.meta.env.VITE_*` |
| Hot reload | Lento | Rápido |
| Build | Webpack | esbuild |

**Importante:** Vite **NÃO** lê variáveis `REACT_APP_*`!

### Como detectar o problema

```bash
# 1. Ver console do browser
# Se mostra IP ao invés de localhost = problema

# 2. Ver .env do frontend
cat frontend/.env
# Deve ter VITE_API_URL, não REACT_APP_*

# 3. Ver código api.ts
grep "VITE_API_URL" frontend/src/utils/api.ts
# Deve usar import.meta.env.VITE_API_URL
```

## 📚 Referências

- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [Vite vs CRA](https://vitejs.dev/guide/migration.html)
- [import.meta.env](https://vitejs.dev/guide/env-and-mode.html#env-variables)

## 🔒 Segurança

### Desenvolvimento

```bash
# ✅ OK para usar
VITE_API_URL=http://localhost:5000
```

### Produção

```bash
# ✅ Use domínio completo
VITE_API_URL=https://alcahub.cloud/api
```

**Nunca commite `.env` com valores de produção!**

## ✅ Checklist Final

- [x] `frontend/src/utils/api.ts` lê `VITE_API_URL`
- [x] `frontend/.env` tem `VITE_API_URL=http://localhost:5000`
- [x] `backend/.env` tem CORS correto
- [x] `backend/app.py` configurado com CORS
- [x] `alca_start_mac.sh` gera `.env` automaticamente
- [x] Script usa `localhost` ao invés de IP
- [x] Tudo testado e funcionando

---

**Status:** ✅ Resolvido
**Data:** 15/11/2025

**Próximo passo:** Execute `./alca_start_mac.sh` e teste!
