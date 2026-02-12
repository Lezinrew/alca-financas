"""
Admin Action Logger
Registra todas as ações administrativas para auditoria
"""
from datetime import datetime
from flask import current_app, request

def log_admin_action(admin_id: str, admin_email: str, action: str, target_id: str = None, details: dict = None):
    """
    Registra uma ação administrativa

    Args:
        admin_id: ID do administrador que executou a ação
        admin_email: Email do administrador
        action: Tipo de ação (block_user, delete_user, promote_admin, etc.)
        target_id: ID do recurso afetado (usuário, etc.)
        details: Detalhes adicionais da ação
    """
    try:
        logs_collection = current_app.config.get('ADMIN_LOGS')
        if not logs_collection:
            # Se não houver collection de logs, tenta criar/obter
            db = current_app.config.get('DB')
            if db:
                logs_collection = db['admin_logs']
                current_app.config['ADMIN_LOGS'] = logs_collection

        if not logs_collection:
            print(f"Warning: Admin logs collection not found, log not saved: {action}")
            return

        log_entry = {
            'admin_id': admin_id,
            'admin_email': admin_email,
            'action': action,
            'target_id': target_id,
            'details': details or {},
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'timestamp': datetime.utcnow()
        }

        logs_collection.insert_one(log_entry)
        print(f"Admin action logged: {admin_email} - {action}")

    except Exception as e:
        # Não deve quebrar o fluxo se falhar ao registrar log
        print(f"Error logging admin action: {e}")

def get_admin_logs(limit=50, skip=0, action_filter=None, admin_filter=None):
    """
    Recupera logs administrativos com filtros opcionais

    Args:
        limit: Número máximo de logs a retornar
        skip: Número de logs a pular (paginação)
        action_filter: Filtrar por tipo de ação
        admin_filter: Filtrar por admin_id

    Returns:
        Lista de logs
    """
    try:
        logs_collection = current_app.config.get('ADMIN_LOGS')
        if not logs_collection:
            return []

        query = {}
        if action_filter:
            query['action'] = action_filter
        if admin_filter:
            query['admin_id'] = admin_filter

        cursor = logs_collection.find(query).sort('timestamp', -1).skip(skip).limit(limit)

        logs = []
        for log in cursor:
            logs.append({
                'id': str(log['_id']),
                'admin_id': log.get('admin_id'),
                'admin_email': log.get('admin_email'),
                'action': log.get('action'),
                'target_id': log.get('target_id'),
                'details': log.get('details', {}),
                'ip_address': log.get('ip_address'),
                'timestamp': log.get('timestamp').isoformat() if log.get('timestamp') else None
            })

        return logs

    except Exception as e:
        print(f"Error retrieving admin logs: {e}")
        return []
