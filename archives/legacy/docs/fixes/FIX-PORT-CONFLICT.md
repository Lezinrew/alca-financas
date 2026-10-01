# 🔧 Fix: Port 5000 Conflict with macOS AirPlay

## ❌ Problema Identificado

O backend não conseguia iniciar na porta 5000, retornando HTTP 403 Forbidden.

### Root Cause

A porta 5000 é usada pelo serviço **AirPlay Receiver** do macOS (AirTunes), que escuta na porta por padrão.

```bash
$ curl -v http://localhost:5000/api/health
< HTTP/1.1 403 Forbidden
< Server: AirTunes/925.4.1
```

## ✅ Solução Implementada

### 1. Mudança para Porta 8001

Configurado o backend para usar a porta 8001 por padrão, evitando conflito com AirPlay.

**`backend/.env`**
```bash
PORT=8001
```

**`frontend/.env`**
```bash
VITE_API_URL=http://localhost:8001
```

### 2. Atualizado `alca_start_mac.sh`

Modificado o script para preferir porta 8001 ao invés de 5000:

```bash
# Antes:
BACKEND_PORT=5000
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    BACKEND_PORT=8001
fi

# Depois:
BACKEND_PORT=8001  # Preferência por 8001 para evitar AirPlay
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    BACKEND_PORT=5000  # Fallback para 5000 se 8001 ocupada
    if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Ambas as portas ocupadas - abortar"
        exit 1
    fi
fi
```

### 3. Atualizado CORS

Adicionado porta 8001 às origens permitidas:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000,http://localhost:8001
```

## 🎯 Por Que Porta 8001?

### Vantagens:
1. **✅ Não conflita com AirPlay** - Porta 5000 é reservada no macOS
2. **✅ Padrão para Flask alternativo** - 8000-8999 são comuns para APIs
3. **✅ Fácil de lembrar** - Próxima da porta 8000 tradicional
4. **✅ Não requer mudanças no sistema** - Não precisa desabilitar AirPlay

### Por Que o AirPlay usa porta 5000?
O AirPlay Receiver permite que seu Mac receba streams de áudio/vídeo de dispositivos Apple. Ele escuta na porta 5000 TCP para conexões UPnP/DLNA.

## 🔄 Como Aplicar o Fix

### Opção 1: Usar Port 8001 (Recomendado)

```bash
# Já está configurado nos .env
# Apenas reinicie os serviços
./alca_start_mac.sh
```

### Opção 2: Desabilitar AirPlay (Se precisar da porta 5000)

1. Abra **System Settings** (Configurações do Sistema)
2. Vá para **General** → **AirDrop & Handoff**
3. Desmarque **AirPlay Receiver**

```bash
# Ou via linha de comando:
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.AirPlayXPCHelper.plist
```

**⚠️ Aviso:** Isso desabilita o AirPlay no seu Mac.

## ✅ Verificação

### 1. Verificar porta 8001 está livre
```bash
lsof -i :8001
# Não deve retornar nada
```

### 2. Verificar backend responde
```bash
curl http://localhost:8001/api/health
# Deve retornar: {"status":"healthy"}
```

### 3. Verificar frontend está configurado
```bash
cat frontend/.env | grep VITE_API_URL
# Deve mostrar: VITE_API_URL=http://localhost:8001
```

### 4. Testar conexão completa
```bash
# Iniciar serviços
./alca_start_mac.sh

# Verificar logs
tail -f logs/backend-*.log
tail -f logs/frontend-*.log
```

## 📊 Teste Completo

Com os serviços rodando, teste no navegador:

1. Acesse: http://localhost:3000
2. Abra DevTools → Console
3. Execute:
```javascript
console.log(import.meta.env.VITE_API_URL)
// Deve mostrar: http://localhost:8001

fetch('http://localhost:8001/api/health')
  .then(r => r.json())
  .then(console.log)
// Deve mostrar: {status: "healthy"}
```

## 🔍 Diagnóstico

### Como detectar o problema do AirPlay:

```bash
# Verificar se AirPlay está usando porta 5000
lsof -i :5000
# Se mostrar AirPlayXPCHelper, está sendo usado pelo AirPlay

# Verificar com curl
curl -v http://localhost:5000 2>&1 | grep Server
# Se mostrar "Server: AirTunes", é o AirPlay
```

### Como verificar disponibilidade de portas:

```bash
# Verificar portas do projeto
for PORT in 3000 5000 5173 8001 27017; do
    echo -n "Porta $PORT: "
    lsof -i :$PORT >/dev/null 2>&1 && echo "OCUPADA" || echo "LIVRE"
done
```

## 🚀 Status Atual

Após aplicar o fix:

```
✅ MongoDB: Running on port 27017
✅ Backend: Running on port 8001
✅ Frontend: Running on port 3000
✅ CORS: Configured correctly
✅ API URL: http://localhost:8001
```

## 📚 Referências

- [macOS AirPlay Technical Details](https://support.apple.com/en-us/HT204289)
- [Flask Default Ports](https://flask.palletsprojects.com/en/latest/server/)
- [Well-Known Ports](https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers)

## ✅ Checklist

- [x] Identificado conflito com AirPlay na porta 5000
- [x] Configurado backend para porta 8001
- [x] Atualizado frontend para usar porta 8001
- [x] Modificado script de inicialização
- [x] Atualizado CORS para incluir porta 8001
- [x] Testado e verificado funcionamento completo
- [x] Documentado solução e alternativas

---

**Status:** ✅ Resolvido
**Data:** 15/11/2025
**Porta Backend:** 8001
**Porta Frontend:** 3000

**Próximo passo:** Aplicação está rodando e pronta para uso!
