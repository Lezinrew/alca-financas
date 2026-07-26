# backend/routes/auth.py

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import uuid
import os
import base64
import json
import jwt
import requests

from utils.auth_utils import require_auth
from services.user_service import create_default_categories, get_user_public
from services.bootstrap_service import AuthBootstrapService, TenantBootstrapError
from schemas.auth_schemas import UserRegisterSchema, UserLoginSchema, RefreshTokenSchema
from extensions import limiter
from pydantic import ValidationError
from services.supabase_auth_service import SupabaseAuthService
from services.user_data_wipe_service import wipe_user_business_data


# Remova o 'url_prefix' daqui. Ele será definido em app.py
bp = Blueprint('auth', __name__)


def _user_id(user):
    """ID do usuário (Supabase usa 'id', MongoDB usa '_id')."""
    return user.get('_id') or user.get('id')


def _user_id_filter(user_id):
    """Filtro para buscar usuário por ID (Supabase: id, MongoDB: _id)."""
    if current_app.config.get('DB_TYPE') == 'supabase':
        return {'id': user_id}
    return {'_id': user_id}


# Adicione '/auth' a todas as rotas de autenticação para agrupar logicamente os endpoints.
@bp.route('/auth/register', methods=['POST'])
@limiter.limit("3 per hour")
def register():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        data = UserRegisterSchema(**request_data)
    except ValidationError as e:
        # Formata erros do Pydantic em mensagens mais amigáveis
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação nos dados fornecidos'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar registro: {str(e)}'}), 400

    email_norm = data.email.strip().lower()

    # Supabase-only: criação de usuário via Supabase Auth
    try:
        auth_service = SupabaseAuthService()
        result = auth_service.sign_up(
            email=email_norm,
            password=data.password,
            name=data.name,
        )

        # Criar categorias padrão (repo já está no config do app)
        categories_collection = current_app.config['CATEGORIES']
        create_default_categories(categories_collection, result['user']['id'])

        return jsonify({
            'message': 'Usuário criado com sucesso',
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token'),
            'user': result.get('user'),
        }), 201
    except Exception as e:
        error_msg = str(e)
        if 'already registered' in error_msg.lower() or 'user already exists' in error_msg.lower():
            return jsonify({'error': 'Email já cadastrado'}), 400
        if 'email rate limit exceeded' in error_msg.lower() or 'rate limit' in error_msg.lower():
            return jsonify({'error': 'Muitas tentativas de cadastro no momento. Tente novamente em instantes.'}), 429
        current_app.logger.error(f"Erro ao registrar usuário (Supabase): {e}")
        return jsonify({'error': f'Erro ao criar usuário: {error_msg}'}), 500


@bp.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'Dados não fornecidos. Certifique-se de enviar JSON válido.'}), 400
        
        data = UserLoginSchema(**request_data)
    except ValidationError as e:
        # Formata erros do Pydantic em mensagens mais amigáveis
        error_messages = []
        for error in e.errors():
            field = error.get('loc', [''])[-1] if error.get('loc') else 'campo'
            msg = error.get('msg', 'Erro de validação')
            if field:
                error_messages.append(f"{field}: {msg}")
            else:
                error_messages.append(msg)
        
        error_message = '; '.join(error_messages) if error_messages else 'Erro de validação nos dados fornecidos'
        return jsonify({'error': error_message}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar login: {str(e)}'}), 400

    email = data.email.strip().lower()

    try:
        auth_service = SupabaseAuthService()
        result = auth_service.sign_in(email=email, password=data.password)
        return jsonify({
            'message': 'Login realizado com sucesso',
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token'),
            'user': result.get('user'),
        })
    except Exception as e:
        error_msg = str(e)
        if 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
            return jsonify({'error': 'Email ou senha incorretos'}), 401
        if 'email not confirmed' in error_msg.lower():
            return jsonify({'error': 'Email não confirmado. Verifique sua caixa de entrada.'}), 401
        current_app.logger.error(f"Erro no login (Supabase): {e}")
        return jsonify({'error': f'Erro no login: {error_msg}'}), 500


@bp.route('/auth/refresh', methods=['POST'])
@limiter.limit("10 per minute")
def refresh():
    try:
        data = RefreshTokenSchema(**request.get_json())
    except ValidationError as e:
        return jsonify({'error': e.errors()}), 400

    try:
        auth_service = SupabaseAuthService()
        result = auth_service.refresh_session(data.refresh_token)
        if not result:
            return jsonify({'error': 'Token inválido ou expirado'}), 401
        return jsonify({
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token'),
        })
    except Exception as e:
        current_app.logger.error(f"Erro ao renovar sessão (Supabase): {e}")
        return jsonify({'error': 'Erro ao renovar token'}), 500


@bp.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    # Supabase-only: o frontend usa supabase.auth.resetPasswordForEmail diretamente.
    return jsonify({'error': 'Use o fluxo de redefinição de senha do Supabase pelo frontend.'}), 410


@bp.route('/auth/reset-password', methods=['POST'])
def reset_password():
    # Supabase-only: o frontend usa supabase.auth.updateUser({ password }) após recovery.
    return jsonify({'error': 'Use o fluxo de redefinição de senha do Supabase pelo frontend.'}), 410


@bp.route('/auth/me', methods=['GET'])
@limiter.exempt
@require_auth
def get_user():
    users_collection = current_app.config['USERS']
    user = users_collection.find_one(_user_id_filter(request.user_id))
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    role = user.get('role') or ('admin' if user.get('is_admin') else 'user')
    status = user.get('status') or 'active'
    is_admin = role == 'admin' or bool(user.get('is_admin'))
    return jsonify({
        'id': _user_id(user),
        'name': user['name'],
        'email': user['email'],
        'settings': user.get('settings', {}),
        'auth_providers': user.get('auth_providers', []),
        'role': role,
        'status': status,
        'is_admin': is_admin,
    })


@bp.route('/auth/bootstrap', methods=['POST'])
@require_auth
def bootstrap_user():
    """
    Bootstrap pós-login (Supabase-only, banco limpo e idempotente).

    Invariante obrigatória:
    - NUNCA exigir tenant antes de `public.users` existir para o `user_id` autenticado.
      `tenant_members.user_id` possui FK para `public.users(id)`.
      Portanto esta rota usa apenas `@require_auth` (não `@require_tenant`).

    Contrato de erro:
    - `403 tenant_required`: usado em rotas de dados quando autenticação existe, mas tenant não foi resolvido.
    - `503 tenant_bootstrap_failed`: usado aqui quando bootstrap mínimo (users/tenant_members/migração) falha.
    """
    user_id = request.user_id
    users_repo = current_app.config["USERS"]
    categories_repo = current_app.config["CATEGORIES"]
    auth_header = request.headers.get("Authorization") or ""
    access_token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header

    try:
        try:
            bootstrap_result = AuthBootstrapService().ensure_user_and_tenant(
                user_id=user_id,
                users_repo=users_repo,
                access_token=access_token,
                jwt_claims=getattr(request, "jwt_payload", None),
            )
        except TypeError as exc:
            # Compatibilidade: containers antigos podem ter ensure_user_and_tenant sem `jwt_claims`.
            if "unexpected keyword argument" in str(exc) and "jwt_claims" in str(exc):
                bootstrap_result = AuthBootstrapService().ensure_user_and_tenant(
                    user_id=user_id,
                    users_repo=users_repo,
                    access_token=access_token,
                )
            else:
                raise
        tenant_id = bootstrap_result.tenant_id
    except TenantBootstrapError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.status_code

    # 3) Seed de categorias por tenant (idempotente)
    existing_categories = []
    if hasattr(categories_repo, "find_by_user"):
        existing_categories = categories_repo.find_by_user(user_id, tenant_id=tenant_id) or []
    else:
        existing_categories = categories_repo.find_all({"user_id": user_id, "tenant_id": tenant_id}) or []

    if not existing_categories:
        create_default_categories(categories_repo, user_id, tenant_id=tenant_id)

    return jsonify({"ok": True, "tenant_id": tenant_id}), 200


@bp.route('/auth/settings', methods=['GET', 'PUT'])
@require_auth
def user_settings():
    users_collection = current_app.config['USERS']
    if request.method == 'GET':
        user = users_collection.find_one(_user_id_filter(request.user_id))
        return jsonify(user.get('settings', {}) if user else {})
    data = request.get_json() or {}
    allowed_settings = ['currency', 'theme', 'language']
    update_data = {k: data[k] for k in allowed_settings if k in data}
    if update_data:
        if hasattr(users_collection, 'update_settings'):
            users_collection.update_settings(request.user_id, update_data)
        else:
            users_collection.update_one({'_id': request.user_id}, {'$set': {f'settings.{k}': v for k, v in update_data.items()}})
    return jsonify({'message': 'Configurações atualizadas com sucesso'})


@bp.route('/auth/google/login', methods=['GET'])
def google_login():
    # Removido em 2026-07-26: callback usava MongoDB (find_one com $or/$push,
    # insert_one) contra o repositório Supabase, que só suporta .eq() simples —
    # a rota nunca funcionou em produção (sempre caía no except genérico) e
    # não é oferecida por nenhum botão no frontend atual (Login.tsx). Também
    # era o único chamador de generate_jwt (token legado da app, removido de
    # auth_utils.py). Reimplementar exigiria reescrever o fluxo contra
    # Supabase Auth (ou usar o provider OAuth nativo do Supabase).
    return jsonify({'error': 'Login com Google não implementado ainda', 'message': 'Configure OAuth do Google via Supabase Auth'}), 501


@bp.route('/auth/google/callback', methods=['GET'])
def google_callback():
    return jsonify({'error': 'Login com Google não implementado ainda', 'message': 'Configure OAuth do Google via Supabase Auth'}), 501


@bp.route('/auth/microsoft/login', methods=['GET'])
def microsoft_login():
    return jsonify({'error': 'Login com Microsoft não implementado ainda', 'message': 'Configure as credenciais do Microsoft OAuth no arquivo .env'}), 501


@bp.route('/auth/apple/login', methods=['GET'])
def apple_login():
    return jsonify({'error': 'Login com Apple não implementado ainda', 'message': 'Configure as credenciais do Apple OAuth no arquivo .env'}), 501


@bp.route('/auth/backup/export', methods=['GET'])
@require_auth
def export_backup():
    """Exporta todos os dados do usuário em formato JSON"""
    try:
        user_id = request.user_id
        categories_collection = current_app.config['CATEGORIES']
        transactions_collection = current_app.config['TRANSACTIONS']
        accounts_collection = current_app.config['ACCOUNTS']
        
        # Busca todos os dados do usuário
        categories = list(categories_collection.find({'user_id': user_id}))
        transactions = list(transactions_collection.find({'user_id': user_id}))
        accounts = list(accounts_collection.find({'user_id': user_id}))
        
        # Remove _id do MongoDB e converte para string
        backup_data = {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'categories': [dict(cat, _id=str(cat['_id'])) for cat in categories],
            'transactions': [dict(tx, _id=str(tx['_id'])) for tx in transactions],
            'accounts': [dict(acc, _id=str(acc['_id'])) for acc in accounts]
        }
        
        return jsonify(backup_data)
    except Exception as e:
        return jsonify({'error': f'Erro ao exportar backup: {str(e)}'}), 500


@bp.route('/auth/backup/import', methods=['POST'])
@require_auth
def import_backup():
    """Importa backup de dados do usuário"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados do backup são obrigatórios'}), 400
        
        categories_collection = current_app.config['CATEGORIES']
        transactions_collection = current_app.config['TRANSACTIONS']
        accounts_collection = current_app.config['ACCOUNTS']
        
        imported_counts = {
            'categories': 0,
            'transactions': 0,
            'accounts': 0
        }
        
        # Importa categorias
        if 'categories' in data and isinstance(data['categories'], list):
            for cat in data['categories']:
                cat['user_id'] = user_id
                cat.pop('_id', None)  # Remove _id para criar novo
                # Verifica se já existe pelo nome e tipo
                existing = categories_collection.find_one({
                    'user_id': user_id,
                    'name': cat.get('name'),
                    'type': cat.get('type')
                })
                if not existing:
                    categories_collection.insert_one(cat)
                    imported_counts['categories'] += 1
        
        # Importa contas
        if 'accounts' in data and isinstance(data['accounts'], list):
            for acc in data['accounts']:
                acc['user_id'] = user_id
                acc.pop('_id', None)
                # Verifica se já existe pelo nome
                existing = accounts_collection.find_one({
                    'user_id': user_id,
                    'name': acc.get('name')
                })
                if not existing:
                    accounts_collection.insert_one(acc)
                    imported_counts['accounts'] += 1
        
        # Importa transações
        if 'transactions' in data and isinstance(data['transactions'], list):
            for tx in data['transactions']:
                tx['user_id'] = user_id
                tx.pop('_id', None)
                # Atualiza category_id e account_id se necessário
                if 'category_id' in tx:
                    # Tenta encontrar categoria pelo nome se ID não existir
                    pass
                transactions_collection.insert_one(tx)
                imported_counts['transactions'] += 1
        
        return jsonify({
            'message': 'Backup importado com sucesso',
            'imported': imported_counts
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao importar backup: {str(e)}'}), 500


@bp.route('/auth/data/clear', methods=['POST'])
@require_auth
def clear_all_data():
    """Limpa todos os dados de negócio do utilizador (conta public.users e auth mantêm-se)."""
    try:
        if not (
            current_app.config.get('CATEGORIES')
            and current_app.config.get('TRANSACTIONS')
            and current_app.config.get('ACCOUNTS')
        ):
            return jsonify({'error': 'Operação indisponível (repositórios não inicializados).'}), 503

        user_id = request.user_id
        counts = wipe_user_business_data(user_id, dict(current_app.config))

        return jsonify({
            'message': 'Todos os dados foram limpos com sucesso',
            'deleted': {
                'categories': counts.get('categories', 0),
                'transactions': counts.get('transactions', 0),
                'accounts': counts.get('accounts', 0),
                'financial_expenses': counts.get('financial_expenses', 0),
                'goals': counts.get('goals', 0),
                'budget_plans': counts.get('budget_plans', 0),
                'budget_monthly': counts.get('budget_monthly', 0),
                'merchant_category_aliases_user': counts.get('merchant_category_aliases_user', 0),
                'merchant_category_aliases_tenant': counts.get('merchant_category_aliases_tenant', 0),
                'chatbot_conversations': counts.get('chatbot_conversations', 0),
                'admin_notification_delivery': counts.get('admin_notification_delivery', 0),
                'admin_audit_logs_target': counts.get('admin_audit_logs_target', 0),
                'admin_audit_logs_actor': counts.get('admin_audit_logs_actor', 0),
            },
            'deleted_detail': counts,
        })
    except Exception as e:
        return jsonify({'error': f'Erro ao limpar dados: {str(e)}'}), 500
