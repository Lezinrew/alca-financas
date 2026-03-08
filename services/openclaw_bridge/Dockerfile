FROM python:3.12-slim

WORKDIR /app

# OpenClaw CLI requer Node ≥22
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# CLI oficial OpenClaw (pacote público; @alca/openclaw-cli não existe no npm)
RUN npm install -g openclaw@latest

COPY services/openclaw_bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/openclaw_bridge/app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8089"]
