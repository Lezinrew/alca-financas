FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @alca/openclaw-cli

COPY services/openclaw_bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/openclaw_bridge/app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8089"]
