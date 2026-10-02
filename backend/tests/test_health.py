"""Health check da API (mantido do antigo tests/integration/test_auth_api.py)."""


def test_health_check(client):
    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'
