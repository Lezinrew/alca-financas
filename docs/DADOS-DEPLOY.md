# 📋 Dados Necessários para Deploy - Alça Finanças

Este documento lista **todos os dados necessários** para que eu possa fazer o deploy da aplicação Alça Finanças na Hostinger.

---

## 🔐 1. Acesso ao Servidor

### 1.1 Credenciais SSH
- **IP do servidor ou domínio**: `exemplo: 192.168.1.100` ou `servidor.hostinger.com.br`
- **Usuário SSH**: `exemplo: root` ou `usuario`
- **Senha SSH** (se usar autenticação por senha)
- **Chave SSH privada** (se usar autenticação por chave) - formato completo com `-----BEGIN OPENSSH PRIVATE KEY-----`
- **Porta SSH** (padrão: 22)

### 1.2 Tipo de Acesso
- [ ] Acesso root (sudo)
- [ ] Acesso com usuário comum + sudo
- [ ] Acesso apenas com usuário específico

---

## 🌐 2. Configuração de Domínio

### 2.1 Domínio Principal
- **Domínio do frontend**: `exemplo: alca-financas.com.br` ou `www.alca-financas.com.br`
- **Domínio da API** (se separado): `exemplo: api.alca-financas.com.br`
- **Ou usar mesmo domínio**: `exemplo: alca-financas.com.br/api`

### 2.2 DNS Configurado
- [ ] DNS apontando para o IP do servidor
- [ ] Registro A configurado
- [ ] Registro CNAME para www (se aplicável)

---

## 🗄️ 3. Banco de Dados MongoDB

### Opção A: MongoDB Atlas (Recomendado) ⭐

- **Connection String completa**: 
  ```
  mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas
  ```
- **Usuário do MongoDB**: `exemplo: alca_user`
- **Senha do MongoDB**: `senha_segura`
- **Nome do banco**: `exemplo: alca_financas`
- **IP do servidor já adicionado na whitelist do Atlas**: [ ] Sim / [ ] Não

### Opção B: MongoDB Local (Apenas VPS)

- **Host**: `localhost` ou `127.0.0.1`
- **Porta**: `27017` (padrão)
- **Usuário** (se autenticação habilitada): `exemplo: alcaadmin`
- **Senha** (se autenticação habilitada): `senha_segura`
- **Nome do banco**: `exemplo: alca_financas`

---

## 🔑 4. Variáveis de Ambiente - Backend

### 4.1 Configurações Básicas
- **FLASK_ENV**: `production`
- **NODE_ENV**: `production`

### 4.2 MongoDB
- **MONGO_URI**: `mongodb+srv://usuario:senha@cluster.mongodb.net/alca_financas`
- **MONGO_DB**: `alca_financas`

### 4.3 Segurança JWT
- **SECRET_KEY**: `chave_super_segura_min_32_caracteres` 
  - *Posso gerar uma chave segura para você se preferir*
- **JWT_EXPIRES_HOURS**: `24` (ou outro valor desejado)

### 4.4 CORS (Permissões de Origem)
- **CORS_ORIGINS**: 
  ```
  https://alca-financas.com.br,https://www.alca-financas.com.br
  ```
  - *Liste todos os domínios que podem acessar a API*

### 4.5 OAuth (Opcional - Login Social)
- **GOOGLE_CLIENT_ID**: `seu-google-client-id.apps.googleusercontent.com`
- **GOOGLE_CLIENT_SECRET**: `seu-google-client-secret`
- **MICROSOFT_CLIENT_ID**: `seu-microsoft-client-id` (se usar)
- **MICROSOFT_CLIENT_SECRET**: `seu-microsoft-client-secret` (se usar)

---

## 🎨 5. Variáveis de Ambiente - Frontend

### 5.1 URL da API
- **VITE_API_URL**: 
  - Se API em subdomínio: `https://api.alca-financas.com.br`
  - Se API no mesmo domínio: `https://alca-financas.com.br/api`

---

## ⚙️ 6. Configurações do Servidor

### 6.1 Informações do Sistema
- **Sistema Operacional**: `exemplo: Ubuntu 22.04` ou `Debian 11`
- **Usuário do sistema** (para rodar a aplicação): `exemplo: www-data` ou `deploy`
- **Diretório de instalação**: `exemplo: /var/www/alca-financas` (padrão recomendado)

### 6.2 Portas
- **Porta do backend** (Gunicorn): `8001` (padrão) ou outra
- **Porta HTTP**: `80` (padrão)
- **Porta HTTPS**: `443` (padrão)

---

## 📧 7. Email/SMTP (Opcional)

Se quiser enviar emails (recuperação de senha, notificações, etc.):

- **SMTP_HOST**: `exemplo: smtp.gmail.com`
- **SMTP_PORT**: `587` (TLS) ou `465` (SSL)
- **SMTP_USER**: `seu-email@gmail.com`
- **SMTP_PASS**: `senha_do_app` (senha de aplicativo, não a senha normal)
- **SMTP_FROM**: `Alça Finanças <noreply@alca-financas.com.br>`

---

## 🔒 8. SSL/HTTPS

### 8.1 Certificado SSL
- **Método preferido**: 
  - [ ] Let's Encrypt (gratuito, automático) - **Recomendado**
  - [ ] Certificado próprio
  - [ ] Certificado da Hostinger

### 8.2 Email para Let's Encrypt
- **Email para notificações SSL**: `seu-email@exemplo.com`
  - *Usado para avisos de renovação do certificado*

---

## 📦 9. Repositório Git

### 9.1 Acesso ao Código
- **URL do repositório**: `exemplo: https://github.com/seu-usuario/alca-financas.git`
- **Branch para deploy**: `main` ou `master`
- **Método de autenticação**:
  - [ ] HTTPS (usuário/senha ou token)
  - [ ] SSH (chave SSH configurada no servidor)

---

## 🛠️ 10. Preferências de Deploy

### 10.1 Estrutura de Deploy
- **Frontend e API no mesmo domínio**: [ ] Sim / [ ] Não
- **API em subdomínio separado**: [ ] Sim / [ ] Não

### 10.2 Configurações Adicionais
- **Número de workers do Gunicorn**: `automático` (baseado em CPUs) ou número específico
- **Timeout de requisições**: `60` segundos (padrão) ou outro valor
- **Habilitar logs detalhados**: [ ] Sim / [ ] Não

---

## 📝 11. Checklist de Preparação

Antes de iniciar o deploy, confirme:

- [ ] Servidor Hostinger contratado e acessível
- [ ] Acesso SSH funcionando
- [ ] Domínio configurado e apontando para o servidor
- [ ] MongoDB Atlas criado OU MongoDB local instalado
- [ ] Todas as credenciais e chaves disponíveis
- [ ] Repositório Git acessível do servidor
- [ ] Email para certificado SSL (se usar Let's Encrypt)

---

## 🚀 12. Como Fornecer os Dados

### Opção 1: Formulário Seguro
Você pode me fornecer os dados diretamente na conversa. **Importante**: 
- ⚠️ **Nunca compartilhe senhas ou chaves em locais públicos**
- ✅ Use mensagens privadas ou compartilhe de forma segura
- ✅ Após o deploy, considere alterar senhas/chaves

### Opção 2: Arquivo de Configuração
Posso criar um arquivo `.env.example` que você preenche e me envia (sem commitar no Git).

### Opção 3: Variáveis de Ambiente no Servidor
Se preferir, posso configurar diretamente no servidor via SSH.

---

## 🔐 Segurança

### Dados Sensíveis
Os seguintes dados são **CRÍTICOS** e devem ser mantidos em segredo:
- 🔴 Senhas (SSH, MongoDB, SMTP)
- 🔴 Chaves privadas (SSH, JWT SECRET_KEY)
- 🔴 Tokens e secrets (OAuth, API keys)

### Dados Públicos (OK compartilhar)
- ✅ Domínio
- ✅ IP do servidor (público)
- ✅ Estrutura de URLs
- ✅ Nomes de usuários (sem senhas)

---

## 📞 Próximos Passos

Após fornecer os dados:

1. ✅ Validarei todas as informações
2. ✅ Criarei os arquivos de configuração necessários
3. ✅ Executarei o deploy passo a passo
4. ✅ Testarei a aplicação
5. ✅ Fornecerei instruções de manutenção

---

**Última atualização**: Dezembro 2024

