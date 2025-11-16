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
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_transactions_with_filters(self, client, auth_headers):
        """Test listing transactions with filters"""
        response = client.get(
            '/api/transactions?month=1&year=2025&type=expense',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_create_transaction_success(self, client, auth_headers, test_category):
        """Test creating a transaction"""
        payload = {
            'description': 'Test Transaction',
            'amount': 100.0,
            'type': 'expense',
            'category_id': test_category['_id'],
            'date': datetime.utcnow().isoformat()
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
            'date': datetime.utcnow().isoformat()
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
            'date': datetime.utcnow().isoformat(),
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
