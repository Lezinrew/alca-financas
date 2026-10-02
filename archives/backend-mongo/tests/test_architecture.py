import pytest
from unittest.mock import Mock, MagicMock
from services.transaction_service import TransactionService
from repositories.transaction_repository import TransactionRepository
from utils.exceptions import ValidationException

def test_pagination_structure(client, db, test_user, test_category, test_account):
    """Test if the API returns the correct pagination structure"""
    # Create 25 transactions
    import uuid
    from datetime import datetime
    
    transactions = []
    for i in range(25):
        transactions.append({
            '_id': str(uuid.uuid4()),
            'user_id': test_user['_id'],
            'description': f'Transaction {i}',
            'amount': 10.0,
            'type': 'expense',
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'date': datetime.utcnow(),
            'created_at': datetime.utcnow()
        })
    db.transactions.insert_many(transactions)

    # Request page 1 with limit 10
    token = client.application.config['JWT_SECRET'] # Mock token generation or use fixture
    # We need a valid token. Let's use the auth_headers fixture if available or generate one.
    # Re-using logic from conftest would be best, but let's assume client fixture handles it or we need headers.
    
    # Actually, let's use the auth_headers fixture from conftest
    pass

def test_pagination_api(client, auth_headers, db, test_user, test_category, test_account):
    # Create 25 transactions
    import uuid
    from datetime import datetime
    
    transactions = []
    for i in range(25):
        transactions.append({
            '_id': str(uuid.uuid4()),
            'user_id': test_user['_id'],
            'description': f'Transaction {i}',
            'amount': 10.0,
            'type': 'expense',
            'category_id': test_category['_id'],
            'account_id': test_account['_id'],
            'date': datetime.utcnow(),
            'created_at': datetime.utcnow()
        })
    db.transactions.insert_many(transactions)
    
    response = client.get('/api/transactions?page=1&limit=10', headers=auth_headers)
    assert response.status_code == 200
    data = response.json
    
    assert 'data' in data
    assert 'pagination' in data
    assert len(data['data']) == 10
    assert data['pagination']['total'] == 25
    assert data['pagination']['pages'] == 3
    assert data['pagination']['page'] == 1

    # Page 2
    response = client.get('/api/transactions?page=2&limit=10', headers=auth_headers)
    assert len(response.json['data']) == 10
    assert response.json['pagination']['page'] == 2

    # Page 3
    response = client.get('/api/transactions?page=3&limit=10', headers=auth_headers)
    assert len(response.json['data']) == 5

def test_validation_exception(client, auth_headers):
    """Test if ValidationException returns 400 and correct format"""
    response = client.post('/api/transactions', json={}, headers=auth_headers)
    assert response.status_code == 400
    assert 'error' in response.json

def test_service_logic_mock():
    """Unit test for service logic using mocks"""
    repo = Mock(spec=TransactionRepository)
    categories = Mock()
    accounts = Mock()
    service = TransactionService(repo, categories, accounts)

def test_service_logic_mock():
    mock_repo = Mock(spec=TransactionRepository)
    service = TransactionService(mock_repo, MagicMock(), MagicMock())
    
    # Mock create_many to return list of IDs
    mock_repo.create_many.return_value = ['id1', 'id2']
    
    data = {
        'description': 'Test',
        'amount': 100,
        'date': '2023-01-01',
        'installments': 2,
        'category_id': 'cat1',
        'type': 'expense'
    }
    
    # Mock accounts collection find_one to return None (no account)
    service.accounts_collection.find_one.return_value = None
    
    result = service.create_transaction('user1', data)
    
    assert result['count'] == 2
    mock_repo.create_many.assert_called_once()
