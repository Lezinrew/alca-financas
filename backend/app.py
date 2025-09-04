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
app.secret_key = os.getenv('SECRET_KEY')

CORS(app, origins=os.getenv('CORS_ORIGINS', '*').split(','))

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

mongo_client = MongoClient(os.getenv('MONGO_URI'))
db = mongo_client[os.getenv('MONGO_DB')]
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
