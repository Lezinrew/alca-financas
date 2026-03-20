# 🔐 GitHub Secrets Configuration

Template para configurar secrets no GitHub Actions.

## Como Configurar

1. Vá para o repositório no GitHub
2. Clique em `Settings`
3. No menu lateral, clique em `Secrets and variables` → `Actions`
4. Clique em `New repository secret`
5. Adicione cada secret abaixo

---

## Secrets Necessários

### 🐳 Docker Registry

**DOCKER_REGISTRY**
```
registry.hub.docker.com
```
ou
```
ghcr.io
```

**DOCKER_USERNAME**
```
seu-usuario-docker
```

**DOCKER_PASSWORD**
```
sua-senha-ou-token-docker
```

Como obter:
1. Docker Hub: https://hub.docker.com/settings/security
2. GitHub Container Registry: https://github.com/settings/tokens

---

### 🌐 Servidor de Produção

**PROD_HOST**
```
alcahub.cloud
```

**PROD_USER**
```
deploy
```

**PROD_SSH_KEY**
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
...
[conteúdo completo da chave privada]
...
-----END OPENSSH PRIVATE KEY-----
```

Como gerar:
```bash
# No servidor
ssh-keygen -t ed25519 -C "deploy@alcahub.cloud" -f ~/.ssh/deploy_key -N ""

# Adicione a chave pública ao authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# Copie a chave privada (cole no GitHub)
cat ~/.ssh/deploy_key
```

---

### 📱 Notificações Telegram (Opcional)

**TELEGRAM_CHAT_ID**
```
123456789
```
(ID numérico do chat que **recebe** o aviso: sua conta, grupo ou canal — não é o `@nome_do_bot`.)

**TELEGRAM_BOT_TOKEN**

Formato real (do BotFather): `<id_numérico_do_bot>:<string_secreta>` — dois trechos separados por `:`.

Exemplo **somente de formato** (fictício — **nunca** use este valor nem cole token real em issue/chat/doc versionado):

```
7123456789:AAHbExemplo_FORMATO_igual_ao_BotFather_nao_e_token_valido
```

**Segurança:** se um token verdadeiro vazar (chat, print, commit), use no @BotFather **`/revoke`** ou **`/token`** e gere outro. Tokens em documentação devem ser sempre placeholders como o acima.

Como obter:
1. Abra Telegram
2. Procure por @BotFather
3. Envie `/newbot` e siga as instruções (ou `/token` em um bot existente)
4. Copie o token fornecido e guarde só em **GitHub Secrets** ou `.env` local (não commitar)
5. Para obter `chat_id`:
   - Envie uma mensagem para seu bot (`/start`)
   - Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   - Copie o `chat.id` da resposta JSON

**Como testar no repositório (GitHub Actions):**

1. Faça push do workflow `.github/workflows/telegram-notify-test.yml` (se ainda não estiver na branch padrão).
2. No GitHub: **Actions** → **Telegram — teste de secrets** → **Run workflow** → escolha a branch → **Run workflow**.
3. Se os secrets estiverem corretos, você recebe a mensagem no Telegram. Erro `missing telegram token or user list` indica token ou `chat_id` vazio/errado.

**Teste local (opcional):** no terminal (não commite o token):

```bash
curl -sS "https://api.telegram.org/bot<SEU_TOKEN>/sendMessage" \
  -d "chat_id=<SEU_CHAT_ID>" \
  --data-urlencode "text=Teste manual Alça Finanças"
```

Substitua `<SEU_TOKEN>` e `<SEU_CHAT_ID>` pelos valores reais.

---

## Secrets Opcionais

### 📊 Codecov (Coverage Reports)

**CODECOV_TOKEN**
```
seu-token-codecov
```

Como obter:
1. Acesse https://codecov.io/
2. Conecte seu repositório
3. Copie o token

---

### 🔍 Sentry (Error Tracking)

**SENTRY_DSN**
```
https://examplePublicKey@o0.ingest.sentry.io/0
```

Como obter:
1. Acesse https://sentry.io/
2. Crie um projeto
3. Copie o DSN

---

### 📈 Google Analytics

**GOOGLE_ANALYTICS_ID**
```
G-XXXXXXXXXX
```

Como obter:
1. Acesse https://analytics.google.com/
2. Crie uma propriedade
3. Copie o Measurement ID

---

## Verificar Configuração

Após adicionar os secrets, você pode verificar se estão corretos:

### Teste 1: Listar Secrets (sem mostrar valores)

No repositório GitHub → Settings → Secrets and variables → Actions

Você deve ver (nomes exatos dos secrets):
- ✅ DOCKER_REGISTRY
- ✅ DOCKER_USERNAME
- ✅ DOCKER_PASSWORD
- ✅ PROD_HOST
- ✅ PROD_USER
- ✅ PROD_SSH_KEY
- ✅ TELEGRAM_CHAT_ID (opcional)
- ✅ TELEGRAM_BOT_TOKEN (opcional)

**Como configurar `DOCKER_REGISTRY`, `DOCKER_USERNAME` e `DOCKER_PASSWORD` no GitHub**

Use estes três secrets **somente** se algum workflow do repositório fizer login/push em um registry (Docker Hub, GHCR, etc.). Se o deploy for só SSH + build no servidor (sem push de imagem), você pode omiti-los.

1. No repositório: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Crie cada um dos três com o nome **exatamente** como na lista acima (maiúsculas e sublinhado).

| Secret | O que colar no valor | Observação |
|--------|----------------------|------------|
| `DOCKER_REGISTRY` | Host do registry, **sem** `https://` e **sem** barra no final | Ex.: `registry.hub.docker.com` (Docker Hub) ou `ghcr.io` (GitHub Container Registry) |
| `DOCKER_USERNAME` | Seu usuário no registry | No GHCR costuma ser seu **username do GitHub** (não o e-mail) |
| `DOCKER_PASSWORD` | Senha ou **token de acesso** | Docker Hub: [Access Tokens](https://hub.docker.com/settings/security). GHCR: PAT com escopo `write:packages` em [Fine-grained ou classic token](https://github.com/settings/tokens) |

Detalhes e exemplos de valores estão na seção **Docker Registry** (tópico com ícone de baleia 🐳) no início deste documento, em **Secrets Necessários**.

### Teste 2: Executar Pipeline

```bash
# Faça um commit simples
git commit --allow-empty -m "test: verificar secrets GitHub"
git push origin main

# Acompanhe em:
# https://github.com/seu-usuario/alca-financas/actions
```

Se houver erros relacionados a secrets, você verá mensagens como:
- `Error: Secret DOCKER_USERNAME is not set`
- `Error: Unable to connect to PROD_HOST`

---

## Secrets por Ambiente

Se quiser separar secrets por ambiente (staging, production):

1. Vá em `Settings` → `Environments`
2. Crie ambientes: `staging`, `production`
3. Adicione secrets específicos para cada ambiente

Exemplo:
```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    environment: production  # Usa secrets do ambiente production
    steps:
      - name: Deploy
        run: ./scripts/deploy.sh
```

---

## Segurança

### ⚠️ NUNCA faça commit de secrets

Adicione ao `.gitignore`:
```
.env
.env.local
.env.production
*.pem
*.key
credentials.json
secrets/
```

### ✅ Rotação de Secrets

Recomendado rotacionar periodicamente:
- [ ] SSH keys: a cada 6 meses
- [ ] Docker tokens: a cada 6 meses
- [ ] API tokens: a cada 3 meses
- [ ] Senhas: a cada 3 meses

### 🔒 Limitar Acesso

No GitHub:
1. Settings → Collaborators
2. Adicione apenas pessoas necessárias
3. Use branch protection rules

---

## Debug de Secrets

Se o deploy falhar, você pode debugar (sem expor valores):

```yaml
# Adicione no workflow
- name: Debug Secrets
  run: |
    echo "DOCKER_REGISTRY is set: ${{ secrets.DOCKER_REGISTRY != '' }}"
    echo "PROD_HOST is set: ${{ secrets.PROD_HOST != '' }}"
    echo "SSH key length: ${#SSH_KEY}"
  env:
    SSH_KEY: ${{ secrets.PROD_SSH_KEY }}
```

---

## Checklist Final

Antes do primeiro deploy, verifique:

- [ ] Todos os secrets obrigatórios estão configurados
- [ ] SSH key está correta (formato OpenSSH)
- [ ] Testou conexão SSH manualmente
- [ ] Docker registry está acessível
- [ ] Domínio está configurado
- [ ] Servidor está preparado
- [ ] .env produção está configurado no servidor

---

## Ajuda

Se tiver problemas:

1. Verifique os logs do GitHub Actions
2. Teste conexões manualmente:
   ```bash
   # SSH
   ssh -i deploy_key deploy@alcahub.cloud

   # Docker
   docker login registry.hub.docker.com
   ```
3. Abra uma issue no repositório

---

**Configuração completa! Agora você pode fazer deploy! 🚀**
