# OpenClaw como microserviço interno — deploy seguro

OpenClaw roda como serviço interno: **sem porta pública**, comunicação apenas pela **rede interna Docker**. Backend e outros serviços acessam via `http://openclaw-gateway:18789`.

---

## 1. Estrutura

```
services/openclaw/
├── Dockerfile              # Imagem segura (não-root, cap_drop, read_only)
├── docker-compose.yml      # Compose standalone (opcional)
├── .env.example            # Modelo de variáveis (copiar para .env)
└── docker-compose.override.example.yml  # Exemplo para expor UI em 127.0.0.1
```

- **.env**: use o `.env` na **raiz do projeto** para o stack (backend + openclaw leem daí). Opcionalmente pode existir `services/openclaw/.env` ao rodar o compose **standalone** em `services/openclaw`. Nenhum `.env` é commitado (está no `.gitignore`).

---

## 2. Configuração local (desenvolvimento)

### 2.1 Variáveis no .env (raiz do projeto)

No `.env` da **raiz do projeto** (ou criar a partir do exemplo), definir pelo menos:

```bash
# Gerar token: openssl rand -hex 32
OPENCLAW_GATEWAY_TOKEN=<valor_gerado>
```

Para usar só o OpenClaw em modo standalone (em `services/openclaw`), copiar `services/openclaw/.env.example` para `services/openclaw/.env` e preencher.

### 2.2 Subir com o projeto (rede interna, sem porta no host)

Na raiz do projeto:

```bash
# Garantir que services/openclaw/.env existe com OPENCLAW_GATEWAY_TOKEN
docker compose up -d --build
```

O gateway fica acessível **só de dentro da rede Docker**, em `http://openclaw-gateway:18789`. O backend pode usar `OPENCLAW_GATEWAY_URL=http://openclaw-gateway:18789` e `OPENCLAW_GATEWAY_TOKEN` (já configurados no compose).

### 2.3 (Opcional) Expor UI apenas em 127.0.0.1

Se quiser acessar o Control UI no navegador **só em localhost**:

- **Opção A** – Override no compose da raiz: crie `docker-compose.override.yml` na raiz com:

```yaml
services:
  openclaw-gateway:
    ports:
      - "127.0.0.1:18789:18789"
```

- **Opção B** – Usar o exemplo em `services/openclaw/docker-compose.override.example.yml` e rodar o compose incluindo esse override.

Depois: `http://127.0.0.1:18789/` (apenas na máquina local).

---

## 3. Produção (VPS Hostinger)

### 3.1 Pré-requisitos

- Docker e Docker Compose no VPS.
- Deploy do resto do projeto (backend/frontend) já funcionando.

### 3.2 .env seguro (fora do repositório)

- Nunca commitar `.env`.
- **Desenvolvimento e produção**: usar o `.env` na **raiz do projeto** e definir `OPENCLAW_GATEWAY_TOKEN` (e opcionalmente chaves de provedores). O compose injeta essas variáveis nos serviços.
- No servidor, conteúdo mínimo no `.env` da raiz:

```bash
OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)   # gerar e colar no .env
# Opcional: chaves de provedores
# CLAUDE_AI_SESSION_KEY=...
# CLAUDE_WEB_SESSION_KEY=...
# CLAUDE_WEB_COOKIE=...
```

- Permissões: `chmod 600 services/openclaw/.env` (e do `.env` da raiz, se usar).

### 3.3 Rodar OpenClaw em produção

No mesmo compose usado em produção (ex.: `docker-compose.prod.yml` ou o que sobe backend/frontend):

- Incluir o serviço `openclaw-gateway` (como no `docker-compose.yml` da raiz).
- **Não** mapear portas do OpenClaw para o host em produção (sem `ports:` no serviço openclaw).
- Garantir que o backend em produção tenha:
  - `OPENCLAW_GATEWAY_URL=http://openclaw-gateway:18789`
  - `OPENCLAW_GATEWAY_TOKEN` igual ao definido no `.env` do OpenClaw.

Assim o OpenClaw fica apenas na rede interna Docker.

### 3.4 Onboarding / configuração (CLI)

Ver seção **"Como usar o openclaw-cli"** abaixo. No servidor, use o mesmo `.env` da raiz e rode os comandos com `docker compose -f docker-compose.prod.yml run --rm openclaw-cli ...`.

---

## 4. Como usar o openclaw-cli

O **openclaw-cli** está no mesmo `docker-compose` do projeto (serviço `openclaw-cli`). Ele usa a mesma imagem e os mesmos volumes do gateway, então enxerga a mesma configuração. Rode **sob demanda** (o serviço não sobe com `up`; use `run`).

**Pré-requisito:** gateway rodando (`docker compose up -d` ou já em execução) e `.env` na raiz com `OPENCLAW_GATEWAY_TOKEN`.

### 4.1 Comando geral

Na **raiz do projeto**:

```bash
docker compose run --rm openclaw-cli <subcomando> [opções]
```

Em **produção** (com `docker-compose.prod.yml`):

```bash
docker compose -f docker-compose.prod.yml run --rm openclaw-cli <subcomando> [opções]
```

### 4.2 Primeira vez: onboarding

Configura provedores de LLM (OpenAI, Anthropic, etc.) e modo do gateway:

```bash
docker compose run --rm openclaw-cli onboard
```

Siga o assistente. Em ambiente headless/Docker, se pedir callback em `http://127.0.0.1:1455/auth/callback`, copie a URL de redirect do navegador e cole no terminal.

### 4.3 Dashboard (link do Control UI)

Obter a URL do Control UI e o token para colar em **Settings → token** na interface:

```bash
docker compose run --rm openclaw-cli dashboard --no-open
```

Imprime a URL (ex.: `http://127.0.0.1:18789/...`) e o token. Se o gateway **não** estiver exposto em nenhuma porta no host, acesse primeiro via túnel SSH ou exponha só em 127.0.0.1 (ver secção 2.3).

### 4.4 Status do gateway

```bash
docker compose run --rm openclaw-cli status
```

### 4.5 Dispositivos (pairing)

Listar pedidos de pairing e aprovar um dispositivo (ex.: navegador):

```bash
docker compose run --rm openclaw-cli devices list
docker compose run --rm openclaw-cli devices approve <requestId>
```

### 4.6 Canais (WhatsApp, Telegram, Discord)

- **WhatsApp** (login com QR):
  ```bash
  docker compose run --rm openclaw-cli channels login
  ```
- **Telegram** (token do BotFather):
  ```bash
  docker compose run --rm openclaw-cli channels add --channel telegram --token "<token>"
  ```
- **Discord** (token do bot):
  ```bash
  docker compose run --rm openclaw-cli channels add --channel discord --token "<token>"
  ```

### 4.7 Ajuda

Listar subcomandos e opções:

```bash
docker compose run --rm openclaw-cli --help
docker compose run --rm openclaw-cli devices --help
docker compose run --rm openclaw-cli channels --help
```

---

## 5. Firewall (VPS Hostinger)

Objetivo: **não expor a porta do OpenClaw** (18789) na internet. Só 22 (SSH), 80 e 443 (HTTP/HTTPS) abertos.

### 5.1 UFW (recomendado)

```bash
# Habilitar UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# NÃO fazer: ufw allow 18789
sudo ufw enable
sudo ufw status
```

### 5.2 Conferir que 18789 não está exposta

```bash
sudo ss -tlnp | grep 18789
# Ou: sudo netstat -tlnp | grep 18789
```

Não deve aparecer **0.0.0.0:18789** (nem `:::18789`). Se você usar apenas `127.0.0.1:18789` no host (override de dev), o `ss` pode mostrar 127.0.0.1:18789 — isso é aceitável, pois não está acessível de fora.

---

## 6. Hardening do container (já aplicado no compose)

| Medida | Uso no compose |
|--------|----------------|
| Sem porta pública | `ports` não definido (ou só 127.0.0.1 em override de dev) |
| Não-root | `user: "1000:1000"` |
| Sem novas capacidades | `security_opt: no-new-privileges:true` |
| Capabilities | `cap_drop: [ALL]` |
| Filesystem read-only | `read_only: true` + `tmpfs` para `/tmp` e volumes para dados |
| Init | `init: true` (reap de zombies) |

---

## 7. Resumo de segurança

- **Rede**: OpenClaw só na rede Docker; backend acessa por nome do serviço.
- **Porta**: Não publicada no host em produção; opcional 127.0.0.1 em dev.
- **Secrets**: `.env` fora do repo, permissões 600, nunca em log ou imagem.
- **Firewall**: UFW permitindo apenas 22, 80, 443.
- **Container**: não-root, read-only rootfs, sem capabilities, no-new-privileges.

Para dúvidas do OpenClaw em si: [docs.openclaw.ai](https://docs.openclaw.ai).
