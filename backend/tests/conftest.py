"""
Pytest configuration and fixtures for all tests
"""
import os
import pytest
from pymongo import MongoClient
from app import app as flask_app
import jwt
from datetime import datetime, timedelta


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    flask_app.config.update({
        'TESTING': True,
        'MONGO_URL': os.getenv('MONGO_URL', 'mongodb://localhost:27017/alca_financas_test'),
        'JWT_SECRET': os.getenv('JWT_SECRET', 'test-secret-key'),
        'RATELIMIT_ENABLED': True,
        'RATELIMIT_STORAGE_URI': 'memory://'
    })

    # Re-initialize DB connection for tests to ensure we use the test database
    mongo_url = flask_app.config['MONGO_URL']
    mongo_client = MongoClient(mongo_url)
    db_name = mongo_url.split('/')[-1]
    db = mongo_client[db_name]
    
    flask_app.config['DB'] = db
    flask_app.config['USERS'] = db.users
    flask_app.config['CATEGORIES'] = db.categories
    flask_app.config['TRANSACTIONS'] = db.transactions
    flask_app.config['ACCOUNTS'] = db.accounts

    yield flask_app


@pytest.fixture(scope='session')
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """Database fixture with cleanup"""
    mongo_url = app.config['MONGO_URL']
    mongo_client = MongoClient(mongo_url)
    db_name = mongo_url.split('/')[-1]
    database = mongo_client[db_name]

    yield database

    # Cleanup after each test
    for collection in database.list_collection_names():
        database[collection].delete_many({})


@pytest.fixture
def test_user(db):
    """Create a test user"""
    from utils.auth_utils import hash_password
    import uuid

    user_id = str(uuid.uuid4())
    user = {
        '_id': user_id,
        'name': 'Test User',
        'email': 'test@alcahub.com.br',
        'password': hash_password('TestPassword123!'),
        'created_at': datetime.utcnow()
    }
    db.users.insert_one(user)
    return user


@pytest.fixture
def auth_token(app, test_user):
    """Generate JWT token for test user"""
    secret = app.config['JWT_SECRET']
    token = jwt.encode(
        {
            'user_id': test_user['_id'],
            'exp': datetime.utcnow() + timedelta(hours=1)
        },
        secret,
        algorithm='HS256'
    )
    return token


@pytest.fixture
def auth_headers(test_user):
    from utils.auth_utils import generate_jwt
    tokens = generate_jwt(test_user['_id'])
    token = tokens['access_token']
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def test_category(db, test_user):
    """Create a test category"""
    import uuid
    category = {
        '_id': str(uuid.uuid4()),
        'user_id': test_user['_id'],
        'name': 'Alimentação',
        'type': 'expense',
        'color': '#FF5722',
        'icon': 'restaurant'
    }
    db.categories.insert_one(category)
    return category


@pytest.fixture
def test_account(db, test_user):
    """Create a test account"""
    import uuid
    account = {
        '_id': str(uuid.uuid4()),
        'user_id': test_user['_id'],
        'name': 'Conta Corrente',
        'type': 'checking',
        'balance': 1000.0,
        'initial_balance': 1000.0,
        'color': '#2196F3'
    }
    db.accounts.insert_one(account)
    return account


@pytest.fixture
def test_transaction(db, test_user, test_category, test_account):
    """Create a test transaction"""
    import uuid
    transaction = {
        '_id': str(uuid.uuid4()),
        'user_id': test_user['_id'],
        'description': 'Compra teste',
        'amount': 50.0,
        'type': 'expense',
        'category_id': test_category['_id'],
        'account_id': test_account['_id'],
        'date': datetime.utcnow(),
        'status': 'pending',
        'is_recurring': False
    }
    db.transactions.insert_one(transaction)
    return transaction


@pytest.fixture
def api_base_url():
    """Get API base URL based on environment"""
    env = os.getenv('NODE_ENV', 'local')
    if env == 'production':
        return os.getenv('PROD_API_URL', 'https://api.alcahub.com.br')
    return os.getenv('LOCAL_API_URL', 'http://localhost:5000')
