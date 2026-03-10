FROM python:3.12-slim

WORKDIR /app

# OpenClaw CLI requer Node ≥22 (e build-essential para dependências nativas como sharp)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# CLI oficial OpenClaw (pacote público no npm)
# --unsafe-perm: necessário para scripts de compilação quando roda como root no Docker
# --max-logs=0: evita exit 254 em ambientes com filesystem restrito (npm 8.6+)
RUN npm install -g openclaw@2026.3.8 --unsafe-perm=true --allow-root --max-logs=0

COPY services/openclaw_bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/openclaw_bridge/app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8089"]
