#!/usr/bin/env bash
set -euo pipefail

echo "==> Criando usuários de teste no Mongo..."
docker exec -i alca_backend python <<'PY'
import os, bcrypt
from pymongo import MongoClient

uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
db_name = os.getenv("MONGO_DB", "finance")
client = MongoClient(uri)
db = client[db_name]

def create_user(username, password):
    if db.users.find_one({"username": username}):
        print(f"Usuário {username} já existe, ignorando...")
        return
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.users.insert_one({"username": username, "password_hash": hashed})
    print(f"Usuário {username} criado com sucesso.")

create_user("teste", "123456")
PY
echo "==> Concluído. Use login: teste / senha: 123456"
