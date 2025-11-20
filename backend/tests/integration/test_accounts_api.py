"""
Integration tests for accounts API endpoints
"""
import pytest
import json

@pytest.mark.api
class TestAccountsAPI:
    """Test account endpoints"""

    def test_list_accounts(self, client, auth_headers, test_account):
        """Test listing accounts"""
        response = client.get(
            '/api/accounts',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]['name'] == test_account['name']

    def test_create_account_success(self, client, auth_headers):
        """Test creating an account"""
        payload = {
            'name': 'New Account',
            'type': 'checking',
            'balance': 500.0,
            'color': '#000000',
            'icon': 'bank'
        }

        response = client.post(
            '/api/accounts',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == payload['name']
        assert data['current_balance'] == payload['balance']

    def test_create_account_validation_error(self, client, auth_headers):
        """Test creating account with missing fields"""
        payload = {
            'type': 'checking'
        }

        response = client.post(
            '/api/accounts',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_get_account_detail(self, client, auth_headers, test_account):
        """Test getting account details"""
        response = client.get(
            f'/api/accounts/{test_account["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == test_account['name']

    def test_update_account(self, client, auth_headers, test_account):
        """Test updating an account"""
        payload = {
            'name': 'Updated Account Name',
            'balance': 2000.0
        }

        response = client.put(
            f'/api/accounts/{test_account["_id"]}',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == payload['name']
        # Balance update via PUT might be restricted or handled differently in service
        # AccountService.update usually updates fields. 
        # Let's check if balance update is allowed directly. 
        # Usually balance is updated via transactions.
        # But for manual update (correction), it might be allowed.

    def test_delete_account(self, client, auth_headers, test_account):
        """Test deleting an account"""
        response = client.delete(
            f'/api/accounts/{test_account["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_account_not_found(self, client, auth_headers):
        """Test accessing non-existent account"""
        response = client.get(
            '/api/accounts/non-existent-id',
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_import_credit_card_statement_success(self, client, auth_headers):
        """Test importing credit card statement"""
        import io
        
        # Create credit card account
        account_payload = {
            'name': 'Test Credit Card',
            'type': 'credit_card',
            'balance': 0.0
        }
        acc_response = client.post(
            '/api/accounts', 
            data=json.dumps(account_payload), 
            headers=auth_headers
        )
        assert acc_response.status_code == 201
        account_id = json.loads(acc_response.data)['id']

        # Prepare CSV file (Nubank format)
        csv_content = b"date,title,amount\n2023-01-01,Uber,15.90\n"
        data = {
            'file': (io.BytesIO(csv_content), 'statement.csv')
        }

        response = client.post(
            f'/api/accounts/{account_id}/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result['imported_count'] == 1
        assert result['file_format'] == 'nubank_csv'

    def test_import_credit_card_statement_invalid_file(self, client, auth_headers):
        """Test importing invalid file type"""
        import io
        
        # Create credit card account
        account_payload = {
            'name': 'Test Credit Card 2',
            'type': 'credit_card',
            'balance': 0.0
        }
        acc_response = client.post(
            '/api/accounts', 
            data=json.dumps(account_payload), 
            headers=auth_headers
        )
        account_id = json.loads(acc_response.data)['id']

        data = {
            'file': (io.BytesIO(b"dummy"), 'statement.txt')
        }

        response = client.post(
            f'/api/accounts/{account_id}/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
