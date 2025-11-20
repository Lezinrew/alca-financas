"""
Integration tests for transactions API endpoints
"""
import pytest
import json
from datetime import datetime


@pytest.mark.api
class TestTransactionsAPI:
    """Test transaction endpoints"""

    def test_list_transactions(self, client, auth_headers, test_transaction):
        """Test listing transactions"""
        response = client.get(
            '/api/transactions',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        # Expect paginated response
        assert 'data' in data
        assert isinstance(data['data'], list)
        assert len(data['data']) > 0

    def test_list_transactions_with_filters(self, client, auth_headers):
        """Test listing transactions with filters"""
        response = client.get(
            '/api/transactions?month=1&year=2025&type=expense',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'data' in data
        assert isinstance(data['data'], list)

    def test_create_transaction_success(self, client, auth_headers, test_category):
        """Test creating a transaction"""
        payload = {
            'description': 'Test Transaction',
            'amount': 100.0,
            'type': 'expense',
            'category_id': test_category['_id'],
            'date': datetime.utcnow().strftime('%Y-%m-%d')
        }

        response = client.post(
            '/api/transactions',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data

    def test_create_transaction_missing_fields(self, client, auth_headers):
        """Test creating transaction with missing fields"""
        payload = {
            'description': 'Incomplete Transaction'
        }

        response = client.post(
            '/api/transactions',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_create_transaction_invalid_type(self, client, auth_headers, test_category):
        """Test creating transaction with invalid type"""
        payload = {
            'description': 'Invalid Transaction',
            'amount': 100.0,
            'type': 'invalid_type',
            'category_id': test_category['_id'],
            'date': datetime.utcnow().strftime('%Y-%m-%d')
        }

        response = client.post(
            '/api/transactions',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_create_installment_transaction(self, client, auth_headers, test_category):
        """Test creating installment transaction"""
        payload = {
            'description': 'Installment Purchase',
            'amount': 300.0,
            'type': 'expense',
            'category_id': test_category['_id'],
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'installments': 3
        }

        response = client.post(
            '/api/transactions',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['count'] == 3

    def test_update_transaction(self, client, auth_headers, test_transaction):
        """Test updating a transaction"""
        payload = {
            'description': 'Updated Description',
            'amount': 75.0
        }

        response = client.put(
            f'/api/transactions/{test_transaction["_id"]}',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_get_transaction_detail(self, client, auth_headers, test_transaction):
        """Test getting transaction details"""
        response = client.get(
            f'/api/transactions/{test_transaction["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['description'] == test_transaction['description']

    def test_delete_transaction(self, client, auth_headers, test_transaction):
        """Test deleting a transaction"""
        response = client.delete(
            f'/api/transactions/{test_transaction["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_transaction_not_found(self, client, auth_headers):
        """Test accessing non-existent transaction"""
        response = client.get(
            '/api/transactions/non-existent-id',
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_unauthorized_access(self, client):
        """Test accessing transactions without auth"""
        response = client.get('/api/transactions')

        assert response.status_code == 401

    def test_import_transactions_csv(self, client, auth_headers, test_account):
        """Test importing transactions from CSV (Nubank format)"""
        import io
        
        # Use Nubank CSV format which is actually supported
        csv_content = b"date,title,amount\n2025-01-15,Uber,50.00\n2025-01-16,Salary,100.00\n"
        data = {
            'file': (io.BytesIO(csv_content), 'nubank.csv'),
            'account_id': test_account['_id']
        }
        
        response = client.post(
            '/api/transactions/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code in [200, 201]
        result = json.loads(response.data)
        assert 'imported_count' in result

    def test_import_transactions_no_file(self, client, auth_headers):
        """Test import without file"""
        response = client.post(
            '/api/transactions/import',
            data={},
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result

    def test_import_transactions_invalid_format(self, client, auth_headers):
        """Test import with invalid file format"""
        import io
        
        data = {
            'file': (io.BytesIO(b"invalid"), 'file.txt')
        }
        
        response = client.post(
            '/api/transactions/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
