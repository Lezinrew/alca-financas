"""Acesso ao PostgreSQL V2 com escopo por tenant, auditoria e outbox.

Toda leitura ou escrita da plataforma de IA passa por ``scoped_tx``: a
transação define ``app.tenant_id`` e as políticas de RLS da migration 0002
só deixam ver linhas desse tenant. Os filtros ``WHERE tenant_id = ...`` no
serviço continuam obrigatórios; RLS é a segunda barreira, não a única.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from psycopg2.extras import Json, RealDictCursor

from .types import canonical_json, json_safe


@contextmanager
def scoped_tx(pool, tenant_id: str) -> Iterator[Any]:
    """Transação no escopo de um tenant. Commit ao sair; rollback em erro."""
    connection = pool.getconn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            yield cursor
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)


@contextmanager
def queue_tx(pool) -> Iterator[Any]:
    """Transação do worker para descobrir itens pendentes de qualquer tenant.

    Só enxerga ``ai_runs`` em fila/execução e ``ai_outbox`` pendente. Depois de
    assumir um item, o worker deve operar com ``scoped_tx`` do tenant dono.
    """
    connection = pool.getconn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT set_config('app.ai_queue', 'on', true)")
            yield cursor
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)


@contextmanager
def plain_tx(pool) -> Iterator[Any]:
    """Transação sem escopo de tenant, para tabelas de identidade de 0001."""
    connection = pool.getconn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)


# O PostgreSQL recusa NUL em ``text``/``jsonb`` e substitutos isolados não são
# UTF-8 válido. Conteúdo vindo de e-mail, PDF, OCR ou modelo pode trazer os
# dois; viram U+FFFD para que a gravação nunca falhe por causa do dado.
_UNSTORABLE = re.compile("[\x00\ud800-\udfff]")


def storable(value: Any) -> Any:
    """Cópia de ``value`` em que todo texto pode ser gravado em ``jsonb``."""
    if isinstance(value, str):
        return _UNSTORABLE.sub("\ufffd", value)
    if isinstance(value, dict):
        return {(storable(key) if isinstance(key, str) else key): storable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [storable(item) for item in value]
    return value


def jsonb(value: Any) -> Json:
    """Adapta para jsonb com serialização determinística, sem float e gravável."""
    return Json(storable(json_safe(value)), dumps=lambda obj: canonical_json(obj))


def write_audit(
    cursor,
    *,
    tenant_id: str,
    actor_user_id: Optional[str],
    event_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Grava um evento em ``audit_events`` na transação corrente.

    ``metadata`` leva referências (ids, hashes, versões, modelo efetivo, custo),
    nunca extrato, corpo de e-mail, prompt, resposta bruta ou segredo.
    """
    cursor.execute(
        """
        INSERT INTO audit_events (tenant_id, actor_user_id, event_type, entity_type, entity_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            str(tenant_id),
            str(actor_user_id) if actor_user_id else None,
            event_type,
            entity_type,
            str(entity_id) if entity_id else None,
            jsonb(metadata or {}),
        ),
    )


def enqueue_outbox(
    cursor,
    *,
    tenant_id: str,
    topic: str,
    dedup_key: str,
    payload: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> bool:
    """Enfileira uma entrega na transação corrente.

    Devolve ``False`` se a mesma ``dedup_key`` já existia: reenvio de
    notificação nunca refaz o efeito financeiro.
    """
    cursor.execute(
        """
        INSERT INTO ai_outbox (tenant_id, operation_id, run_id, topic, payload, dedup_key)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, dedup_key) DO NOTHING
        """,
        (
            str(tenant_id),
            str(operation_id) if operation_id else None,
            str(run_id) if run_id else None,
            topic,
            jsonb(payload or {}),
            dedup_key,
        ),
    )
    return cursor.rowcount == 1
