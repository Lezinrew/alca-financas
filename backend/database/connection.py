"""
Conexão com Banco de Dados (Supabase/PostgreSQL ou MongoDB)
"""
import os
import logging
from typing import Optional, Any
from pymongo import MongoClient

# Opcional: Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Variáveis globais para conexões
_supabase_client: Optional[Any] = None
_db_pool: Optional[Any] = None
_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Any] = None
_db_type: str = "mongodb" # "mongodb" ou "supabase"


def init_db():
    """Inicializa conexões com o banco de dados"""
    global _supabase_client, _db_pool, _mongo_client, _mongo_db, _db_type
    
    # Verifica qual banco usar (prioridade para Supabase se configurado)
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if supabase_url and supabase_key and SUPABASE_AVAILABLE:
        _db_type = "supabase"
        _init_supabase(supabase_url, supabase_key)
    else:
        _db_type = "mongodb"
        _init_mongodb()


def _init_supabase(url, key):
    """Inicializa Supabase"""
    global _supabase_client, _db_pool
    logger.info("📡 Inicializando Supabase...")
    
    supabase_service_key = os.getenv('SUPABASE_SERVICE_KEY', key)
    db_url = os.getenv('SUPABASE_DB_URL')
    
    try:
        from supabase import create_client
        _supabase_client = create_client(url, supabase_service_key)
        logger.info("✅ Cliente Supabase inicializado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar cliente Supabase: {e}")
        raise

    if db_url:
        try:
            from psycopg2 import pool
            from psycopg2.extras import RealDictCursor
            _db_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=db_url,
                cursor_factory=RealDictCursor
            )
            logger.info("✅ Pool de conexões PostgreSQL inicializado")
        except Exception as e:
            logger.warning(f"⚠️  Pool PostgreSQL não inicializado (opcional): {e}")


def _init_mongodb():
    """Inicializa MongoDB"""
    global _mongo_client, _mongo_db
    logger.info("🍃 Inicializando MongoDB...")
    
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
    db_name = os.getenv('MONGO_DB', 'alca_financas')
    
    try:
        _mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Testa a conexão
        _mongo_client.server_info()
        _mongo_db = _mongo_client[db_name]
        logger.info(f"✅ MongoDB inicializado com sucesso em {db_name}")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao MongoDB: {e}")
        raise


def get_db():
    """Retorna o cliente do banco de dados (Supabase Client ou Mongo Database)"""
    global _db_type, _supabase_client, _mongo_db
    
    if _db_type == "supabase":
        if _supabase_client is None:
            init_db()
        return _supabase_client
    else:
        if _mongo_db is None:
            init_db()
        return _mongo_db


def get_db_type() -> str:
    """Retorna o tipo de banco em uso"""
    return _db_type


def get_supabase() -> Any:
    """Retorna o cliente Supabase"""
    if _db_type != "supabase":
        raise ValueError("Aplicação configurada para usar MongoDB, não Supabase")
    return get_db()


def get_mongodb():
    """Retorna o banco MongoDB"""
    if _db_type != "mongodb":
        raise ValueError("Aplicação configurada para usar Supabase, não MongoDB")
    return get_db()


def get_db_connection():
    """Retorna uma conexão do pool PostgreSQL (apenas para Supabase)"""
    if _db_type != "supabase":
        raise ValueError("Conexão PostgreSQL direta disponível apenas com Supabase")
    
    if _db_pool is None:
        init_db()
    
    if _db_pool is None:
        raise RuntimeError("Pool de conexões PostgreSQL não inicializado")
    
    return _db_pool.getconn()


def return_db_connection(conn):
    """Retorna uma conexão ao pool"""
    if _db_pool:
        _db_pool.putconn(conn)


def close_db():
    """Fecha todas as conexões"""
    global _supabase_client, _db_pool, _mongo_client, _mongo_db
    
    if _db_pool:
        _db_pool.closeall()
        _db_pool = None
    
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
    
    _supabase_client = None


