"""PostgreSQL real e descartável para os testes da plataforma de IA.

Ordem de escolha do servidor:

1. ``AI_TEST_PG_ADMIN_URL``: URL administrativa de um servidor LOCAL e
   descartável (por exemplo o container de ``infra/postgres-v2``). Só loopback
   é aceito, para nunca apontar para produção por engano.
2. Pacote ``pgserver`` (PostgreSQL embutido), se instalado.
3. Nenhum: os testes que dependem de banco são pulados e isso deve ser
   relatado como "não executado".

Cada sessão de testes cria um banco próprio (``ai_test_<aleatório>``), aplica as
migrations V2 com um papel de aplicação SEM superusuário (para que as políticas
de RLS sejam de fato exercitadas) e apaga o banco ao final.

Limitação conhecida: o PostgreSQL do ``pgserver`` não traz as extensões
``pgcrypto`` e ``citext`` exigidas por ``0001_core.sql``. Nesse caso o harness
cria um substituto mínimo (``citext`` como domínio de ``text``;
``gen_random_uuid`` já é nativo). Ele também não traz a base de fusos horários:
``AT TIME ZONE 'America/Sao_Paulo'`` falha, por isso o código calcula datas
locais em Python. A validação com ``postgres:17-alpine`` e as extensões reais
continua necessária antes de aplicar em um ambiente existente.
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from psycopg2 import sql


MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "database" / "migrations_v2"
MIGRATIONS = ("0001_core.sql", "0002_ai_platform.sql")
APP_ROLE = "ai_test_app"
# Banco local descartável com autenticação trust/loopback: não é segredo.
APP_ROLE_PASSWORD = "ai-test-app-local"
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_EXTENSION_LINE = re.compile(r"^\s*CREATE EXTENSION IF NOT EXISTS (pgcrypto|citext);\s*$", re.MULTILINE)

_server = None  # mantém o handle do pgserver vivo durante o processo


@dataclass(frozen=True)
class TestDatabase:
    __test__ = False  # não é uma classe de teste

    name: str
    admin_dsn: str
    app_dsn: str
    server_admin_dsn: str
    extensions_shimmed: bool


def _replace(dsn: str, *, database: Optional[str] = None, user: Optional[str] = None,
             password: Optional[str] = None) -> str:
    parts = urlsplit(dsn)
    host = parts.hostname or "127.0.0.1"
    port = ":%s" % parts.port if parts.port else ""
    current_user = parts.username or "postgres"
    current_password = parts.password
    if user is not None:
        current_user, current_password = user, password
    credentials = current_user if not current_password else "%s:%s" % (current_user, current_password)
    path = "/%s" % database if database is not None else parts.path
    return urlunsplit((parts.scheme or "postgresql", "%s@%s%s" % (credentials, host, port), path, "", ""))


def server_admin_dsn() -> Optional[str]:
    """URL administrativa do servidor de teste, ou ``None`` se não houver."""
    global _server
    configured = (os.getenv("AI_TEST_PG_ADMIN_URL") or "").strip()
    if configured:
        host = urlsplit(configured).hostname or ""
        if host not in _LOOPBACK:
            raise RuntimeError("AI_TEST_PG_ADMIN_URL deve apontar para loopback (banco descartável local)")
        return configured
    try:
        import pgserver  # type: ignore
    except ImportError:
        return None
    if _server is None:
        data_dir = Path(tempfile.gettempdir()) / "alca-ai-pgserver-16"
        _server = _start_pgserver(pgserver, data_dir)
    return _server.get_uri()


def _start_pgserver(pgserver, data_dir: Path, patience_s: float = 180.0):
    """Sobe (ou reaproveita) o servidor embutido, tolerando partida lenta.

    O ``pgserver`` dá só 10 s ao ``pg_ctl start``. Depois de um desligamento
    abrupto (processo morto, máquina reiniciada) o PostgreSQL faz recuperação e
    sincroniza o diretório, o que no Windows com antivírus passa de 30 s. O
    servidor continua subindo depois do timeout; aqui esperamos por ele em vez
    de falhar todos os testes.
    """
    import subprocess
    import time

    deadline = time.monotonic() + patience_s
    while True:
        try:
            server = pgserver.get_server(data_dir, cleanup_mode="stop")
            break
        except subprocess.TimeoutExpired:
            # Remove a instância meio inicializada que o pgserver guardou em cache.
            getattr(pgserver.PostgresServer, "_instances", {}).pop(data_dir, None)
            if time.monotonic() >= deadline:
                raise
            time.sleep(3)
    # O pgserver aceita um servidor "em execução" que ainda está em recuperação.
    while True:
        try:
            psycopg2.connect(server.get_uri(), connect_timeout=5).close()
            return server
        except psycopg2.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)


def _ensure_app_role(admin_connection) -> None:
    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cursor.fetchone() is None:
            try:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD %s"
                    ).format(sql.Identifier(APP_ROLE)),
                    (APP_ROLE_PASSWORD,),
                )
            except psycopg2.errors.DuplicateObject:
                pass  # outra sessão de testes criou o papel ao mesmo tempo
            except psycopg2.errors.UniqueViolation:
                pass


def provision() -> Optional[TestDatabase]:
    admin = server_admin_dsn()
    if admin is None:
        return None
    name = "ai_test_%s" % uuid.uuid4().hex[:12]

    connection = psycopg2.connect(admin)
    connection.autocommit = True
    try:
        _ensure_app_role(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(APP_ROLE))
            )
    finally:
        connection.close()

    admin_db_dsn = _replace(admin, database=name)
    app_dsn = _replace(admin, database=name, user=APP_ROLE, password=APP_ROLE_PASSWORD)

    # Extensões exigem privilégio; ficam por conta do papel administrativo.
    shimmed = False
    connection = psycopg2.connect(admin_db_dsn)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM pg_available_extensions WHERE name IN ('pgcrypto', 'citext')"
            )
            available = {row[0] for row in cursor.fetchall()}
            if {"pgcrypto", "citext"} <= available:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS citext")
            else:
                shimmed = True
                cursor.execute("CREATE DOMAIN citext AS text")
            cursor.execute(
                sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE))
            )
    finally:
        connection.close()

    connection = psycopg2.connect(app_dsn)
    try:
        for filename in MIGRATIONS:
            script = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
            script = _EXTENSION_LINE.sub("", script)
            with connection.cursor() as cursor:
                cursor.execute(script)
            connection.commit()
    finally:
        connection.close()

    return TestDatabase(
        name=name,
        admin_dsn=admin_db_dsn,
        app_dsn=app_dsn,
        server_admin_dsn=admin,
        extensions_shimmed=shimmed,
    )


def destroy(database: TestDatabase) -> None:
    connection = psycopg2.connect(database.server_admin_dsn)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database.name))
            )
    finally:
        connection.close()


def truncate_all(database: TestDatabase) -> None:
    """Esvazia todas as tabelas do banco de teste desta sessão."""
    connection = psycopg2.connect(database.app_dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            tables = [row[0] for row in cursor.fetchall()]
            if tables:
                cursor.execute(
                    sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                        sql.SQL(", ").join(sql.Identifier(table) for table in tables)
                    )
                )
        connection.commit()
    finally:
        connection.close()
