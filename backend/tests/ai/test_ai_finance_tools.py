"""Ferramentas finance.* pelo ToolRegistry: schemas, flags, grants e fluxo completo."""

from __future__ import annotations

import json
import logging
from datetime import date

import pytest

from services.ai import policy
from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.finance import build_finance_tools, read
from services.ai.registry import ToolRegistry
from services.ai.settings import AiSettings

from .support import finance_helpers as fh
from .support import seed


PAID_ON = "2026-03-05"
FINANCE_TOOLS = [
    "finance.apply_change", "finance.operation_status", "finance.prepare_change", "finance.read",
    "finance.reverse_change",
]


class PreviewBox:
    """Provedor de prévia de teste: devolve a prévia montada pelo teste.

    Substitui o componente de importação (fora deste componente) e registra as
    chamadas para conferir o que a ferramenta repassa.
    """

    def __init__(self):
        self.previews = {}
        self.calls = []

    def add(self, preview):
        self.previews[(preview.artifact_id, preview.account_id)] = preview
        return preview

    def __call__(self, ctx, artifact_id, account_id):
        self.calls.append((ctx.financial_space_id, artifact_id, account_id))
        if (artifact_id, account_id) not in self.previews:
            raise AiError("not_found", "Anexo não encontrado.")
        return self.previews[(artifact_id, account_id)]


def _registry(pool, settings, box=None):
    registry = ToolRegistry(settings)
    registry.register_all(build_finance_tools(pool, settings, box or PreviewBox()))
    return registry


def _grants(pool, ctx):
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        return policy.load_active_grants(cursor, ctx)


def _run(registry, pool, ctx, name, args):
    return registry.execute(name, args, ctx, _grants(pool, ctx))


def _error(function, *args, **kwargs) -> AiError:
    with pytest.raises(AiError) as excinfo:
        function(*args, **kwargs)
    return excinfo.value


def _payable(pool, world, amount="300.00", space="personal"):
    return seed.create_payable(
        pool, world.tenant_id, fh.space_id(world, space), title="Aluguel", amount_expected=amount,
        competency_month=fh.OCT, due_date=date(2026, 10, 10),
    )


@pytest.mark.unit
def test_tool_definitions_follow_the_contract():
    settings = AiSettings(enabled=True, write_enabled=True)
    registry = _registry(None, settings)  # montar as ferramentas não toca no banco
    assert registry.names() == FINANCE_TOOLS
    manifest = {entry["name"]: entry for entry in registry.manifest()}
    assert {name: manifest[name]["effect"] for name in FINANCE_TOOLS} == {
        "finance.read": "read",
        "finance.prepare_change": "prepare",
        "finance.apply_change": "write",
        "finance.operation_status": "read",
        "finance.reverse_change": "write",
    }
    assert manifest["finance.apply_change"]["requires_flags"] == ["write_enabled"]
    assert manifest["finance.reverse_change"]["requires_flags"] == ["write_enabled"]
    assert manifest["finance.read"]["requires_flags"] == [] == manifest["finance.prepare_change"]["requires_flags"]
    for entry in manifest.values():
        assert entry["schema"]["additionalProperties"] is False
        # Nenhum schema aceita identificadores de escopo.
        assert not {"tenant_id", "actor_id", "financial_space_id"} & set(entry["schema"]["properties"])
    assert set(manifest["finance.read"]["schema"]["properties"]) == {
        "query", "month", "year", "account_id", "date_from", "date_to", "cursor", "limit",
    }
    assert set(manifest["finance.prepare_change"]["schema"]["properties"]) == {
        "kind", "payable_id", "amount", "paid_on", "transaction_id", "payment_method", "artifact_id",
        "account_id", "evidence",
    }
    # Schemas autocontidos: enums e objetos aninhados aparecem no próprio campo.
    assert manifest["finance.read"]["schema"]["properties"]["query"]["enum"] == list(read.QUERIES)
    assert manifest["finance.prepare_change"]["schema"]["properties"]["kind"]["enum"] == [
        "payable_payment", "statement_import",
    ]
    for entry in manifest.values():
        flat = json.dumps(entry["schema"])
        assert "$ref" not in flat and "$defs" not in flat
    # O que o modelo recebe é o mesmo schema.
    spec = [tool.spec() for tool in build_finance_tools(None, settings, PreviewBox()) if tool.name == "finance.read"][0]
    assert spec["parameters"] == manifest["finance.read"]["schema"]


@pytest.mark.unit
def test_schemas_reject_scope_identifiers_unknown_fields_and_floats():
    registry = _registry(None, AiSettings(enabled=True, write_enabled=True))
    some_id = seed.new_id()
    bad_calls = [
        ("finance.read", {"query": "payables_overview", "tenant_id": some_id}),
        ("finance.read", {"query": "payables_overview", "financial_space_id": some_id}),
        ("finance.read", {"query": "payables_overview", "actor_id": some_id}),
        ("finance.read", {"query": "SELECT * FROM payables"}),
        ("finance.read", {"query": "payables_overview", "sql": "SELECT 1"}),
        ("finance.read", {"query": "payables_list", "limit": 1000}),
        ("finance.read", {"query": "realized_totals", "month": 13, "year": 2026}),
        ("finance.read", {"query": "realized_totals", "account_id": "1 OR 1=1"}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": some_id, "amount": 100.5}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": some_id, "amount": "100,50"}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": some_id, "amount": "10.999"}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": some_id, "financial_space_id": some_id}),
        ("finance.prepare_change", {"kind": "delete_everything"}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": some_id,
                                    "evidence": [{"kind": "receipt", "ref": "r", "tenant_id": some_id}]}),
        ("finance.apply_change", {"proposal_id": some_id}),
        ("finance.apply_change", {"proposal_id": some_id, "expected_version": 1, "force": True}),
        ("finance.apply_change", {"proposal_id": some_id, "expected_version": 1, "actor_id": some_id}),
        ("finance.operation_status", {"operation_id": "abc"}),
        ("finance.reverse_change", {"operation_id": some_id}),
        ("finance.reverse_change", {"operation_id": some_id, "reason": "motivo válido", "tenant_id": some_id}),
    ]
    for name, args in bad_calls:
        error = _error(registry.validate_args, name, args)
        assert error.code == "invalid_request", (name, args)
    valid = registry.validate_args(
        "finance.prepare_change",
        {"kind": "payable_payment", "payable_id": some_id, "amount": "100.50", "paid_on": "2026-03-05",
         "evidence": [{"kind": "receipt", "ref": "artifact:%s" % some_id}]},
    )
    assert valid.amount == "100.50" and valid.paid_on == date(2026, 3, 5)


@pytest.mark.integration
def test_tools_need_a_grant_and_scope_arguments_are_rejected(pool, world, settings):
    ctx = world.context(pool)
    registry = _registry(pool, settings)
    payable = _payable(pool, world)
    # Sem grant: nenhuma ferramenta financeira roda.
    for name, args in (
        ("finance.read", {"query": "payables_overview"}),
        ("finance.prepare_change", {"kind": "payable_payment", "payable_id": payable, "amount": "1.00"}),
        ("finance.apply_change", {"proposal_id": seed.new_id(), "expected_version": 1}),
        ("finance.operation_status", {"operation_id": seed.new_id()}),
        ("finance.reverse_change", {"operation_id": seed.new_id(), "reason": "motivo"}),
    ):
        assert _error(_run, registry, pool, ctx, name, args).code == "capability_denied", name
    assert registry.specs_for(_grants(pool, ctx)) == []

    fh.grant(pool, world, mode="observe")
    # Tentar escolher outro espaço pelos argumentos é rejeitado no schema.
    error = _error(_run, registry, pool, ctx, "finance.read",
                   {"query": "payables_overview", "financial_space_id": world.business_space_id})
    assert error.code == "invalid_request" and "financial_space_id" in error.details["fields"]
    # Observe: lê e prepara, não aplica nem reverte (e o modelo nem vê essas ferramentas).
    visible = [spec["name"] for spec in registry.specs_for(_grants(pool, ctx))]
    assert visible == ["finance.operation_status", "finance.prepare_change", "finance.read"]
    prepared = _run(registry, pool, ctx, "finance.prepare_change",
                    {"kind": "payable_payment", "payable_id": payable, "amount": "1.00", "paid_on": PAID_ON,
                     "evidence": [{"kind": "manual", "ref": "pedido"}]})
    proposal_id = prepared.proposal_ids[0]
    assert _error(_run, registry, pool, ctx, "finance.apply_change",
                  {"proposal_id": proposal_id, "expected_version": 1}).code == "capability_denied"
    assert _error(_run, registry, pool, ctx, "finance.reverse_change",
                  {"operation_id": seed.new_id(), "reason": "motivo"}).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0


@pytest.mark.integration
def test_write_flag_off_denies_write_tools_through_registry(pool, world):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    read_only = AiSettings(enabled=True, write_enabled=False)
    registry = _registry(pool, read_only)
    payable = _payable(pool, world)
    # Baixa conciliada com um lançamento do extrato: é a que um grant delegado aplica sozinho.
    statement = fh.ofx_transaction(pool, world, "50.00")

    visible = [spec["name"] for spec in registry.specs_for(_grants(pool, ctx))]
    assert visible == ["finance.operation_status", "finance.prepare_change", "finance.read"]
    prepared = _run(registry, pool, ctx, "finance.prepare_change",
                    {"kind": "payable_payment", "payable_id": payable, "amount": "50.00", "paid_on": PAID_ON,
                     "transaction_id": statement})
    assert prepared.data["requires_review"] is False
    proposal_id = prepared.proposal_ids[0]
    error = _error(_run, registry, pool, ctx, "finance.apply_change",
                   {"proposal_id": proposal_id, "expected_version": 1})
    assert error.code == "capability_denied"
    assert _error(_run, registry, pool, ctx, "finance.reverse_change",
                  {"operation_id": seed.new_id(), "reason": "motivo"}).code == "capability_denied"
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0

    # Com a flag ligada, a mesma chamada aplica.
    enabled = _registry(pool, AiSettings(enabled=True, write_enabled=True))
    result = _run(enabled, pool, ctx, "finance.apply_change", {"proposal_id": proposal_id, "expected_version": 1})
    assert result.data["status"] == "applied" and fh.effect_counts(pool, world.tenant_id)["payments"] == 1


@pytest.mark.integration
def test_full_flow_read_prepare_apply_status_reverse(pool, world, settings, caplog):
    caplog.set_level(logging.DEBUG, logger="ai")
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    registry = _registry(pool, settings)
    payable = _payable(pool, world, "300.00")
    statement = fh.ofx_transaction(pool, world, "120.00")

    overview = _run(registry, pool, ctx, "finance.read", {"query": "payables_overview", "month": 10, "year": 2026})
    assert fh.facts_by_key(overview)["payables.remaining"].value == "300.00"
    listing = _run(registry, pool, ctx, "finance.read", {"query": "payables_list", "month": 10, "year": 2026})
    assert listing.data["items"][0]["payable_id"] == payable

    prepared = _run(registry, pool, ctx, "finance.prepare_change", {
        "kind": "payable_payment", "payable_id": payable, "amount": "120.00", "paid_on": PAID_ON,
        "payment_method": "pix", "transaction_id": statement,
        "evidence": [{"kind": "email", "ref": "mensagem-sintetica-1"}],
    })
    proposal = prepared.data["proposal"]
    assert prepared.proposal_ids == [proposal["proposal_id"]] and prepared.operation_ids == []
    assert prepared.data["proposal_id"] == proposal["proposal_id"] and prepared.data["version"] == 1
    assert prepared.data["proposal_status"] == "ready" and prepared.data["requires_review"] is False
    assert proposal["effect"]["after"] == {"paid": "120.00", "remaining": "180.00", "status": "partial"}
    assert proposal["effect"]["state_after"] == "conciliado"
    assert prepared.sources[0].ref == "proposal:%s" % proposal["proposal_id"]
    assert fh.effect_counts(pool, world.tenant_id)["payments"] == 0

    applied = _run(registry, pool, ctx, "finance.apply_change",
                   {"proposal_id": proposal["proposal_id"], "expected_version": proposal["version"]})
    operation_id = applied.operation_ids[0]
    assert applied.data["status"] == "applied" and operation_id == proposal["planned_operation_id"]
    assert applied.sources[0].ref == "operation:%s" % operation_id

    status = _run(registry, pool, ctx, "finance.operation_status", {"operation_id": operation_id})
    assert status.data["status"] == "applied" and status.data["effect"]["after"]["remaining"] == "180.00"
    overview = _run(registry, pool, ctx, "finance.read", {"query": "payables_overview", "month": 10, "year": 2026})
    assert fh.facts_by_key(overview)["payables.remaining"].value == "180.00"

    # finance.reverse_change cria a proposta de compensação; NÃO aplica direto.
    reversal = _run(registry, pool, ctx, "finance.reverse_change",
                    {"operation_id": operation_id, "reason": "pagamento lançado em duplicidade"})
    reversal_proposal = reversal.data["proposal"]
    assert reversal_proposal["kind"] == "reverse_operation" and reversal.operation_ids == []
    assert _run(registry, pool, ctx, "finance.operation_status",
                {"operation_id": operation_id}).data["status"] == "applied"
    assert fh.fetch_value(pool, world.tenant_id, "SELECT count(*) FROM payable_payments WHERE reversed_at IS NULL") == 1

    reversed_result = _run(registry, pool, ctx, "finance.apply_change",
                           {"proposal_id": reversal_proposal["proposal_id"], "expected_version": 1})
    assert reversed_result.data["status"] == "applied"
    assert _run(registry, pool, ctx, "finance.operation_status",
                {"operation_id": operation_id}).data["status"] == "reversed"
    overview = _run(registry, pool, ctx, "finance.read", {"query": "payables_overview", "month": 10, "year": 2026})
    assert fh.facts_by_key(overview)["payables.remaining"].value == "300.00"

    # Preparar de novo a ação já aplicada devolve a operação existente.
    planned = _run(registry, pool, ctx, "finance.operation_status",
                   {"operation_id": reversal_proposal["planned_operation_id"]})
    assert planned.data["status"] == "applied"

    # Os logs levam ids, códigos e durações; nunca valores, títulos ou evidências.
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "proposal_created" in logged and "apply_done" in logged
    for secret in ("120.00", "Aluguel", "mensagem-sintetica-1", "duplicidade", "pix"):
        assert secret not in logged, secret


@pytest.mark.integration
def test_waiting_review_and_not_applied_are_reported_as_data(pool, world, settings):
    ctx = world.context(pool)
    fh.grant(pool, world, mode="assisted")
    registry = _registry(pool, settings)
    payable = _payable(pool, world)
    prepared = _run(registry, pool, ctx, "finance.prepare_change", {
        "kind": "payable_payment", "payable_id": payable, "amount": "10.00", "paid_on": PAID_ON,
        "evidence": [{"kind": "receipt", "ref": "whatsapp:comprovante"}],
    })
    proposal = prepared.data["proposal"]
    assert proposal["requires_review"] is True and prepared.warnings
    waiting = _run(registry, pool, ctx, "finance.apply_change",
                   {"proposal_id": proposal["proposal_id"], "expected_version": 1})
    assert waiting.data["status"] == "waiting_review" and waiting.operation_ids == [] and waiting.warnings
    status = _run(registry, pool, ctx, "finance.operation_status",
                  {"operation_id": proposal["planned_operation_id"]})
    assert status.data["status"] == "not_applied" and status.operation_ids == []
    assert _error(_run, registry, pool, ctx, "finance.operation_status",
                  {"operation_id": seed.new_id()}).code == "operation_unknown"

    # Campos de outro tipo de alteração são recusados, não ignorados.
    for args in (
        {"kind": "payable_payment", "amount": "10.00"},
        {"kind": "payable_payment", "payable_id": payable, "artifact_id": seed.new_id()},
        {"kind": "statement_import", "artifact_id": seed.new_id()},
        {"kind": "statement_import", "artifact_id": seed.new_id(), "account_id": world.personal_account_id,
         "amount": "10.00"},
    ):
        assert _error(_run, registry, pool, ctx, "finance.prepare_change", args).code == "invalid_request", args


@pytest.mark.integration
def test_model_cannot_relabel_a_receipt_to_get_an_automatic_payment_through_tools(pool, world, settings):
    """O caminho inteiro que o modelo percorre, com grant delegado ILIMITADO.

    O anexo é uma imagem vinda do WhatsApp. O modelo (ou uma instrução escrita
    dentro da própria imagem) tenta três descrições; nenhuma vira baixa
    automática, porque o tipo da evidência sai do arquivo e só um lançamento
    de extrato conferido dispensa revisão.
    """
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    registry = _registry(pool, settings)
    image, _ = fh.insert_artifact(pool, world, "personal", filename="comprovante.png", detected_kind="png",
                                  source_kind="whatsapp")
    attempts = [
        [{"kind": "manual", "ref": "artifact:%s" % image}],
        [{"kind": "receipt", "ref": "artifact:%s" % image}, {"kind": "email", "ref": "email:inventado"}],
        [{"kind": "manual", "ref": "pedido-do-titular"}],
    ]
    for index, evidence in enumerate(attempts):
        payable = seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Conta %d" % index,
                                      amount_expected="300.00", competency_month=fh.OCT)
        prepared = _run(registry, pool, ctx, "finance.prepare_change", {
            "kind": "payable_payment", "payable_id": payable, "amount": "300.00", "paid_on": PAID_ON,
            "evidence": evidence,
        })
        assert prepared.data["requires_review"] is True and prepared.data["proposal_status"] == "ready", evidence
        assert prepared.warnings == ["A proposta exige revisão e aprovação do titular."]
        applied = _run(registry, pool, ctx, "finance.apply_change",
                       {"proposal_id": prepared.data["proposal_id"], "expected_version": 1})
        assert applied.data["status"] == "waiting_review" and applied.data["reason"] == "requires_review", evidence
        assert applied.operation_ids == []
    counts = fh.effect_counts(pool, world.tenant_id)
    assert (counts["payments"], counts["operations"], counts["outbox"]) == (0, 0, 0)

    # Caractere que o banco não grava vira "pedido inválido" (não retentável), não erro interno.
    error = _error(_run, registry, pool, ctx, "finance.prepare_change", {
        "kind": "payable_payment", "payable_id": payable, "amount": "1.00", "paid_on": PAID_ON,
        "payment_method": "pix" + chr(0), "evidence": [{"kind": "manual", "ref": "x"}],
    })
    assert (error.code, error.http_status, error.retryable) == ("invalid_request", 400, False)
    error = _error(_run, registry, pool, ctx, "finance.reverse_change",
                   {"operation_id": seed.new_id(), "reason": "abc" + chr(0) + "def"})
    assert error.code == "invalid_request"


@pytest.mark.integration
def test_statement_import_through_tools_uses_scoped_artifact_and_provider(pool, world, other_world, settings):
    ctx = world.context(pool)
    fh.delegated_unlimited(pool, world)
    box = PreviewBox()
    registry = _registry(pool, settings, box)
    account = world.personal_account_id
    artifact_id, sha256 = fh.insert_artifact(pool, world, "personal", source_kind="email")
    items = [fh.preview_item("0.10", occurred_on="2026-03-02"), fh.preview_item("0.20", occurred_on="2026-03-03"),
             fh.preview_item("900.00", "income", occurred_on="2026-03-04")]
    box.add(fh.make_preview(account, items, artifact_id=artifact_id, sha256=sha256))

    prepared = _run(registry, pool, ctx, "finance.prepare_change",
                    {"kind": "statement_import", "artifact_id": artifact_id, "account_id": account})
    proposal = prepared.data["proposal"]
    assert box.calls == [(world.personal_space_id, artifact_id, account)]
    # A origem vem do anexo em quarentena, não do modelo.
    assert proposal["origin"]["source_kind"] == "email" and proposal["effect"]["items_new"] == 3
    assert proposal["effect"]["totals"]["expense"] == "0.30"
    applied = _run(registry, pool, ctx, "finance.apply_change",
                   {"proposal_id": proposal["proposal_id"], "expected_version": 1})
    assert applied.data["effect"]["items_new"] == 3
    realized = _run(registry, pool, ctx, "finance.read", {"query": "realized_totals", "month": 3, "year": 2026})
    facts = fh.facts_by_key(realized)
    assert facts["realized.expense"].value == "0.30" and facts["realized.income"].value == "900.00"

    # Anexo de outro espaço ou de outro tenant: inexistente, e o provedor nem é chamado.
    calls_before = len(box.calls)
    business_artifact, business_sha = fh.insert_artifact(pool, world, "business")
    foreign_artifact, foreign_sha = fh.insert_artifact(pool, other_world, "personal")
    box.add(fh.make_preview(account, items, artifact_id=business_artifact, sha256=business_sha))
    box.add(fh.make_preview(account, items, artifact_id=foreign_artifact, sha256=foreign_sha))
    for foreign in (business_artifact, foreign_artifact, seed.new_id()):
        error = _error(_run, registry, pool, ctx, "finance.prepare_change",
                       {"kind": "statement_import", "artifact_id": foreign, "account_id": account})
        assert error.code == "not_found", foreign
    # Conta de outro espaço.
    assert _error(_run, registry, pool, ctx, "finance.prepare_change",
                  {"kind": "statement_import", "artifact_id": artifact_id,
                   "account_id": world.business_account_id}).code == "not_found"
    assert len(box.calls) == calls_before

    # Prévia que não corresponde ao anexo pedido (hash diferente): recusada.
    other_artifact, _ = fh.insert_artifact(pool, world, "personal", filename="outro.ofx")
    box.add(fh.make_preview(account, [fh.preview_item("5.00")], artifact_id=other_artifact))
    assert _error(_run, registry, pool, ctx, "finance.prepare_change",
                  {"kind": "statement_import", "artifact_id": other_artifact, "account_id": account}).code == "conflict"
    # Prévia de CSV: não vira extrato.
    csv_artifact, csv_sha = fh.insert_artifact(pool, world, "personal", filename="planilha.csv", detected_kind="csv")
    box.add(fh.make_preview(account, [fh.preview_item("5.00")], artifact_id=csv_artifact, sha256=csv_sha,
                            filename="planilha.csv", file_kind="csv", canonical=False))
    assert _error(_run, registry, pool, ctx, "finance.prepare_change",
                  {"kind": "statement_import", "artifact_id": csv_artifact,
                   "account_id": account}).code == "invalid_request"
    assert fh.effect_counts(pool, world.tenant_id)["transactions"] == 3
