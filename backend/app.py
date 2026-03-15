"""
API Backend - Flask + Supabase (PostgreSQL), modular via Blueprints
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# CRITICAL: Carregar .env ANTES de importar módulos locais
# (routes/utils precisam das env vars já carregadas)
load_dotenv()

from database import init_db, get_db

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from routes.auth_supabase import bp as auth_supabase_bp
    SUPABASE_AUTH_AVAILABLE = True
except ImportError:
    SUPABASE_AUTH_AVAILABLE = False
    logger.warning("Supabase Auth routes não disponíveis (opcional)")

from routes.auth import bp as auth_bp
from routes.categories import bp as categories_bp
from routes.transactions import bp as transactions_bp
from routes.accounts import bp as accounts_bp
from routes.dashboard import bp as dashboard_bp
from routes.reports import bp as reports_bp
from routes.admin import bp as admin_bp
from routes.tenants import bp as tenants_bp
from routes.chatbot import bp as chatbot_bp
from routes.planning import bp as planning_bp

# Permite subir o app (CI/testes/smoke) sem tentar conectar no Supabase
SKIP_DB_INIT = os.getenv("SKIP_DB_INIT", "false").strip().lower() == "true"

app = Flask(__name__)
# SECRET_KEY necessário para sessões (ex.: OAuth). Usa default seguro em dev se não definido.
from extensions import limiter

# ... imports ...

# Validar SECRET_KEY (não permitir defaults inseguros)
SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
if not SECRET_KEY or SECRET_KEY == 'dev-secret-key' or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "\n" + "="*60 + "\n"
        "❌ ERRO CRÍTICO: SECRET_KEY não configurado ou inseguro!\n"
        + "="*60 + "\n"
        "SECRET_KEY deve ter pelo menos 32 caracteres.\n"
        "\n"
        "Para gerar um secret seguro, execute:\n"
        "  openssl rand -hex 32\n"
        "\n"
        "Depois configure no .env:\n"
        "  SECRET_KEY=<valor_gerado>\n"
        "\n"
        "NUNCA use 'dev-secret-key' em produção!\n"
        + "="*60
    )
app.secret_key = SECRET_KEY

# Configuração de sessão para OAuth
# Em produção, usa HTTPS então pode usar SameSite=None para OAuth cross-site
is_production = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = is_production  # True em produção (HTTPS)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if is_production else 'Lax'  # None necessário para OAuth cross-site
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

# Rate Limiting
limiter.init_app(app)

# CORS: em produção defina CORS_ORIGINS com a URL do front (ex: https://alcahub.cloud)
cors_origins = os.getenv('CORS_ORIGINS', '*').strip()
if cors_origins == '*':
    # Se não especificado, permite apenas localhost (produção DEVE definir CORS_ORIGINS)
    cors_origins = 'http://localhost:3000,http://localhost:5173,http://localhost:3001,http://127.0.0.1:3000'
origins_list = [o.strip() for o in cors_origins.split(',') if o.strip()]

CORS(app,
     origins=origins_list,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-Tenant-Id'],
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

# Banco de dados: Supabase (obrigatório)
# Variáveis: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (backend only)

try:
    if not SKIP_DB_INIT:
        init_db()
        db_client = get_db()
        app.config['DB'] = db_client
        app.config['DB_TYPE'] = 'supabase'

        logger.info("📡 Usando Supabase")
        from repositories.user_repository_supabase import UserRepository
        from repositories.category_repository_supabase import CategoryRepository
        from repositories.transaction_repository_supabase import TransactionRepository
        from repositories.account_repository_supabase import AccountRepository
        from repositories.budget_repository_supabase import BudgetRepositorySupabase

        app.config['SUPABASE'] = db_client
        app.config['OAUTH_STATES'] = db_client.table('oauth_states')
        app.config['USER_REPO'] = UserRepository()
        app.config['CATEGORY_REPO'] = CategoryRepository()
        app.config['TRANSACTION_REPO'] = TransactionRepository()
        app.config['ACCOUNT_REPO'] = AccountRepository()
        app.config['BUDGET_REPO'] = BudgetRepositorySupabase()

        app.config['USERS'] = app.config['USER_REPO']
        app.config['CATEGORIES'] = app.config['CATEGORY_REPO']
        app.config['TRANSACTIONS'] = app.config['TRANSACTION_REPO']
        app.config['ACCOUNTS'] = app.config['ACCOUNT_REPO']
    else:
        logger.warning("⚠️  SKIP_DB_INIT=true: pulando init_db()/get_db() (CI/Testes/Smoke)")
        app.config['DB'] = None
        app.config['DB_TYPE'] = 'supabase'

except Exception as e:
    import logging
    logging.error(f"Erro ao inicializar banco de dados: {e}")
    raise


@app.get('/api/health')
def health():
    """Simple health check endpoint."""
    return {'status': 'ok'}, 200

# Observabilidade: métricas Prometheus (opcional, requer prometheus-client)
try:
    from metrics import init_metrics
    init_metrics(app)
    app.config.setdefault("ENV", os.getenv("FLASK_ENV", "production"))
    logger.info("✅ Métricas Prometheus em /api/metrics")
except Exception as e:
    logger.debug("Métricas Prometheus não carregadas: %s", e)

# Registrar blueprints (condicional para permitir CI/testes sem DB real)
if not SKIP_DB_INIT:
    # Registrar blueprints de autenticação
    # Use auth_supabase_bp para Supabase Auth ou auth_bp para autenticação customizada
    USE_SUPABASE_AUTH = os.getenv('USE_SUPABASE_AUTH', 'false').lower() == 'true'

    if USE_SUPABASE_AUTH and SUPABASE_AUTH_AVAILABLE:
        app.register_blueprint(auth_supabase_bp, url_prefix='/api')
        logger.info("✅ Usando Supabase Auth para autenticação")
    else:
        app.register_blueprint(auth_bp, url_prefix='/api')
        if USE_SUPABASE_AUTH:
            logger.warning("⚠️  USE_SUPABASE_AUTH=true mas módulo não disponível. Usando autenticação customizada.")
        else:
            logger.info("✅ Usando autenticação customizada")

    app.register_blueprint(categories_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(planning_bp)
else:
    logger.warning("⚠️  SKIP_DB_INIT=true: blueprints de dados NÃO registrados (somente /api/health disponível)")

from utils.exceptions import AppException

@app.errorhandler(AppException)
def handle_app_exception(e):
    return jsonify(e.to_dict()), e.status_code

def create_indices():
    """Índices são criados no schema SQL do Supabase"""
    # Índices já estão definidos no schema.sql
    # Esta função é mantida para compatibilidade, mas não faz nada
    pass

if __name__ == '__main__':
    create_indices()
    app.run(host='0.0.0.0', port=8001, debug=True)
