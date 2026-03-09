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

# CLI oficial OpenClaw (pacote público; @alca/openclaw-cli não existe no npm)
# --unsafe-perm é necessário pois alguns scripts de compilação falham quando roda como root no docker
RUN npm install -g openclaw@latest --unsafe-perm=true --allow-root

COPY services/openclaw_bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/openclaw_bridge/app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8089"]
