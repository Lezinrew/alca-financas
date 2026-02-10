#!/usr/bin/env python3
"""
Script para definir a senha de um usuário por e-mail.
Uso: na pasta backend: python scripts/set_user_password.py
     ou: python -m scripts.set_user_password
Requer .env com MONGO_URI (ou Supabase configurado).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from database import init_db, get_db, get_db_type
from utils.auth_utils import hash_password


EMAIL = 'lezinrew@gmail.com'
NEW_PASSWORD = '1234mudar'


def main():
    init_db()
    db_type = get_db_type()
    db = get_db()

    if db_type == 'mongodb':
        users = db.users
        user = users.find_one({'email': {'$regex': f'^{EMAIL}$', '$options': 'i'}})
        if not user:
            print(f"❌ Usuário com e-mail {EMAIL} não encontrado.")
            return 1
        hashed = hash_password(NEW_PASSWORD)
        users.update_one({'_id': user['_id']}, {'$set': {'password': hashed}})
        print(f"✅ Senha atualizada para o usuário {user.get('name')} ({user.get('email')}).")
        return 0

    if db_type == 'supabase':
        from supabase import create_client
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
        if not url or not key:
            print("❌ SUPABASE_URL e SUPABASE_SERVICE_KEY (ou SUPABASE_KEY) são necessários.")
            return 1
        client = create_client(url, key)
        r = client.table('users').select('id, email, name').ilike('email', EMAIL).execute()
        if not r.data or len(r.data) == 0:
            print(f"❌ Usuário com e-mail {EMAIL} não encontrado.")
            return 1
        user = r.data[0]
        hashed = hash_password(NEW_PASSWORD)
        # Supabase pode armazenar senha como text; bcrypt gera bytes
        password_value = hashed.decode('utf-8') if isinstance(hashed, bytes) else hashed
        client.table('users').update({'password': password_value}).eq('id', user['id']).execute()
        print(f"✅ Senha atualizada para o usuário {user.get('name')} ({user.get('email')}).")
        return 0

    print("❌ Tipo de banco não suportado.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
