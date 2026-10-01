"""Prévia de importação (AC-02): mesma prévia do importador determinístico.

O caminho testado é o real: anexo baixado da caixa sintética pela ferramenta
de e-mail -> quarentena -> ``imports.preview``. O valor de referência vem de
chamar o importador do produto direto, com os mesmos bytes e a mesma conta.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from services.ai.artifacts import store_attachment
from services.ai.db import scoped_tx
from services.ai.email.base import AttachmentBlob
from services.ai.errors import AiError
from services.ai.imports.preview import build_preview
from services.ai.imports.tools import preview_provider
from services.ai.imports_types import ImportPreview
from services.ofx_import import OfxImportPipeline

from .support import email_helpers as helpers
from .support import seed


pytestmark = pytest.mark.integration

DOWNLOAD = "email.download_attachment"
PREVIEW = "imports.preview"
CENT = Decimal("0.01")

SEPTEMBER = ("m-2026-09-30-extrato", "att-set-ofx", "extrato-setembro-sgml.ofx", "extrato-setembro-2026.ofx")
OCTOBER = ("m-2026-10-10-extrato", "att-out-ofx", "extrato-outubro-1252.ofx", "extrato-outubro-2026.ofx")
RESENT = ("m-2026-10-01-reenvio", "att-set-ofx-v2", "extrato-setembro-reenviado.ofx", "extrato-setembro-2026-v2.ofx")


@pytest.fixture()
def env(pool, settings, world):
    ctx = world.context(pool)
    helpers.grant_all(pool, ctx)
    registry = helpers.build_registry(pool, settings, helpers.CountingFactory(), helpers.make_store())
    helpers.connect_mailbox(pool, ctx)
    return SimpleNamespace(ctx=ctx, registry=registry, world=world, account_id=world.personal_account_id)


def _download(env, pool, message_id, attachment_id) -> str:
    result = helpers.run_tool(env.registry, pool, env.ctx, DOWNLOAD,
                              {"message_id": message_id, "attachment_id": attachment_id})
    return result.data["artifact_id"]


def _upload(pool, settings, ctx, name, filename=None) -> str:
    blob = AttachmentBlob(content=helpers.file_bytes(name), filename=filename or name)
    return store_attachment(pool, ctx, settings, blob=blob, source_kind="upload")["artifact_id"]


def _error(callable_, *args, **kwargs) -> AiError:
    with pytest.raises(AiError) as excinfo:
        callable_(*args, **kwargs)
    return excinfo.value


def _ofx(transactions, ledger_balance=None) -> bytes:
    """OFX SGML sintético. ``transactions``: (AAAAMMDD, valor com sinal em texto, FITID, descrição)."""
    body = "".join(
        "<STMTTRN>\n<TRNTYPE>%s\n<DTPOSTED>%s\n<TRNAMT>%s\n<FITID>%s\n<MEMO>%s\n</STMTTRN>\n"
        % ("DEBIT" if str(amount).startswith("-") else "CREDIT", day, amount, fitid, memo)
        for day, amount, fitid, memo in transactions
    )
    ledger = ""
    if ledger_balance is not None:
        ledger = "<LEDGERBAL>\n<BALAMT>%s\n<DTASOF>20260930\n</LEDGERBAL>\n" % ledger_balance
    return (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>BRL\n"
        "<BANKACCTFROM>\n<BANKID>999\n<ACCTID>SINT-0001\n<ACCTTYPE>CHECKING\n</BANKACCTFROM>\n<BANKTRANLIST>\n"
        + body + "</BANKTRANLIST>\n" + ledger + "</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
    ).encode("ascii")


def _csv(rows) -> bytes:
    """CSV no formato padrão do produto."""
    return ("date,description,amount,type,category_name\n" + "\n".join(rows) + "\n").encode("utf-8")


def _store_bytes(pool, settings, ctx, raw: bytes, filename: str) -> str:
    blob = AttachmentBlob(content=raw, filename=filename)
    return store_attachment(pool, ctx, settings, blob=blob, source_kind="upload")["artifact_id"]


def _money(value) -> str:
    return str(Decimal(str(value)).quantize(CENT))


def _account_name(pool, tenant_id, account_id) -> str:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT name FROM accounts WHERE id = %s AND tenant_id = %s", (account_id, tenant_id))
        return cursor.fetchone()["name"]


def _ledger_keys(pool, tenant_id, account_id):
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute("SELECT fitid, dedup_key FROM transactions WHERE tenant_id = %s AND account_id = %s",
                       (tenant_id, account_id))
        rows = cursor.fetchall()
    return {row["fitid"] for row in rows if row["fitid"]}, {row["dedup_key"] for row in rows if row["dedup_key"]}


def _direct(pool, env, raw: bytes, filename: str):
    """O importador determinístico do produto, chamado direto com os mesmos bytes e conta."""
    fitids, keys = _ledger_keys(pool, env.ctx.tenant_id, env.account_id)
    return OfxImportPipeline().process_file(
        content=raw,
        filename=filename,
        user_id=env.ctx.actor_id,
        tenant_id=env.ctx.tenant_id,
        account_id=env.account_id,
        account_name=_account_name(pool, env.ctx.tenant_id, env.account_id),
        existing_dedup_keys=keys,
        existing_fitids=fitids,
    )


def _project_direct(result):
    """Projeção canônica do resultado do importador (sem campos voláteis)."""
    def item(tx):
        return (tx["date"], tx["description"], _money(tx["amount"]), tx["type"], tx.get("fitid") or None,
                tx["dedup_key"])
    return {
        "items": [item(tx) for tx in result["transactions_to_insert"]],
        "duplicates": [(item(tx), tx["duplicate_reason"]) for tx in result["duplicate_transactions"]],
        "ignored": [(tx["date"], tx["description"], _money(tx["amount"]), tx.get("fitid") or None, tx["reason"])
                    for tx in result["ignored_transactions"]],
    }


def _project_preview(preview: ImportPreview):
    def item(entry):
        return (entry["occurred_on"], entry["description"], entry["amount"], entry["type"], entry["fitid"],
                entry["dedup_key"])
    return {
        "items": [item(entry.to_dict()) for entry in preview.items],
        "duplicates": [(item(entry["item"]), entry["reason"]) for entry in preview.duplicates],
        "ignored": [(entry["occurred_on"], entry["description"], entry["amount"], entry["fitid"], entry["reason"])
                    for entry in preview.ignored],
    }


def _seed_ledger(pool, env, fitids, dedup_key=None):
    """Grava transações na conta do banco de teste com os FITIDs dados."""
    for index, fitid in enumerate(fitids):
        seed.create_transaction(
            pool, env.ctx.tenant_id, env.account_id, env.world.expense_category_id,
            description="Lançamento já importado %d" % index, amount="10.00", occurred_on=date(2026, 9, 1),
            fitid=fitid,
        )
    if dedup_key:
        with scoped_tx(pool, env.ctx.tenant_id) as cursor:
            cursor.execute(
                """
                INSERT INTO transactions (tenant_id, account_id, category_id, description, amount, type,
                                          occurred_on, entry_source, dedup_key)
                VALUES (%s, %s, %s, 'Lançamento manual com mesma chave', 1.00, 'expense', '2026-09-01', 'manual', %s)
                """,
                (env.ctx.tenant_id, env.account_id, env.world.expense_category_id, dedup_key),
            )


# -- AC-02 ----------------------------------------------------------------------------

@pytest.mark.parametrize("message_id, attachment_id, source_file, display_name", [SEPTEMBER, OCTOBER, RESENT])
def test_email_ofx_preview_equals_the_deterministic_importer(pool, settings, env, message_id, attachment_id,
                                                              source_file, display_name):
    artifact_id = _download(env, pool, message_id, attachment_id)
    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    direct = _direct(pool, env, helpers.file_bytes(source_file), display_name)

    assert _project_preview(preview) == _project_direct(direct)
    assert preview.items, "o extrato sintético tem lançamentos"
    assert preview.canonical is True and preview.file_kind == "ofx" and preview.filename == display_name
    assert preview.totals["parsed"] == direct["total_parsed"]
    assert preview.totals["items"] == direct["valid_count"]
    assert preview.totals["duplicates"] == direct["duplicate_count"]
    assert preview.totals["ignored"] == direct["ignored_count"]
    assert preview.declared_balance == _money(direct["ledger_reconciliation"]["declared_balance"])

    # Totais: recalculados em Decimal a partir dos itens, iguais ao que o importador somaria.
    sums = {"income": Decimal("0"), "expense": Decimal("0"), "transfer": Decimal("0")}
    for tx in direct["transactions_to_insert"]:
        sums[tx["type"]] += Decimal(str(tx["amount"]))
    assert preview.totals["income"] == _money(sums["income"])
    assert preview.totals["expense"] == _money(sums["expense"])
    assert preview.totals["transfer"] == _money(sums["transfer"])
    assert preview.totals["net"] == _money(sums["income"] - sums["expense"])
    assert preview.totals["currency"] == "BRL"
    # Nenhum float em lugar nenhum da prévia.
    assert "float" not in {type(value).__name__ for value in _walk(preview.to_dict())}


def _walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


def test_september_statement_has_the_expected_shape(pool, settings, env):
    """Valores conferidos à mão contra o arquivo sintético."""
    preview = build_preview(pool, env.ctx, _download(env, pool, *SEPTEMBER[:2]), env.account_id, settings)
    assert [(item.occurred_on, item.amount, item.type, item.fitid) for item in preview.items] == [
        ("2026-09-05", "4200.00", "income", "SINT-2026-09-0001"),
        ("2026-09-06", "1350.00", "expense", "SINT-2026-09-0002"),
        ("2026-09-10", "89.90", "expense", "SINT-2026-09-0003"),
        ("2026-09-12", "500.00", "transfer", "SINT-2026-09-0004"),
        ("2026-09-15", "237.45", "expense", "SINT-2026-09-0005"),
        ("2026-09-20", "150.10", "income", "SINT-2026-09-0006"),
    ]
    assert preview.totals == {
        "income": "4350.10", "expense": "1677.35", "transfer": "500.00", "net": "2672.75", "currency": "BRL",
        "items": 6, "duplicates": 1, "ignored": 0, "ambiguities": 6, "parsed": 7,
    }
    assert (preview.period_start, preview.period_end) == ("2026-09-05", "2026-09-20")
    assert preview.declared_balance == "2172.75" and preview.institution is None

    # Duplicado dentro do próprio arquivo, com o motivo.
    (duplicate,) = preview.duplicates
    assert duplicate["scope"] == "file" and duplicate["item"]["fitid"] == "SINT-2026-09-0005"
    assert "SINT-2026-09-0005" in duplicate["reason"] and "arquivo" in duplicate["reason"]

    # Transferência e lançamentos sem categoria aparecem como ambiguidades.
    codes = [(entry["code"], entry["item"]["fitid"]) for entry in preview.ambiguities]
    assert ("transfer_without_destination", "SINT-2026-09-0004") in codes
    assert sorted(fitid for code, fitid in codes if code == "unclassified") == [
        "SINT-2026-09-000%d" % index for index in (1, 2, 3, 5, 6)
    ]


def test_windows_1252_statement_keeps_accents(pool, settings, env):
    preview = build_preview(pool, env.ctx, _download(env, pool, *OCTOBER[:2]), env.account_id, settings)
    assert [item.description for item in preview.items] == [
        "Padaria Pão Doce", "Farmácia São João", "Salário Empresa Exemplo Ltda", "Mensalidade Colégio Fictício",
        "Manutenção de conta",
    ]
    assert preview.totals["income"] == "4200.00" and preview.totals["expense"] == "1213.30"


# -- deduplicação ------------------------------------------------------------------------

def test_different_attachment_with_same_transactions_shows_ledger_duplicates(pool, settings, env):
    """Anexos diferentes, mesmas transações: FITID + conta já gravados aparecem como duplicados."""
    first = _download(env, pool, *SEPTEMBER[:2])
    second = _download(env, pool, *RESENT[:2])
    assert first != second                          # arquivos diferentes, artefatos diferentes

    already = ["SINT-2026-09-000%d" % index for index in range(1, 7)]
    _seed_ledger(pool, env, already)

    preview = build_preview(pool, env.ctx, second, env.account_id, settings)
    assert [item.fitid for item in preview.items] == ["SINT-2026-09-0007"]     # só o lançamento novo
    assert sorted(entry["item"]["fitid"] for entry in preview.duplicates) == already
    for entry in preview.duplicates:
        assert entry["scope"] == "ledger"
        assert entry["item"]["fitid"] in entry["reason"] and "já existente" in entry["reason"]
    assert preview.totals["items"] == 1 and preview.totals["duplicates"] == 6
    assert preview.totals["expense"] == "75.00" and preview.totals["income"] == "0.00"

    # A mesma prévia continua igual à do importador com as mesmas chaves do banco.
    direct = _direct(pool, env, helpers.file_bytes(RESENT[2]), RESENT[3])
    assert _project_preview(preview) == _project_direct(direct)


def test_dedup_key_in_the_ledger_also_marks_a_duplicate(pool, settings, env):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    clean = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    target = clean.items[1]                                    # aluguel
    _seed_ledger(pool, env, [], dedup_key=target.dedup_key)

    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    assert target.fitid not in [item.fitid for item in preview.items]
    ledger = [entry for entry in preview.duplicates if entry["scope"] == "ledger"]
    assert [entry["item"]["fitid"] for entry in ledger] == [target.fitid]
    assert "dedup_key" in ledger[0]["reason"]


def test_ledger_of_another_account_or_tenant_does_not_cause_duplicates(pool, settings, env, other_world):
    fitids = ["SINT-2026-09-000%d" % index for index in range(1, 7)]
    # Mesmos FITIDs gravados na conta de negócio e em outro tenant.
    for tenant_id, account_id, category_id in (
        (env.world.tenant_id, env.world.business_account_id, env.world.expense_category_id),
        (other_world.tenant_id, other_world.personal_account_id, other_world.expense_category_id),
    ):
        for fitid in fitids:
            seed.create_transaction(pool, tenant_id, account_id, category_id, description="Outra conta",
                                    amount="1.00", occurred_on=date(2026, 9, 1), fitid=fitid)
    preview = build_preview(pool, env.ctx, _download(env, pool, *SEPTEMBER[:2]), env.account_id, settings)
    assert preview.totals["items"] == 6
    assert [entry["scope"] for entry in preview.duplicates] == ["file"]


# -- escopo ----------------------------------------------------------------------------------

def test_account_must_be_allowed_in_the_context(pool, settings, env, other_world):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    for account in (env.world.business_account_id, other_world.personal_account_id, seed.new_id(), "nao-e-uuid", ""):
        assert _error(build_preview, pool, env.ctx, artifact_id, account, settings).code == "not_found"
    # Conta do tenant, mas sem vínculo com nenhum espaço: fora do alcance.
    loose = seed.create_account(pool, env.world.tenant_id, None, "Conta sem espaço")
    assert _error(build_preview, pool, env.ctx, artifact_id, loose, settings).code == "not_found"
    # A recusa não marcou o artefato como "previewed".
    assert helpers.artifact_row(pool, env.ctx.tenant_id, artifact_id)["state"] == "quarantined"


def test_account_linked_to_the_space_but_absent_from_the_context_is_not_found(pool, settings, env):
    """Primeira barreira: a lista de contas do contexto (resolvida no servidor).
    A conta ESTÁ vinculada ao espaço no banco; quem não a autoriza é o contexto."""
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    newer = seed.create_account(pool, env.world.tenant_id, env.world.personal_space_id, "Conta aberta depois")
    assert newer not in env.ctx.allowed_account_ids
    assert _error(build_preview, pool, env.ctx, artifact_id, newer, settings).code == "not_found"

    narrowed = dataclasses.replace(env.ctx, allowed_account_ids=frozenset())
    assert _error(build_preview, pool, narrowed, artifact_id, env.account_id, settings).code == "not_found"
    assert helpers.artifact_row(pool, env.ctx.tenant_id, artifact_id)["state"] == "quarantined"

    # Com o contexto refeito pelo servidor, a mesma conta é aceita.
    fresh = env.world.context(pool)
    assert build_preview(pool, fresh, artifact_id, newer, settings).account_id == newer


def test_archived_account_is_not_found_even_with_a_stale_context(pool, settings, env):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    with scoped_tx(pool, env.ctx.tenant_id) as cursor:
        cursor.execute("UPDATE accounts SET archived_at = now() WHERE id = %s AND tenant_id = %s",
                       (env.account_id, env.ctx.tenant_id))
    assert env.account_id in env.ctx.allowed_account_ids      # o contexto antigo ainda lista a conta
    assert _error(build_preview, pool, env.ctx, artifact_id, env.account_id, settings).code == "not_found"
    assert helpers.artifact_row(pool, env.ctx.tenant_id, artifact_id)["state"] == "quarantined"


def test_stale_context_does_not_reach_an_account_of_another_space(pool, settings, env, other_world):
    """Segunda barreira: mesmo com a lista de contas do contexto desatualizada,
    a consulta confere tenant e vínculo da conta com o espaço."""
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    for foreign in (env.world.business_account_id, other_world.personal_account_id):
        stale = dataclasses.replace(env.ctx, allowed_account_ids=env.ctx.allowed_account_ids | {foreign})
        assert _error(build_preview, pool, stale, artifact_id, foreign, settings).code == "not_found"


def test_artifact_of_another_tenant_or_space_is_not_found(pool, settings, env, other_world):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    other_ctx = other_world.context(pool)
    assert _error(build_preview, pool, other_ctx, artifact_id, other_world.personal_account_id, settings).code == "not_found"
    business_ctx = env.world.context(pool, "business")
    assert _error(build_preview, pool, business_ctx, artifact_id, env.world.business_account_id, settings).code == "not_found"
    assert _error(build_preview, pool, env.ctx, seed.new_id(), env.account_id, settings).code == "not_found"


def test_preview_writes_no_transactions_and_marks_artifact_previewed(pool, settings, env):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    before = {table: seed.count_rows(pool, env.ctx.tenant_id, table)
              for table in ("transactions", "import_batches", "accounts", "categories")}
    build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    after = {table: seed.count_rows(pool, env.ctx.tenant_id, table) for table in before}
    assert after == before
    assert helpers.artifact_row(pool, env.ctx.tenant_id, artifact_id)["state"] == "previewed"
    (event,) = helpers.audit_events(pool, env.ctx.tenant_id, "ai.import.previewed")
    assert event["metadata"]["items"] == 6 and event["metadata"]["canonical"] is True
    dumped = json.dumps(event["metadata"], ensure_ascii=False)
    assert "Salario" not in dumped and "SINT-2026-09" not in dumped       # só referências e contagens


# -- evidência e CSV ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["foto-comprovante.png", "recibo.jpg"])
def test_images_are_evidence_and_have_no_statement_preview(pool, settings, env, name):
    artifact_id = _upload(pool, settings, env.ctx, name)
    error = _error(build_preview, pool, env.ctx, artifact_id, env.account_id, settings)
    assert error.code == "invalid_request" and error.details["reason"] == "not_a_statement"
    assert "evidência" in error.safe_message


def test_pdf_is_evidence_and_has_no_statement_preview(pool, settings, env):
    pytest.importorskip("pypdf")
    artifact_id = _upload(pool, settings, env.ctx, "comprovante.pdf")
    error = _error(build_preview, pool, env.ctx, artifact_id, env.account_id, settings)
    assert error.code == "invalid_request" and error.details["reason"] == "not_a_statement"


def test_csv_is_listed_but_not_canonical(pool, settings, env):
    artifact_id = _download(env, pool, "m-2026-09-27-csv", "att-csv")
    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    assert preview.canonical is False and preview.file_kind == "csv"
    assert [(item.occurred_on, item.description, item.amount, item.type, item.category_hint, item.fitid)
            for item in preview.items] == [
        ("2026-09-03", "Assinatura Streaming Exemplo", "39.90", "expense", "Lazer", None),
        ("2026-09-04", "Venda Produto Digital", "250.00", "income", "Vendas", None),
        ("2026-09-08", "Taxa Plataforma Exemplo", "25.00", "expense", None, None),
    ]
    (duplicate,) = preview.duplicates
    assert duplicate["scope"] == "file" and duplicate["item"]["description"] == "Venda Produto Digital"
    assert preview.totals["income"] == "250.00" and preview.totals["expense"] == "64.90"
    assert preview.totals["parsed"] == 4 and preview.totals["items"] == 3
    codes = [entry["code"] for entry in preview.ambiguities]
    assert codes[0] == "not_canonical" and codes.count("unclassified") == 1
    assert preview.declared_balance is None and preview.institution is None

    # Chave já gravada na conta: duplicado contra o banco.
    _seed_ledger(pool, env, [], dedup_key=preview.items[0].dedup_key)
    again = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    assert [entry["scope"] for entry in again.duplicates] == ["ledger", "file"]
    assert again.totals["expense"] == "25.00"


def test_csv_in_latin1_and_with_bom_is_handled(pool, settings, env):
    latin1 = _download(env, pool, "m-2026-09-27-csv", "att-csv-latin1")
    preview = build_preview(pool, env.ctx, latin1, env.account_id, settings)
    assert [(item.occurred_on, item.description, item.amount, item.type) for item in preview.items] == [
        ("2026-09-05", "Conta de energia Distribuidora Fictícia", "89.90", "expense"),
        ("2026-09-06", "Transferência recebida Cliente Exemplo", "1200.00", "income"),
    ]
    assert preview.canonical is False

    # O mesmo CSV padrão com BOM dá os mesmos itens que sem BOM.
    plain = build_preview(pool, env.ctx, _upload(pool, settings, env.ctx, "lancamentos.csv"), env.account_id, settings)
    with_bom = AttachmentBlob(content=b"\xef\xbb\xbf" + helpers.file_bytes("lancamentos.csv"), filename="bom.csv")
    bom_id = store_attachment(pool, env.ctx, settings, blob=with_bom, source_kind="upload")["artifact_id"]
    bom = build_preview(pool, env.ctx, bom_id, env.account_id, settings)
    assert [item.to_dict() for item in bom.items] == [item.to_dict() for item in plain.items]
    assert len(bom.items) == 3


def test_csv_without_recognised_rows_reports_it_clearly(pool, settings, env):
    blob = AttachmentBlob(content=b"coluna_a;coluna_b\nx;y\nz;w\n", filename="outra-coisa.csv")
    artifact_id = store_attachment(pool, env.ctx, settings, blob=blob, source_kind="upload")["artifact_id"]
    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    assert preview.items == [] and preview.canonical is False
    assert [entry["code"] for entry in preview.ambiguities] == ["not_canonical", "no_transactions"]


def test_statement_resent_with_the_ofx_extension_gets_the_good_name_in_the_preview(pool, settings, env):
    """O nome da prévia segue para o componente financeiro, que só importa
    arquivo terminado em .ofx. Reenviar os mesmos bytes com o nome certo
    precisa resolver; antes o artefato ficava preso ao primeiro nome."""
    raw = helpers.file_bytes(SEPTEMBER[2])
    first = _store_bytes(pool, settings, env.ctx, raw, "extrato.txt")
    before = build_preview(pool, env.ctx, first, env.account_id, settings)
    assert before.canonical is True and before.filename == "extrato.txt"

    second = _store_bytes(pool, settings, env.ctx, raw, "extrato-setembro.ofx")
    assert second == first
    after = build_preview(pool, env.ctx, second, env.account_id, settings)
    assert after.canonical is True and after.filename == "extrato-setembro.ofx"
    # O conteúdo é o mesmo: só o nome mudou.
    assert _project_preview(after) == _project_preview(before)

    # Anexo sem nome (servidor que só devolve os bytes): o marcador leva a extensão do tipo.
    unnamed = store_attachment(pool, env.ctx, settings, source_kind="email",
                               blob=AttachmentBlob(content=helpers.file_bytes(OCTOBER[2])))["artifact_id"]
    assert build_preview(pool, env.ctx, unnamed, env.account_id, settings).filename == "anexo.ofx"


# -- valores e datas hostis dentro do arquivo -----------------------------------------------------

@pytest.mark.parametrize("amount", ["nan", "-nan", "inf", "-inf", "1e400", "-1e30", "1e16"])
def test_ofx_with_non_finite_or_absurd_amount_is_refused(pool, settings, env, amount):
    """O importador lê valores com ``float``, que aceita nan/inf/1e400. Nada
    disso pode virar "NaN" em itens, totais e fatos, nem erro cru de Decimal."""
    raw = _ofx([("20260905", "-10.00", "SINT-V-1", "Compra valida"), ("20260906", amount, "SINT-V-2", "Valor hostil")])
    artifact_id = _store_bytes(pool, settings, env.ctx, raw, "valor-hostil.ofx")

    error = _error(build_preview, pool, env.ctx, artifact_id, env.account_id, settings)
    assert error.code == "invalid_request" and error.details == {"reason": "invalid_amount"}
    assert error.retryable is False and "valor inválido" in error.safe_message
    # Pela ferramenta o resultado é o mesmo erro: nenhum fato é publicado.
    tool_error = _error(helpers.run_tool, env.registry, pool, env.ctx, PREVIEW,
                        {"artifact_id": artifact_id, "account_ref": env.account_id})
    assert tool_error.code == "invalid_request" and tool_error.details == {"reason": "invalid_amount"}
    # O arquivo recusado não conta como prévia feita.
    assert helpers.artifact_row(pool, env.ctx.tenant_id, artifact_id)["state"] == "quarantined"
    assert helpers.audit_events(pool, env.ctx.tenant_id, "ai.import.previewed") == []


def test_ofx_with_large_but_valid_amount_is_previewed_exactly(pool, settings, env):
    raw = _ofx([("20260905", "-999999999999.99", "SINT-G-1", "Compra grande"),
                ("20260906", "0.01", "SINT-G-2", "Centavo recebido")])
    preview = build_preview(pool, env.ctx, _store_bytes(pool, settings, env.ctx, raw, "grande.ofx"),
                            env.account_id, settings)
    assert [(item.amount, item.type) for item in preview.items] == [("999999999999.99", "expense"), ("0.01", "income")]
    assert preview.totals["expense"] == "999999999999.99" and preview.totals["net"] == "-999999999999.98"


def test_ofx_with_absurd_declared_balance_is_refused(pool, settings, env):
    raw = _ofx([("20260905", "-10.00", "SINT-S-1", "Compra valida")], ledger_balance="9" * 400)
    artifact_id = _store_bytes(pool, settings, env.ctx, raw, "saldo-hostil.ofx")
    error = _error(build_preview, pool, env.ctx, artifact_id, env.account_id, settings)
    assert error.code == "invalid_request" and error.details == {"reason": "invalid_amount"}


def test_csv_negative_amounts_are_normalised_and_do_not_invert_the_net(pool, settings, env):
    """O CSV padrão do produto não tira o sinal. Somado como veio, "-39,90" de
    despesa viraria +39,90 no líquido (250,00 - (-39,90) = 289,90)."""
    raw = _csv([
        "2026-09-03,Assinatura Exemplo,-39.90,expense,Lazer",
        "2026-09-04,Venda Exemplo,250.00,income,Vendas",
        "2026-09-05,Estorno Exemplo,-15.00,income,Vendas",
    ])
    artifact_id = _store_bytes(pool, settings, env.ctx, raw, "negativos.csv")
    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)
    assert [(item.occurred_on, item.amount, item.type) for item in preview.items] == [
        ("2026-09-03", "39.90", "expense"), ("2026-09-04", "250.00", "income"), ("2026-09-05", "15.00", "income"),
    ]
    assert all(Decimal(item.amount) > 0 for item in preview.items)      # o sinal está em ``type``
    assert preview.totals["income"] == "265.00" and preview.totals["expense"] == "39.90"
    assert preview.totals["net"] == "225.10"
    # Receita negativa é contraditória: fica listada, mas pede conferência.
    # Despesa negativa é a convenção dos bancos e não gera aviso.
    conflicts = [entry["item"]["description"] for entry in preview.ambiguities if entry["code"] == "sign_conflict"]
    assert conflicts == ["Estorno Exemplo"]

    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    facts = {fact.key: fact.value for fact in result.facts}
    assert facts["imports.preview.expense"] == "39.90" and facts["imports.preview.income"] == "265.00"


def test_csv_rows_with_invalid_amount_or_date_are_ignored_with_the_reason(pool, settings, env):
    raw = _csv([
        "2026-09-03,Valor nan,nan,expense,Lazer",
        "2026-09-04,Venda Exemplo,250.00,income,Vendas",
        "2026-09-05,Valor inf,inf,expense,Lazer",
        "2026-09-06,Valor enorme,1e30,expense,Lazer",
        "NaT,Data invalida,10.00,expense,Lazer",
        "2026-09-08,Taxa Exemplo,25.00,expense,Taxas",
    ])
    artifact_id = _store_bytes(pool, settings, env.ctx, raw, "hostil.csv")
    preview = build_preview(pool, env.ctx, artifact_id, env.account_id, settings)

    assert [(item.occurred_on, item.description, item.amount, item.type) for item in preview.items] == [
        ("2026-09-04", "Venda Exemplo", "250.00", "income"), ("2026-09-08", "Taxa Exemplo", "25.00", "expense"),
    ]
    assert [entry["description"] for entry in preview.ignored] == [
        "Valor nan", "Valor inf", "Valor enorme", "Data invalida",
    ]
    # Valor que não é número não aparece (ausência, não "NaN"); o da linha de
    # data inválida é um número de verdade e continua visível para conferência.
    assert [entry["amount"] for entry in preview.ignored] == [None, None, None, "10.00"]
    assert all(entry["reason"] for entry in preview.ignored)
    assert "Valor inválido" in preview.ignored[0]["reason"] and "Data inválida" in preview.ignored[3]["reason"]
    assert preview.ignored[3]["occurred_on"] is None and preview.ignored[0]["occurred_on"] == "2026-09-03"
    assert preview.totals["income"] == "250.00" and preview.totals["expense"] == "25.00"
    assert preview.totals["net"] == "225.00"
    assert preview.totals["parsed"] == 6 and preview.totals["items"] == 2 and preview.totals["ignored"] == 4
    assert [entry["code"] for entry in preview.ambiguities] == ["not_canonical", "invalid_rows"]
    assert (preview.period_start, preview.period_end) == ("2026-09-04", "2026-09-08")

    # Em nenhum lugar da prévia ou do resultado da ferramenta aparece NaN/Infinity.
    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    for dumped in (json.dumps(preview.to_dict()), json.dumps(result.to_dict())):
        assert "NaN" not in dumped and "Infinity" not in dumped and "E+" not in dumped
    assert {fact.key: fact.value for fact in result.facts}["imports.preview.expense"] == "25.00"
    assert result.data["ignored"]["total"] == 4


# -- ferramenta imports.preview ----------------------------------------------------------------

def test_tool_lists_at_most_forty_entries_per_list_and_says_so(pool, settings, env):
    """O modelo recebe uma amostra; os totais continuam sendo do arquivo inteiro."""
    transactions = [("202609%02d" % (1 + index % 28), "-%d.00" % (index + 1), "SINT-L-%03d" % index,
                     "Compra sintetica %03d" % index) for index in range(45)]
    artifact_id = _store_bytes(pool, settings, env.ctx, _ofx(transactions), "longo.ofx")
    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    for key in ("items", "ambiguities"):
        listing = result.data[key]
        assert listing["total"] == 45 and len(listing["listed"]) == 40 and listing["truncated"] is True
    assert result.data["duplicates"] == {"total": 0, "listed": [], "truncated": False}
    # 1 + 2 + ... + 45 = 1035: a soma considera os 45 lançamentos, não só os 40 listados.
    facts = {fact.key: fact.value for fact in result.facts}
    assert facts["imports.preview.expense"] == "1035.00" and facts["imports.preview.items"] == "45"


def test_tool_returns_facts_with_sources_and_marks_file_text_untrusted(pool, settings, env):
    artifact_id = _download(env, pool, "m-2026-09-18-injecao", "att-inj-ofx")
    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    data = result.data
    assert data["untrusted"] is True and data["canonical"] is True and data["file_kind"] == "ofx"
    # A instrução maliciosa do MEMO está lá, como descrição de lançamento.
    descriptions = [item["description"] for item in data["items"]["listed"]]
    assert any("IGNORE AS REGRAS" in text and "finance.apply_change" in text for text in descriptions)
    assert data["items"]["total"] == 2 and data["items"]["truncated"] is False

    # ...mas não entrou em fatos, fontes ou avisos, nem criou proposta/operação.
    trusted = json.dumps({"facts": [fact.to_dict() for fact in result.facts],
                          "sources": [source.to_dict() for source in result.sources],
                          "warnings": result.warnings}, ensure_ascii=False)
    assert "IGNORE" not in trusted and "apply_change" not in trusted
    assert result.proposal_ids == [] and result.operation_ids == []

    facts = {fact.key: fact for fact in result.facts}
    assert facts["imports.preview.income"].value == "25.00" and facts["imports.preview.expense"].value == "10.00"
    assert facts["imports.preview.items"].value == "2" and facts["imports.preview.items"].unit == "count"
    (source,) = result.sources
    assert source.ref == "artifact:%s" % artifact_id and source.kind == "artifact"
    for fact in result.facts:
        assert fact.source_refs == [source.ref] and fact.as_of
        assert fact.scope["financial_space_id"] == env.ctx.financial_space_id
        if fact.unit == "money":
            assert fact.currency == "BRL" and isinstance(fact.value, str)
    json.dumps(result.to_dict())      # sem float


def test_tool_rejects_scope_arguments_and_foreign_accounts(pool, settings, env, other_world):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    run = lambda args: helpers.run_tool(env.registry, pool, env.ctx, PREVIEW, args)   # noqa: E731
    base = {"artifact_id": artifact_id, "account_ref": env.account_id}
    for extra in ({"tenant_id": other_world.tenant_id}, {"financial_space_id": other_world.personal_space_id},
                  {"actor_id": other_world.user_id}):
        assert _error(run, dict(base, **extra)).code == "invalid_request"
    assert _error(run, {"artifact_id": artifact_id, "account_ref": "Conta pessoal"}).code == "invalid_request"
    assert _error(run, {"artifact_id": artifact_id, "account_ref": other_world.personal_account_id}).code == "not_found"
    assert _error(run, {"artifact_id": artifact_id, "account_ref": env.world.business_account_id}).code == "not_found"
    assert run(base).data["totals"]["items"] == 6


def test_empty_statement_reports_missing_data_instead_of_zero(pool, settings, env):
    empty = b"OFXHEADER:100\nDATA:OFXSGML\n\n<OFX>\n<BANKMSGSRSV1>\n<STMTRS>\n<CURDEF>BRL\n</STMTRS>\n</BANKMSGSRSV1>\n</OFX>\n"
    artifact_id = store_attachment(
        pool, env.ctx, settings, blob=AttachmentBlob(content=empty, filename="sem-movimento.ofx"), source_kind="upload"
    )["artifact_id"]
    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    facts = {fact.key: fact for fact in result.facts}
    for key in ("imports.preview.income", "imports.preview.expense", "imports.preview.transfer"):
        assert facts[key].value is None and facts[key].missing_reason
    assert facts["imports.preview.items"].value == "0"
    assert [entry["code"] for entry in result.data["ambiguities"]["listed"]] == ["no_transactions"]


def test_csv_tool_result_warns_that_it_is_not_canonical(pool, settings, env):
    artifact_id = _download(env, pool, "m-2026-09-27-csv", "att-csv")
    result = helpers.run_tool(env.registry, pool, env.ctx, PREVIEW,
                              {"artifact_id": artifact_id, "account_ref": env.account_id})
    assert result.data["canonical"] is False and result.sources[0].extra["canonical"] is False
    assert len(result.warnings) == 1 and "não é fonte canônica" in result.warnings[0]


def test_preview_provider_gives_the_financial_component_the_same_preview(pool, settings, env):
    artifact_id = _download(env, pool, *SEPTEMBER[:2])
    provide = preview_provider(pool, settings)
    provided = provide(env.ctx, artifact_id, env.account_id)
    assert isinstance(provided, ImportPreview)
    assert provided.to_dict() == build_preview(pool, env.ctx, artifact_id, env.account_id, settings).to_dict()
    # Ida e volta pelo formato da espinha.
    assert ImportPreview.from_dict(json.loads(json.dumps(provided.to_dict()))).to_dict() == provided.to_dict()
    assert _error(provide, env.ctx, artifact_id, env.world.business_account_id).code == "not_found"
