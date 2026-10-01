"""finance.apply_change: efeito único, autorização vigente e reversão.

Cobre AC-03 (um único efeito), AC-04 (timeout após commit), AC-05 (grant
revogado) e AC-14 (baixa parcial, estados distintos), sempre com PostgreSQL
real e threads reais.

Duas formas de uma baixa chegar a "aplicada", e os testes usam as duas:

* conciliada com um lançamento canônico do extrato (``_prepare_backed``): é a
  única que um grant delegado aplica sozinho;
* sem lastro em extrato (``_prepare`` com evidência descrita pelo modelo):
  sempre exige a aprovação específica do titular (``_register``).
"""

from __future__ import annotations

import threading
import time
from datetime import date
from decimal import Decimal

import pytest

from services.ai import CONTRACT_VERSION, policy
from services.ai.db import jsonb
from services.ai.errors import AiError
from services.ai.finance import operations, proposals, read
from services.ai.settings import AiSettings

from .support import finance_helpers as fh
from .support import seed


MANUAL = [{"kind": "manual", "ref": "pedido-do-titular"}]
PAID_ON = "2026-03-05"  # no passado: data futura exigiria revisão


def _error(function, *args, **kwargs) -> AiError:
    with pytest.raises(AiError) as excinfo:
        function(*args, **kwargs)
    return excinfo.value


def _payable(pool, world, amount="300.00", space="personal", title="Aluguel"):
    return seed.create_payable(
        pool, world.tenant_id, fh.space_id(world, space), title=title, amount_expected=amount,
        competency_month=fh.OCT, due_date=date(2026, 10, 10),
    )


def _prepare(pool, ctx, payable_id, amount="100.00", paid_on=PAID_ON, evidence=None, **kwargs):
    """Baixa SEM lastro em extrato: nasce exigindo revisão."""
    return proposals.prepare_payable_payment(
        pool, ctx, payable_id=payable_id, amount=amount, paid_on=paid_on,
        evidence=MANUAL if evidence is None else evidence, **kwargs
    )


def _prepare_backed(pool, ctx, world, payable_id, amount="100.00", paid_on=PAID_ON, transaction_id=None,
                    evidence=None, **kwargs):
    """Baixa conciliada com um lançamento canônico do extrato.

    Sem ``transaction_id``, cria o lançamento (uma ação nova a cada chamada).
    Para repetir a MESMA ação, o teste cria o lançamento antes e o informa.
    """
    transaction_id = transaction_id or fh.ofx_transaction(pool, world, amount)
    return proposals.prepare_payable_payment(
        pool, ctx, payable_id=payable_id, amount=amount, paid_on=paid_on, evidence=evidence or [],
        transaction_id=transaction_id, **kwargs
    )


def _apply(pool, ctx, settings, view, version=1):
    return operations.apply_proposal(pool, ctx, view["proposal_id"], expected_version=version, settings=settings)


def _approve(pool, ctx, view):
    return proposals.approve(pool, ctx, view["proposal_id"], payload_hash=view["payload_hash"], version=view["version"])


def _register(pool, ctx, settings, view):
    """Caminho do titular: aprovação específica (hash + versão) e aplicação."""
    _approve(pool, ctx, view)
    return _apply(pool, ctx, settings, view)


def _codes(view):
    return sorted(item["code"] for item in view["ambiguities"])


def _payments(pool, tenant_id, payable_id):
    return fh.fetch_all(
        pool, tenant_id,
        "SELECT id, amount, paid_at, transaction_id, reversed_at, reversal_reason, created_by_user_id "
        "FROM payable_payments WHERE tenant_id = %s AND payable_id = %s ORDER BY created_at, id",
        (tenant_id, payable_id),
    )


def _effects(pool, tenant_id):
    """(pagamentos, operações, auditorias de aplicação, outbox)."""
    counts = fh.effect_counts(pool, tenant_id)
    return counts["payments"], counts["operations"], counts["applied_audits"], counts["outbox"]


def _import_preview(world, items=None, **kwargs):
    items = items or [
        fh.preview_item("0.10", occurred_on="2026-03-02"),
        fh.preview_item("0.20", occurred_on="2026-03-03"),
        fh.preview_item("89.90", occurred_on="2026-03-04"),
        fh.preview_item("2500.00", "income", occurred_on="2026-03-05"),
    ]
    return fh.make_preview(world.personal_account_id, items, **kwargs)


def _import(pool, ctx, preview, source_kind="upload"):
    return proposals.prepare_statement_import(pool, ctx, preview=preview, source_kind=source_kind)


# ---------------------------------------------------------------------------
# AC-03: um único efeito.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_concurrent_and_repeated_apply_create_exactly_one_payment(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    statement = fh.ofx_transaction(pool, world, "100.00")
    view = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    assert view["requires_review"] is False
    before = fh.effect_counts(pool, world.tenant_id)

    # Seis workers com a MESMA proposta, comprovadamente ao mesmo tempo: o
    # teste segura a conta a pagar até os seis estarem parados dentro do banco.
    results = fh.run_overlapping(
        pool, [lambda: _apply(pool, ctx, settings, view) for _ in range(6)],
        "SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,),
    )
    assert [status for status, _ in results] == ["ok"] * 6, results
    outcomes = [outcome for _, outcome in results]
    assert all(outcome == outcomes[0] for outcome in outcomes)
    assert outcomes[0]["status"] == "applied" and outcomes[0]["operation_id"] == view["planned_operation_id"]
    # E também soltos de uma vez, sem nada segurando.
    free = fh.run_concurrently([lambda: _apply(pool, ctx, settings, view) for _ in range(6)])
    assert [outcome for _, outcome in free] == outcomes

    # Reenvio sequencial e "failover": outro worker refaz a prévia e aplica.
    assert _apply(pool, ctx, settings, view) == outcomes[0]
    again = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    assert again["proposal_id"] == view["proposal_id"] and again["status"] == "applied"
    assert again["operation_id"] == outcomes[0]["operation_id"]
    assert _apply(pool, ctx, settings, again) == outcomes[0]

    after = fh.effect_counts(pool, world.tenant_id)
    assert after["payments"] - before["payments"] == 1
    assert after["operations"] == 1 and after["applied_audits"] == 1 and after["outbox"] == 1
    payment = _payments(pool, world.tenant_id, payable)[0]
    assert payment["amount"] == Decimal("100.00") and str(payment["created_by_user_id"]) == world.user_id
    outbox = fh.fetch_all(pool, world.tenant_id, "SELECT dedup_key, operation_id, topic, status FROM ai_outbox")[0]
    assert outbox["dedup_key"] == "operation:%s:applied" % outcomes[0]["operation_id"]
    assert str(outbox["operation_id"]) == outcomes[0]["operation_id"] and outbox["status"] == "pending"


@pytest.mark.integration
def test_concurrent_and_repeated_apply_import_statement_once(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    preview = _import_preview(world)
    view = _import(pool, ctx, preview)
    assert view["requires_review"] is False

    # Sobreposição forçada: o lock na conta bancária segura o INSERT do lote
    # (chave estrangeira) até os seis workers estarem parados dentro do banco.
    results = fh.run_overlapping(
        pool, [lambda: _apply(pool, ctx, settings, view) for _ in range(6)],
        "SELECT id FROM accounts WHERE id = %s FOR UPDATE", (world.personal_account_id,),
    )
    assert [status for status, _ in results] == ["ok"] * 6, results
    outcomes = [outcome for _, outcome in results]
    assert all(outcome == outcomes[0] for outcome in outcomes) and outcomes[0]["status"] == "applied"
    free = fh.run_concurrently([lambda: _apply(pool, ctx, settings, view) for _ in range(6)])
    assert [outcome for _, outcome in free] == outcomes
    assert _apply(pool, ctx, settings, view) == outcomes[0]
    # Reenvio do mesmo arquivo: devolve a proposta já aplicada.
    resent = _import(pool, ctx, preview)
    assert resent["proposal_id"] == view["proposal_id"] and resent["status"] == "applied"
    assert _apply(pool, ctx, settings, resent) == outcomes[0]

    counts = fh.effect_counts(pool, world.tenant_id)
    assert counts == {
        "payments": 0, "transactions": 4, "batches": 1, "operations": 1, "applied_audits": 1, "outbox": 1,
    }
    assert outcomes[0]["effect"]["items_new"] == 4 and outcomes[0]["effect"]["items_duplicate"] == 0


@pytest.mark.integration
def test_failover_workers_redo_prepare_and_apply_with_single_effect(pool, world, settings):
    """Failover: cada worker refaz a prévia e aplica, sem saber dos outros.

    Cada worker descreve a evidência de um jeito (é o que acontece quando o
    failover troca de modelo). O rótulo que o modelo escolhe não faz parte da
    identidade da ação: continua sendo UMA baixa.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    statement = fh.ofx_transaction(pool, world, "100.00")
    descriptions = [
        [],
        [{"kind": "manual", "ref": "pedido-1"}],
        [{"kind": "email", "ref": "mensagem-1"}],
        [{"kind": "receipt", "ref": "whatsapp:foto-1"}, {"kind": "manual", "ref": "pedido-2"}],
    ]

    def worker(index):
        def run():
            view = _prepare_backed(
                pool, ctx, world, payable, "100.00", transaction_id=statement,
                evidence=descriptions[index % len(descriptions)],
            )
            return _apply(pool, ctx, settings, view)
        return run

    for _ in range(3):
        results = fh.run_concurrently([worker(index) for index in range(6)])
        assert [status for status, _ in results] == ["ok"] * 6, results
        assert len({outcome["operation_id"] for _, outcome in results}) == 1
        assert all(outcome["status"] == "applied" for _, outcome in results)
    assert _effects(pool, world.tenant_id) == (1, 1, 1, 1)
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 1
    assert [row["amount"] for row in _payments(pool, world.tenant_id, payable)] == [Decimal("100.00")]


@pytest.mark.integration
def test_same_payment_described_with_other_evidence_labels_is_not_a_second_payment(pool, world, settings):
    """A mesma baixa refeita com outro rótulo de evidência não vira outro pagamento.

    Conta de 300, baixa de 100 em 05/03 aplicada. O reenvio descreve a MESMA
    baixa (conta, valor e data) citando outra "evidência". Se o rótulo
    escolhido pelo modelo entrasse na chave, nasceria outra operação e a conta
    ficaria com 200 pagos.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")

    first_view = _prepare(pool, ctx, payable, "100.00", evidence=[{"kind": "manual", "ref": "pedido-1"}])
    first = _register(pool, ctx, settings, first_view)
    for evidence in (
        [{"kind": "email", "ref": "msg-1"}],
        [{"kind": "receipt", "ref": "whatsapp:foto-9"}],
        [{"kind": "manual", "ref": "pedido-1"}, {"kind": "email", "ref": "msg-2"}],
        [],
    ):
        again = _prepare(pool, ctx, payable, "100.00", evidence=evidence)
        assert again["proposal_id"] == first_view["proposal_id"] and again["status"] == "applied", evidence
        assert again["operation_id"] == first["operation_id"]
        assert _apply(pool, ctx, settings, again) == first
    assert [row["amount"] for row in _payments(pool, world.tenant_id, payable)] == [Decimal("100.00")]
    assert _effects(pool, world.tenant_id) == (1, 1, 1, 1)
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 1

    # Mesma conta, valor e data, mas agora com OUTRA identidade conferida pelo
    # backend (um lançamento do extrato): é outra ação, e por isso mesmo vem
    # marcada como possível duplicidade. Nem o grant ilimitado a aplica.
    statement = fh.ofx_transaction(pool, world, "100.00")
    twin = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    assert twin["proposal_id"] != first_view["proposal_id"]
    assert _codes(twin) == ["possible_duplicate"] and twin["requires_review"] is True
    duplicate = twin["ambiguities"][0]
    assert duplicate["blocking"] is False and duplicate["payments"] == 1
    waiting = _apply(pool, ctx, settings, twin)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "requires_review"
    assert len(_payments(pool, world.tenant_id, payable)) == 1

    # Valor ou data diferentes não são duplicidade.
    assert _codes(_prepare_backed(pool, ctx, world, payable, "100.01")) == []
    assert _codes(_prepare_backed(pool, ctx, world, payable, "100.00", paid_on="2026-03-06")) == []


@pytest.mark.integration
def test_open_proposal_for_same_payable_amount_and_date_is_flagged_as_possible_duplicate(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    first = _prepare_backed(pool, ctx, world, payable, "100.00")
    assert _codes(first) == []
    # Outra proposta, ainda em aberto, para a mesma conta, valor e data.
    second = _prepare_backed(pool, ctx, world, payable, "100.00")
    assert second["proposal_id"] != first["proposal_id"]
    assert _codes(second) == ["possible_duplicate"] and second["ambiguities"][0]["proposals"] == 1
    assert _apply(pool, ctx, settings, second)["status"] == "waiting_review"
    # A primeira segue aplicável; depois dela, a segunda fica desatualizada.
    assert _apply(pool, ctx, settings, first)["status"] == "applied"
    _approve(pool, ctx, second)
    assert _error(_apply, pool, ctx, settings, second).code == "stale_proposal"
    assert [row["amount"] for row in _payments(pool, world.tenant_id, payable)] == [Decimal("100.00")]


@pytest.mark.integration
def test_prepare_that_waited_for_concurrent_apply_returns_the_applied_proposal(pool, world, settings):
    """Uma prévia pedida ENQUANTO a mesma ação está sendo aplicada não abre
    uma segunda proposta: espera e devolve a que foi aplicada."""
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    statement = fh.ofx_transaction(pool, world, "100.00")
    view = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    results = fh.run_overlapping(
        pool,
        [
            lambda: _apply(pool, ctx, settings, view),
            lambda: _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement),
        ],
        "SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,),
    )
    assert [status for status, _ in results] == ["ok", "ok"], results
    applied, prepared = results[0][1], results[1][1]
    assert prepared["proposal_id"] == view["proposal_id"] and prepared["status"] == "applied"
    assert prepared["operation_id"] == applied["operation_id"]
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 1
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 1


@pytest.mark.integration
def test_two_different_actions_on_same_payable_are_serialized_without_overpaying(pool, world, settings):
    """Duas baixas distintas, que somadas passam do saldo: só uma entra."""
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    first = _prepare_backed(pool, ctx, world, payable, "200.00")
    second = _prepare_backed(pool, ctx, world, payable, "150.00", paid_on="2026-03-06")
    assert first["proposal_id"] != second["proposal_id"]
    assert first["requires_review"] is False and second["requires_review"] is False

    results = fh.run_overlapping(
        pool,
        [lambda: _apply(pool, ctx, settings, first), lambda: _apply(pool, ctx, settings, second)],
        "SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,),
    )
    statuses = sorted(status for status, _ in results)
    assert statuses == ["error", "ok"], results
    failure = [outcome for status, outcome in results if status == "error"][0]
    assert isinstance(failure, AiError) and failure.code == "stale_proposal"
    rows = _payments(pool, world.tenant_id, payable)
    assert len(rows) == 1 and rows[0]["amount"] in (Decimal("200.00"), Decimal("150.00"))
    assert fh.effect_counts(pool, world.tenant_id)["operations"] == 1


# ---------------------------------------------------------------------------
# AC-04: timeout depois do commit.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_timeout_after_commit_checks_status_and_does_not_reapply(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    view = _prepare_backed(pool, ctx, world, payable, "100.00")
    planned = view["planned_operation_id"]

    # Antes de qualquer tentativa: o id planejado existe, mas nada foi aplicado.
    pending = operations.operation_status(pool, ctx, planned)
    assert pending["status"] == "not_applied" and pending["proposal_id"] == view["proposal_id"]
    assert pending["effect"] is None

    class WriteTimeout(Exception):
        pass

    def apply_then_lose_the_answer():
        # O commit acontece; a resposta se perde no caminho de volta.
        _apply(pool, ctx, settings, view)
        raise WriteTimeout()

    def executor():
        """O que o executor faz: em timeout, consulta o estado antes de repetir."""
        try:
            apply_then_lose_the_answer()
        except WriteTimeout:
            status = operations.operation_status(pool, ctx, planned)
            if status["status"] == "not_applied":
                return _apply(pool, ctx, settings, view)
            return status

    recovered = executor()
    assert recovered["status"] == "applied" and recovered["operation_id"] == planned
    assert recovered["effect"]["payment_id"] and recovered["effect"]["after"]["paid"] == "100.00"
    assert len(_payments(pool, world.tenant_id, payable)) == 1

    # Uma nova chamada de apply devolve o mesmo resultado, sem segundo efeito.
    replay = _apply(pool, ctx, settings, view)
    assert replay["operation_id"] == planned and replay["effect"] == recovered["effect"]
    assert replay == _apply(pool, ctx, settings, view)
    assert _effects(pool, world.tenant_id) == (1, 1, 1, 1)


@pytest.mark.integration
def test_failure_before_commit_leaves_nothing_and_status_says_not_applied(pool, world, settings, ai_database):
    """Se a transação do efeito falha, não sobra operação, auditoria nem outbox."""
    from psycopg2 import pool as pg_pool

    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    view = _prepare_backed(pool, ctx, world, payable, "100.00")

    # Trava a conta a pagar por fora; a aplicação desiste do lock em 300 ms,
    # DEPOIS de já ter travado a proposta e revalidado o grant.
    blocker = pool.getconn()
    impatient = pg_pool.ThreadedConnectionPool(1, 2, dsn=ai_database.app_dsn, options="-c lock_timeout=300")
    try:
        with blocker.cursor() as cursor:
            cursor.execute("SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,))
        error = _error(_apply, impatient, ctx, settings, view)
        assert error.code == "internal_error" and error.retryable is True
    finally:
        impatient.closeall()
        blocker.rollback()
        pool.putconn(blocker)

    assert _effects(pool, world.tenant_id) == (0, 0, 0, 0)
    assert operations.operation_status(pool, ctx, view["planned_operation_id"])["status"] == "not_applied"
    assert proposals.get_proposal_view(pool, ctx, view["proposal_id"])["status"] == "ready"
    # Agora sim é seguro tentar de novo.
    assert _apply(pool, ctx, settings, view)["status"] == "applied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 1


# ---------------------------------------------------------------------------
# AC-05: grant revogado.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_revoked_grant_blocks_effect_even_for_approved_proposal(pool, world, settings):
    ctx = world.context(pool)
    grant_id = fh.grant(pool, world, mode="assisted")
    payable = _payable(pool, world)
    view = _prepare(pool, ctx, payable)
    _approve(pool, ctx, view)

    policy.revoke_grant(pool, ctx, grant_id, "titular revogou")
    error = _error(_apply, pool, ctx, settings, view)
    assert error.code == "capability_denied" and error.http_status == 403
    assert _effects(pool, world.tenant_id) == (0, 0, 0, 0)
    assert proposals.get_proposal_view(pool, ctx, view["proposal_id"])["status"] == "approved"

    # Com uma autorização nova e vigente, a mesma proposta aprovada é aplicada.
    fh.grant(pool, world, mode="assisted")
    assert _apply(pool, ctx, settings, view)["status"] == "applied"


@pytest.mark.integration
def test_revoked_or_expired_delegated_grant_blocks_effect(pool, world, settings):
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world)
    view = _prepare_backed(pool, ctx, world, payable)
    policy.revoke_grant(pool, ctx, grant_id, "titular revogou")
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"

    # Grant vencido (valid_until no passado) também não autoriza.
    expired = fh.delegated_unlimited(pool, world)
    fh.execute(
        pool, world.tenant_id,
        "UPDATE ai_grants SET valid_from = now() - interval '2 days', valid_until = now() - interval '1 day' "
        "WHERE id = %s", (expired,),
    )
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0
    # Controle: com um grant vigente, a mesma proposta aplica.
    fh.delegated_unlimited(pool, world)
    assert _apply(pool, ctx, settings, view)["status"] == "applied"


@pytest.mark.integration
def test_grant_changed_after_grant_approval_is_denied(pool, world, settings):
    """Proposta aprovada por grant guarda id + versão; se a versão mudou, nega."""
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world)
    view = _prepare_backed(pool, ctx, world, payable)
    fh.approve_by_grant(pool, world.tenant_id, view["proposal_id"], grant_id)
    fh.execute(pool, world.tenant_id, "UPDATE ai_grants SET version = 2 WHERE id = %s", (grant_id,))
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0
    fh.execute(pool, world.tenant_id, "UPDATE ai_grants SET version = 1 WHERE id = %s", (grant_id,))
    assert _apply(pool, ctx, settings, view)["status"] == "applied"


@pytest.mark.integration
def test_grant_approved_proposal_that_requires_review_still_waits(pool, world, settings):
    """Aprovação por grant nunca vale para proposta que exige revisão.

    O estado "aprovada por grant" + ``requires_review`` não é produzido pelo
    caminho normal, mas se existir (gravado por outro caminho) a aplicação não
    pode tratá-lo como aprovação do titular.
    """
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world)
    receipt = _prepare(pool, ctx, payable, evidence=[{"kind": "receipt", "ref": "whatsapp:comprovante-1"}])
    assert receipt["requires_review"] is True
    fh.approve_by_grant(pool, world.tenant_id, receipt["proposal_id"], grant_id)

    waiting = _apply(pool, ctx, settings, receipt)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "requires_review"
    assert _effects(pool, world.tenant_id) == (0, 0, 0, 0)
    assert _payments(pool, world.tenant_id, payable) == []


@pytest.mark.integration
def test_concurrent_revocation_waits_for_effect_and_never_leaves_unauthorized_effect(pool, world, settings):
    """A revogação concorrente espera a transação do efeito terminar.

    Ordem forçada: a aplicação trava o grant (FOR SHARE) e fica parada no lock
    da conta a pagar, que o teste segura. A revogação, disparada nesse meio,
    não consegue passar na frente. Solto o lock: o efeito confirma com o grant
    ainda vigente e só então a revogação entra. Depois dela, nada mais aplica.
    """
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    first = _prepare_backed(pool, ctx, world, payable, "100.00")
    second = _prepare_backed(pool, ctx, world, payable, "50.00")

    outcome = {}

    def do_apply():
        try:
            outcome["apply"] = _apply(pool, ctx, settings, first)
        except BaseException as exc:  # noqa: BLE001
            outcome["apply"] = exc

    def do_revoke():
        try:
            outcome["revoke"] = policy.revoke_grant(pool, ctx, grant_id, "revogação concorrente")
        except BaseException as exc:  # noqa: BLE001
            outcome["revoke"] = exc

    blocker = pool.getconn()
    try:
        with blocker.cursor() as cursor:
            cursor.execute("SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,))
        applier = threading.Thread(target=do_apply)
        applier.start()
        assert fh.wait_for_blocked_backends(pool, 1) >= 1, "a aplicação não chegou ao lock da conta a pagar"
        revoker = threading.Thread(target=do_revoke)
        revoker.start()
        assert fh.wait_for_blocked_backends(pool, 2) >= 2, "a revogação não ficou esperando"
        time.sleep(0.3)
        # Enquanto o efeito não termina, a revogação NÃO entrou.
        assert revoker.is_alive() and "revoke" not in outcome
        assert fh.fetch_value(pool, world.tenant_id, "SELECT revoked_at FROM ai_grants WHERE id = %s",
                              (grant_id,)) is None
    finally:
        blocker.rollback()
        pool.putconn(blocker)
    applier.join(30)
    revoker.join(30)
    assert not applier.is_alive() and not revoker.is_alive()

    assert isinstance(outcome["apply"], dict) and outcome["apply"]["status"] == "applied"
    assert isinstance(outcome["revoke"], policy.Grant) and outcome["revoke"].revoked_at is not None
    assert len(_payments(pool, world.tenant_id, payable)) == 1
    # O efeito foi confirmado antes de a revogação valer.
    applied_at = fh.fetch_value(pool, world.tenant_id, "SELECT applied_at FROM ai_operations")
    audit_revoked = fh.fetch_value(
        pool, world.tenant_id, "SELECT created_at FROM audit_events WHERE event_type = 'ai.grant.revoked'"
    )
    assert applied_at is not None and audit_revoked is not None
    # Depois da revogação, nenhuma outra proposta é aplicada.
    assert _error(_apply, pool, ctx, settings, second).code == "capability_denied"
    assert len(_payments(pool, world.tenant_id, payable)) == 1


@pytest.mark.integration
def test_racing_revocation_never_yields_effect_without_grant(pool, world, settings):
    """Corrida livre: ou aplicou com grant vigente, ou negou sem gravar nada."""
    ctx = world.context(pool)
    for round_index in range(6):
        grant_id = fh.delegated_unlimited(pool, world)
        payable = _payable(pool, world, "300.00", title="Conta %d" % round_index)
        view = _prepare_backed(pool, ctx, world, payable, "100.00")
        other = _prepare_backed(pool, ctx, world, payable, "1.00")
        results = fh.run_concurrently([
            lambda: _apply(pool, ctx, settings, view),
            lambda: policy.revoke_grant(pool, ctx, grant_id, "corrida"),
        ])
        assert results[1][0] == "ok"
        rows = _payments(pool, world.tenant_id, payable)
        operations_for = seed.count_rows(pool, world.tenant_id, "ai_operations", "proposal_id = %s",
                                         (view["proposal_id"],))
        if results[0][0] == "ok":
            assert results[0][1]["status"] == "applied" and len(rows) == 1 and operations_for == 1
            grant_used = fh.fetch_value(pool, world.tenant_id, "SELECT grant_id FROM ai_operations "
                                        "WHERE proposal_id = %s", (view["proposal_id"],))
            assert str(grant_used) == grant_id
        else:
            assert results[0][1].code == "capability_denied" and rows == [] and operations_for == 0
        # Em qualquer desfecho o grant terminou revogado e nada mais aplica.
        assert _error(_apply, pool, ctx, settings, other).code == "capability_denied"


@pytest.mark.integration
def test_other_member_of_same_space_cannot_use_owners_grant_or_approval(pool, admin_pool, world, settings):
    """Grant e aprovação são do ATOR: outro integrante do mesmo espaço não os herda."""
    owner = world.context(pool)
    fh.delegated_unlimited(pool, world)
    member_id = fh.add_space_member(pool, world, "alfa")
    member = fh.context_for(pool, world, member_id)
    assert member.financial_space_id == owner.financial_space_id and member.actor_id != owner.actor_id

    payable = _payable(pool, world, "300.00")
    other_payable = _payable(pool, world, "50.00", title="Condomínio")
    automatic = _prepare_backed(pool, owner, world, payable, "100.00")   # o grant do titular aplicaria
    manual = _prepare(pool, owner, other_payable, "50.00")               # precisa de aprovação específica
    approval = {"payload_hash": manual["payload_hash"], "version": 1}

    def denied_everything():
        # Com o pool administrativo a RLS é ignorada: só os filtros do serviço seguram.
        for database_pool in (pool, admin_pool):
            assert _error(_apply, database_pool, member, settings, automatic).code == "capability_denied"
            assert _error(proposals.approve, database_pool, member, manual["proposal_id"],
                          **approval).code == "capability_denied"
            assert _error(_apply, database_pool, member, settings, manual).code == "capability_denied"

    # Sem grant próprio: vê a proposta do espaço de que participa, mas não aprova nem aplica.
    assert proposals.get_proposal_view(pool, member, automatic["proposal_id"])["status"] == "ready"
    denied_everything()
    # Grant próprio só de observação: continua sem aprovar e sem aplicar.
    seed.create_grant(pool, world.tenant_id, world.personal_space_id, member_id, mode="observe")
    denied_everything()
    # A aprovação do titular não vira autorização do integrante.
    _approve(pool, owner, manual)
    assert _error(_apply, pool, member, settings, manual).code == "capability_denied"
    assert _effects(pool, world.tenant_id) == (0, 0, 0, 0)

    # Nem a reversão de uma operação do titular.
    applied = _apply(pool, owner, settings, automatic)
    reversal = proposals.prepare_reversal(pool, member, applied["operation_id"], "tentativa do integrante")
    assert _error(_apply, pool, member, settings, reversal).code == "capability_denied"
    assert _payments(pool, world.tenant_id, payable)[0]["reversed_at"] is None
    # O titular segue aplicando as dele.
    assert _apply(pool, owner, settings, manual)["status"] == "applied"
    operation_actors = fh.fetch_all(pool, world.tenant_id, "SELECT DISTINCT actor_user_id FROM ai_operations")
    assert [str(row["actor_user_id"]) for row in operation_actors] == [world.user_id]


# ---------------------------------------------------------------------------
# Modos de autonomia.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_no_grant_and_observe_mode_deny_apply(pool, world, settings):
    ctx = world.context(pool)
    payable = _payable(pool, world)
    view = _prepare_backed(pool, ctx, world, payable)
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    fh.grant(pool, world, mode="observe")
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    # Grant delegado de OUTRO espaço não vale aqui.
    fh.delegated_unlimited(pool, world, "business")
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    # Delegado sem a capacidade de aplicar também não.
    fh.delegated_unlimited(pool, world, capabilities=["finance.read", "finance.prepare_change"])
    assert _error(_apply, pool, ctx, settings, view).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0
    # Controle: a mesma proposta aplica quando o grant delegado tem a capacidade.
    fh.delegated_unlimited(pool, world)
    assert _apply(pool, ctx, settings, view)["status"] == "applied"


@pytest.mark.integration
def test_assisted_mode_requires_specific_approval(pool, world, settings):
    ctx = world.context(pool)
    fh.grant(pool, world, mode="assisted")
    payable = _payable(pool, world)
    view = _prepare_backed(pool, ctx, world, payable)

    waiting = _apply(pool, ctx, settings, view)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "needs_specific_approval"
    assert "operation_id" not in waiting and "effect" not in waiting
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0

    _approve(pool, ctx, view)
    # Versão divergente na aplicação: recusa.
    assert _error(_apply, pool, ctx, settings, view, version=2).code == "stale_proposal"
    applied = _apply(pool, ctx, settings, view)
    assert applied["status"] == "applied" and applied["effect"]["state_after"] == "conciliado"
    row = fh.fetch_all(pool, world.tenant_id, "SELECT * FROM ai_proposals WHERE id = %s", (view["proposal_id"],))[0]
    assert row["status"] == "applied" and row["approval_kind"] == "specific"
    assert str(row["approved_by_user_id"]) == world.user_id

    # Baixa sem lastro em extrato: o motivo da espera é a revisão exigida.
    manual = _prepare(pool, ctx, payable, "30.00", paid_on="2026-03-08")
    waiting = _apply(pool, ctx, settings, manual)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "requires_review"
    assert _register(pool, ctx, settings, manual)["effect"]["state_after"] == "registrado_pago"


@pytest.mark.integration
def test_delegated_mode_applies_within_limit_and_waits_above_it(pool, world, settings):
    ctx = world.context(pool)
    grant_id = fh.grant(pool, world, mode="delegated", amount_limit="150.00")
    payable = _payable(pool, world, "1000.00")

    within = _apply(pool, ctx, settings, _prepare_backed(pool, ctx, world, payable, "150.00"))
    assert within["status"] == "applied"
    above_view = _prepare_backed(pool, ctx, world, payable, "150.01")
    assert above_view["requires_review"] is False
    above = _apply(pool, ctx, settings, above_view)
    assert above["status"] == "waiting_review" and above["reason"] == "needs_specific_approval"
    assert above["planned_operation_id"] == above_view["planned_operation_id"]
    assert [row["amount"] for row in _payments(pool, world.tenant_id, payable)] == [Decimal("150.00")]

    operation = fh.fetch_all(pool, world.tenant_id, "SELECT * FROM ai_operations")[0]
    assert str(operation["grant_id"]) == grant_id and str(operation["actor_user_id"]) == world.user_id
    proposal = fh.fetch_all(pool, world.tenant_id, "SELECT * FROM ai_proposals WHERE id = %s",
                            (within["proposal_id"],))[0]
    assert proposal["approval_kind"] == "grant" and str(proposal["approved_grant_id"]) == grant_id
    assert proposal["approved_grant_version"] == 1

    # Acima do limite, a aprovação específica do titular resolve.
    _approve(pool, ctx, above_view)
    assert _apply(pool, ctx, settings, above_view)["status"] == "applied"
    assert len(_payments(pool, world.tenant_id, payable)) == 2


@pytest.mark.integration
def test_delegated_grant_source_restriction_uses_only_verified_origins(pool, world, settings):
    """A origem do efeito sai de anexos conferidos (ou do canal), nunca do rótulo."""
    ctx = world.context(pool)
    payable = _payable(pool, world, "1000.00")
    fh.delegated_unlimited(pool, world, allowed_sources=["email"])

    def source_of(view):
        return view["origin"]["source_kinds"]

    # Pedido pelo app, sem anexo: a origem é o canal ("manual"). Não coberto.
    manual = _prepare_backed(pool, ctx, world, payable, "10.00")
    assert manual["requires_review"] is False and source_of(manual) == ["manual"]
    assert _apply(pool, ctx, settings, manual)["reason"] == "needs_specific_approval"
    # Um "e-mail" apenas citado pelo modelo não vira origem e-mail.
    claimed = _prepare_backed(pool, ctx, world, payable, "11.00",
                              evidence=[{"kind": "email", "ref": "email:mensagem-inventada"}])
    assert source_of(claimed) == ["manual"]
    assert _apply(pool, ctx, settings, claimed)["status"] == "waiting_review"
    # Anexo que de fato chegou por e-mail (está na quarentena do espaço): coberto,
    # mesmo que o modelo o tenha rotulado de outro jeito.
    from_email, _ = fh.insert_artifact(pool, world, "personal", filename="extrato-email.ofx", source_kind="email")
    email = _prepare_backed(pool, ctx, world, payable, "12.00",
                            evidence=[{"kind": "manual", "ref": "artifact:%s" % from_email}])
    assert source_of(email) == ["email"]
    assert _apply(pool, ctx, settings, email)["status"] == "applied"
    # Evidências de duas origens conferidas: o grant precisa cobrir as duas.
    from_upload, _ = fh.insert_artifact(pool, world, "personal", filename="extrato-upload.ofx", source_kind="upload")
    mixed = _prepare_backed(pool, ctx, world, payable, "13.00", evidence=[
        {"kind": "email", "ref": "artifact:%s" % from_email}, {"kind": "email", "ref": "artifact:%s" % from_upload},
    ])
    assert source_of(mixed) == ["email", "upload"]
    assert _apply(pool, ctx, settings, mixed)["status"] == "waiting_review"
    assert [row["amount"] for row in _payments(pool, world.tenant_id, payable)] == [Decimal("12.00")]

    # Importação: vale a origem do anexo.
    uploaded = _import(pool, ctx, _import_preview(world, [fh.preview_item("5.00", occurred_on="2026-03-02")]))
    assert _apply(pool, ctx, settings, uploaded)["status"] == "waiting_review"
    emailed = _import(pool, ctx, _import_preview(world, [fh.preview_item("6.00", occurred_on="2026-03-03")]), "email")
    assert _apply(pool, ctx, settings, emailed)["status"] == "applied"


@pytest.mark.integration
def test_delegated_grant_period_restriction(pool, world, settings):
    ctx = world.context(pool)
    payable = _payable(pool, world, "1000.00")
    fh.delegated_unlimited(pool, world, period_start=date(2026, 3, 1), period_end=date(2026, 3, 31))
    inside = _prepare_backed(pool, ctx, world, payable, "10.00", paid_on="2026-03-31")
    outside = _prepare_backed(pool, ctx, world, payable, "10.00", paid_on="2026-04-01")
    assert _apply(pool, ctx, settings, inside)["status"] == "applied"
    assert _apply(pool, ctx, settings, outside)["status"] == "waiting_review"
    # Importação: a menor e a maior data precisam caber no período.
    spanning = _import_preview(world, [
        fh.preview_item("10.00", occurred_on="2026-03-30"),
        fh.preview_item("10.00", occurred_on="2026-04-02"),
    ])
    view = _import(pool, ctx, spanning)
    assert _apply(pool, ctx, settings, view)["status"] == "waiting_review"
    assert seed.count_rows(pool, world.tenant_id, "import_batches") == 0


@pytest.mark.integration
def test_account_restricted_grant_does_not_cover_effects_without_account(pool, world, settings):
    """Grant delegado restrito a contas só aplica sozinho o que identifica a conta."""
    tenant = world.tenant_id
    restricted = fh.delegated_unlimited(pool, world, account_ids=[world.personal_account_id])
    ctx = world.context(pool)
    payable = _payable(pool, world, "300.00")

    # Baixa "registrado pago": não aponta para transação, logo não tem conta.
    registered = _register(pool, ctx, settings, _prepare(pool, ctx, payable, "100.00"))
    assert registered["effect"]["authorization"]["account_ids"] == []
    # A reversão dela herda a mesma autorização (sem conta) e não exige revisão.
    reversal = proposals.prepare_reversal(pool, ctx, registered["operation_id"], "lançado por engano")
    assert reversal["requires_review"] is False
    waiting = _apply(pool, ctx, settings, reversal)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "needs_specific_approval"
    assert _payments(pool, tenant, payable)[0]["reversed_at"] is None

    # Mesmo que a proposta já chegue "aprovada por grant", o grant restrito não cobre.
    fh.approve_by_grant(pool, tenant, reversal["proposal_id"], restricted)
    assert _error(_apply, pool, ctx, settings, reversal).code == "capability_denied"
    assert _payments(pool, tenant, payable)[0]["reversed_at"] is None

    # Controle 1: efeito que identifica a conta do grant é aplicado.
    conciliated = _prepare_backed(pool, ctx, world, payable, "50.00", paid_on="2026-03-06")
    assert conciliated["scope"]["accounts"][0]["id"] == world.personal_account_id
    assert _apply(pool, ctx, settings, conciliated)["status"] == "applied"
    # Controle 2: sem restrição de conta, a reversão sem conta é coberta.
    policy.revoke_grant(pool, ctx, restricted, "troca de grant")
    fh.delegated_unlimited(pool, world)
    other = _payable(pool, world, "80.00", title="Outra conta")
    other_registered = _register(pool, ctx, settings, _prepare(pool, ctx, other, "80.00"))
    other_reversal = proposals.prepare_reversal(pool, ctx, other_registered["operation_id"], "engano")
    assert _apply(pool, ctx, settings, other_reversal)["status"] == "applied"


@pytest.mark.integration
def test_unverifiable_evidence_never_skips_review_whatever_label_the_model_uses(pool, world, settings):
    """Fase 1: sem lastro em extrato não há baixa automática, nem com grant ilimitado.

    O tipo da evidência é derivado do ARQUIVO guardado na quarentena. Trocar o
    rótulo, juntar uma referência de e-mail que ninguém conferiu ou simplesmente
    não citar o anexo não tira a proposta da revisão.
    """
    ctx = world.context(pool)
    tenant = world.tenant_id
    fh.delegated_unlimited(pool, world)
    image, _ = fh.insert_artifact(pool, world, "personal", filename="comprovante.png", detected_kind="png",
                                  source_kind="whatsapp")
    emailed_pdf, _ = fh.insert_artifact(pool, world, "personal", filename="boleto.pdf", detected_kind="pdf",
                                        source_kind="email")
    image_ref, pdf_ref = "artifact:%s" % image, "artifact:%s" % emailed_pdf
    cases = [
        ("comprovante sozinho", [{"kind": "receipt", "ref": image_ref}], "receipt_only"),
        ("imagem rotulada como manual", [{"kind": "manual", "ref": image_ref}], "receipt_only"),
        ("imagem rotulada como e-mail", [{"kind": "email", "ref": image_ref}], "receipt_only"),
        ("PDF de e-mail rotulado como manual", [{"kind": "manual", "ref": pdf_ref}], "receipt_only"),
        ("comprovante + e-mail inventado",
         [{"kind": "receipt", "ref": image_ref}, {"kind": "email", "ref": "email:inventado"}], "receipt_only"),
        ("comprovante citado sem anexo", [{"kind": "receipt", "ref": "whatsapp:comprovante-1"}], "receipt_only"),
        ("só pedido manual", [{"kind": "manual", "ref": "pedido-do-titular"}], "no_statement_backing"),
        ("só e-mail citado", [{"kind": "email", "ref": "email:inventado"}], "no_statement_backing"),
        ("nenhuma evidência", [], "missing_evidence"),
    ]
    views = {}
    for label, evidence, code in cases:
        payable = _payable(pool, world, "300.00", title=label)
        view = _prepare(pool, ctx, payable, "300.00", evidence=evidence)
        assert view["status"] == "ready" and view["requires_review"] is True, label
        assert _codes(view) == [code] and view["ambiguities"][0]["blocking"] is False, label
        assert view["effect"]["state_after"] == "registrado_pago", label
        waiting = _apply(pool, ctx, settings, view)
        assert waiting["status"] == "waiting_review" and waiting["reason"] == "requires_review", label
        assert _payments(pool, tenant, payable) == [], label
        views[label] = (payable, view)
    assert _effects(pool, tenant) == (0, 0, 0, 0)

    # O tipo e a origem gravados são os do arquivo, não os declarados.
    relabelled = views["imagem rotulada como manual"][1]
    assert [(item["kind"], item["verified"]) for item in relabelled["evidence"]] == [("receipt", True)]
    assert relabelled["origin"]["source_kinds"] == ["whatsapp"]
    pdf_view = views["PDF de e-mail rotulado como manual"][1]
    assert pdf_view["evidence"][0]["kind"] == "receipt" and pdf_view["origin"]["source_kinds"] == ["email"]
    invented = views["comprovante + e-mail inventado"][1]
    assert [(item["kind"], item["verified"]) for item in invented["evidence"]] == [("email", False), ("receipt", True)]
    assert invented["origin"]["source_kinds"] == ["whatsapp"]  # o e-mail inventado não vira origem

    # Só a aprovação específica do titular aplica.
    payable, receipt = views["comprovante sozinho"]
    assert _register(pool, ctx, settings, receipt)["status"] == "applied"
    assert fh.fetch_value(pool, tenant, "SELECT approval_kind FROM ai_proposals WHERE id = %s",
                          (receipt["proposal_id"],)) == "specific"
    assert [row["amount"] for row in _payments(pool, tenant, payable)] == [Decimal("300.00")]

    # Controle: o que dispensa revisão é a transação do extrato conferida no banco,
    # e aí o comprovante junto não atrapalha.
    backed_payable = _payable(pool, world, "300.00", title="Com extrato")
    backed = _prepare_backed(pool, ctx, world, backed_payable, "300.00",
                             evidence=[{"kind": "receipt", "ref": image_ref}])
    assert backed["requires_review"] is False and backed["effect"]["state_after"] == "conciliado"
    assert _apply(pool, ctx, settings, backed)["status"] == "applied"


@pytest.mark.integration
def test_write_flag_off_denies_apply(pool, world):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    view = _prepare_backed(pool, ctx, world, _payable(pool, world))
    disabled = AiSettings(enabled=True, write_enabled=False)
    assert _error(_apply, pool, ctx, disabled, view).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0
    assert _apply(pool, ctx, AiSettings(enabled=True, write_enabled=True), view)["status"] == "applied"


# ---------------------------------------------------------------------------
# Expirada, alvo alterado, conflito.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_expired_and_rejected_proposals_do_not_apply(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world)
    expired = _prepare_backed(pool, ctx, world, payable, "10.00")
    fh.expire_proposal(pool, world.tenant_id, expired["proposal_id"])
    assert _error(_apply, pool, ctx, settings, expired).code == "stale_proposal"
    # A mudança de estado foi confirmada (não se perdeu no rollback do erro).
    assert fh.fetch_value(pool, world.tenant_id, "SELECT status FROM ai_proposals WHERE id = %s",
                          (expired["proposal_id"],)) == "expired"
    assert _error(_apply, pool, ctx, settings, expired).code == "stale_proposal"

    # Aprovada e depois vencida: também não aplica.
    approved = _prepare(pool, ctx, payable, "20.00")
    _approve(pool, ctx, approved)
    fh.expire_proposal(pool, world.tenant_id, approved["proposal_id"])
    assert _error(_apply, pool, ctx, settings, approved).code == "stale_proposal"

    rejected = _prepare_backed(pool, ctx, world, payable, "30.00")
    proposals.reject(pool, ctx, rejected["proposal_id"], "não reconheço")
    assert _error(_apply, pool, ctx, settings, rejected).code == "conflict"
    assert _error(_apply, pool, ctx, settings, {"proposal_id": seed.new_id()}).code == "not_found"
    assert _effects(pool, world.tenant_id) == (0, 0, 0, 0)


@pytest.mark.integration
def test_changed_target_marks_proposal_stale_and_applies_nothing(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id

    # 1) Outro pagamento entrou depois da prévia.
    payable = _payable(pool, world, "300.00")
    view = _prepare_backed(pool, ctx, world, payable, "250.00")
    fh.add_payment(pool, tenant, payable, "100.00")
    assert _error(_apply, pool, ctx, settings, view).code == "stale_proposal"
    assert proposals.get_proposal_view(pool, ctx, view["proposal_id"])["status"] == "stale"
    assert len(_payments(pool, tenant, payable)) == 1  # só o de fora; não virou 350 sobre 300
    assert seed.count_rows(pool, tenant, "audit_events", "event_type = 'ai.proposal.stale'") == 1

    # 2) A conta foi cancelada depois da prévia.
    canceled = _payable(pool, world, "300.00", title="Será cancelada")
    canceled_view = _prepare_backed(pool, ctx, world, canceled, "10.00")
    fh.cancel_payable(pool, tenant, canceled)
    assert _error(_apply, pool, ctx, settings, canceled_view).code == "stale_proposal"

    # 3) O valor previsto foi editado depois da prévia (mesmo aprovada).
    edited = _payable(pool, world, "300.00", title="Será editada")
    edited_view = _prepare(pool, ctx, edited, "10.00")
    _approve(pool, ctx, edited_view)
    fh.execute(pool, tenant, "UPDATE payables SET amount_expected = 5.00 WHERE id = %s", (edited,))
    assert _error(_apply, pool, ctx, settings, edited_view).code == "stale_proposal"

    # 4) A transação conciliada foi vinculada a outro pagamento.
    reconciled = _payable(pool, world, "300.00", title="Conciliada")
    transaction = fh.ofx_transaction(pool, world, "300.00")
    reconciled_view = _prepare_backed(pool, ctx, world, reconciled, "300.00", transaction_id=transaction)
    other = _payable(pool, world, "300.00", title="Outra")
    fh.execute(pool, tenant, "INSERT INTO payable_payments (tenant_id, payable_id, transaction_id, amount, paid_at) "
               "VALUES (%s, %s, %s, 300.00, now())", (tenant, other, transaction))
    assert _error(_apply, pool, ctx, settings, reconciled_view).code == "stale_proposal"

    # 5) A transação conciliada foi cancelada (saiu do realizado).
    vanished = _payable(pool, world, "40.00", title="Lastro cancelado")
    vanishing = fh.ofx_transaction(pool, world, "40.00")
    vanished_view = _prepare_backed(pool, ctx, world, vanished, "40.00", transaction_id=vanishing)
    fh.execute(pool, tenant, "UPDATE transactions SET status = 'canceled', canceled_at = now() WHERE id = %s",
               (vanishing,))
    assert _error(_apply, pool, ctx, settings, vanished_view).code == "stale_proposal"

    for untouched in (reconciled, canceled, edited, vanished):
        assert _payments(pool, tenant, untouched) == []
    assert fh.effect_counts(pool, tenant)["operations"] == 0


@pytest.mark.integration
def test_same_operation_key_with_different_payload_is_conflict(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    payable = _payable(pool, world, "300.00")
    view = _prepare(pool, ctx, payable, "100.00", notes="primeira")
    applied = _register(pool, ctx, settings, view)

    # Pelo caminho normal: mesma ação com outros dados depois de aplicada.
    assert _error(_prepare, pool, ctx, payable, "100.00", notes="segunda").code == "conflict"
    assert _error(_prepare, pool, ctx, payable, "100.00", notes="primeira", payment_method="pix").code == "conflict"
    # Com os mesmos dados, devolve a proposta aplicada (inclusive com outro rótulo de evidência).
    same = _prepare(pool, ctx, payable, "100.00", notes="primeira", evidence=[{"kind": "email", "ref": "outro-rotulo"}])
    assert same["proposal_id"] == view["proposal_id"] and same["status"] == "applied"

    # Barreira final em ai_operations: uma proposta com a MESMA chave e payload
    # diferente (situação de corrida, montada aqui direto no banco).
    row = fh.fetch_all(pool, tenant, "SELECT * FROM ai_proposals WHERE id = %s", (view["proposal_id"],))[0]
    divergent_payload = dict(row["payload"], notes="segunda")
    targets = dict(row["target_versions"])
    targets["payable"] = dict(targets["payable"], paid="100.00", payment_count=1)
    twin = seed.new_id()
    fh.execute(
        pool, tenant,
        """
        INSERT INTO ai_proposals (id, tenant_id, financial_space_id, created_by_user_id, kind, status, payload,
            payload_hash, target_versions, expected_effect, operation_key, expires_at)
        VALUES (%s, %s, %s, %s, 'payable_payment', 'ready', %s, %s, %s, %s, %s, now() + interval '1 day')
        """,
        (twin, tenant, world.personal_space_id, world.user_id, jsonb(divergent_payload),
         proposals.payload_hash_for(divergent_payload), jsonb(targets), jsonb(row["expected_effect"]),
         row["operation_key"]),
    )
    error = _error(operations.apply_proposal, pool, ctx, twin, expected_version=1, settings=settings)
    assert error.code == "conflict" and error.http_status == 409
    assert len(_payments(pool, tenant, payable)) == 1 and fh.effect_counts(pool, tenant)["operations"] == 1

    # Mesma chave e MESMO payload em outra proposta: devolve o resultado anterior.
    proposals.reject(pool, ctx, twin, "payload divergente")
    same_id = seed.new_id()
    fh.execute(
        pool, tenant,
        """
        INSERT INTO ai_proposals (id, tenant_id, financial_space_id, created_by_user_id, kind, status, payload,
            payload_hash, target_versions, expected_effect, operation_key, expires_at)
        VALUES (%s, %s, %s, %s, 'payable_payment', 'ready', %s, %s, %s, %s, %s, now() + interval '1 day')
        """,
        (same_id, tenant, world.personal_space_id, world.user_id, jsonb(row["payload"]), row["payload_hash"],
         jsonb(targets), jsonb(row["expected_effect"]), row["operation_key"]),
    )
    replay = operations.apply_proposal(pool, ctx, same_id, expected_version=1, settings=settings)
    assert replay["operation_id"] == applied["operation_id"] and replay["effect"] == applied["effect"]
    assert len(_payments(pool, tenant, payable)) == 1 and fh.effect_counts(pool, tenant)["applied_audits"] == 1


# ---------------------------------------------------------------------------
# AC-14: baixa parcial e estados distintos.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_partial_payments_keep_each_entry_and_remaining_balance(pool, world, settings):
    ctx = world.context(pool)
    fh.grant(pool, world, mode="assisted")
    tenant = world.tenant_id
    payable = _payable(pool, world, "300.00")

    first = _register(pool, ctx, settings, _prepare(pool, ctx, payable, "100.10"))
    assert first["effect"]["before"] == {"paid": "0.00", "remaining": "300.00", "status": "pending"}
    assert first["effect"]["after"] == {"paid": "100.10", "remaining": "199.90", "status": "partial"}

    overview = fh.facts_by_key(read.payables_overview(pool, ctx, month=10, year=2026))
    assert overview["payables.paid"].value == "100.10" and overview["payables.remaining"].value == "199.90"
    assert overview["payables.count.partial"].value == "1" and overview["payables.count.paid"].value == "0"
    item = read.payables_list(pool, ctx, month=10, year=2026).data["items"][0]
    assert (item["status"], item["paid"], item["remaining"]) == ("partial", "100.10", "199.90")

    # Pagamento maior que o saldo: exige revisão e NÃO quita.
    over = _prepare(pool, ctx, payable, "199.91")
    assert over["status"] == "draft" and over["requires_review"] is True
    assert _error(_approve, pool, ctx, over).code == "ambiguous_evidence"
    assert _error(_apply, pool, ctx, settings, over).code == "ambiguous_evidence"
    item = read.payables_list(pool, ctx, month=10, year=2026).data["items"][0]
    assert (item["status"], item["remaining"]) == ("partial", "199.90")

    second = _register(pool, ctx, settings, _prepare(pool, ctx, payable, "199.90", paid_on="2026-03-20"))
    assert second["effect"]["after"] == {"paid": "300.00", "remaining": "0.00", "status": "paid"}
    rows = _payments(pool, tenant, payable)
    # Cada lançamento preservado, com a data local informada.
    assert [row["amount"] for row in rows] == [Decimal("100.10"), Decimal("199.90")]
    assert [row["paid_at"].date().isoformat() for row in rows] == ["2026-03-05", "2026-03-20"]
    overview = fh.facts_by_key(read.payables_overview(pool, ctx, month=10, year=2026))
    assert overview["payables.remaining"].value == "0.00" and overview["payables.count.paid"].value == "1"
    independent = fh.fetch_value(pool, tenant, "SELECT sum(amount)::numeric FROM payable_payments "
                                 "WHERE payable_id = %s AND reversed_at IS NULL", (payable,))
    assert Decimal(overview["payables.paid"].value) == independent == Decimal("300.00")


@pytest.mark.integration
def test_registered_paid_and_reconciled_are_distinct_states(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    plain_payable = _payable(pool, world, "80.00", title="Sem extrato")
    linked_payable = _payable(pool, world, "90.00", title="Com extrato")
    transaction = fh.ofx_transaction(pool, world, "90.00")

    # "Registrado pago" nunca é automático: sem lastro em extrato, só com o titular.
    plain_view = _prepare(pool, ctx, plain_payable, "80.00")
    assert plain_view["effect"]["state_after"] == "registrado_pago" and plain_view["requires_review"] is True
    assert _apply(pool, ctx, settings, plain_view)["status"] == "waiting_review"
    plain = _register(pool, ctx, settings, plain_view)
    # "Conciliado" tem lastro conferido no banco: o grant delegado aplica.
    linked = _apply(pool, ctx, settings,
                    _prepare_backed(pool, ctx, world, linked_payable, "90.00", transaction_id=transaction))
    assert plain["effect"]["state_after"] == "registrado_pago" and plain["effect"]["transaction_id"] is None
    assert linked["effect"]["state_after"] == "conciliado" and linked["effect"]["transaction_id"] == transaction
    assert _payments(pool, tenant, plain_payable)[0]["transaction_id"] is None
    assert str(_payments(pool, tenant, linked_payable)[0]["transaction_id"]) == transaction
    assert operations.get_operation_view(pool, ctx, plain["operation_id"])["state"] == "registrado_pago"
    assert operations.get_operation_view(pool, ctx, linked["operation_id"])["state"] == "conciliado"

    # Grant restrito a uma conta: a conciliação em conta fora do grant vai para revisão.
    policy.revoke_grant(pool, ctx, fh.fetch_value(pool, tenant, "SELECT id FROM ai_grants"), "troca de grant")
    other_account = seed.create_account(pool, tenant, world.personal_space_id, "Segunda conta pessoal")
    fh.delegated_unlimited(pool, world, account_ids=[other_account])
    ctx = world.context(pool)
    third = _payable(pool, world, "10.00", title="Terceira")
    view = _prepare_backed(pool, ctx, world, third, "10.00", paid_on="2026-03-06")
    assert _apply(pool, ctx, settings, view)["reason"] == "needs_specific_approval"
    # Na conta do grant, aplica.
    inside = fh.ofx_transaction(pool, world, "10.00", account_id=other_account)
    fourth = _payable(pool, world, "10.00", title="Quarta")
    covered = _prepare_backed(pool, ctx, world, fourth, "10.00", paid_on="2026-03-07", transaction_id=inside)
    assert _apply(pool, ctx, settings, covered)["status"] == "applied"


# ---------------------------------------------------------------------------
# Importação: efeito.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_statement_import_effect_follows_canonical_rule(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant, account = world.tenant_id, world.personal_account_id
    seed.create_transaction(pool, tenant, account, world.expense_category_id, description="Já importado",
                            amount="40.00", occurred_on=date(2026, 3, 3), fitid="FIT-JA-EXISTE")
    items = [
        fh.preview_item("0.10", occurred_on="2026-03-02", description="  Padaria   Sintética  "),
        fh.preview_item("0.20", occurred_on="2026-03-04"),
        fh.preview_item("1500.00", "income", occurred_on="2026-03-05"),
        fh.preview_item("40.00", fitid="FIT-JA-EXISTE", occurred_on="2026-03-03"),
    ]
    preview = fh.make_preview(account, items, filename="Extrato-Marco.OFX")
    view = _import(pool, ctx, preview)
    assert (view["effect"]["items_new"], view["effect"]["items_duplicate"]) == (3, 1)
    # O duplicado já está no realizado: ignorá-lo é seguro e não pede revisão.
    assert view["requires_review"] is False and view["effect"]["items_duplicate_canceled"] == 0

    result = _apply(pool, ctx, settings, view)
    effect = result["effect"]
    # Duplicado é contado, não é erro.
    assert (effect["items_new"], effect["items_duplicate"]) == (3, 1)
    assert effect["totals"] == {"income": "1500.00", "expense": "0.30", "net": "1499.70"}
    assert effect["state_after"] == "importado" and effect["source_file"] == "Extrato-Marco.OFX"

    rows = fh.fetch_all(
        pool, tenant,
        "SELECT t.*, c.name AS category_name, c.type AS category_type FROM transactions t "
        "JOIN categories c ON c.id = t.category_id WHERE t.import_batch_id = %s ORDER BY t.occurred_on",
        (effect["import_batch_id"],),
    )
    assert len(rows) == 3
    for row in rows:
        assert row["entry_source"] == "ofx" and row["status"] == "paid"
        assert row["source_file"] == "Extrato-Marco.OFX" and row["source_file"].lower().endswith(".ofx")
        assert row["category_name"] == "Não classificado" and row["category_type"] == row["type"]
        assert row["fitid"] and row["dedup_key"] and str(row["account_id"]) == account
        assert str(row["created_by_user_id"]) == world.user_id
    assert rows[0]["description"] == "Padaria Sintética"
    # Uma categoria "Não classificado" por tipo, criada sob demanda e reaproveitada.
    assert seed.count_rows(pool, tenant, "categories", "tenant_id = %s AND name = 'Não classificado'", (tenant,)) == 2
    batch = fh.fetch_all(pool, tenant, "SELECT * FROM import_batches WHERE id = %s", (effect["import_batch_id"],))[0]
    assert (batch["status"], batch["file_format"], batch["imported_count"], batch["duplicate_count"]) == (
        "completed", "ofx", 3, 1,
    )
    assert batch["total_income"] == Decimal("1500.00") and batch["total_expense"] == Decimal("0.30")

    # O que foi importado entra no realizado (mesma regra canônica) com valor exato.
    facts = fh.facts_by_key(read.realized_totals(pool, ctx, month=3, year=2026))
    assert facts["realized.expense"].value == "40.30" and facts["realized.income"].value == "1500.00"

    # Outro arquivo com os mesmos lançamentos: tudo duplicado, nada a importar.
    other_file = fh.make_preview(account, items[:3], filename="reenvio.ofx")
    assert _error(proposals.prepare_statement_import, pool, ctx, preview=other_file,
                  source_kind="upload").code == "conflict"
    # Segunda importação reaproveita as categorias.
    more = fh.make_preview(account, [fh.preview_item("7.00", occurred_on="2026-03-09")], filename="abril.ofx")
    _apply(pool, ctx, settings, _import(pool, ctx, more))
    assert seed.count_rows(pool, tenant, "categories", "tenant_id = %s AND name = 'Não classificado'", (tenant,)) == 2


@pytest.mark.integration
def test_import_with_transfers_requires_review_and_skips_them(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    preview = _import_preview(world, [
        fh.preview_item("10.00", occurred_on="2026-03-02"),
        fh.preview_item("500.00", "transfer", occurred_on="2026-03-03"),
    ])
    view = _import(pool, ctx, preview)
    assert _apply(pool, ctx, settings, view)["status"] == "waiting_review"
    _approve(pool, ctx, view)
    effect = _apply(pool, ctx, settings, view)["effect"]
    assert (effect["items_new"], effect["items_transfer_skipped"]) == (1, 1)
    assert seed.count_rows(pool, world.tenant_id, "transactions", "type = 'transfer'") == 0
    assert fh.fetch_value(pool, world.tenant_id, "SELECT ignored_count FROM import_batches") == 1


@pytest.mark.integration
def test_ledger_change_after_preview_makes_import_stale(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    items = [fh.preview_item("10.00", fitid="FIT-1", occurred_on="2026-03-02"),
             fh.preview_item("20.00", fitid="FIT-2", occurred_on="2026-03-03")]
    view = _import(pool, ctx, _import_preview(world, items))
    # Um dos lançamentos entra por outro caminho antes da aplicação.
    seed.create_transaction(pool, world.tenant_id, world.personal_account_id, world.expense_category_id,
                            description="Entrou por fora", amount="10.00", occurred_on=date(2026, 3, 2), fitid="FIT-1")
    assert _error(_apply, pool, ctx, settings, view).code == "stale_proposal"
    assert fh.effect_counts(pool, world.tenant_id)["transactions"] == 1
    assert fh.effect_counts(pool, world.tenant_id)["batches"] == 0


@pytest.mark.integration
def test_statement_entries_that_exist_only_as_canceled_rows_require_review(pool, world, settings):
    """"Já existe" não é "já está no realizado".

    Uma importação revertida deixa os lançamentos cancelados, ocupando FITID e
    chave. Um extrato NOVO com os mesmos lançamentos os trataria como
    duplicados e os ignoraria; aplicado sem aviso, o realizado ficaria
    incompleto em silêncio.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    account = world.personal_account_id
    eleven = fh.preview_item("11.00", fitid="FIT-G1", occurred_on="2026-05-05")
    twenty_two = fh.preview_item("22.00", fitid="FIT-G2", occurred_on="2026-05-06")
    thirty_three = fh.preview_item("33.00", fitid="FIT-G3", occurred_on="2026-05-07")

    def may_expense():
        return fh.facts_by_key(read.realized_totals(pool, ctx, month=5, year=2026))["realized.expense"].value

    first = _apply(pool, ctx, settings, _import(pool, ctx, fh.make_preview(account, [eleven, twenty_two],
                                                                         filename="maio-a.ofx")))
    assert may_expense() == "33.00"
    _apply(pool, ctx, settings, proposals.prepare_reversal(pool, ctx, first["operation_id"], "arquivo errado"))
    assert may_expense() is None

    # Outro arquivo, mesmos dois lançamentos e um novo. O provedor deste teste
    # entrega tudo em ``items``; quem descobre os duplicados é a conferência no banco.
    view = _import(pool, ctx, fh.make_preview(account, [eleven, twenty_two, thirty_three], filename="maio-b.ofx"))
    effect = view["effect"]
    assert (effect["items_new"], effect["items_duplicate"], effect["items_duplicate_canceled"]) == (1, 2, 2)
    assert view["status"] == "ready" and view["requires_review"] is True
    assert _codes(view) == ["duplicate_of_canceled"]
    warning = view["ambiguities"][0]
    assert warning["count"] == 2 and warning["total"] == "33.00" and "R$ 33,00" in warning["message"]
    assert "CANCELADO" in view["summary_pt_br"] and "fora do realizado" in view["summary_pt_br"]
    waiting = _apply(pool, ctx, settings, view)
    assert waiting["status"] == "waiting_review" and waiting["reason"] == "requires_review"
    assert may_expense() is None and seed.count_rows(pool, world.tenant_id, "import_batches") == 1

    # O importador real já tira os duplicados de ``items`` e os lista em
    # ``duplicates``: a conferência vale do mesmo jeito.
    filtered = _import(pool, ctx, fh.make_preview(account, [thirty_three], duplicates=[eleven, twenty_two],
                                                  filename="maio-c.ofx"))
    assert (filtered["effect"]["items_new"], filtered["effect"]["items_duplicate"]) == (1, 2)
    assert filtered["effect"]["items_duplicate_canceled"] == 2 and _codes(filtered) == ["duplicate_of_canceled"]
    assert _apply(pool, ctx, settings, filtered)["status"] == "waiting_review"

    # Extrato só com lançamentos cancelados: nada a importar, e a mensagem diz por quê.
    nothing = _error(proposals.prepare_statement_import, pool, ctx, source_kind="upload",
                     preview=fh.make_preview(account, [eleven, twenty_two], filename="maio-d.ofx"))
    assert nothing.code == "conflict" and "cancelados" in nothing.safe_message

    # Ciente do aviso, o titular aprova: entra só o lançamento novo; os cancelados não voltam.
    applied = _register(pool, ctx, settings, filtered)
    assert applied["effect"]["items_new"] == 1 and may_expense() == "33.00"
    canceled = seed.count_rows(pool, world.tenant_id, "transactions", "status = 'canceled'")
    assert canceled == 2


@pytest.mark.integration
def test_duplicate_that_gets_canceled_after_the_preview_makes_the_import_stale(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    account = world.personal_account_id
    existing = fh.ledger_transaction(pool, world, "40.00", fitid="FIT-ATIVO", dedup_key="chave-ativa")
    known = fh.preview_item("40.00", fitid="FIT-ATIVO", dedup_key="chave-ativa", occurred_on="2026-05-05")
    new = fh.preview_item("7.00", occurred_on="2026-05-06")
    same_file = {"filename": "junho.ofx", "sha256": fh.synthetic_sha256("junho"), "artifact_id": seed.new_id()}
    view = _import(pool, ctx, fh.make_preview(account, [new], duplicates=[known], **same_file))
    # Na prévia o duplicado está no realizado: nada a revisar.
    assert view["requires_review"] is False and view["effect"]["items_duplicate"] == 1

    fh.execute(pool, world.tenant_id, "UPDATE transactions SET status = 'canceled', canceled_at = now() WHERE id = %s",
               (existing,))
    assert _error(_apply, pool, ctx, settings, view).code == "stale_proposal"
    assert seed.count_rows(pool, world.tenant_id, "import_batches") == 0
    # A nova prévia do MESMO arquivo já nasce com o aviso.
    again = _import(pool, ctx, fh.make_preview(account, [new], duplicates=[known], **same_file))
    assert again["proposal_id"] != view["proposal_id"] and _codes(again) == ["duplicate_of_canceled"]


# ---------------------------------------------------------------------------
# Reversão.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_payment_reversal_compensates_keeps_history_and_is_idempotent(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    payable = _payable(pool, world, "300.00")
    applied = _apply(pool, ctx, settings, _prepare_backed(pool, ctx, world, payable, "100.00"))
    operation_id = applied["operation_id"]

    assert _error(proposals.prepare_reversal, pool, ctx, operation_id, "").code == "invalid_request"
    reversal = proposals.prepare_reversal(pool, ctx, operation_id, "lançado na conta errada")
    assert reversal["kind"] == "reverse_operation" and reversal["status"] == "ready"
    assert reversal["effect"]["state_after"] == "revertido"
    assert reversal["effect"]["before"] == {"paid": "100.00", "remaining": "200.00", "status": "partial"}
    assert reversal["effect"]["after"] == {"paid": "0.00", "remaining": "300.00", "status": "pending"}
    assert "Reverter o pagamento de R$ 100,00" in reversal["summary_pt_br"]
    # Preparar a reversão não reverte nada.
    assert _payments(pool, tenant, payable)[0]["reversed_at"] is None
    # Segundo pedido (até com outro texto) devolve a mesma proposta aberta.
    assert proposals.prepare_reversal(pool, ctx, operation_id, "outro texto")["proposal_id"] == reversal["proposal_id"]

    result = _apply(pool, ctx, settings, reversal)
    assert result["status"] == "applied" and result["kind"] == "reverse_operation"
    assert result["effect"]["reverses_operation_id"] == operation_id
    assert result["effect"]["after"] == {"paid": "0.00", "remaining": "300.00", "status": "pending"}

    # Histórico preservado: a linha continua lá, marcada como revertida.
    rows = _payments(pool, tenant, payable)
    assert len(rows) == 1 and rows[0]["reversed_at"] is not None
    assert rows[0]["reversal_reason"] == "lançado na conta errada"
    status = operations.operation_status(pool, ctx, operation_id)
    assert status["status"] == "reversed" and status["reversed_by_operation_id"] == result["operation_id"]
    assert operations.operation_status(pool, ctx, result["operation_id"])["reverses_operation_id"] == operation_id
    assert seed.count_rows(pool, tenant, "ai_operations") == 2
    overview = fh.facts_by_key(read.payables_overview(pool, ctx, month=10, year=2026))
    assert overview["payables.paid"].value == "0.00" and overview["payables.count.pending"].value == "1"

    # Reverter duas vezes devolve o mesmo resultado, sem novo efeito.
    again = proposals.prepare_reversal(pool, ctx, operation_id, "de novo")
    assert again["proposal_id"] == reversal["proposal_id"] and again["status"] == "applied"
    assert _apply(pool, ctx, settings, again) == result
    assert _apply(pool, ctx, settings, reversal) == result
    assert _effects(pool, tenant) == (1, 2, 2, 2)
    # Reaplicar a proposta original não refaz o pagamento.
    replay = operations.apply_proposal(pool, ctx, applied["proposal_id"], expected_version=1, settings=settings)
    assert replay["operation_id"] == operation_id and replay["operation_status"] == "reversed"
    assert len(_payments(pool, tenant, payable)) == 1
    # Reversão de reversão não existe.
    assert _error(proposals.prepare_reversal, pool, ctx, result["operation_id"], "desfazer").code == "invalid_request"

    # O pagamento revertido não conta mais no saldo de uma nova prévia: a conta
    # volta a aceitar o valor integral (e não só os 200 que "sobrariam").
    full = _prepare(pool, ctx, payable, "300.00", paid_on="2026-03-09")
    assert full["status"] == "ready" and "overpayment" not in _codes(full)
    assert full["effect"]["before"] == {"paid": "0.00", "remaining": "300.00", "status": "pending"}
    assert full["effect"]["after"] == {"paid": "300.00", "remaining": "0.00", "status": "paid"}


@pytest.mark.integration
def test_concurrent_reversal_applies_once(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    applied = _apply(pool, ctx, settings, _prepare_backed(pool, ctx, world, payable, "100.00"))
    reversal = proposals.prepare_reversal(pool, ctx, applied["operation_id"], "engano")
    results = fh.run_overlapping(
        pool, [lambda: _apply(pool, ctx, settings, reversal) for _ in range(5)],
        "SELECT id FROM payables WHERE id = %s FOR UPDATE", (payable,),
    )
    assert [status for status, _ in results] == ["ok"] * 5, results
    assert len({outcome["operation_id"] for _, outcome in results}) == 1
    assert _effects(pool, world.tenant_id) == (1, 2, 2, 2)


@pytest.mark.integration
def test_reapplying_after_reversal_is_a_new_operation_and_needs_review(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    statement = fh.ofx_transaction(pool, world, "100.00")
    first_view = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    first = _apply(pool, ctx, settings, first_view)
    _apply(pool, ctx, settings, proposals.prepare_reversal(pool, ctx, first["operation_id"], "engano"))

    # O reenvio do mesmo pedido não refaz sozinho o que o titular desfez.
    second_view = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement)
    assert second_view["proposal_id"] != first_view["proposal_id"]
    assert second_view["planned_operation_id"] != first["operation_id"]
    assert _codes(second_view) == ["previously_reversed"]
    assert _apply(pool, ctx, settings, second_view)["status"] == "waiting_review"
    assert len([row for row in _payments(pool, world.tenant_id, payable) if row["reversed_at"] is None]) == 0
    # Trocar a descrição da evidência não faz o pedido parecer novo: é a mesma
    # ação, logo a mesma proposta, com o mesmo aviso.
    relabelled = _prepare_backed(pool, ctx, world, payable, "100.00", transaction_id=statement,
                                 evidence=[{"kind": "email", "ref": "outra-referencia"}])
    assert relabelled["proposal_id"] == second_view["proposal_id"]
    assert _codes(relabelled) == ["previously_reversed"]

    second = _register(pool, ctx, settings, second_view)
    assert second["status"] == "applied" and second["operation_id"] != first["operation_id"]
    rows = _payments(pool, world.tenant_id, payable)
    assert len(rows) == 2 and [row["reversed_at"] is None for row in rows] == [False, True]


@pytest.mark.integration
def test_import_reversal_cancels_transactions_and_rolls_back_batch(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    preview = _import_preview(world)
    applied = _apply(pool, ctx, settings, _import(pool, ctx, preview))
    batch_id = applied["effect"]["import_batch_id"]
    assert fh.facts_by_key(read.realized_totals(pool, ctx, month=3, year=2026))["realized.expense"].value == "90.20"

    reversal = proposals.prepare_reversal(pool, ctx, applied["operation_id"], "arquivo errado")
    assert reversal["effect"]["items_new"] == 4
    assert reversal["effect"]["totals"] == {"income": "2500.00", "expense": "90.20", "net": "2409.80"}
    result = _apply(pool, ctx, settings, reversal)
    assert result["effect"]["items_canceled"] == 4

    rows = fh.fetch_all(pool, tenant, "SELECT status, canceled_at FROM transactions WHERE import_batch_id = %s",
                        (batch_id,))
    # Nada apagado: as 4 linhas seguem no banco, canceladas.
    assert len(rows) == 4 and all(row["status"] == "canceled" and row["canceled_at"] for row in rows)
    batch = fh.fetch_all(pool, tenant, "SELECT status, rolled_back_at FROM import_batches WHERE id = %s",
                         (batch_id,))[0]
    assert batch["status"] == "rolled_back" and batch["rolled_back_at"] is not None
    assert operations.operation_status(pool, ctx, applied["operation_id"])["status"] == "reversed"
    # Sai do realizado.
    assert fh.facts_by_key(read.realized_totals(pool, ctx, month=3, year=2026))["realized.expense"].value is None
    # Idempotente.
    assert _apply(pool, ctx, settings, reversal) == result
    assert seed.count_rows(pool, tenant, "ai_operations") == 2
    # O mesmo arquivo não é reimportado depois da reversão.
    assert _error(proposals.prepare_statement_import, pool, ctx, preview=preview,
                  source_kind="upload").code == "conflict"


@pytest.mark.integration
def test_import_reversal_is_blocked_while_a_payment_is_reconciled_with_it(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    preview = _import_preview(world, [fh.preview_item("90.00", fitid="FIT-ALUGUEL", occurred_on="2026-03-05")])
    applied = _apply(pool, ctx, settings, _import(pool, ctx, preview))
    transaction = str(fh.fetch_value(pool, tenant, "SELECT id FROM transactions WHERE fitid = 'FIT-ALUGUEL'"))
    payable = _payable(pool, world, "90.00")
    payment = _apply(pool, ctx, settings,
                     _prepare_backed(pool, ctx, world, payable, "90.00", transaction_id=transaction))
    assert payment["effect"]["state_after"] == "conciliado"

    assert _error(proposals.prepare_reversal, pool, ctx, applied["operation_id"], "arquivo errado").code == "conflict"
    # Revertido o pagamento, a importação pode ser revertida.
    _apply(pool, ctx, settings, proposals.prepare_reversal(pool, ctx, payment["operation_id"], "engano"))
    result = _apply(pool, ctx, settings,
                    proposals.prepare_reversal(pool, ctx, applied["operation_id"], "arquivo errado"))
    assert result["effect"]["items_canceled"] == 1


@pytest.mark.integration
@pytest.mark.parametrize("winner", ["payment", "reversal"])
def test_import_reversal_racing_a_reconciled_payment_never_leaves_payment_on_canceled_entry(
    pool, world, settings, winner
):
    """Reversão da importação x baixa conciliada com um lançamento dela, ao mesmo tempo.

    As duas propostas nascem válidas (a reversão foi preparada ANTES de existir
    o pagamento). Quem confirma primeiro vence; a outra tem de enxergar o que
    foi confirmado e desistir. O que nunca pode sobrar é um pagamento ativo
    apontando para um lançamento cancelado.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    preview = _import_preview(world, [fh.preview_item("90.00", fitid="FIT-CORRIDA", occurred_on="2026-03-05")])
    imported = _apply(pool, ctx, settings, _import(pool, ctx, preview))
    transaction = str(fh.fetch_value(pool, tenant, "SELECT id FROM transactions WHERE fitid = 'FIT-CORRIDA'"))
    payable = _payable(pool, world, "90.00")
    payment_view = _prepare_backed(pool, ctx, world, payable, "90.00", transaction_id=transaction)
    reversal_view = proposals.prepare_reversal(pool, ctx, imported["operation_id"], "arquivo errado")
    assert payment_view["requires_review"] is False and reversal_view["requires_review"] is False

    views = {"payment": payment_view, "reversal": reversal_view}
    loser = "reversal" if winner == "payment" else "payment"
    results = fh.run_second_while_first_holds_its_locks(
        pool, tenant, operations.outbox_dedup_key(views[winner]["planned_operation_id"]),
        lambda: _apply(pool, ctx, settings, views[winner]),
        lambda: _apply(pool, ctx, settings, views[loser]),
    )
    assert results[0][0] == "ok" and results[0][1]["status"] == "applied", results
    assert results[1][0] == "error" and results[1][1].code == "stale_proposal", results

    # Invariante, valha quem valer: nenhum pagamento ativo sobre lançamento cancelado.
    orphans = fh.fetch_value(
        pool, tenant,
        "SELECT count(*) FROM payable_payments pp JOIN transactions t ON t.id = pp.transaction_id "
        "WHERE pp.tenant_id = %s AND pp.reversed_at IS NULL AND t.status = 'canceled'", (tenant,),
    )
    assert orphans == 0
    entry_status = fh.fetch_value(pool, tenant, "SELECT status FROM transactions WHERE id = %s", (transaction,))
    batch_status = fh.fetch_value(pool, tenant, "SELECT status FROM import_batches")
    active_payments = [row for row in _payments(pool, tenant, payable) if row["reversed_at"] is None]
    import_status = operations.operation_status(pool, ctx, imported["operation_id"])["status"]
    if winner == "payment":
        assert (entry_status, batch_status, import_status) == ("paid", "completed", "applied")
        assert [str(row["transaction_id"]) for row in active_payments] == [transaction]
    else:
        assert (entry_status, batch_status, import_status) == ("canceled", "rolled_back", "reversed")
        assert active_payments == []
    assert seed.count_rows(pool, tenant, "ai_operations") == 2  # importação + quem venceu
    assert proposals.get_proposal_view(pool, ctx, views[loser]["proposal_id"])["status"] == "stale"


@pytest.mark.integration
def test_batch_cancellation_skips_entries_backing_an_active_payment_and_aborts_the_reversal(pool, world, settings):
    """Segunda barreira da reversão de importação, exercitada sem a primeira.

    A primeira barreira é o lock das transações do lote (teste de corrida
    acima). Aqui o pagamento conciliado aparece DEPOIS de os vínculos terem
    sido contados, na mesma transação: o cancelamento tem de pular o
    lançamento que virou lastro, e a reversão inteira tem de ser desfeita.
    """
    from services.ai.db import scoped_tx
    from services.ai.finance import repository

    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant = world.tenant_id
    preview = _import_preview(world, [
        fh.preview_item("90.00", fitid="FIT-LASTRO", occurred_on="2026-03-05"),
        fh.preview_item("10.00", fitid="FIT-LIVRE", occurred_on="2026-03-06"),
    ])
    imported = _apply(pool, ctx, settings, _import(pool, ctx, preview))
    batch_id = imported["effect"]["import_batch_id"]
    backing = str(fh.fetch_value(pool, tenant, "SELECT id FROM transactions WHERE fitid = 'FIT-LASTRO'"))
    payable = _payable(pool, world, "90.00")
    reversal = proposals.prepare_reversal(pool, ctx, imported["operation_id"], "arquivo errado")
    payload = fh.fetch_value(pool, tenant, "SELECT payload FROM ai_proposals WHERE id = %s", (reversal["proposal_id"],))
    link_payment = (
        "INSERT INTO payable_payments (tenant_id, payable_id, transaction_id, amount, paid_at) "
        "VALUES (%s, %s, %s, 90.00, now())"
    )

    def statuses():
        rows = fh.fetch_all(pool, tenant, "SELECT fitid, status FROM transactions WHERE import_batch_id = %s",
                            (batch_id,))
        return {row["fitid"]: row["status"] for row in rows}

    class Undo(Exception):
        pass

    # O cancelamento pula o lançamento com pagamento ativo.
    with pytest.raises(Undo):
        with scoped_tx(pool, tenant) as cursor:
            cursor.execute(link_payment, (tenant, payable, backing))
            assert repository.cancel_batch_transactions(cursor, ctx, batch_id) == 1
            cursor.execute("SELECT fitid, status FROM transactions WHERE import_batch_id = %s", (batch_id,))
            assert {row["fitid"]: row["status"] for row in cursor.fetchall()} == {
                "FIT-LASTRO": "paid", "FIT-LIVRE": "canceled",
            }
            raise Undo()
    assert statuses() == {"FIT-LASTRO": "paid", "FIT-LIVRE": "paid"}

    # E a reversão, vendo que sobrou lançamento por cancelar, desiste de tudo.
    with pytest.raises(AiError) as excinfo:
        with scoped_tx(pool, tenant) as cursor:
            _, rows = proposals.load_targets(cursor, ctx, proposals.KIND_REVERSAL, payload, lock=True)
            assert rows["batch"]["linked_transactions"] == 0 and rows["batch"]["active_transactions"] == 2
            cursor.execute(link_payment, (tenant, payable, backing))
            operations._apply_reversal(cursor, ctx, payload, rows, seed.new_id())
    assert excinfo.value.code == "conflict"
    assert statuses() == {"FIT-LASTRO": "paid", "FIT-LIVRE": "paid"}
    assert fh.fetch_value(pool, tenant, "SELECT status FROM import_batches WHERE id = %s", (batch_id,)) == "completed"
    assert operations.operation_status(pool, ctx, imported["operation_id"])["status"] == "applied"
    assert _payments(pool, tenant, payable) == []


@pytest.mark.integration
def test_reversal_respects_modes_and_revocation(pool, world, settings):
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world, capabilities=["finance.apply_change", "finance.prepare_change"])
    payable = _payable(pool, world, "300.00")
    applied = _apply(pool, ctx, settings, _prepare_backed(pool, ctx, world, payable, "100.00"))
    reversal = proposals.prepare_reversal(pool, ctx, applied["operation_id"], "engano")
    # O grant aplica, mas não tem a capacidade de reverter.
    assert _error(_apply, pool, ctx, settings, reversal).code == "capability_denied"
    assert _payments(pool, world.tenant_id, payable)[0]["reversed_at"] is None

    policy.revoke_grant(pool, ctx, grant_id, "troca")
    fh.grant(pool, world, mode="assisted")
    assert _apply(pool, ctx, settings, reversal)["status"] == "waiting_review"
    _approve(pool, ctx, reversal)
    assert _apply(pool, ctx, settings, reversal)["status"] == "applied"
    assert _payments(pool, world.tenant_id, payable)[0]["reversed_at"] is not None


# ---------------------------------------------------------------------------
# AC-01: isolamento de operações. Auditoria.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_operations_are_unknown_from_other_space_and_tenant(pool, admin_pool, world, other_world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world, "personal")
    fh.delegated_unlimited(pool, world, "business")
    fh.delegated_unlimited(pool, other_world, "personal")
    payable = _payable(pool, world, "300.00")
    applied = _apply(pool, ctx, settings, _prepare_backed(pool, ctx, world, payable, "100.00"))
    operation_id = applied["operation_id"]

    for database_pool in (pool, admin_pool):  # admin_pool ignora RLS
        for intruder in (world.context(pool, "business"), other_world.context(pool)):
            for function in (operations.operation_status, operations.get_operation_view):
                assert _error(function, database_pool, intruder, operation_id).code == "operation_unknown"
            assert _error(proposals.prepare_reversal, database_pool, intruder, operation_id, "x y z").code == \
                "operation_unknown"
            assert _error(operations.apply_proposal, database_pool, intruder, applied["proposal_id"],
                          expected_version=1, settings=settings).code == "not_found"
    for unknown in (seed.new_id(), "não-é-uuid", None):
        error = _error(operations.operation_status, pool, ctx, unknown)
        assert error.code == "operation_unknown" and error.http_status == 404
    assert operations.operation_status(pool, ctx, operation_id)["status"] == "applied"
    assert _payments(pool, world.tenant_id, payable)[0]["reversed_at"] is None
    assert seed.count_rows(pool, other_world.tenant_id, "ai_proposals") == 0


@pytest.mark.integration
def test_audit_records_actor_grant_policy_and_references_without_amounts(pool, world, settings):
    ctx = world.context(pool)
    grant_id = fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    applied = _apply(pool, ctx, settings,
                     _prepare_backed(pool, ctx, world, payable, "123.45", notes="anotação sintética"))

    event = fh.fetch_all(
        pool, world.tenant_id,
        "SELECT * FROM audit_events WHERE tenant_id = %s AND event_type = 'ai.operation.applied'",
        (world.tenant_id,),
    )[0]
    metadata = event["metadata"]
    assert str(event["actor_user_id"]) == world.user_id and str(event["entity_id"]) == applied["operation_id"]
    assert event["entity_type"] == "ai_operation"
    assert metadata["grant_id"] == grant_id and metadata["grant_version"] == 1 and metadata["grant_mode"] == "delegated"
    assert metadata["approval_kind"] == "grant" and metadata["policy_version"] == 1
    assert metadata["contract_version"] == CONTRACT_VERSION
    assert metadata["proposal_id"] == applied["proposal_id"] and metadata["operation_id"] == applied["operation_id"]
    assert metadata["financial_space_id"] == world.personal_space_id and metadata["trace_id"] == ctx.trace_id
    assert metadata["before"] == {"payable_id": payable, "status": "pending", "payment_count": 0}
    assert metadata["after"]["status"] == "partial"
    assert metadata["after"]["payment_id"] == applied["effect"]["payment_id"]
    # Antes/depois por referência: valores e texto livre ficam em ai_operations.effect.
    flat = str(metadata)
    assert "123.45" not in flat and "anotação sintética" not in flat

    view = operations.get_operation_view(pool, ctx, applied["operation_id"])
    assert view["status"] == "applied" and view["grant_id"] == grant_id and view["actor_user_id"] == world.user_id
    assert "R$ 123,45" in view["summary_pt_br"]
    assert view["scope"]["financial_space"]["id"] == world.personal_space_id
