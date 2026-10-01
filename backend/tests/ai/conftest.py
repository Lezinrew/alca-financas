"""Fixtures dos testes da plataforma de IA.

Estes testes não importam ``app`` nem dependem de Supabase/Mongo. Rode com:

    cd backend
    python -m pytest -c tests/ai/pytest.ini tests/ai
"""

from __future__ import annotations

import pytest
from psycopg2 import pool as pg_pool

from services.ai.settings import AiSettings

from .support import pg, seed


@pytest.fixture(scope="session")
def ai_database():
    database = pg.provision()
    if database is None:
        pytest.skip(
            "PostgreSQL de teste indisponível: instale pgserver ou defina AI_TEST_PG_ADMIN_URL"
        )
    try:
        yield database
    finally:
        pg.destroy(database)


@pytest.fixture()
def pool(ai_database):
    """Pool com o papel de aplicação (sem superusuário; RLS ativo)."""
    pg.truncate_all(ai_database)
    # Pré-aquecido: com minconn=1 o pool abriria conexões dentro do próprio
    # lock, serializando as threads e mascarando corridas nos testes de
    # concorrência. Com 8 conexões prontas, duas threads entram de fato juntas.
    database_pool = pg_pool.ThreadedConnectionPool(8, 16, dsn=ai_database.app_dsn)
    try:
        yield database_pool
    finally:
        database_pool.closeall()


@pytest.fixture()
def admin_pool(ai_database):
    """Pool administrativo, só para preparar cenários que exigem privilégio."""
    database_pool = pg_pool.ThreadedConnectionPool(1, 2, dsn=ai_database.admin_dsn)
    try:
        yield database_pool
    finally:
        database_pool.closeall()


@pytest.fixture()
def settings(tmp_path):
    return AiSettings(
        enabled=True,
        cloud_enabled=False,
        email_enabled=True,
        write_enabled=True,
        quarantine_dir=str(tmp_path / "quarentena"),
    )


@pytest.fixture()
def world(pool):
    return seed.make_world(pool, "alfa")


@pytest.fixture()
def other_world(pool):
    """Segundo tenant, para os testes de isolamento."""
    return seed.make_world(pool, "beta")
