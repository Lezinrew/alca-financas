#!/usr/bin/env bash
set -euo pipefail

# ===== 0) Inputs =====
GID="${GOOGLE_CLIENT_ID:-}"
GSECRET="${GOOGLE_CLIENT_SECRET:-}"
REDIRECT="${GOOGLE_REDIRECT_URI:-http://localhost:5000/api/auth/google/callback}"
API_URL="${VITE_API_URL:-http://localhost:5000}"

if [ -z "$GID" ]; then read -rp "Google CLIENT_ID: " GID; fi
if [ -z "$GSECRET" ]; then read -rp "Google CLIENT_SECRET: " GSECRET; fi

mkdir -p backend frontend

# ===== 1) .envs =====
cat > backend/.env <<EOF
SECRET_KEY=change_me
MONGO_URI=mongodb://mongo:27017
MONGO_DB=finance
CORS_ORIGINS=http://localhost:5173,http://localhost
JWT_EXPIRES_HOURS=24
GOOGLE_CLIENT_ID=${GID}
GOOGLE_CLIENT_SECRET=${GSECRET}
GOOGLE_REDIRECT_URI=${REDIRECT}
EOF

cat > frontend/.env <<EOF
VITE_API_URL=${API_URL}
EOF
echo "✔ .env criados/atualizados."

# ===== 2) Patches no backend/app.py =====
if [ -f backend/app.py ]; then
  # 2.1) Corrigir discovery URL se estiver com underscore
  sed -i "s|/.well-known/openid_configuration|/.well-known/openid-configuration|g" backend/app.py || true

  # 2.2) Se existir um IF com __google_oidc_nonce__ sem bloco, insere "pass" na linha seguinte
  awk '
  match(\$0, /^([[:space:]]*)if .*__google_oidc_nonce__.*:[[:space:]]*$/, m) {
    print;
    printf "%s    pass\n", m[1];
    next
  }
  { print }
  ' backend/app.py > backend/app.py.tmp && mv backend/app.py.tmp backend/app.py
  echo "✔ Corrigido possível if do nonce sem bloco."
fi

# ===== 3) Subir containers =====
echo "▶ Subindo containers (build + up)…"
docker compose up -d --build

# ===== 4) Checar backend e mostrar logs =====
echo "▶ Testando /api/auth/google/login…"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5000/api/auth/google/login || true

echo "Pronto! Frontend: http://localhost:5173"
echo "Se a Google recusar, confira o Redirect URI na Console:"
echo "  ${REDIRECT}"
echo "▶ Logs do backend (CTRL+C para sair)…"
docker compose logs -f backend
