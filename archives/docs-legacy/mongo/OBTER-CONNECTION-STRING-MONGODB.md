# 📋 Passo a Passo: Obter Connection String do MongoDB Atlas

Este guia mostra como obter a connection string do MongoDB Atlas para configurar o servidor.

---

## 🎯 Objetivo

Obter a connection string completa do MongoDB Atlas para atualizar o `MONGO_URI` no servidor.

---

## 📝 Passo a Passo Completo

### Passo 1: Acessar o MongoDB Atlas

1. Abra seu navegador e acesse: **https://cloud.mongodb.com/**
2. Faça login com sua conta do MongoDB Atlas
3. Você será redirecionado para o dashboard

---

### Passo 2: Navegar até o Cluster

1. No menu lateral esquerdo, procure por **"Database"** (Banco de Dados)
2. Clique em **"Database"** ou **"Clusters"**
3. Você verá uma lista dos seus clusters
4. Clique no cluster que você quer usar (geralmente há apenas um, chamado algo como `Cluster0`)

---

### Passo 3: Conectar ao Cluster

1. No cluster selecionado, você verá um botão verde **"Connect"** (Conectar)
2. Clique no botão **"Connect"**

---

### Passo 4: Escolher Método de Conexão

1. Uma janela modal será aberta com opções de conexão
2. Escolha a opção: **"Connect your application"** (Conectar sua aplicação)
   - Esta opção mostra um ícone de código `</>`
   - **NÃO escolha** "Connect using MongoDB Compass" ou "Connect using Mongo Shell"

---

### Passo 5: Copiar a Connection String

1. Na tela "Connect your application", você verá:
   - Um dropdown com o driver (geralmente já vem selecionado "Node.js")
   - Uma connection string que começa com `mongodb+srv://`
   
2. **Copie a connection string completa**
   - Ela terá o formato: `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   - **IMPORTANTE:** A senha na string estará como `<password>` (placeholder)

---

### Passo 6: Substituir Usuário e Senha

A connection string que você copiou tem placeholders. Você precisa substituir:

1. **`<username>`** → Substitua por: `lezinrew`
2. **`<password>`** → Substitua por: `2GPSrU2fXcQAhEBJ`

**Exemplo:**

**Antes (com placeholders):**
```
mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

**Depois (com suas credenciais):**
```
mongodb+srv://lezinrew:2GPSrU2fXcQAhEBJ@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

### Passo 7: Adicionar Nome do Banco de Dados

1. Na connection string, você verá algo como:
   ```
   mongodb+srv://lezinrew:2GPSrU2fXcQAhEBJ@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

2. **Adicione o nome do banco** antes do `?`:
   ```
   mongodb+srv://lezinrew:2GPSrU2fXcQAhEBJ@cluster0.xxxxx.mongodb.net/alca_financas?retryWrites=true&w=majority
   ```
   
   - Note o `/alca_financas` adicionado antes do `?`

---

### Passo 8: Verificar a Connection String Final

Sua connection string final deve ter este formato:

```
mongodb+srv://lezinrew:2GPSrU2fXcQAhEBJ@cluster0.xxxxx.mongodb.net/alca_financas?retryWrites=true&w=majority
```

**Componentes:**
- ✅ `mongodb+srv://` - Protocolo
- ✅ `lezinrew` - Usuário
- ✅ `2GPSrU2fXcQAhEBJ` - Senha
- ✅ `cluster0.xxxxx.mongodb.net` - Nome do cluster (seu será diferente)
- ✅ `/alca_financas` - Nome do banco de dados
- ✅ `?retryWrites=true&w=majority` - Parâmetros de conexão

---

### Passo 9: Enviar a Connection String

1. **Copie a connection string completa** (com usuário, senha e nome do banco)
2. **Envie para mim** ou execute o script de atualização:

```bash
./scripts/update-mongo-uri-remote.sh "mongodb+srv://lezinrew:2GPSrU2fXcQAhEBJ@cluster0.xxxxx.mongodb.net/alca_financas?retryWrites=true&w=majority"
```

**⚠️ IMPORTANTE:** Substitua `cluster0.xxxxx.mongodb.net` pelo nome real do seu cluster!

---

## 🖼️ Visualização dos Passos

### Tela 1: Dashboard do MongoDB Atlas
```
Menu Lateral:
├── Database
│   └── Clusters
│       └── Cluster0 ← Clique aqui
```

### Tela 2: Botão Connect
```
┌─────────────────────────────────┐
│  Cluster0                       │
│  [Connect] ← Clique aqui        │
└─────────────────────────────────┘
```

### Tela 3: Opções de Conexão
```
┌─────────────────────────────────┐
│  Choose a connection method     │
│                                  │
│  ○ Connect using MongoDB Compass │
│  ○ Connect using Mongo Shell     │
│  ● Connect your application ←    │
│  ○ Connect using VS Code         │
└─────────────────────────────────┘
```

### Tela 4: Connection String
```
┌─────────────────────────────────────────────────────┐
│  Connect your application                          │
│                                                     │
│  Driver: [Node.js ▼]                               │
│                                                     │
│  Connection String:                                │
│  ┌─────────────────────────────────────────────┐   │
│  │ mongodb+srv://<username>:<password>@        │   │
│  │ cluster0.xxxxx.mongodb.net/                 │   │
│  │ ?retryWrites=true&w=majority                │   │
│  └─────────────────────────────────────────────┘   │
│  [📋 Copy] ← Clique para copiar                    │
└─────────────────────────────────────────────────────┘
```

---

## ⚠️ Observações Importantes

### 1. Senhas com Caracteres Especiais

Se sua senha tiver caracteres especiais (como `@`, `#`, `%`, etc.), eles precisam ser **codificados em URL**:

- `@` → `%40`
- `#` → `%23`
- `%` → `%25`
- `&` → `%26`
- `=` → `%3D`
- `+` → `%2B`
- `/` → `%2F`
- `?` → `%3F`

**Exemplo:** Se sua senha fosse `senha@123`, na connection string ficaria `senha%40123`

**Sua senha atual (`2GPSrU2fXcQAhEBJ`) não tem caracteres especiais, então está OK!**

### 2. Nome do Cluster

O nome do cluster pode variar. Exemplos comuns:
- `cluster0.xxxxx.mongodb.net`
- `cluster1.xxxxx.mongodb.net`
- `alca-financas.xxxxx.mongodb.net`

**Use o nome exato que aparece no MongoDB Atlas!**

### 3. Nome do Banco de Dados

O nome do banco que estamos usando é: **`alca_financas`**

Se você quiser usar outro nome, pode, mas precisa ser consistente em todo o projeto.

---

## ✅ Checklist

Use este checklist para garantir que você fez tudo corretamente:

- [ ] Acessei o MongoDB Atlas
- [ ] Naveguei até "Database" → "Clusters"
- [ ] Cliquei no cluster desejado
- [ ] Cliquei em "Connect"
- [ ] Escolhi "Connect your application"
- [ ] Copiei a connection string
- [ ] Substituí `<username>` por `lezinrew`
- [ ] Substituí `<password>` por `2GPSrU2fXcQAhEBJ`
- [ ] Adicionei `/alca_financas` antes do `?`
- [ ] Verifiquei que a connection string está completa
- [ ] Enviei a connection string ou executei o script de atualização

---

## 🚀 Próximos Passos

Após obter a connection string:

1. **Atualizar o servidor remoto:**
   ```bash
   ./scripts/update-mongo-uri-remote.sh "sua-connection-string-aqui"
   ```

2. **Verificar se o backend iniciou:**
   ```bash
   ssh root@alcahub.cloud 'systemctl status alca-financas'
   ```

3. **Testar o login:**
   - Acesse: https://alcahub.cloud/login
   - Clique em "Continuar com Google"
   - Deve funcionar! 🎉

---

## ❌ Problemas Comuns

### Problema 1: Não consigo encontrar "Connect"

**Solução:**
- Certifique-se de que você está na página do cluster
- Procure por um botão verde ou azul com o texto "Connect"
- Algumas versões têm um ícone de conexão (🔌) ao lado do nome do cluster

### Problema 2: A connection string não funciona

**Soluções:**
1. Verifique se substituiu `<username>` e `<password>` corretamente
2. Verifique se adicionou o nome do banco (`/alca_financas`)
3. Verifique se o IP do servidor está na whitelist do MongoDB Atlas
4. Verifique se o usuário e senha estão corretos

### Problema 3: Esqueci a senha do usuário

**Solução:**
- Acesse "Database Access" no MongoDB Atlas
- Encontre o usuário `lezinrew`
- Clique em "Edit" e redefina a senha
- Atualize a connection string com a nova senha

---

## 📞 Precisa de Ajuda?

Se após seguir todos os passos você ainda tiver dúvidas:

1. Envie a connection string que você obteve (você pode mascarar a senha se preferir)
2. Envie um print da tela do MongoDB Atlas
3. Verifique os logs do backend para ver erros específicos

---

**Última atualização:** 24/11/2025

