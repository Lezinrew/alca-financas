"""
Transaction Repository para Supabase
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from .base_repository_supabase import BaseRepository
from database.connection import get_supabase


class TransactionRepository(BaseRepository):
    def __init__(self):
        super().__init__("transactions")
    
    def find_by_filter(
        self, 
        user_id: str, 
        filters: Dict[str, Any], 
        page: int = 1, 
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Busca transações com filtros e paginação
        """
        try:
            supabase = get_supabase()
            query = supabase.table(self.table_name).select("*", count="exact")
            
            # Filtro obrigatório: user_id
            query = query.eq("user_id", user_id)
            
            # Filtro por mês/ano
            if filters.get('month') and filters.get('year'):
                month = int(filters['month'])
                year = int(filters['year'])
                start_date = f"{year}-{month:02d}-01"
                if month == 12:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_date = f"{year}-{month + 1:02d}-01"
                query = query.gte("date", start_date).lt("date", end_date)
            
            # Filtro por categoria
            if filters.get('category_id'):
                query = query.eq("category_id", filters['category_id'])
            
            # Filtro por tipo
            if filters.get('type'):
                query = query.eq("type", filters['type'])
            
            # Filtro por conta
            if filters.get('account_id'):
                query = query.eq("account_id", filters['account_id'])
            
            # Ordenação
            query = query.order("date", desc=True)
            
            # Paginação
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)
            
            response = query.execute()
            
            total = response.count if hasattr(response, 'count') else len(response.data or [])
            
            return {
                'data': response.data if response.data else [],
                'pagination': {
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page if total > 0 else 0
                }
            }
        except Exception as e:
            import logging
            logging.error(f"Erro ao buscar transações: {e}")
            return {
                'data': [],
                'pagination': {
                    'total': 0,
                    'page': page,
                    'per_page': per_page,
                    'pages': 0
                }
            }
    
    def find_by_user_and_date_range(
        self, user_id: str, start_date: str, end_date: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Busca transações do usuário em um intervalo de datas (ISO)."""
        try:
            query = (
                get_supabase()
                .table(self.table_name)
                .select("*")
                .eq("user_id", user_id)
                .gte("date", start_date)
                .lt("date", end_date)
                .order("date", desc=True)
            )
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            import logging
            logging.error(f"Erro ao buscar transações por período: {e}")
            return []

    def find_by_user_limit(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Busca últimas transações do usuário (para recent_transactions)."""
        try:
            response = (
                get_supabase()
                .table(self.table_name)
                .select("*")
                .eq("user_id", user_id)
                .order("date", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            import logging
            logging.error(f"Erro ao buscar transações recentes: {e}")
            return []

    def create_many(self, transactions: List[Dict[str, Any]]) -> List[str]:
        """
        Cria múltiplas transações
        """
        if not transactions:
            return []
        
        try:
            # Adicionar timestamps
            now = datetime.utcnow().isoformat()
            for tx in transactions:
                if 'created_at' not in tx:
                    tx['created_at'] = now
                if 'updated_at' not in tx:
                    tx['updated_at'] = now
            
            supabase = get_supabase()
            response = supabase.table(self.table_name).insert(transactions).execute()
            
            if response.data:
                return [item['id'] for item in response.data]
            return []
        except Exception as e:
            import logging
            logging.error(f"Erro ao criar múltiplas transações: {e}")
            return []

