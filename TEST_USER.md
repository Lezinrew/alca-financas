# 🔐 Usuário de Teste - Alça Finanças

## Credenciais Padrão

**Email**: `teste@alca.com`  
**Senha**: `1234567`

---

## Como Criar o Usuário de Teste

### Opção 1: Via Registro na Interface (Recomendado)

1. Inicie o projeto: `./alca_start_mac.sh`
2. Acesse: http://localhost:3000
3. Clique em "Registrar" ou "Criar Conta"
4. Preencha:
   - **Nome**: Teste
   - **Email**: teste@alca.com (ou qualquer email)
   - **Senha**: 1234567 (ou qualquer senha)
5. Faça login

### Opção 2: Via Script de Seed (MongoDB Docker)

Se você estiver usando MongoDB via Docker:

```bash
./alca_seed_user.sh
```

**Nota**: Este script só funciona se o MongoDB estiver rodando via Docker com o container `alca_backend`.

### Opção 3: Via MongoDB Direto

Se preferir criar manualmente no MongoDB:

```bash
# Conectar ao MongoDB
mongosh mongodb://localhost:27017/alca_financas

# Criar usuário
db.users.insertOne({
  email: "teste@alca.com",
  name: "Usuário Teste",
  password_hash: "$2b$12$...", // Use bcrypt para gerar
  created_at: new Date()
})
```

### Opção 4: Via API (curl)

```bash
# Registrar novo usuário
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste",
    "email": "teste@alca.com",
    "password": "1234567"
  }'
```

---

## Testando o Login

### Via Interface Web
1. Acesse: http://localhost:3000
2. Faça login com as credenciais acima

### Via API (curl)
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@alca.com",
    "password": "1234567"
  }'
```

Você receberá um token JWT que pode usar para autenticar outras requisições.

---

## Dicas

- **Múltiplos usuários**: Você pode criar quantos usuários quiser via registro
- **Senha esquecida**: Não há recuperação de senha em dev, apenas crie um novo usuário
- **Dados de teste**: Use o endpoint de importação para adicionar transações de exemplo
- **Reset completo**: Para limpar tudo, pare o MongoDB e delete a pasta `mongo_data/`

---

## Troubleshooting

### "Email já cadastrado"
- Use outro email ou delete o usuário existente do MongoDB
- Ou faça login com o usuário existente

### "Credenciais inválidas"
- Verifique se digitou o email e senha corretamente
- Certifique-se de que o usuário foi criado com sucesso
- Verifique os logs do backend: `tail -f logs/backend-*.log`

### Script de seed não funciona
- Certifique-se de que o MongoDB está rodando via Docker
- Verifique se o container `alca_backend` existe
- Use a Opção 1 (registro via interface) como alternativa
