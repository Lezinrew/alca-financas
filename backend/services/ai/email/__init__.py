"""E-mail como fonte de extratos e comprovantes (contrato, seções 5 e 10).

Peças:

* ``base``        -- interface ``EmailConnector`` (buscar, ler, baixar; só leitura);
* ``fixture``     -- caixa postal sintética em disco, para desenvolvimento e testes;
* ``mcp_http``    -- conector genérico sobre um servidor MCP, dirigido por configuração;
* ``credentials`` -- cofre: o banco guarda a referência, o token fica fora;
* ``connections`` -- vínculo caixa <-> titular, revogável e auditado;
* ``tools``       -- as três ferramentas ``email.*`` entregues ao registro.

Importar este pacote não abre conexão, não lê credencial nem arquivo de
configuração. ``tools`` não é importado aqui de propósito: ele depende de
``services.ai.artifacts``, que por sua vez usa ``email.base``.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from ..errors import AiError
from ..settings import AiSettings
from .base import (
    AttachmentBlob,
    AttachmentInfo,
    ConnectorAuthError,
    EmailConnector,
    EmailMessage,
    EmailPage,
    EmailSummary,
)
from .connections import (
    EmailConnection,
    get_active_connection,
    list_connections,
    register_connection,
    revoke_connection,
)
from .credentials import CredentialStore, EnvCredentialStore, InMemoryCredentialStore, Secret


logger = logging.getLogger("ai.email")

# Recebe a conexão ativa e o cofre; devolve o conector daquela caixa.
ConnectorFactory = Callable[[EmailConnection, CredentialStore], EmailConnector]

CONNECTOR_KINDS = ("none", "fixture", "mcp_http")


def build_connector_factory(settings: AiSettings) -> ConnectorFactory:
    """Fábrica de conectores conforme ``settings.email_connector``.

    A configuração é lida no primeiro uso, não aqui: montar a plataforma com o
    e-mail mal configurado não derruba o restante (AC-11); só as ferramentas de
    e-mail respondem ``connector_unavailable``.
    """
    kind = settings.email_connector
    state = {"mcp_config": None}

    def factory(connection: EmailConnection, credential_store: CredentialStore) -> EmailConnector:
        if kind == "fixture":
            from .fixture import FixtureEmailConnector

            if not settings.email_fixture_dir:
                raise AiError("connector_unavailable", "A caixa postal de teste não foi configurada.", retryable=False)
            return FixtureEmailConnector(
                settings.email_fixture_dir, max_attachment_bytes=settings.artifact_max_bytes
            )
        if kind == "mcp_http":
            from .mcp_http import McpHttpEmailConnector, load_mcp_config

            if state["mcp_config"] is None:
                state["mcp_config"] = load_mcp_config(settings.email_mcp_config_path)
            reference: Optional[str] = connection.credential_ref
            return McpHttpEmailConnector(
                state["mcp_config"],
                # O token é buscado a cada requisição, no momento do uso.
                token_provider=lambda: credential_store.get(reference or ""),
                max_attachment_bytes=settings.artifact_max_bytes,
            )
        if kind != "none":
            logger.error("event=email_connector_unknown")
        raise AiError("connector_unavailable", "Nenhum conector de e-mail está configurado.", retryable=False)

    return factory


__all__ = [
    "AttachmentBlob",
    "AttachmentInfo",
    "ConnectorAuthError",
    "ConnectorFactory",
    "CredentialStore",
    "EmailConnection",
    "EmailConnector",
    "EmailMessage",
    "EmailPage",
    "EmailSummary",
    "EnvCredentialStore",
    "InMemoryCredentialStore",
    "Secret",
    "build_connector_factory",
    "get_active_connection",
    "list_connections",
    "register_connection",
    "revoke_connection",
]
