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
from routes.admin import bp as admin_bp

load_dotenv()

app = Flask(__name__)
# SECRET_KEY necessário para sessões (ex.: OAuth). Usa default seguro em dev se não definido.
from extensions import limiter

# ... imports ...

app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configuração de sessão para OAuth
# Em produção, usa HTTPS então pode usar SameSite=None para OAuth cross-site
is_production = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = is_production  # True em produção (HTTPS)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if is_production else 'Lax'  # None necessário para OAuth cross-site
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

# Rate Limiting
limiter.init_app(app)

# CORS configuration - permite localhost e IPs locais
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    # Se não especificado, permite localhost em portas comuns
    cors_origins = 'http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000'

CORS(app,
     origins=cors_origins.split(','),
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
     expose_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
     max_age=3600)

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
app.config['OAUTH_STATES'] = db.oauth_states  # Cache temporário para states do OAuth

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
app.register_blueprint(admin_bp)

from utils.exceptions import AppException

@app.errorhandler(AppException)
def handle_app_exception(e):
    return jsonify(e.to_dict()), e.status_code

def create_indices(db):
    db.transactions.create_index([('user_id', 1), ('date', -1)])
    db.transactions.create_index([('user_id', 1), ('category_id', 1)])
    db.users.create_index('email', unique=True)

if __name__ == '__main__':
    create_indices(db)
    app.run(host='0.0.0.0', port=8001, debug=True)
