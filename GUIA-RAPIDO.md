# 🚀 Guia Rápido - Alça Finanças

## ✅ Problema Resolvido: Docker não está rodando

Os scripts foram ajustados para funcionar **com ou sem Docker**!

---

## 🎯 Como Iniciar (3 comandos)

```bash
# 1. Certifique-se que MongoDB está rodando
npm run mongo

# 2. Inicie tudo
npm start

# 3. Acesse
# Frontend: http://localhost:3000 ou http://localhost:5173
# Backend:  http://localhost:8001 ou http://localhost:5000
```

---

## 📦 Primeira Vez?

### 1. Instale MongoDB

**Opção A: Com Docker (Recomendado)**
```bash
# Inicie Docker Desktop primeiro
docker run -d -p 27017:27017 --name alca-mongo mongo:6.0
```

**Opção B: Instalação Local**
```bash
# macOS
brew install mongodb-community
brew services start mongodb-community

# Ubuntu
sudo apt install mongodb
sudo systemctl start mongodb

# Windows
# Baixe e instale: https://www.mongodb.com/try/download/community
```

### 2. Clone e Configure

```bash
git clone <repo>
cd alca-financas
npm start  # Vai instalar tudo automaticamente
```

---

## 🔧 Comandos Disponíveis

```bash
npm start              # Inicia tudo (recomendado)
npm run dev            # Alias para start
npm stop               # Para todos os serviços
npm run mongo          # Apenas MongoDB
npm test               # Todos os testes
npm run test:e2e       # Testes E2E
```

---

## ⚠️ Problemas Comuns

### Porta já em uso

**Erro:** `Port 3000 is already in use`

**Solução:**
```bash
# Encontre o processo
lsof -ti:3000

# Mate o processo
kill -9 $(lsof -ti:3000)

# Ou use outra porta no .env
echo "LOCAL_WEB_URL=http://localhost:3001" >> .env
```

### MongoDB não conecta

**Solução:**
```bash
# Verifique se está rodando
mongosh --eval "db.adminCommand('ping')"

# Se não estiver:
npm run mongo
```

### Backend na porta errada

O backend pode iniciar em diferentes portas:
- `5000` (preferencial)
- `8001` (se 5000 estiver ocupada)

Os scripts detectam automaticamente!

### Docker daemon não está rodando

**Não tem problema!** Os scripts agora funcionam sem Docker se você tiver MongoDB instalado localmente.

---

## 📍 Estrutura de Portas

| Serviço | Porta Preferencial | Porta Alternativa |
|---------|-------------------|-------------------|
| Frontend | 3000 | 5173 (Vite) |
| Backend | 5000 | 8001 |
| MongoDB | 27017 | - |

---

## 📝 Ver Logs em Tempo Real

```bash
# Backend
tail -f logs/backend.log

# Frontend
tail -f logs/frontend.log

# Ambos
tail -f logs/*.log
```

---

## 🧪 Testes

```bash
# Todos os testes
npm test

# Apenas unitários
npm run test:unit

# Apenas E2E
npm run test:e2e

# E2E em produção
npm run test:e2e:prod
```

---

## 🚀 Deploy em Produção

```bash
# Requer configuração de secrets
npm run deploy:prod
```

---

## 📚 Documentação Completa

- [README Principal](./README.md)
- [Guia de Testes](./docs/TESTING.md)
- [Quick Start Detalhado](./README-QUICKSTART.md)
- [API Checklist](./docs/backend_api_qa_checklist.md)

---

## 🆘 Ainda com Problemas?

1. **Limpe tudo e recomece:**
```bash
npm stop
rm -rf backend/venv frontend/node_modules
npm start
```

2. **Verifique os logs:**
```bash
tail -f logs/*.log
```

3. **Abra uma issue:**
https://github.com/lezinrew/alca-financas/issues

---

**Desenvolvido com ❤️ pela equipe Alça Finanças**
