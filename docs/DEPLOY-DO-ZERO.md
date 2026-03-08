# Deploy do zero – servidor novo e primeiro deploy

Guia em sequência: preparar o servidor, enviar o `.env` (sem depender do GitHub) e rodar o primeiro deploy.

---

## Visão geral

1. **Servidor:** VPS com SSH (root). O script de deploy instala Docker e Docker Compose.
2. **Na sua máquina:** você monta o `.env` e envia com **pscp** (Windows) ou **scp** (Mac/Linux).
3. **Deploy:** roda o script que clona o repositório no servidor e sobe os containers (o `.env` já estará lá).

---

## 1. Pré-requisitos

- VPS com **Ubuntu/Debian**, acesso **SSH (root)** e portas **80 e 443** abertas.
- **Domínio** com DNS apontando para o IP do servidor (ex.: `alcahub.cloud`, `api.alcahub.cloud`).
- **Supabase:** projeto criado e anotadas as variáveis (URL, `service_role`, `anon`).
- Na sua máquina: **Git** e **SSH** (ou PuTTY/pscp no Windows).

---

## 2. No servidor (uma vez)

Conectar via SSH e garantir que o diretório do projeto existe (o script também cria, mas você pode fazer antes para enviar o `.env`):

```bash
ssh root@SEU_IP_VPS

# Criar diretório do projeto (se ainda não existir)
mkdir -p /var/www/alca-financas
exit
```

**Nota:** O script de deploy faz o clone automaticamente usando `git clone .` para evitar criar subpastas. Se você for clonar manualmente, use:

```bash
cd /var/www/alca-financas
git clone https://github.com/Lezinrew/alca-financas.git .
```

(O ponto `.` no final clona direto no diretório atual, evitando `/var/www/alca-financas/alca-financas`)

O script de deploy instala Docker e Docker Compose no servidor; não é obrigatório instalar antes.

---

## 3. Na sua máquina – preparar o `.env`

Na raiz do repositório:

**Opção A – Script auxiliar (recomendado)**

```bash
cd /caminho/para/alca-financas
./scripts/setup-env.sh
```

O script cria o `.env` a partir de `.env.example` (se não existir), pode gerar `SECRET_KEY` e `JWT_SECRET` com `openssl`, e oferece:
1. Preenchimento interativo das credenciais **Supabase** (URL + service_role + anon)
2. Abrir o `.env` no editor para preencher o restante manualmente

Para só abrir o `.env` no editor: `./scripts/setup-env.sh --editor-only`

**Opção B – Manual**

```bash
cp .env.example .env
# Edite .env com: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY,
# SECRET_KEY, JWT_SECRET (openssl rand -hex 32), CORS_ORIGINS, DOMAIN, etc.
```

Use o `.env.example` como referência e preencha pelo menos:

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`
- `SECRET_KEY` e `JWT_SECRET` (ex.: `openssl rand -hex 32`)
- `CORS_ORIGINS` (ex.: `https://alcahub.cloud,https://www.alcahub.cloud`)
- `VITE_API_URL` (ex.: `https://api.alcahub.cloud`)
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (mesmos do Supabase)

---

## 4. Enviar o `.env` para o servidor (sem GitHub)

Assim o servidor já fica com o `.env` antes do deploy; o script **não** sobrescreve se o arquivo já existir.

### Windows (PowerShell ou CMD) – **pscp** (PuTTY)

Se ainda não tiver: baixe PuTTY e use o `pscp.exe` do mesmo instalador.

```cmd
cd C:\caminho\para\alca-financas

pscp -pw SUA_SENHA_SSH .env root@SEU_IP_VPS:/var/www/alca-financas/.env
```

Com chave em vez de senha:

```cmd
pscp -i C:\Users\Voce\.ssh\sua_chave.ppk .env root@SEU_IP_VPS:/var/www/alca-financas/.env
```

### Mac / Linux – **scp**

```bash
cd /caminho/para/alca-financas

# Com senha (vai pedir a senha)
scp .env root@SEU_IP_VPS:/var/www/alca-financas/.env

# Com chave SSH
scp -i ~/.ssh/sua_chave .env root@SEU_IP_VPS:/var/www/alca-financas/.env
```

Substitua `SEU_IP_VPS` (ex.: `76.13.239.220`) e o caminho da chave conforme seu ambiente.

---

## 5. Primeiro deploy

Na sua máquina, na raiz do repositório:

```bash
cd /caminho/para/alca-financas

# Variáveis do deploy (ajuste IP, domínio e chave se precisar)
export SERVER_HOST="76.13.239.220"
export SERVER_USER="root"
export PROJECT_DIR="/var/www/alca-financas"
export DOMAIN="alcahub.cloud"

# Opcional: chave SSH (senão o script pede senha)
export SERVER_SSH_KEY="$HOME/.ssh/id_rsa"

# Rodar deploy (instala Docker no servidor, clona o repo, build e sobe os containers)
./scripts/deploy-docker-remote.sh
```

O script vai:

- Instalar Docker e Docker Compose no servidor (se não existirem)
- Criar `PROJECT_DIR` e fazer `git clone` (ou `git pull`) do repositório
- Ver que o `.env` já existe e **não** sobrescrevê-lo
- Fazer build das imagens e subir os containers

---

## 6. Depois do deploy

- **Frontend:** `https://SEU_DOMINIO` (ex.: `https://alcahub.cloud`)
- **API:** `https://api.SEU_DOMINIO` (ex.: `https://api.alcahub.cloud`)
- **Health:** `https://api.SEU_DOMINIO/api/health`

Se o proxy/reverso (Traefik, Nginx, etc.) já estiver apontando para as portas dos containers, o app deve abrir no navegador.

Para ver logs e reiniciar:

```bash
ssh root@SEU_IP_VPS 'cd /var/www/alca-financas && docker-compose -f docker-compose.prod.yml logs -f backend'
ssh root@SEU_IP_VPS 'cd /var/www/alca-financas && docker-compose -f docker-compose.prod.yml restart'
```

---

## Resumo dos comandos (copiar e colar)

Ajuste `SEU_IP_VPS`, `SEU_DOMINIO` e o caminho do projeto.

**1. Criar diretório no servidor (se quiser fazer antes):**
```bash
ssh root@SEU_IP_VPS "mkdir -p /var/www/alca-financas"
```

**2. Enviar .env (Mac/Linux):**
```bash
scp .env root@SEU_IP_VPS:/var/www/alca-financas/.env
```

**2. Enviar .env (Windows – pscp):**
```cmd
pscp -pw SUA_SENHA .env root@SEU_IP_VPS:/var/www/alca-financas/.env
```

**3. Deploy:**
```bash
export SERVER_HOST="SEU_IP_VPS"
export SERVER_USER="root"
export PROJECT_DIR="/var/www/alca-financas"
export DOMAIN="SEU_DOMINIO"
./scripts/deploy-docker-remote.sh
```

Para mais detalhes e troubleshooting, veja [DEPLOY-GUIDE.md](DEPLOY-GUIDE.md).
