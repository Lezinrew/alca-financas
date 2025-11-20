"""
Integration tests for dashboard API endpoints
"""
import pytest
import json


@pytest.mark.api
class TestDashboardAPI:
    """Test dashboard endpoints"""

    def test_get_dashboard(self, client, auth_headers):
        """Test getting dashboard summary"""
        response = client.get(
            '/api/dashboard',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        # Dashboard returns expense_by_category, income_by_category, etc.
        assert 'summary' in data
        assert 'recent_transactions' in data

    def test_get_dashboard_advanced(self, client, auth_headers):
        """Test dashboard advanced endpoint with evolution"""
        response = client.get(
            '/api/dashboard-advanced?show_evolution=true',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'summary' in data
        assert 'monthly_evolution' in data
        assert isinstance(data['monthly_evolution'], list)

    def test_get_dashboard_advanced_no_evolution(self, client, auth_headers):
        """Test dashboard advanced without evolution"""
        response = client.get(
            '/api/dashboard-advanced?show_evolution=false',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'summary' in data
        assert 'monthly_evolution' not in data

    def test_get_dashboard_settings(self, client, auth_headers):
        """Test get dashboard settings"""
        response = client.get(
            '/api/dashboard-settings',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        # Should have default settings
        assert 'show_expenses_by_category' in data

    def test_update_dashboard_settings(self, client, auth_headers):
        """Test update dashboard settings"""
        payload = {
            'show_expenses_by_category': False,
            'show_income_by_category': True,
            'show_balance_chart': False
        }
        
        response = client.put(
            '/api/dashboard-settings',
            data=json.dumps(payload),
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data

    def test_get_dashboard_with_params(self, client, auth_headers):
        """Test getting dashboard with month/year params"""
        response = client.get(
            '/api/dashboard?month=1&year=2025',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
