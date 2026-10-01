"""Apoio aos testes das ferramentas financeiras. Tudo sintético.

As consultas "independentes" daqui são escritas à mão, sem reaproveitar nada de
``services.ai.finance.repository``: servem de segunda opinião para conferir
que os números das ferramentas batem com uma agregação NUMERIC do banco.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from psycopg2.extras import execute_values

from services.ai.db import scoped_tx
from services.ai.imports_types import ImportPreview, PreviewItem

from . import seed


OCT = date(2026, 10, 1)
NOV = date(2026, 11, 1)


def space_id(world, space: str) -> str:
    return world.personal_space_id if space == "personal" else world.business_space_id


def grant(pool, world, space: str = "personal", **kwargs) -> str:
    """Grant do titular no espaço escolhido (atalho de ``seed.create_grant``)."""
    return seed.create_grant(pool, world.tenant_id, space_id(world, space), world.user_id, **kwargs)


def delegated_unlimited(pool, world, space: str = "personal", **kwargs) -> str:
    return grant(pool, world, space, mode="delegated", amount_unlimited=True, **kwargs)


def fetch_all(pool, tenant_id: str, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(sql, tuple(params))
        return [dict(row) for row in cursor.fetchall()]


def fetch_value(pool, tenant_id: str, sql: str, params: Sequence[Any] = ()) -> Any:
    rows = fetch_all(pool, tenant_id, sql, params)
    return list(rows[0].values())[0] if rows else None


def execute(pool, tenant_id: str, sql: str, params: Sequence[Any] = ()) -> int:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(sql, tuple(params))
        return cursor.rowcount


def bulk_transactions(
    pool,
    tenant_id: str,
    account_id: str,
    category_id: str,
    amounts: Sequence[Any],
    *,
    occurred_on: date = date(2026, 10, 15),
    tx_type: str = "expense",
    status: str = "paid",
    source_file: Optional[str] = "extrato-sintetico.ofx",
    entry_source: str = "ofx",
) -> None:
    """Insere muitas transações de uma vez (uma linha por valor)."""
    rows = [
        (
            tenant_id, account_id, category_id, "Lançamento sintético %d" % index, Decimal(str(amount)), tx_type,
            occurred_on, status, entry_source, source_file, uuid.uuid4().hex,
            datetime.now(timezone.utc) if status == "canceled" else None,
        )
        for index, amount in enumerate(amounts)
    ]
    with scoped_tx(pool, tenant_id) as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO transactions (
                tenant_id, account_id, category_id, description, amount, type,
                occurred_on, status, entry_source, source_file, fitid, canceled_at
            ) VALUES %s
            """,
            rows,
            page_size=500,
        )


def create_transfer(
    pool,
    tenant_id: str,
    account_id: str,
    destination_account_id: str,
    amount: Any,
    occurred_on: date,
    source_file: str = "extrato-sintetico.ofx",
) -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO transactions (
                tenant_id, account_id, destination_account_id, description, amount, type,
                occurred_on, status, entry_source, source_file, fitid
            ) VALUES (%s, %s, %s, 'Transferência sintética', %s, 'transfer', %s, 'paid', 'ofx', %s, %s)
            RETURNING id
            """,
            (tenant_id, account_id, destination_account_id, Decimal(str(amount)), occurred_on, source_file,
             uuid.uuid4().hex),
        )
        return str(cursor.fetchone()["id"])


def ofx_transaction(
    pool,
    world,
    amount: Any = "100.00",
    occurred_on: date = date(2026, 3, 5),
    *,
    account_id: Optional[str] = None,
) -> str:
    """Despesa canônica de extrato (arquivo .ofx, paga) em uma conta do titular.

    É o único lastro que dispensa revisão em uma baixa: os testes que precisam
    de uma proposta aplicável por grant delegado conciliam com uma destas.
    """
    return seed.create_transaction(
        pool, world.tenant_id, account_id or world.personal_account_id, world.expense_category_id,
        description="Débito sintético no extrato", amount=amount, occurred_on=occurred_on,
    )


def ledger_transaction(
    pool,
    world,
    amount: Any,
    *,
    fitid: Optional[str] = None,
    dedup_key: Optional[str] = None,
    status: str = "paid",
    source_file: Optional[str] = "extrato-sintetico.ofx",
    entry_source: str = "ofx",
    occurred_on: date = date(2026, 5, 5),
    account_id: Optional[str] = None,
) -> str:
    """Lançamento já existente na conta, com FITID e chave de deduplicação à escolha."""
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO transactions (
                tenant_id, account_id, category_id, description, amount, type, occurred_on, status,
                entry_source, source_file, fitid, dedup_key, canceled_at
            ) VALUES (%s, %s, %s, 'Lançamento existente', %s, 'expense', %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                world.tenant_id, account_id or world.personal_account_id, world.expense_category_id,
                Decimal(str(amount)), occurred_on, status, entry_source, source_file, fitid, dedup_key,
                datetime.now(timezone.utc) if status == "canceled" else None,
            ),
        )
        return str(cursor.fetchone()["id"])


def add_space_member(pool, world, slug: str, space: str = "personal", role: str = "member") -> str:
    """Outro integrante do mesmo tenant e do mesmo espaço (sem grant nenhum)."""
    user_id = seed.create_user(pool, "integrante-%s@example.test" % slug, "Integrante %s" % slug)
    seed.add_tenant_member(pool, world.tenant_id, user_id, "member")
    seed.add_space_member(pool, world.tenant_id, space_id(world, space), user_id, role)
    return user_id


def context_for(pool, world, user_id: str, space: str = "personal"):
    """Contexto resolvido pelo servidor para outro usuário do tenant."""
    from services.ai.scope import resolve_scope

    return resolve_scope(
        pool, user_id=user_id, requested_tenant_id=world.tenant_id, requested_space_id=space_id(world, space)
    )


def approve_by_grant(pool, tenant_id: str, proposal_id: str, grant_id: str, grant_version: int = 1) -> None:
    """Deixa a proposta no estado "aprovada por grant", gravado direto no banco.

    O código do componente nunca deixa uma proposta parada nesse estado (a
    aprovação por grant e a aplicação acontecem na mesma transação), mas a
    tabela permite e outro caminho pode gravá-lo. Os testes usam isto para
    provar que a aplicação reconfere tudo mesmo assim.
    """
    execute(
        pool, tenant_id,
        "UPDATE ai_proposals SET status = 'approved', approval_kind = 'grant', approved_grant_id = %s, "
        "approved_grant_version = %s, approved_hash = payload_hash, approved_at = now() "
        "WHERE id = %s AND tenant_id = %s",
        (grant_id, grant_version, proposal_id, tenant_id),
    )


def add_payment(
    pool,
    tenant_id: str,
    payable_id: str,
    amount: Any,
    *,
    paid_at: Optional[datetime] = None,
    reversed_reason: Optional[str] = None,
) -> str:
    """Pagamento gravado direto na tabela (como faria o app fora da IA)."""
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            """
            INSERT INTO payable_payments (tenant_id, payable_id, amount, paid_at, reversed_at, reversal_reason)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                tenant_id, payable_id, Decimal(str(amount)), paid_at or seed.utc(2026, 10, 5),
                datetime.now(timezone.utc) if reversed_reason else None, reversed_reason,
            ),
        )
        return str(cursor.fetchone()["id"])


def cancel_payable(pool, tenant_id: str, payable_id: str) -> None:
    execute(pool, tenant_id, "UPDATE payables SET canceled_at = now() WHERE id = %s AND tenant_id = %s",
            (payable_id, tenant_id))


def expire_proposal(pool, tenant_id: str, proposal_id: str) -> None:
    """Empurra o vencimento da proposta para o passado."""
    execute(
        pool, tenant_id,
        "UPDATE ai_proposals SET created_at = now() - interval '3 days', expires_at = now() - interval '1 hour' "
        "WHERE id = %s AND tenant_id = %s",
        (proposal_id, tenant_id),
    )


def synthetic_sha256(label: str = "") -> str:
    """Hash de um conteúdo sintético (calculado; nenhum literal no código)."""
    return hashlib.sha256(("arquivo sintético %s %s" % (label, uuid.uuid4().hex)).encode("utf-8")).hexdigest()


def insert_artifact(
    pool,
    world,
    space: str = "personal",
    *,
    artifact_id: Optional[str] = None,
    sha256: Optional[str] = None,
    filename: str = "extrato-sintetico.ofx",
    source_kind: str = "upload",
    detected_kind: str = "ofx",
) -> Tuple[str, str]:
    """Registra um anexo na quarentena do espaço. Devolve (artifact_id, sha256)."""
    artifact_id = artifact_id or seed.new_id()
    sha256 = sha256 or synthetic_sha256(filename)
    execute(
        pool, world.tenant_id,
        """
        INSERT INTO ai_artifacts (
            id, tenant_id, financial_space_id, created_by_user_id, source_kind, original_filename,
            detected_kind, size_bytes, sha256, storage_key, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1024, %s, %s, now() + interval '7 days')
        """,
        (artifact_id, world.tenant_id, space_id(world, space), world.user_id, source_kind, filename,
         detected_kind, sha256, "quarentena/%s" % artifact_id),
    )
    return artifact_id, sha256


def preview_item(
    amount: str,
    tx_type: str = "expense",
    *,
    occurred_on: str = "2026-10-10",
    description: str = "Compra sintética",
    fitid: Optional[str] = None,
    dedup_key: Optional[str] = None,
) -> PreviewItem:
    fitid = fitid or uuid.uuid4().hex
    return PreviewItem(
        dedup_key=dedup_key or "dedup-%s" % fitid,
        occurred_on=occurred_on,
        description=description,
        amount=amount,
        type=tx_type,
        fitid=fitid,
    )


def make_preview(
    account_id: str,
    items: Sequence[PreviewItem],
    *,
    artifact_id: Optional[str] = None,
    sha256: Optional[str] = None,
    filename: str = "extrato-sintetico.ofx",
    file_kind: str = "ofx",
    canonical: bool = True,
    ambiguities: Optional[List[Dict[str, Any]]] = None,
    duplicates: Optional[Sequence[PreviewItem]] = None,
    institution: Optional[str] = "Banco Fictício",
) -> ImportPreview:
    """Prévia montada no teste.

    ``duplicates``: lançamentos que o importador já tirou de ``items`` por
    existirem na conta (é assim que o importador real entrega).
    """
    return ImportPreview(
        artifact_id=artifact_id or seed.new_id(),
        artifact_sha256=sha256 or synthetic_sha256(filename),
        filename=filename,
        file_kind=file_kind,
        account_id=account_id,
        canonical=canonical,
        items=list(items),
        duplicates=[
            {"item": item.to_dict(), "reason": "Lançamento já existente na conta.", "scope": "ledger"}
            for item in duplicates or []
        ],
        ambiguities=list(ambiguities or []),
        institution=institution,
    )


def effect_counts(pool, tenant_id: str) -> Dict[str, int]:
    """Contagem de tudo que um efeito financeiro da IA pode gravar."""
    return {
        "payments": seed.count_rows(pool, tenant_id, "payable_payments", "tenant_id = %s", (tenant_id,)),
        "transactions": seed.count_rows(pool, tenant_id, "transactions", "tenant_id = %s", (tenant_id,)),
        "batches": seed.count_rows(pool, tenant_id, "import_batches", "tenant_id = %s", (tenant_id,)),
        "operations": seed.count_rows(pool, tenant_id, "ai_operations"),
        "applied_audits": seed.count_rows(
            pool, tenant_id, "audit_events", "tenant_id = %s AND event_type = 'ai.operation.applied'", (tenant_id,)
        ),
        "outbox": seed.count_rows(pool, tenant_id, "ai_outbox"),
    }


def run_concurrently(callables: Sequence[Callable[[], Any]], timeout: float = 60.0) -> List[Tuple[str, Any]]:
    """Dispara as funções ao mesmo tempo, em threads reais.

    Devolve, na ordem, ("ok", resultado) ou ("error", exceção).
    """
    barrier = threading.Barrier(len(callables))
    results = [("error", RuntimeError("não executou"))] * len(callables)  # type: List[Tuple[str, Any]]

    def runner(index: int, function: Callable[[], Any]) -> None:
        try:
            barrier.wait(timeout=20)
            results[index] = ("ok", function())
        except BaseException as exc:  # noqa: BLE001 - o teste inspeciona a exceção
            results[index] = ("error", exc)

    threads = [threading.Thread(target=runner, args=(index, function)) for index, function in enumerate(callables)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout)
        assert not thread.is_alive(), "thread não terminou: possível deadlock"
    return results


def run_overlapping(
    pool, callables: Sequence[Callable[[], Any]], lock_sql: str, lock_params: Sequence[Any], timeout: float = 60.0
) -> List[Tuple[str, Any]]:
    """Garante sobreposição REAL entre as chamadas.

    Threads soltas ao mesmo tempo podem, por sorte, rodar uma depois da outra
    (cada chamada dura milissegundos) e o teste passaria sem concorrência
    nenhuma. Aqui o teste segura um lock de linha de que o efeito precisa,
    dispara as chamadas, espera TODAS ficarem paradas dentro do banco e só
    então solta o lock.

    As chamadas partem uma de cada vez, na ordem dada, e a seguinte só parte
    quando a anterior já está parada: assim a ordem de chegada ao banco é
    conhecida e o teste não depende de qual thread o sistema escalona antes.
    """
    results = [("error", RuntimeError("não executou"))] * len(callables)  # type: List[Tuple[str, Any]]

    def runner(index: int, function: Callable[[], Any]) -> None:
        try:
            results[index] = ("ok", function())
        except BaseException as exc:  # noqa: BLE001 - o teste inspeciona a exceção
            results[index] = ("error", exc)

    threads = [threading.Thread(target=runner, args=(index, function)) for index, function in enumerate(callables)]
    blocker = pool.getconn()
    try:
        with blocker.cursor() as cursor:
            cursor.execute(lock_sql, tuple(lock_params))
            assert cursor.fetchone() is not None, "o lock do teste não encontrou a linha"
        for position, thread in enumerate(threads, start=1):
            thread.start()
            blocked = wait_for_blocked_backends(pool, position)
            assert blocked >= position, "só %d de %d chamadas chegaram a concorrer" % (blocked, position)
    finally:
        blocker.rollback()
        pool.putconn(blocker)
    for thread in threads:
        thread.join(timeout)
        assert not thread.is_alive(), "thread não terminou: possível deadlock"
    return results


def run_second_while_first_holds_its_locks(
    pool, tenant_id: str, first_outbox_key: str, first: Callable[[], Any], second: Callable[[], Any],
    timeout: float = 60.0,
) -> List[Tuple[str, Any]]:
    """Ordem forçada entre dois efeitos DIFERENTES que disputam as mesmas linhas.

    ``first`` roda o efeito inteiro e fica parada no último passo (o outbox),
    ainda sem confirmar e com todos os locks do efeito tomados. Só então
    ``second`` parte e fica parada no lock que as duas disputam. Aí o teste
    solta ``first``: ela confirma, e ``second`` segue vendo o que foi
    confirmado.

    Como ``first`` é segurada: o teste insere, sem confirmar, uma linha de
    outbox com a mesma ``dedup_key``. O ``INSERT ... ON CONFLICT DO NOTHING``
    de ``first`` precisa esperar essa transação acabar para saber se há
    conflito. O teste desfaz a linha dele (rollback), e ``first`` grava a sua.
    """
    results = [("error", RuntimeError("não executou"))] * 2  # type: List[Tuple[str, Any]]

    def runner(index: int, function: Callable[[], Any]) -> None:
        try:
            results[index] = ("ok", function())
        except BaseException as exc:  # noqa: BLE001 - o teste inspeciona a exceção
            results[index] = ("error", exc)

    threads = [
        threading.Thread(target=runner, args=(index, function)) for index, function in enumerate((first, second))
    ]
    blocker = pool.getconn()
    try:
        with blocker.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
            cursor.execute(
                "INSERT INTO ai_outbox (tenant_id, topic, dedup_key) VALUES (%s, 'teste.bloqueio', %s)",
                (tenant_id, first_outbox_key),
            )
        threads[0].start()
        assert wait_for_blocked_backends(pool, 1) >= 1, "a primeira aplicação não chegou ao outbox"
        threads[1].start()
        assert wait_for_blocked_backends(pool, 2) >= 2, "a segunda aplicação não ficou esperando a primeira"
    finally:
        blocker.rollback()
        pool.putconn(blocker)
    for thread in threads:
        thread.join(timeout)
        assert not thread.is_alive(), "thread não terminou: possível deadlock"
    return results


def wait_for_blocked_backends(pool, minimum: int, timeout: float = 15.0) -> int:
    """Espera até haver pelo menos ``minimum`` sessões paradas em lock."""
    deadline = time.monotonic() + timeout
    waiting = 0
    while time.monotonic() < deadline:
        connection = pool.getconn()
        try:
            with connection.cursor() as cursor:
                # Só as sessões DESTE banco de teste: o servidor é compartilhado
                # com outras suítes que rodam em paralelo.
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
                waiting = cursor.fetchone()[0]
            connection.rollback()
        finally:
            pool.putconn(connection)
        if waiting >= minimum:
            return waiting
        time.sleep(0.05)
    return waiting


def decimal_sum(values: Sequence[Any]) -> Decimal:
    return sum((Decimal(str(value)) for value in values), Decimal("0"))


def facts_by_key(result) -> Dict[str, Any]:
    """{chave: fato} de um ToolResult (uma moeda só nos testes)."""
    return {fact.key: fact for fact in result.facts}


def tomorrow_plus(days: int) -> date:
    return datetime.now(timezone.utc).date() + timedelta(days=days)
