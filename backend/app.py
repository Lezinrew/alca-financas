"""
API Backend - Flask + MongoDB, modular via Blueprints
"""

import os
from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

from routes.auth import bp as auth_bp
from routes.categories import bp as categories_bp
from routes.transactions import bp as transactions_bp
from routes.accounts import bp as accounts_bp
from routes.dashboard import bp as dashboard_bp
from routes.reports import bp as reports_bp

load_dotenv()

app = Flask(__name__)
# SECRET_KEY necessário para sessões (ex.: OAuth). Usa default seguro em dev se não definido.
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# CORS configuration - permite localhost e IPs locais
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    # Se não especificado, permite localhost em portas comuns
    cors_origins = 'http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000'

CORS(app,
     origins=cors_origins.split(','),
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

oauth = OAuth(app)
app.config['OAUTH'] = oauth
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Configuração segura do MongoDB com defaults locais
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
MONGO_DB = os.getenv('MONGO_DB', 'alca_financas')

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
app.config['DB'] = db
app.config['USERS'] = db.users
app.config['CATEGORIES'] = db.categories
app.config['TRANSACTIONS'] = db.transactions
app.config['ACCOUNTS'] = db.accounts

@app.get('/api/health')
def health():
    """Simple health check endpoint."""
    return {'status': 'ok'}, 200

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(categories_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(reports_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)
