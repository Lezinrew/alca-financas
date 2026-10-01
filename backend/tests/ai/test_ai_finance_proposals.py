"""finance.prepare_change: propostas, aprovação específica e isolamento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from services.ai.errors import AiError
from services.ai.finance import operations, proposals

from .support import finance_helpers as fh
from .support import seed


MANUAL = [{"kind": "manual", "ref": "pedido-do-titular"}]
# Data de pagamento no passado: data futura vira ambiguidade ("future_date"),
# e os testes não podem depender do relógio da máquina.
PAID_ON = "2026-03-05"


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
    return proposals.prepare_payable_payment(
        pool, ctx, payable_id=payable_id, amount=amount, paid_on=paid_on,
        evidence=MANUAL if evidence is None else evidence, **kwargs
    )


def _codes(view):
    return sorted(item["code"] for item in view["ambiguities"])


def _blocking(view):
    """Códigos das ambiguidades IMPEDITIVAS (as que deixam a proposta em draft)."""
    return sorted(item["code"] for item in view["ambiguities"] if item["blocking"])


def _ambiguity(view, code):
    return [item for item in view["ambiguities"] if item["code"] == code][0]


# Toda baixa sem lançamento de extrato conferido leva este aviso (não impeditivo).
UNBACKED = "no_statement_backing"


# ---------------------------------------------------------------------------
# Baixa: efeito esperado, chave e hash.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_partial_payment_proposal_shows_before_and_after_from_database(pool, world, settings):
    ctx = world.context(pool)
    payable = _payable(pool, world, "300.00")
    fh.add_payment(pool, world.tenant_id, payable, "50.25")

    view = _prepare(pool, ctx, payable, "100.50", settings=settings)

    assert view["kind"] == "payable_payment" and view["status"] == "ready" and view["version"] == 1
    # Sem lançamento de extrato conferido, a baixa nasce exigindo revisão.
    assert view["requires_review"] is True and _codes(view) == [UNBACKED] and _blocking(view) == []
    effect = view["effect"]
    assert effect["state_after"] == "registrado_pago"
    assert effect["before"] == {"paid": "50.25", "remaining": "249.75", "status": "partial"}
    assert effect["after"] == {"paid": "150.75", "remaining": "149.25", "status": "partial"}
    assert view["scope"]["financial_space"] == {
        "id": world.personal_space_id, "name": "Pessoal", "kind": "personal"
    }
    assert view["origin"]["source_kind"] == "manual" and view["origin"]["label"] == "Aluguel"
    assert view["origin"]["period"] == {"start": PAID_ON, "end": PAID_ON}
    # A evidência descrita no pedido fica guardada como anotação NÃO conferida.
    assert view["evidence"] == [dict(MANUAL[0], verified=False)] and view["operation_id"] is None
    # O resumo é montado com os números do banco, em pt-BR.
    assert "R$ 100,50" in view["summary_pt_br"] and "R$ 149,25" in view["summary_pt_br"]
    assert "registrado pago" in view["summary_pt_br"]
    # Proposta não altera dado financeiro.
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 1
    assert fh.effect_counts(pool, world.tenant_id)["operations"] == 0
    # Vence em 24 h (padrão do contrato).
    seconds = fh.fetch_value(
        pool, world.tenant_id,
        "SELECT extract(epoch FROM expires_at - created_at) FROM ai_proposals WHERE id = %s", (view["proposal_id"],),
    )
    assert int(seconds) == settings.proposal_ttl_hours * 3600 == 86400
    assert proposals.get_proposal_view(pool, ctx, view["proposal_id"]) == view


@pytest.mark.integration
def test_full_payment_is_only_paid_when_amount_covers_the_balance(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world, "300.00")
    exact = _prepare(pool, ctx, payable, "300.00")
    assert exact["effect"]["after"] == {"paid": "300.00", "remaining": "0.00", "status": "paid"}
    one_cent_short = _prepare(pool, ctx, payable, "299.99")
    assert one_cent_short["effect"]["after"] == {"paid": "299.99", "remaining": "0.01", "status": "partial"}


@pytest.mark.integration
def test_same_action_returns_same_live_proposal_and_keys_come_from_backend(pool, world):
    ctx = world.context(pool)
    tenant = world.tenant_id
    payable = _payable(pool, world)
    first = _prepare(pool, ctx, payable)
    again = _prepare(pool, ctx, payable)
    assert again["proposal_id"] == first["proposal_id"] and again["payload_hash"] == first["payload_hash"]
    # O rótulo e a referência livre da evidência são texto do modelo: não mudam
    # a ação. Descrever a mesma baixa de outro jeito devolve a MESMA proposta.
    for evidence in (
        [{"kind": "manual", "ref": "a"}, {"kind": "email", "ref": "b"}],
        [{"kind": "email", "ref": "b"}, {"kind": "manual", "ref": "a"}],
        [{"kind": "receipt", "ref": "whatsapp:foto-7"}],
        [],
    ):
        relabelled = _prepare(pool, ctx, payable, evidence=evidence)
        assert relabelled["proposal_id"] == first["proposal_id"], evidence
        assert relabelled["payload_hash"] == first["payload_hash"]
    assert seed.count_rows(pool, tenant, "ai_proposals") == 1

    # Valor, data, anexo conferido ou transação diferentes são OUTRA ação.
    artifact, sha256 = fh.insert_artifact(pool, world, "personal", filename="comprovante.pdf", detected_kind="pdf")
    transaction = fh.ofx_transaction(pool, world, "100.00")
    others = [
        _prepare(pool, ctx, payable, "100.01"),
        _prepare(pool, ctx, payable, paid_on="2026-03-06"),
        _prepare(pool, ctx, payable, evidence=[{"kind": "receipt", "ref": "artifact:%s" % artifact}]),
        _prepare(pool, ctx, payable, transaction_id=transaction),
    ]
    ids = {first["proposal_id"]} | {view["proposal_id"] for view in others}
    assert len(ids) == 5
    assert seed.count_rows(pool, tenant, "ai_proposals") == 5
    # As duas últimas repetem conta, valor e data da primeira: possível duplicidade.
    assert [("possible_duplicate" in _codes(view)) for view in others] == [False, False, True, True]

    row = fh.fetch_all(pool, tenant, "SELECT * FROM ai_proposals WHERE id = %s", (first["proposal_id"],))[0]
    assert row["payload_hash"] == proposals.payload_hash_for(row["payload"])
    assert first["planned_operation_id"] == proposals.operation_id_for(tenant, row["operation_key"])
    assert len(row["operation_key"]) == 64 and row["operation_key"] != row["payload_hash"]
    assert row["target_versions"]["payable"]["paid"] == "0.00"
    assert row["target_versions"]["payable"]["payment_count"] == 0
    # A chave sai só do que o backend conferiu: escopo, origem, tipo e identidade.
    assert row["operation_key"] == proposals.operation_key_for(
        ctx, kind="payable_payment", source=["manual"],
        identity={"payable_id": payable, "amount": "100.00", "paid_on": PAID_ON, "transaction_id": None,
                  "artifacts": []},
    )
    # No payload (o que o titular aprova) só entra evidência conferida.
    assert row["payload"]["evidence"] == [] and row["evidence"] == [dict(MANUAL[0], verified=False)]
    with_artifact = fh.fetch_all(pool, tenant, "SELECT payload, evidence FROM ai_proposals WHERE id = %s",
                                 (others[2]["proposal_id"],))[0]
    expected = {"kind": "receipt", "ref": "artifact:%s" % artifact, "sha256": sha256}
    assert with_artifact["payload"]["evidence"] == [expected]
    assert with_artifact["evidence"] == [dict(expected, verified=True)]


@pytest.mark.integration
def test_operation_key_is_scoped_to_tenant_and_space(pool, world, other_world):
    identity = {"payable_id": seed.new_id(), "amount": "1.00"}
    keys = {
        proposals.operation_key_for(context, kind="payable_payment", source=["manual"], identity=identity)
        for context in (world.context(pool), world.context(pool, "business"), other_world.context(pool))
    }
    assert len(keys) == 3
    ctx = world.context(pool)
    base = proposals.operation_key_for(ctx, kind="payable_payment", source=["manual"], identity=identity)
    assert base != proposals.operation_key_for(ctx, kind="payable_payment", source=["email"], identity=identity)
    assert base != proposals.operation_key_for(ctx, kind="statement_import", source=["manual"], identity=identity)
    assert base == proposals.operation_key_for(ctx, kind="payable_payment", source=["manual"], identity=dict(identity))


@pytest.mark.integration
def test_concurrent_prepare_of_same_action_creates_one_proposal(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world)
    # Cada chamada descreve a evidência de um jeito; continua sendo uma ação só.
    labels = [[], MANUAL, [{"kind": "email", "ref": "mensagem-1"}], [{"kind": "receipt", "ref": "foto-1"}]]
    results = fh.run_concurrently([
        (lambda evidence=labels[index % len(labels)]: _prepare(pool, ctx, payable, evidence=evidence))
        for index in range(6)
    ])
    assert [status for status, _ in results] == ["ok"] * 6, results
    assert len({view["proposal_id"] for _, view in results}) == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 1
    assert seed.count_rows(pool, world.tenant_id, "audit_events", "event_type = 'ai.proposal.created'") == 1


@pytest.mark.integration
def test_same_key_with_different_payload_is_conflict(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world)
    first = _prepare(pool, ctx, payable, notes="primeira anotação")
    error = _error(_prepare, pool, ctx, payable, notes="outra anotação")
    assert error.code == "conflict" and error.http_status == 409
    assert _error(_prepare, pool, ctx, payable, notes="primeira anotação", payment_method="pix").code == "conflict"
    # Depois de rejeitar a anterior, a variação pode ser proposta.
    proposals.reject(pool, ctx, first["proposal_id"], "anotação errada")
    second = _prepare(pool, ctx, payable, notes="outra anotação")
    assert second["proposal_id"] != first["proposal_id"] and second["status"] == "ready"


# ---------------------------------------------------------------------------
# Ambiguidades: nunca inferir quitação.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_overpayment_requires_review_and_never_settles(pool, world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    payable = _payable(pool, world, "300.00")
    fh.add_payment(pool, world.tenant_id, payable, "250.00")

    view = _prepare(pool, ctx, payable, "50.01")
    assert view["status"] == "draft" and view["requires_review"] is True
    assert _blocking(view) == ["overpayment"]
    message = _ambiguity(view, "overpayment")["message"]
    assert "R$ 50,01" in message and "R$ 50,00" in message
    # O "depois" não é calculado: nada de presumir quitação.
    assert view["effect"]["after"] is None
    assert view["effect"]["before"] == {"paid": "250.00", "remaining": "50.00", "status": "partial"}
    # Nem com lançamento de extrato conferido o pagamento maior passa.
    backed = _prepare(pool, ctx, payable, "50.01", "2026-03-06",
                      transaction_id=fh.ofx_transaction(pool, world, "50.01"), evidence=[])
    assert backed["status"] == "draft" and _codes(backed) == ["overpayment"]

    for draft in (view, backed):
        assert _error(proposals.approve, pool, ctx, draft["proposal_id"], payload_hash=draft["payload_hash"],
                      version=1).code == "ambiguous_evidence"
        assert _error(operations.apply_proposal, pool, ctx, draft["proposal_id"], expected_version=1,
                      settings=settings).code == "ambiguous_evidence"
    counts = fh.effect_counts(pool, world.tenant_id)
    assert counts["payments"] == 1 and counts["operations"] == 0 and counts["outbox"] == 0
    # A conta segue parcial.
    assert fh.fetch_value(
        pool, world.tenant_id,
        "SELECT sum(amount) FROM payable_payments WHERE payable_id = %s AND reversed_at IS NULL", (payable,),
    ) == Decimal("250.00")


@pytest.mark.integration
def test_reversed_payments_do_not_count_in_the_balance_of_a_new_proposal(pool, world):
    """Saldo da prévia = previsto − pagamentos VÁLIDOS. Pagamento revertido não conta."""
    ctx = world.context(pool)
    payable = _payable(pool, world, "300.00")
    fh.add_payment(pool, world.tenant_id, payable, "100.00", reversed_reason="lançado por engano")
    fh.add_payment(pool, world.tenant_id, payable, "50.00")

    view = _prepare(pool, ctx, payable, "250.00")
    # Com o revertido somado, o saldo seria 150 e os 250 virariam "pagamento maior".
    assert view["status"] == "ready" and _blocking(view) == []
    assert view["effect"]["before"] == {"paid": "50.00", "remaining": "250.00", "status": "partial"}
    assert view["effect"]["after"] == {"paid": "300.00", "remaining": "0.00", "status": "paid"}
    versions = fh.fetch_value(pool, world.tenant_id, "SELECT target_versions FROM ai_proposals WHERE id = %s",
                              (view["proposal_id"],))
    assert versions["payable"]["paid"] == "50.00" and versions["payable"]["payment_count"] == 1
    assert _blocking(_prepare(pool, ctx, payable, "250.01")) == ["overpayment"]


@pytest.mark.integration
def test_missing_amount_or_date_and_canceled_payable_become_blocking_ambiguities(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world)
    no_amount = _prepare(pool, ctx, payable, None)
    assert no_amount["status"] == "draft" and _blocking(no_amount) == ["missing_amount"]
    assert no_amount["effect"]["after"] is None
    no_date = _prepare(pool, ctx, payable, "10.00", None)
    assert no_date["status"] == "draft" and _blocking(no_date) == ["missing_date"]
    neither = _prepare(pool, ctx, payable, "", "")
    assert _blocking(neither) == ["missing_amount", "missing_date"]
    assert all(view["requires_review"] for view in (no_amount, no_date, neither))

    canceled = _payable(pool, world, title="Cancelada")
    fh.cancel_payable(pool, world.tenant_id, canceled)
    view = _prepare(pool, ctx, canceled)
    assert view["status"] == "draft" and _blocking(view) == ["payable_canceled"] and view["effect"]["after"] is None


@pytest.mark.integration
def test_evidence_without_statement_backing_always_requires_review(pool, world):
    """Sem lançamento de extrato conferido, toda baixa nasce exigindo revisão.

    Cada caso usa um valor diferente: com o mesmo valor e a mesma data seriam a
    mesma ação (o texto da evidência não entra na identidade).
    """
    ctx = world.context(pool)
    payable = _payable(pool, world, "1000.00")
    receipt = _prepare(pool, ctx, payable, "100.00", evidence=[{"kind": "receipt", "ref": "whatsapp:mensagem-123"}])
    assert receipt["status"] == "ready" and receipt["requires_review"] is True
    assert _codes(receipt) == ["receipt_only"] and receipt["ambiguities"][0]["blocking"] is False
    assert receipt["effect"]["state_after"] == "registrado_pago"

    none = _prepare(pool, ctx, payable, "101.00", evidence=[])
    assert none["requires_review"] is True and _codes(none) == ["missing_evidence"]

    # Comprovante + uma referência de e-mail que o backend não tem como conferir:
    # o lastro continua sendo só o comprovante, e o "e-mail" não vira origem.
    mixed = _prepare(pool, ctx, payable, "102.00",
                     evidence=[{"kind": "receipt", "ref": "r1"}, {"kind": "email", "ref": "e1"}])
    assert mixed["requires_review"] is True and _codes(mixed) == ["receipt_only"]
    assert mixed["origin"]["source_kinds"] == ["manual"]
    assert [item["verified"] for item in mixed["evidence"]] == [False, False]

    manual = _prepare(pool, ctx, payable, "103.00")
    assert manual["status"] == "ready" and manual["requires_review"] is True and _codes(manual) == [UNBACKED]
    email = _prepare(pool, ctx, payable, "104.00", evidence=[{"kind": "email", "ref": "mensagem-1"}])
    assert _codes(email) == [UNBACKED] and email["origin"]["source_kinds"] == ["manual"]

    future = _prepare(pool, ctx, payable, "105.00", paid_on=fh.tomorrow_plus(5).isoformat())
    assert _codes(future) == ["future_date", UNBACKED] and future["status"] == "ready"
    assert future["requires_review"] is True


@pytest.mark.integration
def test_whatsapp_file_is_a_receipt_whatever_its_format(pool, world):
    """O tipo e a origem da evidência saem do anexo guardado, não do rótulo declarado."""
    ctx = world.context(pool)
    payable = _payable(pool, world)
    forwarded, _ = fh.insert_artifact(pool, world, "personal", filename="extrato-encaminhado.ofx",
                                      detected_kind="ofx", source_kind="whatsapp")
    uploaded, _ = fh.insert_artifact(pool, world, "personal", filename="extrato-enviado.ofx",
                                     detected_kind="ofx", source_kind="upload")
    # Tudo que chega pelo WhatsApp é comprovante para conferência, até um arquivo de extrato.
    via_whatsapp = _prepare(pool, ctx, payable, "10.00", evidence=[{"kind": "email", "ref": "artifact:%s" % forwarded}])
    assert _codes(via_whatsapp) == ["receipt_only"] and via_whatsapp["evidence"][0]["kind"] == "receipt"
    assert via_whatsapp["origin"]["source_kinds"] == ["whatsapp"]
    # O mesmo tipo de arquivo enviado pelo app não é comprovante, mesmo rotulado como tal.
    # E, sem uma transação do extrato conferida, continua exigindo revisão.
    via_upload = _prepare(pool, ctx, payable, "11.00", evidence=[{"kind": "receipt", "ref": "artifact:%s" % uploaded}])
    assert _codes(via_upload) == [UNBACKED] and via_upload["evidence"][0]["kind"] == "manual"
    assert via_upload["origin"]["source_kinds"] == ["upload"] and via_upload["requires_review"] is True
    assert all(item["verified"] for item in via_whatsapp["evidence"] + via_upload["evidence"])


@pytest.mark.integration
def test_invalid_money_dates_and_evidence_are_rejected(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world)
    for amount in (100.5, "10,50", "1.005", "-5.00", "0", "abc", True):
        assert _error(_prepare, pool, ctx, payable, amount).code == "invalid_request", amount
    assert _error(_prepare, pool, ctx, payable, paid_on="05/10/2026").code == "invalid_request"
    assert _error(_prepare, pool, ctx, "não-é-uuid").code == "invalid_request"
    for evidence in (
        [{"kind": "screenshot", "ref": "x"}],
        [{"kind": "receipt", "ref": "texto com espaços e instruções"}],
        [{"kind": "receipt"}],
        "receipt",
        [{"kind": "manual", "ref": "r%d" % index} for index in range(11)],
        # Evidência de extrato sem a transação validada: o modelo não declara lastro.
        [{"kind": "ofx_transaction", "ref": "transaction:%s" % seed.new_id()}],
        # O prefixo "transaction:" é reservado, venha com o rótulo que vier.
        [{"kind": "manual", "ref": "transaction:%s" % seed.new_id()}],
        [{"kind": "receipt", "ref": "artifact:nao-e-uuid"}],
    ):
        assert _error(_prepare, pool, ctx, payable, evidence=evidence).code == "invalid_request", evidence
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 0


@pytest.mark.integration
def test_control_characters_are_invalid_request_or_cleaned_never_a_database_error(pool, world, settings):
    """NUL e companhia não chegam ao banco.

    Antes o INSERT falhava (o PostgreSQL recusa NUL em texto e jsonb) e o erro
    saía como 500 "retentável": o executor repetiria um pedido que nunca passa.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    tenant, account = world.tenant_id, world.personal_account_id
    payable = _payable(pool, world)
    nul, surrogate = chr(0), chr(0xD800)

    # Texto vindo dos argumentos: pedido inválido (400, não retentável).
    for kwargs in (
        {"payment_method": "pix" + nul},
        {"notes": "pago" + nul + " no app"},
        {"notes": "pago " + surrogate},
        {"payment_method": "pix" + chr(7)},
    ):
        error = _error(_prepare, pool, ctx, payable, **kwargs)
        assert (error.code, error.http_status, error.retryable) == ("invalid_request", 400, False), kwargs
    view = _prepare(pool, ctx, payable)
    assert _error(proposals.reject, pool, ctx, view["proposal_id"], "motivo" + nul).code == "invalid_request"
    assert _error(proposals.prepare_reversal, pool, ctx, seed.new_id(), "motivo" + nul).code == "invalid_request"
    # Tabulação e quebra de linha viram espaço, como sempre.
    assert proposals.reject(pool, ctx, view["proposal_id"], "valor\terrado\n mesmo")["status"] == "rejected"
    assert fh.fetch_value(pool, tenant, "SELECT rejected_reason FROM ai_proposals WHERE id = %s",
                          (view["proposal_id"],)) == "valor errado mesmo"
    assert seed.count_rows(pool, tenant, "ai_proposals") == 1

    # Extrato: campo de identidade com NUL não é "limpo" (mudaria a identidade): evidência ambígua.
    for bad in (
        fh.preview_item("5.00", fitid="FIT" + nul + "1"),
        fh.preview_item("5.00", dedup_key="chave" + nul),
        fh.preview_item("5.00", dedup_key="chave" + surrogate),
    ):
        error = _error(proposals.prepare_statement_import, pool, ctx, source_kind="upload",
                       preview=fh.make_preview(account, [bad]))
        assert (error.code, error.retryable) == ("ambiguous_evidence", False)
    damaged_duplicate = fh.make_preview(account, [fh.preview_item("5.00")],
                                        duplicates=[fh.preview_item("6.00", dedup_key="dup" + nul)])
    assert _error(proposals.prepare_statement_import, pool, ctx, source_kind="upload",
                  preview=damaged_duplicate).code == "ambiguous_evidence"

    # Texto cosmético do arquivo (descrição, banco, nome, período, avisos) é limpo e a importação segue.
    item = fh.preview_item("5.00", description="mercado" + nul + "sintético" + chr(1), occurred_on="2026-03-07")
    preview = fh.make_preview(
        account, [item], filename="extra" + nul + "to.ofx", institution="Banco" + nul + " Fictício",
        ambiguities=[{"code": "aviso" + nul, "message": "confira" + nul + " o saldo", "item": None}, "lixo"],
    )
    preview.period_start, preview.period_end = "2026-03-01" + nul, "não é data"
    imported = proposals.prepare_statement_import(pool, ctx, preview=preview, source_kind="upload")
    assert imported["origin"]["label"] == "extrato.ofx"
    assert imported["origin"]["period"] == {"start": "2026-03-07", "end": "2026-03-07"}
    assert imported["effect"]["target"]["institution"] == "Banco Fictício"
    assert [(entry["code"], entry["message"]) for entry in imported["ambiguities"]] == [("aviso", "confira o saldo")]
    proposals.approve(pool, ctx, imported["proposal_id"], payload_hash=imported["payload_hash"], version=1)
    applied = operations.apply_proposal(pool, ctx, imported["proposal_id"], expected_version=1, settings=settings)
    assert applied["effect"]["items_new"] == 1
    stored = fh.fetch_all(pool, tenant, "SELECT description, source_file FROM transactions")[0]
    assert stored == {"description": "mercado sintético", "source_file": "extrato.ofx"}


# ---------------------------------------------------------------------------
# registrado_pago x conciliado.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_only_canonical_unlinked_expense_reconciles(pool, world):
    ctx = world.context(pool)
    tenant, account, category = world.tenant_id, world.personal_account_id, world.expense_category_id
    payable = _payable(pool, world, "300.00")

    def transaction(**kwargs):
        defaults = {"description": "Pagamento aluguel", "amount": "300.00", "occurred_on": date(2026, 10, 5)}
        defaults.update(kwargs)
        return seed.create_transaction(pool, tenant, account, category, **defaults)

    ofx = transaction()
    view = _prepare(pool, ctx, payable, "300.00", transaction_id=ofx)
    # Lançamento canônico do extrato, conferido no banco: é o que dispensa revisão.
    assert view["status"] == "ready" and view["requires_review"] is False and view["ambiguities"] == []
    assert view["effect"]["state_after"] == "conciliado"
    assert {"kind": "ofx_transaction", "ref": "transaction:%s" % ofx, "verified": True} in view["evidence"]
    assert [account_view["id"] for account_view in view["scope"]["accounts"]] == [account]
    assert "conciliado no extrato" in view["summary_pt_br"]

    # Mesma baixa sem transação é OUTRO estado e outra ação (e exige revisão).
    plain = _prepare(pool, ctx, payable, "300.00")
    assert plain["effect"]["state_after"] == "registrado_pago" and plain["proposal_id"] != view["proposal_id"]
    assert plain["scope"]["accounts"] == [] and plain["requires_review"] is True

    # Comprovante + transação de extrato validada: o lastro é o extrato.
    second_payable = _payable(pool, world, "300.00", title="Internet")
    with_receipt = _prepare(pool, ctx, second_payable, "300.00", transaction_id=transaction(),
                            evidence=[{"kind": "receipt", "ref": "comprovante-1"}])
    assert with_receipt["requires_review"] is False and with_receipt["effect"]["state_after"] == "conciliado"
    # O modelo pode repetir a referência da própria transação; ela não é contada duas vezes.
    third_payable = _payable(pool, world, "300.00", title="Luz")
    declared_tx = transaction()
    declared = _prepare(pool, ctx, third_payable, "300.00", transaction_id=declared_tx,
                        evidence=[{"kind": "ofx_transaction", "ref": "transaction:%s" % declared_tx}])
    assert declared["evidence"] == [{"kind": "ofx_transaction", "ref": "transaction:%s" % declared_tx,
                                     "verified": True}]

    not_canonical = [
        transaction(source_file="planilha.csv", entry_source="csv"),
        transaction(source_file=None, entry_source="manual"),
        transaction(source_file="legacy:extrato.ofx:excluded"),
        transaction(status="pending"),
        seed.create_transaction(pool, tenant, account, world.income_category_id, description="Salário",
                                amount="300.00", occurred_on=date(2026, 10, 5), tx_type="income"),
    ]
    for index, transaction_id in enumerate(not_canonical):
        draft = _prepare(pool, ctx, payable, "300.00", "2026-03-%02d" % (11 + index), transaction_id=transaction_id,
                         evidence=[{"kind": "ofx_transaction", "ref": "transaction:%s" % transaction_id}])
        assert draft["status"] == "draft" and _blocking(draft) == ["uncertain_link"], index
        assert draft["effect"]["state_after"] == "registrado_pago"
        # Nem declarada pelo modelo a transação inelegível vira evidência de extrato.
        assert not [item for item in draft["evidence"] if item["kind"] == "ofx_transaction"]

    # Valor do pagamento diferente do valor da transação: revisão, sem bloquear.
    mismatch = _prepare(pool, ctx, payable, "120.00", transaction_id=ofx)
    assert mismatch["status"] == "ready" and _codes(mismatch) == ["transaction_amount_mismatch"]

    # Transação já vinculada a um pagamento ativo não concilia outro.
    other_payable = _payable(pool, world, "300.00", title="Condomínio")
    fh.execute(
        pool, tenant,
        "INSERT INTO payable_payments (tenant_id, payable_id, transaction_id, amount, paid_at) "
        "VALUES (%s, %s, %s, 300.00, now())",
        (tenant, other_payable, ofx),
    )
    linked = _prepare(pool, ctx, payable, "300.00", "2026-03-20", transaction_id=ofx)
    assert linked["status"] == "draft" and _blocking(linked) == ["uncertain_link"]


# ---------------------------------------------------------------------------
# AC-01: isolamento.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_targets_outside_scope_are_not_found(pool, world, other_world):
    ctx = world.context(pool)
    tenant = world.tenant_id
    own = _payable(pool, world)
    business_payable = _payable(pool, world, space="business")
    loose_payable = seed.create_payable(pool, tenant, None, title="Sem vínculo", amount_expected="10.00",
                                        competency_month=fh.OCT)
    foreign_payable = _payable(pool, other_world)
    for payable in (business_payable, loose_payable, foreign_payable, seed.new_id()):
        assert _error(_prepare, pool, ctx, payable).code == "not_found"

    business_tx = seed.create_transaction(pool, tenant, world.business_account_id, world.expense_category_id,
                                          description="Do negócio", amount="100.00", occurred_on=date(2026, 10, 5))
    foreign_tx = seed.create_transaction(pool, other_world.tenant_id, other_world.personal_account_id,
                                         other_world.expense_category_id, description="Outro tenant",
                                         amount="100.00", occurred_on=date(2026, 10, 5))
    for transaction_id in (business_tx, foreign_tx, seed.new_id()):
        assert _error(_prepare, pool, ctx, own, transaction_id=transaction_id).code == "not_found"

    # Anexo de outro espaço não serve de evidência.
    business_artifact, _ = fh.insert_artifact(pool, world, "business", filename="comprovante.pdf",
                                              detected_kind="pdf")
    foreign_artifact, _ = fh.insert_artifact(pool, other_world, "personal", filename="comprovante.pdf",
                                             detected_kind="pdf")
    for artifact in (business_artifact, foreign_artifact):
        evidence = [{"kind": "receipt", "ref": "artifact:%s" % artifact}]
        assert _error(_prepare, pool, ctx, own, evidence=evidence).code == "not_found"
    own_artifact, _ = fh.insert_artifact(pool, world, "personal", filename="comprovante.pdf", detected_kind="pdf",
                                         source_kind="whatsapp")
    view = _prepare(pool, ctx, own, evidence=[{"kind": "receipt", "ref": "artifact:%s" % own_artifact}])
    assert view["origin"]["source_kind"] == "whatsapp" and view["requires_review"] is True
    assert seed.count_rows(pool, tenant, "ai_proposals") == 1


@pytest.mark.integration
def test_proposals_are_invisible_from_other_space_and_tenant(pool, admin_pool, world, other_world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world, "personal")
    fh.delegated_unlimited(pool, world, "business")
    fh.delegated_unlimited(pool, other_world, "personal")
    view = _prepare(pool, ctx, _payable(pool, world))
    proposal_id, payload_hash = view["proposal_id"], view["payload_hash"]

    intruders = [world.context(pool, "business"), other_world.context(pool)]
    # Com o pool administrativo a RLS é ignorada: aí só os filtros do serviço seguram.
    for database_pool in (pool, admin_pool):
        for intruder in intruders:
            assert _error(proposals.get_proposal_view, database_pool, intruder, proposal_id).code == "not_found"
            assert _error(proposals.approve, database_pool, intruder, proposal_id, payload_hash=payload_hash,
                          version=1).code == "not_found"
            assert _error(proposals.reject, database_pool, intruder, proposal_id, "tentativa").code == "not_found"
            assert _error(operations.apply_proposal, database_pool, intruder, proposal_id, expected_version=1,
                          settings=settings).code == "not_found"
            assert _error(operations.operation_status, database_pool, intruder,
                          view["planned_operation_id"]).code == "operation_unknown"
    assert proposals.get_proposal_view(pool, ctx, proposal_id)["status"] == "ready"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0
    # expire_due de um tenant não toca nas propostas de outro. Com o pool
    # administrativo (RLS ignorada) só o filtro por tenant do próprio UPDATE segura.
    other_ctx = other_world.context(pool)
    other_view = _prepare(pool, other_ctx, _payable(pool, other_world))
    fh.expire_proposal(pool, world.tenant_id, proposal_id)
    fh.expire_proposal(pool, other_world.tenant_id, other_view["proposal_id"])

    def status_of(tenant_id, wanted):
        return fh.fetch_value(admin_pool, tenant_id, "SELECT status FROM ai_proposals WHERE id = %s", (wanted,))

    assert proposals.expire_due(admin_pool, other_world.tenant_id) == 1
    assert status_of(other_world.tenant_id, other_view["proposal_id"]) == "expired"
    assert status_of(world.tenant_id, proposal_id) == "ready"
    for database_pool in (pool, admin_pool):
        assert proposals.expire_due(database_pool, other_world.tenant_id) == 0
        assert status_of(world.tenant_id, proposal_id) == "ready"
    # A auditoria da expiração fica no tenant dono da proposta.
    audits = fh.fetch_all(admin_pool, world.tenant_id,
                          "SELECT tenant_id FROM audit_events WHERE event_type = 'ai.proposal.expired'")
    assert [str(row["tenant_id"]) for row in audits] == [other_world.tenant_id]
    assert proposals.expire_due(admin_pool, world.tenant_id) == 1
    assert status_of(world.tenant_id, proposal_id) == "expired"


# ---------------------------------------------------------------------------
# Aprovação específica, rejeição, expiração e alvo alterado.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_specific_approval_binds_hash_and_version(pool, world):
    ctx = world.context(pool)
    fh.grant(pool, world, mode="assisted")
    view = _prepare(pool, ctx, _payable(pool, world))
    proposal_id, payload_hash = view["proposal_id"], view["payload_hash"]

    assert _error(proposals.approve, pool, ctx, proposal_id, payload_hash="0" * 64, version=1).code == "conflict"
    assert _error(proposals.approve, pool, ctx, proposal_id, payload_hash=payload_hash,
                  version=2).code == "stale_proposal"
    assert _error(proposals.approve, pool, ctx, proposal_id, payload_hash=payload_hash,
                  version="x").code == "invalid_request"
    assert proposals.get_proposal_view(pool, ctx, proposal_id)["status"] == "ready"

    approved = proposals.approve(pool, ctx, proposal_id, payload_hash=payload_hash, version=1)
    assert approved["status"] == "approved" and approved["payload_hash"] == payload_hash
    row = fh.fetch_all(pool, world.tenant_id, "SELECT * FROM ai_proposals WHERE id = %s", (proposal_id,))[0]
    assert row["approval_kind"] == "specific" and str(row["approved_by_user_id"]) == world.user_id
    assert row["approved_hash"] == payload_hash and row["approved_at"] is not None
    # Clique repetido devolve o mesmo estado, sem nova auditoria.
    assert proposals.approve(pool, ctx, proposal_id, payload_hash=payload_hash, version=1)["status"] == "approved"
    assert seed.count_rows(pool, world.tenant_id, "audit_events", "event_type = 'ai.proposal.approved'") == 1
    # Aprovar não aplica.
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0


@pytest.mark.integration
def test_observe_or_no_grant_cannot_approve(pool, world):
    ctx = world.context(pool)
    view = _prepare(pool, ctx, _payable(pool, world))
    arguments = {"payload_hash": view["payload_hash"], "version": 1}
    assert _error(proposals.approve, pool, ctx, view["proposal_id"], **arguments).code == "capability_denied"
    fh.grant(pool, world, mode="observe")
    assert _error(proposals.approve, pool, ctx, view["proposal_id"], **arguments).code == "capability_denied"
    assert proposals.get_proposal_view(pool, ctx, view["proposal_id"])["status"] == "ready"


@pytest.mark.integration
def test_reject_and_expire(pool, world):
    ctx = world.context(pool)
    fh.grant(pool, world, mode="assisted")
    tenant = world.tenant_id
    payable = _payable(pool, world)
    first = _prepare(pool, ctx, payable)
    assert _error(proposals.reject, pool, ctx, first["proposal_id"], "  ").code == "invalid_request"
    rejected = proposals.reject(pool, ctx, first["proposal_id"], "valor errado")
    assert rejected["status"] == "rejected"
    assert proposals.reject(pool, ctx, first["proposal_id"], "de novo")["status"] == "rejected"
    assert _error(proposals.approve, pool, ctx, first["proposal_id"], payload_hash=first["payload_hash"],
                  version=1).code == "conflict"

    # A mesma ação pode ser proposta de novo depois da rejeição.
    second = _prepare(pool, ctx, payable)
    assert second["proposal_id"] != first["proposal_id"] and second["status"] == "ready"

    # Vencida: a visão já mostra "expired"; aprovar marca e recusa.
    fh.expire_proposal(pool, tenant, second["proposal_id"])
    assert proposals.get_proposal_view(pool, ctx, second["proposal_id"])["status"] == "expired"
    assert _error(proposals.approve, pool, ctx, second["proposal_id"], payload_hash=second["payload_hash"],
                  version=1).code == "stale_proposal"
    assert fh.fetch_value(pool, tenant, "SELECT status FROM ai_proposals WHERE id = %s",
                          (second["proposal_id"],)) == "expired"

    # Nova prévia da mesma ação substitui a vencida; expire_due varre as demais.
    third = _prepare(pool, ctx, payable)
    other = _prepare(pool, ctx, payable, "55.00")
    fh.expire_proposal(pool, tenant, third["proposal_id"])
    assert proposals.expire_due(pool, tenant) == 1
    assert proposals.expire_due(pool, tenant) == 0
    statuses = {
        str(row["id"]): row["status"]
        for row in fh.fetch_all(pool, tenant, "SELECT id, status FROM ai_proposals")
    }
    assert statuses[third["proposal_id"]] == "expired" and statuses[other["proposal_id"]] == "ready"
    fourth = _prepare(pool, ctx, payable)
    assert fourth["proposal_id"] not in (first["proposal_id"], second["proposal_id"], third["proposal_id"])


@pytest.mark.integration
def test_changed_target_makes_previous_proposal_stale_on_new_preview(pool, world):
    ctx = world.context(pool)
    payable = _payable(pool, world, "300.00")
    first = _prepare(pool, ctx, payable, "100.00")
    fh.add_payment(pool, world.tenant_id, payable, "30.00")  # pagamento feito por fora
    second = _prepare(pool, ctx, payable, "100.00")
    assert second["proposal_id"] != first["proposal_id"]
    assert second["effect"]["before"]["paid"] == "30.00" and second["effect"]["after"]["remaining"] == "170.00"
    assert proposals.get_proposal_view(pool, ctx, first["proposal_id"])["status"] == "stale"


# ---------------------------------------------------------------------------
# Importação de extrato.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_statement_import_only_accepts_canonical_ofx_in_allowed_account(pool, world, other_world):
    ctx = world.context(pool)
    account = world.personal_account_id
    items = [fh.preview_item("10.00")]

    def prepare(preview, source_kind="upload"):
        return proposals.prepare_statement_import(pool, ctx, preview=preview, source_kind=source_kind)

    for preview in (
        fh.make_preview(account, items, filename="extrato.csv", file_kind="csv", canonical=False),
        fh.make_preview(account, items, filename="extrato.csv", file_kind="csv", canonical=True),
        fh.make_preview(account, items, canonical=False),
        fh.make_preview(account, items, filename="extrato.pdf"),
        fh.make_preview(account, items, filename="legacy:extrato.ofx:excluded"),
    ):
        assert _error(prepare, preview).code == "invalid_request"
    for foreign_account in (world.business_account_id, other_world.personal_account_id, seed.new_id()):
        assert _error(prepare, fh.make_preview(foreign_account, items)).code == "not_found"
    assert _error(prepare, fh.make_preview(account, items), "sms").code == "invalid_request"
    assert _error(prepare, {"items": []}).code == "invalid_request"
    assert _error(prepare, fh.make_preview(account, [fh.preview_item("abc")])).code == "ambiguous_evidence"
    assert _error(prepare, fh.make_preview(account, [fh.preview_item("1.00", "refund")])).code == "ambiguous_evidence"
    assert _error(prepare, fh.make_preview(account, [fh.preview_item("5.00", "transfer")])).code == "conflict"
    assert seed.count_rows(pool, world.tenant_id, "ai_proposals") == 0


@pytest.mark.integration
def test_statement_import_expected_effect_counts_totals_and_transfers(pool, world):
    ctx = world.context(pool)
    tenant, account = world.tenant_id, world.personal_account_id
    # Um lançamento do extrato já está no sistema (mesmo FITID).
    seed.create_transaction(pool, tenant, account, world.expense_category_id, description="Já importado",
                            amount="40.00", occurred_on=date(2026, 10, 3), fitid="FIT-JA-EXISTE")
    items = [
        fh.preview_item("0.10", occurred_on="2026-10-02"),
        fh.preview_item("0.20", occurred_on="2026-10-04"),
        fh.preview_item("1500.00", "income", occurred_on="2026-10-05"),
        fh.preview_item("40.00", fitid="FIT-JA-EXISTE", occurred_on="2026-10-03"),
        fh.preview_item("250.00", "transfer", occurred_on="2026-10-06"),
        fh.preview_item("50.00", "transfer", occurred_on="2026-10-07"),
        # Repetido dentro do próprio arquivo.
        fh.preview_item("9.99", dedup_key="repetido", fitid="FIT-A", occurred_on="2026-10-08"),
        fh.preview_item("9.99", dedup_key="repetido", fitid="FIT-B", occurred_on="2026-10-08"),
    ]
    preview = fh.make_preview(account, items, filename="C:\\Users\\titular\\extrato-outubro.OFX")
    view = proposals.prepare_statement_import(pool, ctx, preview=preview, source_kind="email")

    assert view["kind"] == "statement_import" and view["status"] == "ready"
    effect = view["effect"]
    assert effect["state_after"] == "importado"
    assert (effect["items_new"], effect["items_duplicate"], effect["items_transfer_skipped"]) == (4, 2, 2)
    assert effect["totals"] == {
        "income": "1500.00", "expense": "10.29", "net": "1489.71", "transfer_skipped": "300.00",
    }
    # Transferência não é aplicada e vira ambiguidade (logo, revisão).
    assert _codes(view) == ["transfer_without_destination"] and view["requires_review"] is True
    assert view["ambiguities"][0]["count"] == 2 and view["ambiguities"][0]["total"] == "300.00"
    assert view["origin"] == {
        "source_kind": "email", "source_kinds": ["email"], "label": "extrato-outubro.OFX",
        "period": {"start": "2026-10-02", "end": "2026-10-08"},
    }
    assert [item["id"] for item in view["scope"]["accounts"]] == [account]
    assert view["evidence"][0]["ref"] == "artifact:%s" % preview.artifact_id
    # Nada foi gravado em transactions.
    assert fh.effect_counts(pool, tenant)["transactions"] == 1

    payload = fh.fetch_value(pool, tenant, "SELECT payload FROM ai_proposals WHERE id = %s", (view["proposal_id"],))
    assert all(item["type"] in ("income", "expense") for item in payload["items"])
    assert payload["filename"] == "extrato-outubro.OFX"  # só o nome, sem o caminho
    # O lançamento que já existe está no realizado: duplicado seguro, sem aviso.
    assert effect["items_duplicate_canceled"] == 0 and effect["items_duplicate_outside_realized"] == 0
    assert payload["known_duplicates"] == []

    # Mesmo arquivo na mesma conta: mesma proposta.
    assert proposals.prepare_statement_import(pool, ctx, preview=preview, source_kind="email")["proposal_id"] == \
        view["proposal_id"]

    # Extrato em que tudo já existe: nada a importar.
    duplicate_only = fh.make_preview(account, [fh.preview_item("40.00", fitid="FIT-JA-EXISTE")])
    assert _error(proposals.prepare_statement_import, pool, ctx, preview=duplicate_only,
                  source_kind="upload").code == "conflict"


@pytest.mark.integration
def test_statement_duplicates_of_rows_outside_the_realized_are_flagged(pool, world):
    """Duplicado só é "seguro de ignorar" se a linha existente está no realizado."""
    ctx = world.context(pool)
    tenant, account = world.tenant_id, world.personal_account_id
    # O que já ocupa as chaves na conta:
    fh.ledger_transaction(pool, world, "10.00", dedup_key="chave-csv", source_file="planilha.csv", entry_source="csv")
    fh.ledger_transaction(pool, world, "20.00", fitid="FIT-PENDENTE", dedup_key="chave-pendente", status="pending")
    fh.ledger_transaction(pool, world, "30.00", fitid="FIT-CANCELADO", dedup_key="chave-cancelada", status="canceled")
    fh.ledger_transaction(pool, world, "40.00", fitid="FIT-REALIZADO", dedup_key="chave-realizada")
    # Chave em linha cancelada e FITID em linha do realizado: basta uma no realizado.
    fh.ledger_transaction(pool, world, "60.00", fitid="FIT-MISTA-C", dedup_key="mista-cancelada", status="canceled")
    fh.ledger_transaction(pool, world, "60.00", fitid="FIT-MISTA-R", dedup_key="mista-realizada")
    items = [
        fh.preview_item("10.00", dedup_key="chave-csv"),                              # só existe como CSV
        fh.preview_item("20.00", fitid="FIT-PENDENTE", dedup_key="chave-nova-1"),     # existe, mas pendente
        fh.preview_item("30.00", fitid="FIT-CANCELADO", dedup_key="chave-cancelada"),  # existe, cancelado
        fh.preview_item("40.00", fitid="FIT-REALIZADO", dedup_key="chave-realizada"),  # já no realizado
        fh.preview_item("60.00", fitid="FIT-MISTA-R", dedup_key="mista-cancelada"),
        fh.preview_item("50.00"),                                                      # novo
    ]
    view = proposals.prepare_statement_import(pool, ctx, preview=fh.make_preview(account, items),
                                              source_kind="upload")
    effect = view["effect"]
    assert (effect["items_new"], effect["items_duplicate"]) == (1, 5)
    assert (effect["items_duplicate_canceled"], effect["items_duplicate_outside_realized"]) == (1, 2)
    assert effect["totals"]["expense"] == "50.00"
    assert view["status"] == "ready" and view["requires_review"] is True
    assert _codes(view) == ["duplicate_of_canceled", "duplicate_outside_realized"]
    canceled, outside = _ambiguity(view, "duplicate_of_canceled"), _ambiguity(view, "duplicate_outside_realized")
    assert (canceled["count"], canceled["total"]) == (1, "30.00")
    assert (outside["count"], outside["total"]) == (2, "30.00")
    assert "CANCELADO" in view["summary_pt_br"] and "outra origem" in view["summary_pt_br"]
    versions = fh.fetch_value(pool, tenant, "SELECT target_versions FROM ai_proposals WHERE id = %s",
                              (view["proposal_id"],))
    assert (versions["ledger_matches"], versions["ledger_unrealized_matches"]) == (5, 3)

    # Duplicado apontado pela prévia com valor ilegível: não derruba a importação
    # (ele não será aplicado); entra no aviso pela identificação, com total 0.00.
    unreadable = fh.preview_item("abc", fitid="FIT-CANCELADO", dedup_key="chave-cancelada")
    tolerant = proposals.prepare_statement_import(
        pool, ctx, source_kind="upload",
        preview=fh.make_preview(account, [fh.preview_item("70.00")], duplicates=[unreadable]),
    )
    warning = _ambiguity(tolerant, "duplicate_of_canceled")
    assert (warning["count"], warning["total"]) == (1, "0.00") and tolerant["effect"]["items_new"] == 1


# ---------------------------------------------------------------------------
# Unidade.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_money_parsing_and_formatting():
    assert proposals.parse_amount("1234.5") == Decimal("1234.50")
    assert proposals.parse_amount(Decimal("0.01")) == Decimal("0.01")
    assert proposals.parse_amount(15) == Decimal("15.00")
    assert proposals.parse_amount(None) is None and proposals.parse_amount("  ") is None
    for bad in (0.1, "1.999", "0", "-1", "NaN", "Infinity", "1e3x"):
        with pytest.raises(AiError):
            proposals.parse_amount(bad)
    assert proposals.format_money("1234567.5") == "R$ 1.234.567,50"
    assert proposals.format_money(Decimal("0.3")) == "R$ 0,30"
    assert proposals.format_money("999.999") == "R$ 1.000,00"
    assert proposals.format_money("12.00", "USD") == "USD 12,00"


@pytest.mark.unit
def test_operation_id_is_deterministic_uuid5():
    first = proposals.operation_id_for("tenant-a", "a" * 64)
    assert first == proposals.operation_id_for("tenant-a", "a" * 64)
    assert first != proposals.operation_id_for("tenant-b", "a" * 64)
    assert first != proposals.operation_id_for("tenant-a", "b" * 64)
    import uuid

    assert uuid.UUID(first).version == 5
