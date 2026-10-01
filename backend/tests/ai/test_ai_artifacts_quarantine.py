"""Quarentena de anexos: limites, tipo pelo conteúdo, deduplicação, escopo e expurgo."""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading

import pytest

from services.ai import artifacts
from services.ai.artifacts import (
    detect_kind,
    purge_expired,
    read_artifact,
    sanitize_filename,
    set_artifact_state,
    store_attachment,
)
from services.ai.db import scoped_tx
from services.ai.email.base import AttachmentBlob
from services.ai.errors import AiError
from services.ai.settings import MIB, AiSettings

from .support import email_helpers as helpers
from .support import seed


OFX = "extrato-setembro-sgml.ofx"


def _blob(name: str, filename: str = None, declared: str = None) -> AttachmentBlob:
    return AttachmentBlob(content=helpers.file_bytes(name), filename=filename or name, declared_mime=declared)


def _store(pool, ctx, settings, blob, **kwargs):
    kwargs.setdefault("source_kind", "upload")
    kwargs.setdefault("source_ref", {"upload_ref": "teste"})
    return store_attachment(pool, ctx, settings, blob=blob, **kwargs)


def _error(callable_, *args, **kwargs) -> AiError:
    with pytest.raises(AiError) as excinfo:
        callable_(*args, **kwargs)
    return excinfo.value


def _expire(pool, tenant_id: str, artifact_id: str) -> None:
    with scoped_tx(pool, tenant_id) as cursor:
        cursor.execute(
            "UPDATE ai_artifacts SET expires_at = now() - interval '1 minute' WHERE id = %s AND tenant_id = %s",
            (artifact_id, tenant_id),
        )


# -- detecção pelo conteúdo (sem banco) ------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize(
    "name, kind",
    [
        ("extrato-setembro-sgml.ofx", "ofx"),
        ("extrato-outubro-1252.ofx", "ofx"),      # Windows-1252 com acentos e CRLF
        ("lancamentos.csv", "csv"),
        ("extrato-latin1.csv", "csv"),
        ("comprovante.pdf", "pdf"),
        ("foto-comprovante.png", "png"),
        ("recibo.jpg", "jpeg"),
    ],
)
def test_kind_is_detected_from_content(name, kind):
    assert detect_kind(helpers.file_bytes(name)) == kind


@pytest.mark.unit
@pytest.mark.parametrize(
    "content, reason",
    [
        (helpers.file_bytes("falso-pdf.html"), "forbidden_type"),
        (helpers.file_bytes("falso-pdf.bin"), "forbidden_type"),       # assinatura de executável
        (helpers.file_bytes("arquivo.zip"), "forbidden_type"),
        (helpers.file_bytes("desconhecido.bin"), "unknown_type"),
        (b"\x7fELF\x02\x01\x01" + bytes(40), "forbidden_type"),
        (b"#!/bin/sh\necho teste\n", "forbidden_type"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(40), "forbidden_type"),   # documento do Office antigo
        (b"<html><body>OFXHEADER:100 <OFX></body></html>", "forbidden_type"),  # HTML que cita OFX
        (b"data,valor\n<script>alert(1)</script>,2\n", "forbidden_type"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>", "forbidden_type"),
        (b"apenas um texto corrido sem estrutura de planilha", "unknown_type"),
        (b"a,b\n1,2,3\n4\n", "unknown_type"),                                 # delimitador inconsistente
        ("d\x00a\x00t\x00a\x00".encode("latin-1"), "unknown_type"),             # UTF-16 não é aceito
    ],
)
def test_forbidden_and_unknown_content_is_refused(content, reason):
    error = _error(detect_kind, content)
    assert error.code == "invalid_request" and error.details["reason"] == reason


@pytest.mark.unit
def test_csv_needs_a_consistent_delimiter():
    assert detect_kind(b"data;valor;descricao\n01/09/2026;10,50;Padaria\n02/09/2026;7,00;Banca\n") == "csv"
    assert detect_kind(b"a\tb\n1\t2\n") == "csv"
    assert detect_kind("\ufeffdate,amount\n2026-09-01,10.00\n".encode("utf-8")) == "csv"   # BOM
    assert detect_kind(b'a,b\n"texto, com virgula",2\n') == "csv"
    assert _error(detect_kind, b"uma linha so,sem segunda\n").code == "invalid_request"


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("../../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\fatura.pdf", "fatura.pdf"),
        ("C:\\Users\\Pessoa\\extrato.ofx", "extrato.ofx"),
        ("/var/tmp/../x/extrato.ofx.exe", "extrato.ofx.exe"),
        ("..", "anexo"),
        ("", "anexo"),
        (None, "anexo"),
        ("  relatório  de   vendas .csv ", "relatório de vendas .csv"),
        ("nome\r\ncom\x00controle\u202e.ofx", "nomecomcontrole.ofx"),
        ('a<b>c:d"e|f?g*.pdf', "a_b_c_d_e_f_g_.pdf"),
        ("x" * 300 + ".ofx", "x" * 116 + ".ofx"),
    ],
)
def test_filename_is_sanitized_and_never_carries_path_components(raw, expected):
    cleaned = sanitize_filename(raw)
    assert cleaned == expected
    assert "/" not in cleaned and "\\" not in cleaned and cleaned not in (".", "..") and len(cleaned) <= 120


# -- gravação -------------------------------------------------------------------------

@pytest.mark.integration
def test_store_writes_file_under_tenant_space_hash_and_audits_by_reference(pool, settings, world):
    ctx = world.context(pool)
    raw = helpers.file_bytes(OFX)
    record = _store(pool, ctx, settings, _blob(OFX, "../../extrato de setembro.ofx", "application/x-ofx"),
                    source_kind="email", source_ref={"message_id": "m-1", "attachment_id": "a-1"})
    sha256 = hashlib.sha256(raw).hexdigest()
    assert record["sha256"] == sha256 and record["size_bytes"] == len(raw) and record["detected_kind"] == "ofx"
    assert record["filename"] == "extrato de setembro.ofx" and record["state"] == "quarantined"
    assert record["deduplicated"] is False and record["declared_matches"] is True
    assert record["source_ref"] == {"message_id": "m-1", "attachment_id": "a-1"}

    relative = "%s/%s/%s" % (ctx.tenant_id, ctx.financial_space_id, sha256)
    assert helpers.quarantine_files(settings) == [relative]
    assert (settings.resolved_quarantine_dir() / relative).read_bytes() == raw

    row = helpers.artifact_row(pool, ctx.tenant_id, record["artifact_id"])
    assert row["original_filename"] == "extrato de setembro.ofx" and str(row["created_by_user_id"]) == ctx.actor_id
    # Validade de 7 dias.
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute(
            "SELECT extract(epoch FROM (expires_at - created_at)) AS ttl FROM ai_artifacts WHERE id = %s",
            (record["artifact_id"],),
        )
        ttl_days = float(cursor.fetchone()["ttl"]) / 86400
    assert 6.99 < ttl_days < 7.01

    (event,) = helpers.audit_events(pool, ctx.tenant_id, "ai.artifact.")
    assert event["event_type"] == "ai.artifact.stored" and event["entity_id"] == record["artifact_id"]
    assert event["metadata"]["sha256"] == sha256 and event["metadata"]["size_bytes"] == len(raw)
    dumped = json.dumps(event["metadata"], ensure_ascii=False)
    assert "extrato de setembro" not in dumped and "OFXHEADER" not in dumped and "Salario" not in dumped


@pytest.mark.integration
def test_same_content_is_deduplicated_per_space(pool, settings, world):
    personal = world.context(pool, "personal")
    business = world.context(pool, "business")
    first = _store(pool, personal, settings, _blob(OFX, "extrato.ofx"))
    again = _store(pool, personal, settings, _blob(OFX, "outro-nome.ofx"))
    assert again["artifact_id"] == first["artifact_id"] and again["deduplicated"] is True
    # Os dois nomes combinam com o tipo detectado: vale o da primeira entrada.
    assert again["filename"] == "extrato.ofx"
    assert len(helpers.quarantine_files(settings)) == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_artifacts") == 1

    # Outro espaço do mesmo tenant: artefato e diretório próprios.
    other = _store(pool, business, settings, _blob(OFX, "extrato.ofx"))
    assert other["artifact_id"] != first["artifact_id"] and other["deduplicated"] is False
    files = helpers.quarantine_files(settings)
    assert len(files) == 2 and {path.split("/")[1] for path in files} == {
        world.personal_space_id, world.business_space_id
    }
    kinds = [event["event_type"] for event in helpers.audit_events(pool, world.tenant_id, "ai.artifact.")]
    assert kinds == ["ai.artifact.stored", "ai.artifact.deduplicated", "ai.artifact.stored"]

    # Conteúdo diferente, artefato diferente.
    different = _store(pool, personal, settings, _blob("extrato-setembro-reenviado.ofx"))
    assert different["artifact_id"] != first["artifact_id"] and different["sha256"] != first["sha256"]


@pytest.mark.integration
def test_resend_with_the_right_extension_fixes_the_stored_name(pool, settings, world):
    """O mesmo OFX entra com um nome que não termina em .ofx e depois é
    reenviado com o nome certo: o artefato é o mesmo, e o nome passa a ser o
    bom. Sem isso o conteúdo ficaria impossível de importar neste espaço."""
    ctx = world.context(pool)
    first = _store(pool, ctx, settings, _blob(OFX, "extrato.txt", "text/plain"))
    assert first["filename"] == "extrato.txt" and first["declared_mime"] == "text/plain"

    fixed = _store(pool, ctx, settings, _blob(OFX, "extrato-setembro.ofx", "application/x-ofx"))
    assert fixed["artifact_id"] == first["artifact_id"] and fixed["deduplicated"] is True
    assert fixed["filename"] == "extrato-setembro.ofx" and fixed["declared_mime"] == "application/x-ofx"
    row = helpers.artifact_row(pool, ctx.tenant_id, first["artifact_id"])
    assert row["original_filename"] == "extrato-setembro.ofx"
    assert read_artifact(pool, ctx, first["artifact_id"], settings)[0]["filename"] == "extrato-setembro.ofx"

    # A troca só vale de nome ruim para nome bom. Um reenvio com nome ruim
    # (por exemplo, vindo de um e-mail malicioso) não estraga o nome bom...
    for worse in ("x.ofx.exe", "extrato.txt", "outro.csv", ""):
        blob = AttachmentBlob(content=helpers.file_bytes(OFX), filename=worse, declared_mime="application/pdf")
        again = _store(pool, ctx, settings, blob)
        assert again["artifact_id"] == first["artifact_id"]
        assert again["filename"] == "extrato-setembro.ofx" and again["declared_mime"] == "application/x-ofx"
    # ...e entre dois nomes ruins continua valendo o primeiro.
    other = world.context(pool, "business")
    _store(pool, other, settings, _blob(OFX, "extrato.txt"))
    assert _store(pool, other, settings, _blob(OFX, "x.ofx.exe"))["filename"] == "extrato.txt"

    # A auditoria registra só o FATO da troca, nunca o nome.
    events = helpers.audit_events(pool, ctx.tenant_id, "ai.artifact.deduplicated")
    assert [event["metadata"]["filename_updated"] for event in events
            if event["metadata"]["financial_space_id"] == ctx.financial_space_id] == [True, False, False, False, False]
    assert "extrato-setembro" not in helpers.audit_dump(pool, ctx.tenant_id)


@pytest.mark.integration
def test_resend_does_not_rename_consumed_evidence_but_renames_a_purged_artifact(pool, settings, world):
    ctx = world.context(pool)
    consumed = _store(pool, ctx, settings, _blob(OFX, "extrato.txt"))
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        assert set_artifact_state(cursor, ctx, consumed["artifact_id"], "consumed") is True
    # Evidência de um efeito aplicado: o registro não muda mais.
    assert _store(pool, ctx, settings, _blob(OFX, "extrato.ofx"))["filename"] == "extrato.txt"

    purged = _store(pool, ctx, settings, _blob("extrato-setembro-reenviado.ofx", "reenvio.dat"))
    _expire(pool, ctx.tenant_id, purged["artifact_id"])
    assert purge_expired(pool, ctx.tenant_id, settings) == 1
    # A linha expurgada é reaproveitada; o reenvio com nome certo conserta o nome.
    revived = _store(pool, ctx, settings, _blob("extrato-setembro-reenviado.ofx", "reenvio.ofx"))
    assert revived["artifact_id"] == purged["artifact_id"] and revived["state"] == "quarantined"
    assert revived["filename"] == "reenvio.ofx"


@pytest.mark.integration
@pytest.mark.parametrize(
    "name, filename, expected",
    [
        (OFX, "anexo", "anexo.ofx"),          # nome-marcador do conector quando o servidor não informa nome
        (OFX, "", "anexo.ofx"),
        (OFX, None, "anexo.ofx"),
        (OFX, "../..", "anexo.ofx"),
        ("lancamentos.csv", "", "anexo.csv"),
        ("foto-comprovante.png", None, "anexo.png"),
        ("recibo.jpg", "", "anexo.jpg"),
        # Nome informado por quem enviou não é alterado, mesmo sem extensão.
        (OFX, "extrato", "extrato"),
        (OFX, "anexo.txt", "anexo.txt"),
    ],
)
def test_placeholder_name_gets_the_extension_of_the_detected_kind(pool, settings, world, name, filename, expected):
    ctx = world.context(pool)
    blob = AttachmentBlob(content=helpers.file_bytes(name), filename=filename)
    record = store_attachment(pool, ctx, settings, blob=blob, source_kind="email")
    assert record["filename"] == expected
    assert helpers.artifact_row(pool, ctx.tenant_id, record["artifact_id"])["original_filename"] == expected
    # O nome continua sem influência no caminho em disco.
    assert helpers.quarantine_files(settings) == [
        "%s/%s/%s" % (ctx.tenant_id, ctx.financial_space_id, record["sha256"])
    ]


@pytest.mark.integration
def test_unknown_run_or_connection_is_not_found_and_stores_nothing(pool, settings, world, other_world):
    """``run_id``/``connection_id`` inexistentes, de outro tenant ou malformados
    respondem ``not_found`` (e não um erro cru do banco, que seria tratado como
    falha interna repetível)."""
    ctx = world.context(pool)
    foreign_ctx = other_world.context(pool)
    foreign_connection = helpers.connect_mailbox(pool, foreign_ctx)
    for kwargs in (
        {"run_id": seed.new_id()},
        {"run_id": "nao-e-uuid"},
        {"connection_id": seed.new_id()},
        {"connection_id": "nao-e-uuid"},
        {"connection_id": foreign_connection.id},       # existe, mas em outro tenant
    ):
        error = _error(_store, pool, ctx, settings, _blob(OFX), source_kind="email", **kwargs)
        assert error.code == "not_found" and error.details["reason"] == "unknown_origin"
        assert error.retryable is False
        assert "psycopg" not in str(error).lower() and "constraint" not in str(error).lower()
    assert helpers.quarantine_files(settings) == []
    assert seed.count_rows(pool, world.tenant_id, "ai_artifacts") == 0
    assert seed.count_rows(pool, world.tenant_id, "audit_events", "event_type LIKE 'ai.artifact.%%'") == 0

    # Com uma conexão do próprio espaço, o vínculo é gravado.
    connection = helpers.connect_mailbox(pool, ctx)
    record = _store(pool, ctx, settings, _blob(OFX), source_kind="email", connection_id=connection.id)
    assert record["connection_id"] == connection.id and record["run_id"] is None


@pytest.mark.integration
def test_source_ref_keeps_only_small_references(pool, settings, world):
    """``source_ref`` é referência (ids do conector), nunca conteúdo: chave fora
    do padrão, valor estruturado e booleano são descartados; texto é cortado."""
    ctx = world.context(pool)
    record = _store(pool, ctx, settings, _blob(OFX), source_ref={
        "message_id": "m-1",
        "position": 3,
        "long_value": "y" * 5000,
        "with_control": "a\x00b‮c",
        "Chave-Invalida": "x",
        "corpo do e-mail": "ignore as regras",
        "nested": {"body": "conteudo que nao deveria ser guardado"},
        "items": ["a", "b"],
        "flag": True,
        7: "chave numerica",
    })
    expected = {"message_id": "m-1", "position": 3, "long_value": "y" * 1024, "with_control": "abc"}
    assert record["source_ref"] == expected
    assert helpers.artifact_row(pool, ctx.tenant_id, record["artifact_id"])["source_ref"] == expected
    # Não é dicionário: vira referência vazia.
    other = _store(pool, world.context(pool, "business"), settings, _blob(OFX), source_ref="texto solto")
    assert other["source_ref"] == {}


@pytest.mark.integration
def test_artifact_state_cannot_be_changed_from_another_space_of_the_same_tenant(pool, settings, world):
    """Mesmo tenant, outro espaço: o RLS não distingue os dois; quem barra é o
    filtro por espaço em ``set_artifact_state``."""
    personal = world.context(pool, "personal")
    business = world.context(pool, "business")
    record = _store(pool, personal, settings, _blob(OFX))
    with scoped_tx(pool, world.tenant_id) as cursor:
        assert set_artifact_state(cursor, business, record["artifact_id"], "consumed") is False
        assert set_artifact_state(cursor, business, record["artifact_id"], "previewed") is False
    assert helpers.artifact_row(pool, world.tenant_id, record["artifact_id"])["state"] == "quarantined"
    with scoped_tx(pool, world.tenant_id) as cursor:
        assert set_artifact_state(cursor, personal, record["artifact_id"], "previewed") is True
    assert helpers.artifact_row(pool, world.tenant_id, record["artifact_id"])["state"] == "previewed"


@pytest.mark.integration
def test_concurrent_stores_of_the_same_file_yield_one_artifact(pool, settings, world):
    ctx = world.context(pool)
    results, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            results.append(_store(pool, ctx, settings, _blob(OFX)))
        except Exception as exc:  # pragma: no cover - o teste falha abaixo
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len({record["artifact_id"] for record in results}) == 1
    assert sorted(record["deduplicated"] for record in results) == [False] + [True] * 7
    assert len(helpers.quarantine_files(settings)) == 1
    record, content = read_artifact(pool, ctx, results[0]["artifact_id"], settings)
    assert content == helpers.file_bytes(OFX)


# -- limites ---------------------------------------------------------------------------

@pytest.mark.integration
def test_file_over_20_mib_is_refused_without_writing(pool, settings, world):
    ctx = world.context(pool)
    assert settings.artifact_max_bytes == 20 * MIB
    header = b"OFXHEADER:100\n<OFX>\n"
    over = header + b" " * (20 * MIB + 1 - len(header))
    error = _error(_store, pool, ctx, settings, AttachmentBlob(content=over, filename="grande.ofx"))
    assert error.code == "payload_too_large" and error.http_status == 413
    assert helpers.quarantine_files(settings) == []
    assert seed.count_rows(pool, world.tenant_id, "ai_artifacts") == 0
    assert seed.count_rows(pool, world.tenant_id, "audit_events") == 0

    # Exatamente no limite é aceito.
    exact = header + b" " * (20 * MIB - len(header))
    record = _store(pool, ctx, settings, AttachmentBlob(content=exact, filename="limite.ofx"))
    assert record["size_bytes"] == 20 * MIB and len(helpers.quarantine_files(settings)) == 1


@pytest.mark.integration
def test_empty_and_invalid_blobs_are_refused(pool, settings, world):
    ctx = world.context(pool)
    empty = _error(_store, pool, ctx, settings, AttachmentBlob(content=b"", filename="vazio.ofx"))
    assert empty.code == "invalid_request" and empty.details["reason"] == "empty_file"
    assert "vazio" in empty.safe_message
    assert _error(_store, pool, ctx, settings, AttachmentBlob(content="texto", filename="x.ofx")).code == "invalid_request"
    assert _error(_store, pool, ctx, settings, _blob(OFX), source_kind="ftp").code == "invalid_request"
    for name, declared in (("falso-pdf.html", "application/pdf"), ("falso-pdf.bin", "application/pdf"),
                           ("arquivo.zip", "application/x-ofx"), ("desconhecido.bin", None)):
        assert _error(_store, pool, ctx, settings, _blob(name, "comprovante.pdf", declared)).code == "invalid_request"
    assert helpers.quarantine_files(settings) == [] and seed.count_rows(pool, world.tenant_id, "ai_artifacts") == 0


@pytest.mark.integration
def test_declared_mime_is_informative_and_content_decides(pool, settings, world):
    ctx = world.context(pool)
    png = _store(pool, ctx, settings, _blob("foto-comprovante.png", "foto.jpg", "image/jpeg"))
    assert png["detected_kind"] == "png" and png["declared_mime"] == "image/jpeg" and png["declared_matches"] is False
    csv = _store(pool, ctx, settings, _blob("lancamentos.csv", "dados.txt", "TEXT/CSV; charset=utf-8"))
    assert csv["detected_kind"] == "csv" and csv["declared_mime"] == "text/csv" and csv["declared_matches"] is True
    none = _store(pool, ctx, settings, _blob("recibo.jpg", "recibo.jpg", "isto nao e um mime"))
    assert none["detected_kind"] == "jpeg" and none["declared_mime"] is None and none["declared_matches"] is None


# -- PDF ----------------------------------------------------------------------------------

@pytest.mark.integration
def test_pdf_page_limit_and_password(pool, tmp_path, world):
    pytest.importorskip("pypdf")
    ctx = world.context(pool)
    settings = AiSettings(quarantine_dir=str(tmp_path / "q"), pdf_max_pages=2)

    ok = _store(pool, ctx, settings, _blob("comprovante.pdf"))
    assert ok["detected_kind"] == "pdf"

    too_many = _error(_store, pool, ctx, settings, _blob("fatura-3-paginas.pdf"))
    assert too_many.code == "payload_too_large" and too_many.details["reason"] == "pdf_too_many_pages"
    # Com o limite padrão (100) o mesmo arquivo passa.
    default = AiSettings(quarantine_dir=str(tmp_path / "q"))
    assert _store(pool, ctx, default, _blob("fatura-3-paginas.pdf"))["detected_kind"] == "pdf"

    locked = _error(_store, pool, ctx, settings, _blob("comprovante-protegido.pdf"))
    assert locked.code == "invalid_request" and locked.details["reason"] == "pdf_password_protected"
    # Pede desbloqueio seguro e orienta a NÃO mandar a senha pela conversa.
    assert "senha" in locked.safe_message and "Não informe a senha" in locked.safe_message

    broken = _error(_store, pool, ctx, settings, AttachmentBlob(content=b"%PDF-1.7\nlixo sem estrutura", filename="x.pdf"))
    assert broken.code == "invalid_request" and broken.details["reason"] == "pdf_invalid"
    assert len(helpers.quarantine_files(settings)) == 2   # só os dois aceitos


@pytest.mark.integration
def test_pdf_is_refused_when_it_cannot_be_validated(pool, settings, world, monkeypatch):
    """Sem pypdf não há como contar páginas nem ver senha: o PDF não entra."""
    ctx = world.context(pool)
    monkeypatch.setattr(artifacts, "_pdf_reader_class", lambda: None)
    error = _error(_store, pool, ctx, settings, _blob("comprovante.pdf"))
    assert error.code == "invalid_request" and error.details["reason"] == "pdf_validation_unavailable"
    assert helpers.quarantine_files(settings) == []
    # Os demais tipos continuam funcionando.
    assert _store(pool, ctx, settings, _blob(OFX))["detected_kind"] == "ofx"


# -- leitura e escopo -----------------------------------------------------------------------

@pytest.mark.integration
def test_read_is_scoped_and_checks_integrity(pool, settings, world, other_world):
    ctx = world.context(pool)
    record = _store(pool, ctx, settings, _blob(OFX))
    raw = helpers.file_bytes(OFX)

    stored_record, content = read_artifact(pool, ctx, record["artifact_id"], settings)
    assert content == raw and stored_record["artifact_id"] == record["artifact_id"]
    # Também funciona sem ``settings`` (caminho gravado, conferido contra o escopo).
    assert read_artifact(pool, ctx, record["artifact_id"])[1] == raw

    for foreign in (other_world.context(pool), world.context(pool, "business")):
        for call in ((pool, foreign, record["artifact_id"], settings), (pool, foreign, record["artifact_id"])):
            assert _error(read_artifact, *call).code == "not_found"
    assert _error(read_artifact, pool, ctx, seed.new_id(), settings).code == "not_found"
    assert _error(read_artifact, pool, ctx, "../../etc/passwd", settings).code == "not_found"

    # Arquivo adulterado em disco não é entregue.
    path = settings.resolved_quarantine_dir() / helpers.quarantine_files(settings)[0]
    path.write_bytes(raw + b"adulterado")
    assert _error(read_artifact, pool, ctx, record["artifact_id"], settings).code == "internal_error"
    path.unlink()
    assert _error(read_artifact, pool, ctx, record["artifact_id"], settings).code == "not_found"


@pytest.mark.integration
def test_tampered_storage_key_cannot_point_outside_the_scope(pool, settings, world, tmp_path):
    ctx = world.context(pool)
    record = _store(pool, ctx, settings, _blob(OFX))
    outside = tmp_path / "fora" / "segredo.txt"
    outside.parent.mkdir()
    outside.write_bytes(helpers.file_bytes(OFX))
    with scoped_tx(pool, ctx.tenant_id) as cursor:
        cursor.execute("UPDATE ai_artifacts SET storage_key = %s WHERE id = %s", (str(outside), record["artifact_id"]))
    # Sem settings: o caminho gravado é recusado por não terminar em tenant/espaço/hash.
    assert _error(read_artifact, pool, ctx, record["artifact_id"]).code == "internal_error"
    # Com settings: o caminho é refeito a partir do escopo e ignora o texto gravado.
    assert read_artifact(pool, ctx, record["artifact_id"], settings)[1] == helpers.file_bytes(OFX)


# -- expurgo ----------------------------------------------------------------------------------

@pytest.mark.integration
def test_purge_removes_expired_files_but_keeps_consumed_evidence(pool, settings, world, other_world):
    ctx = world.context(pool)
    expired = _store(pool, ctx, settings, _blob(OFX))
    fresh = _store(pool, ctx, settings, _blob("lancamentos.csv"))
    evidence = _store(pool, ctx, settings, _blob("foto-comprovante.png"))
    foreign_ctx = other_world.context(pool)
    foreign = _store(pool, foreign_ctx, settings, _blob(OFX))

    with scoped_tx(pool, ctx.tenant_id) as cursor:
        assert set_artifact_state(cursor, ctx, evidence["artifact_id"], "consumed") is True
        assert set_artifact_state(cursor, ctx, evidence["artifact_id"], "previewed") is False   # não regride
        # Outro tenant não altera o estado deste artefato.
        assert set_artifact_state(cursor, foreign_ctx, expired["artifact_id"], "consumed") is False
    for record in (expired, evidence):
        _expire(pool, ctx.tenant_id, record["artifact_id"])
    _expire(pool, foreign_ctx.tenant_id, foreign["artifact_id"])

    # Vencido já não é legível, mesmo antes do expurgo.
    assert _error(read_artifact, pool, ctx, expired["artifact_id"], settings).code == "not_found"

    assert purge_expired(pool, ctx.tenant_id, settings) == 1
    files = helpers.quarantine_files(settings)
    assert not any(path.endswith(expired["sha256"]) and path.startswith(ctx.tenant_id) for path in files)
    assert any(path.endswith(fresh["sha256"]) for path in files)
    assert any(path.endswith(evidence["sha256"]) for path in files)          # evidência preservada
    assert any(path.startswith(foreign_ctx.tenant_id) for path in files)      # outro tenant intocado
    assert helpers.artifact_row(pool, ctx.tenant_id, expired["artifact_id"])["state"] == "expired"
    assert helpers.artifact_row(pool, ctx.tenant_id, evidence["artifact_id"])["state"] == "consumed"
    assert read_artifact(pool, ctx, evidence["artifact_id"], settings)[1] == helpers.file_bytes("foto-comprovante.png")
    assert purge_expired(pool, ctx.tenant_id, settings) == 0                  # idempotente
    assert len(helpers.audit_events(pool, ctx.tenant_id, "ai.artifact.purged")) == 1

    # Enviar de novo o mesmo arquivo devolve o MESMO artefato, de volta à quarentena.
    revived = _store(pool, ctx, settings, _blob(OFX))
    assert revived["artifact_id"] == expired["artifact_id"] and revived["state"] == "quarantined"
    assert read_artifact(pool, ctx, revived["artifact_id"], settings)[1] == helpers.file_bytes(OFX)


@pytest.mark.integration
def test_quarantine_files_are_private_on_posix(pool, settings, world):
    if os.name != "posix":
        pytest.skip("permissões de arquivo POSIX não se aplicam neste sistema")
    ctx = world.context(pool)
    _store(pool, ctx, settings, _blob(OFX))
    path = settings.resolved_quarantine_dir() / helpers.quarantine_files(settings)[0]
    assert (path.stat().st_mode & 0o077) == 0
    # Diretórios do tenant e do espaço também são privados.
    assert (path.parent.stat().st_mode & 0o077) == 0 and (path.parent.parent.stat().st_mode & 0o077) == 0
