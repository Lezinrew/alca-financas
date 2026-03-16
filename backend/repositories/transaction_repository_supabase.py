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

    def create(self, data: Dict[str, Any]) -> str:
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id é obrigatório para criar transação.")
        if data.get("account_id") and not data.get("account_tenant_id"):
            raise ValueError("account_tenant_id é obrigatório quando account_id está preenchido.")
        if data.get("category_id") and not data.get("category_tenant_id"):
            raise ValueError("category_tenant_id é obrigatório quando category_id está preenchido.")
        if not data.get("account_tenant_id"):
            data = {**data, "account_tenant_id": tenant_id}
        if not data.get("category_tenant_id"):
            data = {**data, "category_tenant_id": tenant_id}
        return super().create(data)

    def find_by_filter(
        self,
        user_id: str,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 20,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca transações com filtros e paginação
        """
        try:
            supabase = get_supabase()
            query = supabase.table(self.table_name).select("*", count="exact")

            # Filtro obrigatório: user_id
            query = query.eq("user_id", user_id)

            # Filtro opcional: tenant_id (quando resolvido)
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            
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
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: Optional[int] = None,
        tenant_id: Optional[str] = None,
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
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            import logging
            logging.error(f"Erro ao buscar transações por período: {e}")
            return []

    def find_advanced(
        self,
        user_id: str,
        params: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca transações com filtros avançados e paginação.
        Suporta:
        - page, limit, sort
        - date_from, date_to OU month/year
        - type
        - account_ids (lista separada por vírgula)
        - category_ids (lista separada por vírgula)
        - min_amount, max_amount
        - search (ilike em description)
        - status
        - method (quando existir no schema)
        """
        from database.connection import get_supabase
        import logging

        page = int(params.get("page") or 1)
        per_page = int(params.get("limit") or 50)
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 50

        try:
            supabase = get_supabase()
            query = supabase.table(self.table_name).select("*", count="exact")

            # Escopo obrigatório
            query = query.eq("user_id", user_id)
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)

            # Período
            date_from = params.get("date_from")
            date_to = params.get("date_to")
            month = params.get("month")
            year = params.get("year")

            if date_from and date_to:
                query = query.gte("date", str(date_from)).lte("date", str(date_to))
            elif month and year:
                # Compatibilidade com filtros antigos
                m = int(month)
                y = int(year)
                start_date = f"{y}-{m:02d}-01"
                if m == 12:
                    end_date = f"{y + 1}-01-01"
                else:
                    end_date = f"{y}-{m + 1:02d}-01"
                query = query.gte("date", start_date).lt("date", end_date)

            # Tipo
            if params.get("type"):
                query = query.eq("type", params["type"])

            # Contas múltiplas
            account_ids = params.get("account_ids") or params.get("account_id")
            if account_ids:
                ids = [str(x).strip() for x in str(account_ids).split(",") if str(x).strip()]
                if ids:
                    query = query.in_("account_id", ids)

            # Categorias múltiplas
            category_ids = params.get("category_ids") or params.get("category_id")
            if category_ids:
                ids = [str(x).strip() for x in str(category_ids).split(",") if str(x).strip()]
                if ids:
                    query = query.in_("category_id", ids)

            # Intervalo de valor
            if params.get("min_amount") not in (None, ""):
                try:
                    query = query.gte("amount", float(params["min_amount"]))
                except (TypeError, ValueError):
                    pass
            if params.get("max_amount") not in (None, ""):
                try:
                    query = query.lte("amount", float(params["max_amount"]))
                except (TypeError, ValueError):
                    pass

            # Status
            if params.get("status"):
                query = query.eq("status", params["status"])

            # Método (campo opcional no schema)
            if params.get("method"):
                query = query.eq("method", params["method"])

            # Recorrente
            if params.get("is_recurring") in (True, "true", "1", 1):
                query = query.eq("is_recurring", True)

            # Busca textual em múltiplos campos (description, merchant_name, notes)
            search = params.get("search")
            if search:
                s = str(search).strip()
                if s:
                    pattern = f"%{s}%"
                    # Usa OR em múltiplas colunas quando suportado
                    query = query.or_(
                        f"description.ilike.{pattern},merchant_name.ilike.{pattern},notes.ilike.{pattern}"
                    )

            # Ordenação
            sort_raw = params.get("sort") or "date:desc"
            field, _, direction = str(sort_raw).partition(":")
            field = field or "date"
            desc = (direction or "desc").lower() != "asc"
            query = query.order(field, desc=desc)

            # Paginação
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            response = query.execute()
            total = response.count if hasattr(response, "count") else len(response.data or [])

            return {
                "data": response.data or [],
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page if total > 0 else 0,
                },
            }
        except Exception as e:
            logging.error(f"Erro ao buscar transações (find_advanced): {e}")
            return {
                "data": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "per_page": per_page,
                    "pages": 0,
                },
            }

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
        Cria múltiplas transações. Garante account_tenant_id e category_tenant_id = tenant_id.
        """
        if not transactions:
            return []
        try:
            now = datetime.utcnow().isoformat()
            for tx in transactions:
                if "created_at" not in tx:
                    tx["created_at"] = now
                if "updated_at" not in tx:
                    tx["updated_at"] = now
                t_tenant_id = tx.get("tenant_id")
                if not t_tenant_id:
                    raise ValueError("Cada transação deve ter tenant_id.")
                if tx.get("account_id") and not tx.get("account_tenant_id"):
                    raise ValueError("account_tenant_id é obrigatório quando account_id está preenchido.")
                if tx.get("category_id") and not tx.get("category_tenant_id"):
                    raise ValueError("category_tenant_id é obrigatório quando category_id está preenchido.")
                if not tx.get("account_tenant_id"):
                    tx["account_tenant_id"] = t_tenant_id
                if not tx.get("category_tenant_id"):
                    tx["category_tenant_id"] = t_tenant_id
            supabase = get_supabase()
            response = supabase.table(self.table_name).insert(transactions).execute()
            
            if response.data:
                return [item['id'] for item in response.data]
            return []
        except Exception as e:
            import logging
            logging.error(f"Erro ao criar múltiplas transações: {e}")
            return []

