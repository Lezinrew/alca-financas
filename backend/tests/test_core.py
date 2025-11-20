import pytest
from unittest.mock import Mock
from services.category_service import CategoryService
from services.account_service import AccountService
from utils.exceptions import ValidationException, NotFoundException

def test_category_crud(client, auth_headers, db, test_user):
    # Create
    data = {
        'name': 'New Category',
        'type': 'expense',
        'color': '#000000',
        'icon': 'test'
    }
    resp = client.post('/api/categories', json=data, headers=auth_headers)
    assert resp.status_code == 201
    cat_id = resp.json['id']
    
    # List
    resp = client.get('/api/categories', headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json) >= 1
    
    # Update
    update_data = {'name': 'Updated Category'}
    resp = client.put(f'/api/categories/{cat_id}', json=update_data, headers=auth_headers)
    assert resp.status_code == 200
    
    # Verify Update
    cat = db.categories.find_one({'_id': cat_id})
    assert cat['name'] == 'Updated Category'
    
    # Delete
    resp = client.delete(f'/api/categories/{cat_id}', headers=auth_headers)
    assert resp.status_code == 200
    assert db.categories.find_one({'_id': cat_id}) is None

def test_account_crud(client, auth_headers, db, test_user):
    # Create
    data = {
        'name': 'New Account',
        'type': 'checking',
        'initial_balance': 1000
    }
    resp = client.post('/api/accounts', json=data, headers=auth_headers)
    assert resp.status_code == 201
    acc_id = resp.json['id']
    
    # List
    resp = client.get('/api/accounts', headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json) >= 1
    
    # Update
    update_data = {'name': 'Updated Account'}
    resp = client.put(f'/api/accounts/{acc_id}', json=update_data, headers=auth_headers)
    assert resp.status_code == 200
    
    # Verify Update
    acc = db.accounts.find_one({'_id': acc_id})
    assert acc['name'] == 'Updated Account'
    
    # Delete
    resp = client.delete(f'/api/accounts/{acc_id}', headers=auth_headers)
    assert resp.status_code == 200
    assert db.accounts.find_one({'_id': acc_id}) is None

def test_category_validation(client, auth_headers):
    # Missing fields
    resp = client.post('/api/categories', json={'name': 'Test'}, headers=auth_headers)
    assert resp.status_code == 400
    
    # Invalid type
    resp = client.post('/api/categories', json={'name': 'Test', 'type': 'invalid'}, headers=auth_headers)
    assert resp.status_code == 400

def test_account_validation(client, auth_headers):
    # Invalid type
    resp = client.post('/api/accounts', json={'name': 'Test', 'type': 'invalid'}, headers=auth_headers)
    assert resp.status_code == 400

def test_delete_with_transactions(client, auth_headers, db, test_user, test_category, test_account):
    # Create transaction linked to category and account
    db.transactions.insert_one({
        'user_id': test_user['_id'],
        'category_id': test_category['_id'],
        'account_id': test_account['_id'],
        'amount': 10,
        'type': 'expense',
        'date': '2023-01-01'
    })
    
    # Try delete category
    resp = client.delete(f'/api/categories/{test_category["_id"]}', headers=auth_headers)
    assert resp.status_code == 400
    assert 'Não é possível deletar' in resp.json['error']
    
    # Try delete account
    resp = client.delete(f'/api/accounts/{test_account["_id"]}', headers=auth_headers)
    assert resp.status_code == 400
    assert 'Não é possível deletar' in resp.json['error']

def test_transaction_crud(client, auth_headers, db, test_user, test_account, test_category):
    # Create
    data = {
        'description': 'Test Transaction',
        'amount': 100.0,
        'date': '2023-01-01',
        'type': 'expense',
        'category_id': test_category['_id'],
        'account_id': test_account['_id'],
        'status': 'paid'
    }
    resp = client.post('/api/transactions', json=data, headers=auth_headers)
    assert resp.status_code == 201
    
    # Verify balance update
    acc = db.accounts.find_one({'_id': test_account['_id']})
    # Initial balance (from fixture or default) - 100
    # Assuming fixture creates with 0 or known amount. 
    # Let's check the logic: create_transaction calls _update_account_balance
    
    # List
    resp = client.get('/api/transactions', headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json['data']) >= 1
    tx_id = resp.json['data'][0]['id']
    
    # Update
    update_data = {'description': 'Updated Transaction'}
    resp = client.put(f'/api/transactions/{tx_id}', json=update_data, headers=auth_headers)
    assert resp.status_code == 200
    
    # Verify Update
    tx = db.transactions.find_one({'_id': tx_id})
    assert tx['description'] == 'Updated Transaction'
    
    # Delete
    resp = client.delete(f'/api/transactions/{tx_id}', headers=auth_headers)
    assert resp.status_code == 200
    assert db.transactions.find_one({'_id': tx_id}) is None
    
    # Verify balance revert (optional, if implemented)
    # Our service implements revert on delete
    acc_after = db.accounts.find_one({'_id': test_account['_id']})
    assert acc_after['current_balance'] == acc['current_balance'] + 100 # Reverted the expense

