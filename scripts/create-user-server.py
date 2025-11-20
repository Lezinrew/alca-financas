#!/usr/bin/env python3
"""
Script para criar usuário no servidor de produção
"""

import subprocess
import sys
import json

# Configurações do servidor
SERVER_HOST = "alcahub.com.br"
SERVER_USER = "root"
SERVER_PASS = "4203434@Mudar"
PROJECT_DIR = "/var/www/alca-financas"

def execute_ssh(command, check=True):
    """Executa comando remoto via SSH usando sshpass"""
    cmd = [
        "sshpass", "-p", SERVER_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{SERVER_USER}@{SERVER_HOST}",
        command
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        if check:
            print(f"❌ Erro ao executar comando: {command}")
            print(f"Erro: {e.stderr}")
            sys.exit(1)
        return e.stdout, e.stderr, e.returncode

def main():
    print("🔵 Criando usuário no servidor...")
    
    # Dados do usuário
    email = "lezinrew@gmail.com"
    name = "Leandro X Pinho"
    password = input("Digite a senha para o usuário (ou pressione Enter para usar 'senha123'): ").strip()
    if not password:
        password = "senha123"
    
    print(f"\n📝 Criando usuário:")
    print(f"   Email: {email}")
    print(f"   Nome: {name}")
    print(f"   Senha: {'*' * len(password)}")
    
    # Script Python para criar o usuário
    create_user_script = f"""
import sys
sys.path.insert(0, '{PROJECT_DIR}/backend')

from pymongo import MongoClient
from utils.auth_utils import hash_password
from services.user_service import create_user, create_default_categories
from datetime import datetime
import uuid

# Conectar ao MongoDB
mongo_uri = "mongodb://localhost:27017/alca_financas"
client = MongoClient(mongo_uri)
db = client['alca_financas']
users_collection = db.users
categories_collection = db.categories

# Verificar se usuário já existe
existing_user = users_collection.find_one({{'email': '{email}'}})
if existing_user:
    print(f"⚠️  Usuário {{existing_user['email']}} já existe!")
    sys.exit(1)

# Criar usuário
user_data = {{
    'name': '{name}',
    'email': '{email}',
    'password': '{password}'
}}

user = create_user(users_collection, user_data, hash_password)
create_default_categories(categories_collection, user['_id'])

print(f"✅ Usuário criado com sucesso!")
print(f"   ID: {{user['_id']}}")
print(f"   Email: {{user['email']}}")
print(f"   Nome: {{user['name']}}")
"""
    
    # Executar script no servidor
    print("\n🔵 Executando script no servidor...")
    stdout, stderr, code = execute_ssh(f"""
        cd {PROJECT_DIR}/backend && \
        source venv/bin/activate && \
        python3 << 'PYTHON_SCRIPT'
{create_user_script}
PYTHON_SCRIPT
    """)
    
    if code == 0:
        print(stdout)
        print("\n✅ Usuário criado com sucesso no servidor!")
        print(f"\n📝 Você pode fazer login com:")
        print(f"   Email: {email}")
        print(f"   Senha: {password}")
        print(f"\n🌐 Acesse: http://alcahub.com.br")
    else:
        print("❌ Erro ao criar usuário:")
        print(stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

