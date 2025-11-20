"""
Integration tests for reports API endpoints
"""
import pytest
import json


@pytest.mark.api
class TestReportsAPI:
    """Test reports endpoints"""

    def test_reports_overview_expenses_by_category(self, client, auth_headers):
        """Test reports overview for expenses by category"""
        response = client.get(
            '/api/reports/overview?type=expenses_by_category',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['report_type'] == 'expenses_by_category'
        assert 'data' in data
        assert 'total_amount' in data

    def test_reports_overview_income_by_category(self, client, auth_headers):
        """Test reports overview for income by category"""
        response = client.get(
            '/api/reports/overview?type=income_by_category',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['report_type'] == 'income_by_category'

    def test_reports_overview_balance_by_account(self, client, auth_headers):
        """Test reports overview for balance by account"""
        response = client.get(
            '/api/reports/overview?type=balance_by_account',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['report_type'] == 'balance_by_account'

    def test_reports_evolution(self, client, auth_headers):
        """Test reports evolution endpoint"""
        response = client.get(
            '/api/reports/evolution',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data

    def test_reports_comparison(self, client, auth_headers):
        """Test reports comparison endpoint"""
        response = client.get(
            '/api/reports/comparison',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'current_period' in data
        assert 'previous_period' in data
        assert 'variations' in data

    def test_reports_comparison_with_params(self, client, auth_headers):
        """Test reports comparison with specific month/year"""
        response = client.get(
            '/api/reports/comparison?current_month=1&current_year=2025',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'current_period' in data
        assert 'previous_period' in data
