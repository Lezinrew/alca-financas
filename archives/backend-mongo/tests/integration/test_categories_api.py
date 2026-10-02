"""
Integration tests for categories API endpoints
"""
import pytest
import json

@pytest.mark.api
class TestCategoriesAPI:
    """Test category endpoints"""

    def test_list_categories(self, client, auth_headers, test_category):
        """Test listing categories"""
        response = client.get(
            '/api/categories',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]['name'] == test_category['name']

    def test_create_category_success(self, client, auth_headers):
        """Test creating a category"""
        payload = {
            'name': 'New Category',
            'type': 'expense',
            'color': '#FFFFFF',
            'icon': 'star'
        }

        response = client.post(
            '/api/categories',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == payload['name']

    def test_create_category_validation_error(self, client, auth_headers):
        """Test creating category with missing fields"""
        payload = {
            'type': 'expense'
        }

        response = client.post(
            '/api/categories',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_get_category_detail(self, client, auth_headers, test_category):
        """Test getting category details"""
        response = client.get(
            f'/api/categories/{test_category["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == test_category['name']

    def test_update_category(self, client, auth_headers, test_category):
        """Test updating a category"""
        payload = {
            'name': 'Updated Category Name'
        }

        response = client.put(
            f'/api/categories/{test_category["_id"]}',
            data=json.dumps(payload),
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == payload['name']

    def test_delete_category(self, client, auth_headers, test_category):
        """Test deleting a category"""
        response = client.delete(
            f'/api/categories/{test_category["_id"]}',
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_category_not_found(self, client, auth_headers):
        """Test accessing non-existent category"""
        response = client.get(
            '/api/categories/non-existent-id',
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_import_categories_json(self, client, auth_headers):
        """Test importing categories from JSON file"""
        import io
        
        json_content = json.dumps([
            {
                'name': 'Imported Category 1',
                'type': 'expense',
                'color': '#FF0000',
                'icon': 'star'
            },
            {
                'name': 'Imported Category 2',
                'type': 'income',
                'color': '#00FF00',
                'icon': 'circle'
            }
        ])
        
        data = {
            'file': (io.BytesIO(json_content.encode('utf-8')), 'categories.json')
        }
        
        response = client.post(
            '/api/categories/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['imported_count'] == 2

    def test_import_categories_invalid_file(self, client, auth_headers):
        """Test importing categories with invalid file type"""
        import io
        
        data = {
            'file': (io.BytesIO(b"invalid content"), 'categories.txt')
        }
        
        response = client.post(
            '/api/categories/import',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
