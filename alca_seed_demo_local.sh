#!/usr/bin/env bash
set -eo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
MONGO_DB="${MONGO_DB:-alca_financas}"

echo "==> Ativando venv do backend (criando se necessário)"
cd "$BACKEND_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install bcrypt pymongo >/dev/null

echo "==> Inserindo/atualizando usuário demo em $MONGO_URI/$MONGO_DB"
python - <<PY
import os, sys, bcrypt, datetime, uuid
from pymongo import MongoClient

mongo_uri = os.getenv('MONGO_URI', '$MONGO_URI')
db_name = os.getenv('MONGO_DB', '$MONGO_DB')

client = MongoClient(mongo_uri)
db = client[db_name]

email = 'demo@alca.fin'
password_plain = os.getenv('DEMO_PASSWORD', 'demo123') # Ideally should be injected via env var in production

existing = db.users.find_one({'email': email})
hashed = bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

if existing:
    # Atualiza apenas campos relevantes
    db.users.update_one({'_id': existing['_id']}, {'$set': {
        'password': hashed,
        'name': existing.get('name') or 'Demo User',
        'settings': existing.get('settings') or {'currency': 'BRL', 'theme': 'light', 'language': 'pt'},
        'auth_providers': existing.get('auth_providers') or [],
    }})
    user_id = existing['_id']
    print('Usuário demo já existia. Senha atualizada.')
else:
    user_id = str(uuid.uuid4())
    db.users.insert_one({
        '_id': user_id,
        'name': 'Demo User',
        'email': email,
        'password': hashed,
        'settings': {'currency': 'BRL', 'theme': 'light', 'language': 'pt'},
        'auth_providers': [],
        'created_at': datetime.datetime.utcnow(),
    })
    print('Usuário demo criado.')

# Garantir categorias padrão mínimas
default_categories = [
    {'name': 'Alimentação', 'type': 'expense'},
    {'name': 'Transporte', 'type': 'expense'},
    {'name': 'Salário', 'type': 'income'},
]
for cat in default_categories:
    exists = db.categories.find_one({'name': cat['name'], 'user_id': user_id})
    if not exists:
        db.categories.insert_one({
            'user_id': user_id,
            'name': cat['name'],
            'type': cat['type'],
            'created_at': datetime.datetime.utcnow(),
        })

print('Usuário demo pronto: email=demo@alca.fin senha=demo123')
PY

echo "==> Concluído. Faça login com demo@alca.fin / demo123"

