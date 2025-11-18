from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from services.category_service import list_categories, create_category, update_category, delete_category


bp = Blueprint('categories', __name__, url_prefix='/api/categories')


@bp.route('', methods=['GET', 'POST'])
@require_auth
def categories():
    categories_collection = current_app.config['CATEGORIES']
    if request.method == 'GET':
        return jsonify(list_categories(categories_collection, request.user_id))
    data = request.get_json()
    if not data.get('name') or not data.get('type'):
        return jsonify({'error': 'Nome e tipo da categoria são obrigatórios'}), 400
    if data['type'] not in ['income', 'expense']:
        return jsonify({'error': 'Tipo deve ser income ou expense'}), 400
    category = create_category(categories_collection, request.user_id, data)
    return jsonify(category), 201


@bp.route('/<category_id>', methods=['PUT', 'DELETE'])
@require_auth
def category_detail(category_id: str):
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    category = categories_collection.find_one({'_id': category_id, 'user_id': request.user_id})
    if not category:
        return jsonify({'error': 'Categoria não encontrada'}), 404
    if request.method == 'DELETE':
        ok = delete_category(categories_collection, transactions_collection, request.user_id, category_id)
        if not ok:
            count = transactions_collection.count_documents({'category_id': category_id})
            return jsonify({'error': f'Não é possível deletar. Existem {count} transações nesta categoria'}), 400
        return jsonify({'message': 'Categoria deletada com sucesso'})
    data = request.get_json()
    update_category(categories_collection, request.user_id, category_id, data)
    return jsonify({'message': 'Categoria atualizada com sucesso'})


@bp.route('/import', methods=['POST'])
@require_auth
def import_categories():
    """Importa categorias de um arquivo JSON ou CSV"""
    try:
        user_id = request.user_id
        categories_collection = current_app.config['CATEGORIES']
        
        if 'file' not in request.files:
            return jsonify({'error': 'Arquivo é obrigatório'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        filename_lower = file.filename.lower()
        imported_count = 0
        errors = []
        
        if filename_lower.endswith('.json'):
            import json
            try:
                data = json.loads(file.read().decode('utf-8'))
                categories_data = data if isinstance(data, list) else data.get('categories', [])
                
                for idx, cat in enumerate(categories_data):
                    try:
                        if not cat.get('name') or not cat.get('type'):
                            errors.append(f'Linha {idx + 1}: Nome e tipo são obrigatórios')
                            continue
                        
                        # Verifica se já existe
                        existing = categories_collection.find_one({
                            'user_id': user_id,
                            'name': cat['name'],
                            'type': cat['type']
                        })
                        
                        if existing:
                            errors.append(f'Categoria "{cat["name"]}" já existe')
                            continue
                        
                        category_data = {
                            'user_id': user_id,
                            'name': cat['name'],
                            'type': cat['type'],
                            'color': cat.get('color', '#6366f1'),
                            'icon': cat.get('icon', 'circle'),
                            'description': cat.get('description', '')
                        }
                        
                        categories_collection.insert_one(category_data)
                        imported_count += 1
                    except Exception as e:
                        errors.append(f'Linha {idx + 1}: {str(e)}')
            
            except json.JSONDecodeError:
                return jsonify({'error': 'Arquivo JSON inválido'}), 400
        
        elif filename_lower.endswith('.csv'):
            import csv
            from io import StringIO
            
            try:
                content = file.read().decode('utf-8')
                reader = csv.DictReader(StringIO(content))
                
                for idx, row in enumerate(reader):
                    try:
                        if not row.get('name') or not row.get('type'):
                            errors.append(f'Linha {idx + 2}: Nome e tipo são obrigatórios')
                            continue
                        
                        existing = categories_collection.find_one({
                            'user_id': user_id,
                            'name': row['name'],
                            'type': row['type']
                        })
                        
                        if existing:
                            errors.append(f'Categoria "{row["name"]}" já existe')
                            continue
                        
                        category_data = {
                            'user_id': user_id,
                            'name': row['name'],
                            'type': row['type'],
                            'color': row.get('color', '#6366f1'),
                            'icon': row.get('icon', 'circle'),
                            'description': row.get('description', '')
                        }
                        
                        categories_collection.insert_one(category_data)
                        imported_count += 1
                    except Exception as e:
                        errors.append(f'Linha {idx + 2}: {str(e)}')
            
            except Exception as e:
                return jsonify({'error': f'Erro ao processar CSV: {str(e)}'}), 400
        
        else:
            return jsonify({'error': 'Apenas arquivos JSON e CSV são aceitos'}), 400
        
        return jsonify({
            'message': f'{imported_count} categorias importadas com sucesso',
            'imported_count': imported_count,
            'errors': errors if errors else None
        })
    
    except Exception as e:
        return jsonify({'error': f'Erro ao importar categorias: {str(e)}'}), 500


