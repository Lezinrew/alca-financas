# OpenClaw Gateway - imagem segura para microserviço interno
# Base oficial; sem root, sem capacidades extras, filesystem read-only onde possível.
# Uso: apenas rede interna Docker, sem exposição de portas ao host.

ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:main
FROM ${OPENCLAW_IMAGE}

# Garantir usuário não-root (imagem oficial já usa node/1000)
USER node

# Diretório de trabalho (somente leitura exceto /tmp e volumes explícitos)
WORKDIR /app

# Healthcheck definido no docker-compose (usa env OPENCLAW_GATEWAY_TOKEN em runtime).
# A imagem base já expõe 18789; não adicionamos portas aqui.

ENTRYPOINT ["node", "dist/index.js", "gateway"]
CMD ["--bind", "0.0.0.0", "--port", "18789"]
