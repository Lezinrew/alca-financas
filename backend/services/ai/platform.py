"""Montagem explícita da plataforma; importar não abre banco nem rede."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .email import EnvCredentialStore, build_connector_factory
from .email.tools import build_email_tools
from .finance.tools import build_finance_tools
from .gateway.gateway import DefaultModelGateway, build_gateway
from .imports.tools import build_import_tools, preview_provider
from .misc_tools import build_misc_tools
from .orchestrator import Orchestrator
from .registry import ToolRegistry
from .settings import AiSettings
from .worker import Worker


@dataclass(frozen=True)
class AiPlatform:
    settings: AiSettings
    pool: Any
    registry: ToolRegistry
    gateway: DefaultModelGateway
    orchestrator: Orchestrator
    worker: Worker


def build_platform(
    pool, settings: Optional[AiSettings] = None, *, adapters=None,
    email_connector_factory=None, credential_store=None,
) -> AiPlatform:
    """Liga os componentes reais sem iniciar processamento em segundo plano."""
    settings = settings if settings is not None else AiSettings.from_env()
    registry = ToolRegistry(settings)
    registry.register_all(build_finance_tools(pool, settings, preview_provider(pool, settings)))
    registry.register_all(build_email_tools(
        pool, settings,
        email_connector_factory if email_connector_factory is not None else build_connector_factory(settings),
        credential_store if credential_store is not None else EnvCredentialStore(),
    ))
    registry.register_all(build_import_tools(pool, settings))
    registry.register_all(build_misc_tools(pool, settings))
    gateway = build_gateway(pool, settings, adapters=adapters)
    orchestrator = Orchestrator(pool, settings, registry, gateway)
    return AiPlatform(settings, pool, registry, gateway, orchestrator, Worker(pool, settings, orchestrator))
