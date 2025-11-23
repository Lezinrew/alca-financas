from flask import Blueprint, request, jsonify, current_app
from utils.auth_utils import require_auth
from repositories.category_repository import CategoryRepository
from services.category_service import CategoryService
from utils.exceptions import ValidationException, NotFoundException

bp = Blueprint('categories', __name__, url_prefix='/api/categories')

@bp.route('', methods=['GET', 'POST'])
@require_auth
def categories():
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    repo = CategoryRepository(categories_collection)
    service = CategoryService(repo, transactions_collection)

    if request.method == 'GET':
        return jsonify(service.list_categories(request.user_id))
    
    try:
        # Debug: verifica Content-Type
        content_type = request.content_type
        print(f"DEBUG: Content-Type recebido: {content_type}")
        
        data = request.get_json(force=True)  # force=True para tentar parsear mesmo sem Content-Type correto
        print(f"DEBUG: Dados recebidos: {data}")
        print(f"DEBUG: Tipo dos dados: {type(data)}")
        
        if not data:
            # Tenta pegar dados do form se JSON não funcionou
            if request.form:
                data = dict(request.form)
                print(f"DEBUG: Dados do form: {data}")
            else:
                return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        # Validação básica antes de chamar o serviço
        if not isinstance(data, dict):
            return jsonify({'error': 'Dados devem ser um objeto JSON'}), 400
        
        print(f"DEBUG: Chamando create_category com user_id={request.user_id}, data={data}")
        category = service.create_category(request.user_id, data)
        return jsonify(category), 201
    except ValidationException as e:
        print(f"DEBUG: ValidationException: {e.to_dict()}")
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        import traceback
        print(f"DEBUG: Exception: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Erro ao criar categoria: {str(e)}'}), 500

@bp.route('/<category_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def category_detail(category_id: str):
    categories_collection = current_app.config['CATEGORIES']
    transactions_collection = current_app.config['TRANSACTIONS']
    
    repo = CategoryRepository(categories_collection)
    service = CategoryService(repo, transactions_collection)

    try:
        if request.method == 'GET':
            return jsonify(service.get_category(request.user_id, category_id))

        if request.method == 'DELETE':
            service.delete_category(request.user_id, category_id)
            return jsonify({'message': 'Categoria deletada com sucesso'})
        
        data = request.get_json()
        result = service.update_category(request.user_id, category_id, data)
        return jsonify(result)
    except (ValidationException, NotFoundException) as e:
        return jsonify(e.to_dict()), e.status_code


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


