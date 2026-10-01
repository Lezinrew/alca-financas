"""Pool de conexões do PostgreSQL V2, independente do cliente Supabase."""

# Compatibilidade com o Python 3.9 do CI: as assinaturas usam `X | None`.
from __future__ import annotations

from contextlib import contextmanager
import os
from threading import Lock

from psycopg2 import pool
from psycopg2.extras import RealDictCursor


_pool = None
_pool_lock = Lock()


def get_v2_database_url() -> str:
    database_url = (os.getenv("DATABASE_V2_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_V2_URL não configurada")
    return database_url


def init_v2_pool(database_url: str | None = None, minconn: int = 1, maxconn: int = 10):
    """Inicializa uma vez o pool do PostgreSQL V2."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = pool.ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                dsn=database_url or get_v2_database_url(),
                cursor_factory=RealDictCursor,
            )
    return _pool


def close_v2_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def v2_connection(database_pool=None):
    """Entrega uma conexão e garante commit/rollback/devolução ao pool."""
    selected_pool = database_pool or init_v2_pool()
    connection = selected_pool.getconn()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        selected_pool.putconn(connection)

