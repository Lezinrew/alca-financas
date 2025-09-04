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


