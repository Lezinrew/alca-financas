# 🎯 Próximo Passo - Deploy para Produção

## ✅ O Que Já Foi Feito

- ✅ Estrutura completa de testes
- ✅ CI/CD pipeline configurado
- ✅ Scripts de automação funcionais
- ✅ Documentação completa

---

## 🚀 Agora: Configurar Produção

Você tem **3 opções** para configurar o ambiente de produção:

---

## Opção 1: Configuração Rápida (Recomendado)

### 1. Instale GitHub CLI

```bash
# macOS
brew install gh

# Ubuntu
sudo apt install gh

# Windows
winget install GitHub.cli
```

### 2. Autentique

```bash
gh auth login
```

### 3. Execute o Script Interativo

```bash
./scripts/setup-github-secrets.sh
```

O script vai pedir:
- Docker username/password
- Host do servidor (alcahub.com.br)
- SSH key
- Telegram (opcional)

### 4. Prepare o Servidor

Siga o guia completo:
```bash
# Leia este arquivo
cat docs/SETUP-PRODUCAO.md
```

Ou acesse online:
https://github.com/seu-usuario/alca-financas/blob/main/docs/SETUP-PRODUCAO.md

---

## Opção 2: Configuração Manual

### 1. Configure Secrets no GitHub

Acesse: https://github.com/seu-usuario/alca-financas/settings/secrets/actions

Adicione os secrets seguindo o template:
```bash
cat .github/SECRETS-TEMPLATE.md
```

### 2. Prepare o Servidor

Siga o passo a passo completo em `docs/SETUP-PRODUCAO.md`

---

## Opção 3: Deploy Local Primeiro

Se ainda não tem servidor, teste localmente:

```bash
# Iniciar ambiente local
npm start

# Executar todos os testes
npm test

# Quando estiver pronto, configure a produção
```

---

## 📋 Checklist de Produção

Siga esta ordem:

### Parte 1: Infraestrutura (30-60 min)

- [ ] **1.1** Contratar/configurar servidor (DigitalOcean, AWS, Vultr)
- [ ] **1.2** Configurar DNS (alcahub.com.br → IP do servidor)
- [ ] **1.3** Instalar Docker no servidor
- [ ] **1.4** Criar usuário `deploy`
- [ ] **1.5** Configurar Nginx
- [ ] **1.6** Instalar SSL/TLS (Let's Encrypt)

**Guia completo:** `docs/SETUP-PRODUCAO.md` (Seções 1-3)

### Parte 2: Banco de Dados (15-30 min)

Escolha uma opção:

- [ ] **2.A** MongoDB Atlas (Recomendado - Grátis)
  - Criar conta em https://mongodb.com/cloud/atlas
  - Criar cluster
  - Obter connection string

OU

- [ ] **2.B** MongoDB Local no Servidor
  - Instalar MongoDB
  - Configurar autenticação

**Guia completo:** `docs/SETUP-PRODUCAO.md` (Seção 4)

### Parte 3: Secrets GitHub (10 min)

- [ ] **3.1** Instalar GitHub CLI (`gh`)
- [ ] **3.2** Autenticar: `gh auth login`
- [ ] **3.3** Executar: `./scripts/setup-github-secrets.sh`

OU configurar manualmente seguindo: `.github/SECRETS-TEMPLATE.md`

### Parte 4: Variáveis Servidor (5 min)

- [ ] **4.1** SSH no servidor: `ssh deploy@alcahub.com.br`
- [ ] **4.2** Criar `.env` em `/var/www/alcahub/.env`
- [ ] **4.3** Adicionar variáveis (MongoDB, JWT, etc)

**Template:** `docs/SETUP-PRODUCAO.md` (Seção 6)

### Parte 5: Primeiro Deploy (10 min)

- [ ] **5.1** Commit código: `git add . && git commit -m "feat: setup produção"`
- [ ] **5.2** Push: `git push origin main`
- [ ] **5.3** Acompanhar: https://github.com/seu-usuario/alca-financas/actions
- [ ] **5.4** Verificar: https://alcahub.com.br

---

## 🎬 Comandos em Sequência

Se você já tem tudo pronto, execute:

```bash
# 1. Configure secrets (se instalou gh CLI)
./scripts/setup-github-secrets.sh

# 2. Commita e faz push
git add .
git commit -m "feat: configuração de produção completa"
git push origin main

# 3. Acompanhe o deploy
gh run watch

# 4. Quando concluir, teste
curl https://api.alcahub.com.br/api/health
curl https://alcahub.com.br
```

---

## 📚 Documentação Disponível

| Arquivo | Descrição |
|---------|-----------|
| **PROXIMO-PASSO.md** | Este arquivo (começa aqui!) |
| **docs/SETUP-PRODUCAO.md** | Guia completo passo a passo |
| **.github/SECRETS-TEMPLATE.md** | Como configurar secrets |
| **GUIA-RAPIDO.md** | Referência rápida de comandos |
| **README-QUICKSTART.md** | Início rápido local |
| **docs/TESTING.md** | Guia de testes |

---

## 🆘 Precisa de Ajuda?

### Servidor

**Recomendações (custo/benefício):**

1. **DigitalOcean** ($6/mês)
   - https://www.digitalocean.com/
   - Droplet: 1GB RAM, 25GB SSD
   - Tutorial completo disponível

2. **Vultr** ($6/mês)
   - https://www.vultr.com/
   - Similar ao DigitalOcean

3. **AWS EC2** (Grátis 12 meses)
   - https://aws.amazon.com/free/
   - t2.micro free tier

### MongoDB

**Recomendação:**

**MongoDB Atlas** (Grátis)
- https://www.mongodb.com/cloud/atlas
- 512MB storage grátis
- Perfeito para começar

### Domínio

Se não tem domínio ainda:

1. **Registro.br** (se for .br)
   - https://registro.br/
   - ~R$ 40/ano

2. **Namecheap** (internacionais)
   - https://www.namecheap.com/
   - ~$10/ano

### Dúvidas Comuns

**P: Preciso pagar por tudo isso?**
R: Não! Você pode usar:
- MongoDB Atlas: Grátis
- GitHub Actions: Grátis (2000 min/mês)
- Servidor: A partir de $6/mês

**P: Quanto tempo leva?**
R: 1-2 horas se for a primeira vez

**P: Preciso saber muito de DevOps?**
R: Não! Os scripts automatizam tudo. Basta seguir o passo a passo.

**P: E se eu não tiver servidor ainda?**
R: Comece testando localmente com `npm start`

---

## 🎯 Resumo do Próximo Passo

**Se tem servidor e domínio:**
1. Execute `./scripts/setup-github-secrets.sh`
2. Siga `docs/SETUP-PRODUCAO.md`
3. Faça `git push origin main`

**Se NÃO tem servidor ainda:**
1. Contrate um servidor ($6/mês DigitalOcean)
2. Configure DNS
3. Siga `docs/SETUP-PRODUCAO.md`

**Se quer testar antes:**
1. Execute `npm start`
2. Execute `npm test`
3. Acesse http://localhost:3000

---

## 📞 Suporte

- 📖 Documentação: `/docs`
- 🐛 Issues: https://github.com/seu-usuario/alca-financas/issues
- 💬 Discussions: https://github.com/seu-usuario/alca-financas/discussions

---

**Você está a 1 comando de colocar seu app no ar! 🚀**

```bash
./scripts/setup-github-secrets.sh
```
