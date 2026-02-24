# OpenClaw — microserviço interno

Gateway OpenClaw rodando em Docker: **sem porta pública**, apenas rede interna. O backend acessa em `http://openclaw-gateway:18789`.

## Uso no projeto (recomendado)

Na **raiz do projeto**:

1. No `.env` da raiz, defina `OPENCLAW_GATEWAY_TOKEN` (ex.: `openssl rand -hex 32`).
2. Suba o stack: `docker compose up -d --build`.
3. O serviço `openclaw-gateway` fica na rede `alca-financas-network`; nenhuma porta é exposta no host.

Para acessar o Control UI em **localhost** (opcional), use um override com `ports: ["127.0.0.1:18789:18789"]` (ver `docker-compose.override.example.yml` e `docs/OPENCLAW-DEPLOY-SEGURO.md`).

## Uso standalone (apenas OpenClaw)

```bash
cd services/openclaw
cp .env.example .env
# Editar .env: OPENCLAW_GATEWAY_TOKEN=...
docker compose up -d --build
```

## Segurança

- Container: não-root (`user: 1000:1000`), `read_only: true`, `cap_drop: ALL`, `no-new-privileges`.
- Rede: sem `ports` no compose principal; tráfego só entre containers.
- Secrets: `.env` fora do repositório (nunca commitar).

## openclaw-cli

O CLI roda sob demanda (não sobe com `docker compose up`). Na **raiz do projeto**:

```bash
# Onboarding (primeira vez)
docker compose run --rm openclaw-cli onboard

# Link do Control UI
docker compose run --rm openclaw-cli dashboard --no-open

# Status, dispositivos, canais (WhatsApp/Telegram/Discord)
docker compose run --rm openclaw-cli status
docker compose run --rm openclaw-cli devices list
docker compose run --rm openclaw-cli channels login
```

Guia completo e todos os comandos: [docs/OPENCLAW-DEPLOY-SEGURO.md](../../docs/OPENCLAW-DEPLOY-SEGURO.md#4-como-usar-o-openclaw-cli).
