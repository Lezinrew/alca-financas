import os
import sys
from pymongo import MongoClient
import bcrypt
from dotenv import load_dotenv

# Adiciona o diretório backend ao path para importar utils se necessário
sys.path.append(os.path.join(os.getcwd(), 'backend'))

load_dotenv(os.path.join('backend', '.env'))

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
MONGO_DB = os.getenv('MONGO_DB', 'alca_financas')

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
users_collection = db.users

email = 'lezinrew@gmail.com'
new_password = '1234@Mudar'

# Gera hash compatível com o sistema (bcrypt)
hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

# MongoDB armazena como Binary por padrão quando usamos bytes, o que é o correto
result = users_collection.update_one(
    {'email': email},
    {'$set': {'password': hashed_password}}
)

if result.matched_count > 0:
    print(f"✅ Senha resetada com sucesso para {email}")
    if result.modified_count == 0:
        print("ℹ️  A senha já era a mesma.")
else:
    print(f"❌ Usuário {email} não encontrado no banco {MONGO_DB}")

client.close()
