"""Apoio aos testes de e-mail, quarentena e prévia de importação.

Tudo sintético. A credencial abaixo é uma frase repetida em português, sem
formato de token de nenhum provedor.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.ai import policy
from services.ai.db import scoped_tx
from services.ai.email import InMemoryCredentialStore, register_connection
from services.ai.email.fixture import FixtureEmailConnector
from services.ai.email.tools import build_email_tools
from services.ai.imports.tools import build_import_tools
from services.ai.registry import ToolRegistry, ToolResult
from services.ai.settings import AiSettings

from . import seed


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "email"
FILES_DIR = FIXTURE_DIR / "files"

FAKE_CREDENTIAL = "segredo-teste-segredo-teste-segredo"
CREDENTIAL_REF = "memory:caixa-sintetica"
CURSOR_KEY = b"chave-teste-chave-teste-chave-te"


def file_bytes(name: str) -> bytes:
    return (FILES_DIR / name).read_bytes()


def make_store(value: str = FAKE_CREDENTIAL) -> InMemoryCredentialStore:
    return InMemoryCredentialStore({CREDENTIAL_REF: value})


def connect_mailbox(pool, ctx, *, label: str = "Caixa sintética", credential_ref: str = CREDENTIAL_REF):
    return register_connection(
        pool, ctx, provider="fixture", mailbox_label=label, credential_ref=credential_ref,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )


class CountingFactory:
    """Fábrica de conectores que conta quantas vezes foi chamada."""

    def __init__(self, directory: Path = FIXTURE_DIR, max_attachment_bytes: int = 20 * 1024 * 1024) -> None:
        self.directory = directory
        self.max_attachment_bytes = max_attachment_bytes
        self.calls = 0
        self.connection_ids: List[str] = []

    def __call__(self, connection, credential_store):
        self.calls += 1
        self.connection_ids.append(connection.id)
        # Um conector real buscaria o token aqui; fazemos o mesmo para que o
        # segredo circule de verdade pelo caminho que os testes inspecionam.
        credential_store.get(connection.credential_ref)
        return FixtureEmailConnector(self.directory, max_attachment_bytes=self.max_attachment_bytes)


def build_registry(pool, settings: AiSettings, factory, store, cursor_key: bytes = CURSOR_KEY) -> ToolRegistry:
    registry = ToolRegistry(settings)
    registry.register_all(build_email_tools(pool, settings, factory, store, cursor_key=cursor_key))
    registry.register_all(build_import_tools(pool, settings))
    return registry


def grant_all(pool, ctx, mode: str = "observe") -> str:
    return seed.create_grant(pool, ctx.tenant_id, ctx.financial_space_id, ctx.actor_id, mode=mode)


def run_tool(registry: ToolRegistry, pool, ctx, name: str, args: Dict[str, Any]) -> ToolResult:
    """Executa pelo registro, como o orquestrador: flags, grants e schema."""
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        grants = policy.load_active_grants(cursor, ctx)
    return registry.execute(name, args, ctx, grants)


def quarantine_files(settings: AiSettings) -> List[str]:
    """Todos os arquivos sob o diretório de quarentena, em caminho relativo POSIX."""
    root = settings.resolved_quarantine_dir()
    if not root.exists():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def audit_dump(pool, tenant_id: str) -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT event_type, entity_type, entity_id::text, metadata FROM audit_events WHERE tenant_id = %s "
            "ORDER BY created_at, id",
            (tenant_id,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    return json.dumps(rows, ensure_ascii=False, sort_keys=True)


def audit_events(pool, tenant_id: str, prefix: str) -> List[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "SELECT event_type, entity_id::text AS entity_id, metadata FROM audit_events "
            "WHERE tenant_id = %s AND event_type LIKE %s ORDER BY created_at, id",
            (tenant_id, prefix + "%"),
        )
        return [dict(row) for row in cursor.fetchall()]


def copy_mailbox(destination: Path, extra_messages: Optional[List[Dict[str, Any]]] = None) -> Path:
    """Copia a caixa sintética para um diretório temporário (para acrescentar casos)."""
    shutil.copytree(str(FIXTURE_DIR), str(destination))
    if extra_messages:
        path = destination / "mailbox.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["messages"].extend(extra_messages)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return destination


def artifact_row(pool, tenant_id: str, artifact_id: str) -> Optional[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT * FROM ai_artifacts WHERE id = %s AND tenant_id = %s", (artifact_id, tenant_id))
        row = cursor.fetchone()
    return dict(row) if row else None
