"""
Base Repository para Supabase (PostgreSQL)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from database.connection import get_supabase, get_db_connection, return_db_connection
import logging

logger = logging.getLogger(__name__)


class BaseRepository:
    """Repository base para operações CRUD no Supabase"""
    
    def __init__(self, table_name: str):
        """
        Inicializa o repository
        
        Args:
            table_name: Nome da tabela no Supabase
        """
        self.table_name = table_name
        self.supabase = get_supabase()
    
    def find_all(
        self, 
        filter_query: Dict[str, Any] = None, 
        sort_by: str = None, 
        ascending: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca todos os registros
        
        Args:
            filter_query: Filtros (ex: {'user_id': 'uuid', 'active': True})
            sort_by: Campo para ordenação
            ascending: Ordem crescente (True) ou decrescente (False)
            limit: Limite de resultados
            offset: Offset para paginação
        """
        try:
            query = self.supabase.table(self.table_name).select("*")
            
            # Aplicar filtros
            if filter_query:
                for key, value in filter_query.items():
                    query = query.eq(key, value)
            
            # Ordenação
            if sort_by:
                order = "asc" if ascending else "desc"
                query = query.order(sort_by, desc=(not ascending))
            
            # Paginação
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Erro ao buscar registros em {self.table_name}: {e}")
            return []
    
    def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """
        Busca registro por ID
        
        Args:
            id: UUID do registro
        """
        try:
            response = self.supabase.table(self.table_name).select("*").eq("id", id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro {id} em {self.table_name}: {e}")
            return None
    
    def find_one(self, filter_query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Busca um registro por filtro
        
        Args:
            filter_query: Filtros (ex: {'email': 'user@example.com'})
        """
        try:
            query = self.supabase.table(self.table_name).select("*")
            
            for key, value in filter_query.items():
                query = query.eq(key, value)
            
            response = query.limit(1).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar registro em {self.table_name}: {e}")
            return None
    
    def create(self, data: Dict[str, Any]) -> str:
        """
        Cria novo registro
        
        Args:
            data: Dados do registro
            
        Returns:
            ID do registro criado
        """
        try:
            # Adicionar timestamps se não existirem
            if 'created_at' not in data:
                data['created_at'] = datetime.utcnow().isoformat()
            if 'updated_at' not in data:
                data['updated_at'] = datetime.utcnow().isoformat()
            
            # Compatível com clientes supabase-py que não suportam encadear .select()
            # após .insert() no mesmo builder.
            response = self.supabase.table(self.table_name).insert(data).execute()

            if response.data and len(response.data) > 0:
                row = response.data[0]
                rid = row.get("id") or data.get("id")
                if rid is not None:
                    return str(rid)

            insert_id = data.get("id")
            if insert_id is not None:
                row = self.find_by_id(str(insert_id))
                if row:
                    return str(insert_id)

            raise ValueError("Nenhum registro foi criado")
        except Exception as e:
            logger.error(f"Erro ao criar registro em {self.table_name}: {e}")
            raise
    
    def update(self, id: str, data: Dict[str, Any]) -> bool:
        """
        Atualiza registro por ID
        
        Args:
            id: UUID do registro
            data: Dados para atualizar
            
        Returns:
            True se atualizado com sucesso
        """
        try:
            # Adicionar updated_at
            if 'updated_at' not in data:
                data['updated_at'] = datetime.utcnow().isoformat()
            
            response = self.supabase.table(self.table_name).update(data).eq("id", id).execute()
            
            return response.data is not None and len(response.data) > 0
        except Exception as e:
            logger.error(f"Erro ao atualizar registro {id} em {self.table_name}: {e}")
            return False
    
    def delete(self, id: str) -> bool:
        """
        Deleta registro por ID
        
        Args:
            id: UUID do registro
            
        Returns:
            True se deletado com sucesso
        """
        try:
            response = self.supabase.table(self.table_name).delete().eq("id", id).execute()
            return True  # Supabase sempre retorna sucesso se não houver erro
        except Exception as e:
            logger.error(f"Erro ao deletar registro {id} em {self.table_name}: {e}")
            return False

    def delete_many(self, filter_query: Dict[str, Any]) -> int:
        """
        Remove todos os registos que cumprem o filtro (conjunção de .eq em cada chave).

        Usa count() antes do DELETE para devolver o número de linhas removidas de forma
        compatível com todos os clientes PostgREST (sem depender de RETURNING).
        """
        if not filter_query:
            raise ValueError("delete_many requer filter_query não vazio")
        try:
            total = self.count(filter_query)
            if total == 0:
                return 0
            query = self.supabase.table(self.table_name).delete()
            for key, value in filter_query.items():
                query = query.eq(key, value)
            query.execute()
            return total
        except Exception as e:
            logger.error(f"Erro delete_many em {self.table_name}: {e}")
            raise

    def count(self, filter_query: Dict[str, Any] = None) -> int:
        """
        Conta registros
        
        Args:
            filter_query: Filtros opcionais
        """
        try:
            query = self.supabase.table(self.table_name).select("id", count="exact")
            
            if filter_query:
                for key, value in filter_query.items():
                    query = query.eq(key, value)
            
            response = query.execute()
            return response.count if hasattr(response, 'count') else 0
        except Exception as e:
            logger.error(f"Erro ao contar registros em {self.table_name}: {e}")
            return 0

