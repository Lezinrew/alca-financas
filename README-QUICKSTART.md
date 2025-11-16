# 🚀 Quick Start - Alça Finanças

## Início Rápido (Sem Docker)

### 1️⃣ Pré-requisitos

- **Node.js** 18+ ([Download](https://nodejs.org/))
- **Python** 3.9+ ([Download](https://www.python.org/))
- **MongoDB** (veja opções abaixo)

### 2️⃣ Instalar MongoDB

Escolha uma opção:

#### Opção A: Com Docker (Recomendado)
```bash
# Inicie Docker Desktop primeiro
docker run -d -p 27017:27017 --name alca-mongo mongo:6.0
```

#### Opção B: Instalação Local

**macOS:**
```bash
brew install mongodb-community
brew services start mongodb-community
```

**Ubuntu/Debian:**
```bash
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
```

**Windows:**
1. Baixe: https://www.mongodb.com/try/download/community
2. Instale e inicie o serviço MongoDB

### 3️⃣ Iniciar o Projeto

```bash
# Clone o repositório
git clone <repo-url>
cd alca-financas

# Inicie tudo com um comando
npm start
```

Ou use o script diretamente:
```bash
./scripts/quick-start.sh
```

### 4️⃣ Acessar a Aplicação

Aguarde alguns segundos e acesse:

- 🌐 **Frontend:** http://localhost:3000
- 🔧 **Backend API:** http://localhost:5000
- 🗄️ **MongoDB:** mongodb://localhost:27017

### 5️⃣ Login Demo

Use o **"Login com IA"** para acesso instantâneo com dados de demonstração!

---

## 📝 Comandos Úteis

```bash
# Iniciar tudo
npm start

# Parar todos os serviços
npm stop

# Apenas MongoDB
npm run mongo

# Ver logs
tail -f logs/backend.log
tail -f logs/frontend.log

# Executar testes
npm test
```

---

## 🐛 Problemas Comuns

### MongoDB não conecta

```bash
# Verifique se está rodando
mongosh --eval "db.adminCommand('ping')"

# Se não estiver, inicie:
# Docker:
docker start alca-mongo

# macOS:
brew services start mongodb-community

# Linux:
sudo systemctl start mongod
```

### Porta já em uso

```bash
# Backend (5000) ou Frontend (3000) já em uso?
# Mude as portas no .env:
LOCAL_API_URL=http://localhost:5001
LOCAL_WEB_URL=http://localhost:3001
```

### Permissão negada nos scripts

```bash
chmod +x scripts/*.sh
```

---

## 🔧 Desenvolvimento Avançado

### Com Docker Compose (Completo)

Se preferir usar Docker para tudo:

```bash
# Inicie Docker Desktop primeiro
npm run dev:docker
```

### Apenas Backend

```bash
cd backend
source venv/bin/activate
python app.py
```

### Apenas Frontend

```bash
cd frontend
npm run dev
```

---

## 📚 Próximos Passos

- Leia a [documentação completa](./README.md)
- Veja a [estrutura de testes](./docs/TESTING.md)
- Explore a [API no Postman](./docs/backend_api_qa_checklist.md)

---

**Dúvidas?** Abra uma issue no GitHub!
