"""Conector de e-mail: interface, caixa sintética, base64 de anexos e cofre.

Sem banco. A caixa postal fica em ``tests/ai/fixtures/email`` e é 100% sintética.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import pickle
from datetime import date

import pytest

from services.ai.email import base
from services.ai.email.base import EmailConnector, decode_base64_payload, max_encoded_length
from services.ai.email.credentials import (
    EnvCredentialStore,
    InMemoryCredentialStore,
    Secret,
    validate_credential_ref,
)
from services.ai.email.fixture import FixtureEmailConnector
from services.ai.errors import AiError
from services.ai.types import json_safe

from .support import email_helpers as helpers


pytestmark = pytest.mark.unit

CTX = None  # a caixa sintética não usa o contexto


@pytest.fixture()
def connector():
    return FixtureEmailConnector(helpers.FIXTURE_DIR)


def _all_pages(connector, **filters):
    pages, cursor = [], None
    while True:
        page = connector.search(CTX, cursor=cursor, **filters)
        pages.append(page)
        cursor = page.next_cursor
        if cursor is None:
            return pages


# -- interface ----------------------------------------------------------------

def test_interface_has_only_read_operations():
    """A interface não tem enviar, apagar, mover, rotular nem alterar."""
    from services.ai.email.mcp_http import McpHttpEmailConnector

    # ``close`` só libera recursos locais (conexões HTTP); não age sobre a caixa.
    allowed = {"search", "get_message", "download_attachment", "close", "connect"}
    public = {name for name in vars(EmailConnector) if not name.startswith("_")}
    assert public == {"search", "get_message", "download_attachment", "close"}
    for implementation in (FixtureEmailConnector, McpHttpEmailConnector):
        operations = {
            name for name in dir(implementation)
            if not name.startswith("_") and callable(getattr(implementation, name))
        }
        assert operations <= allowed
        forbidden = ("send", "delete", "trash", "move", "label", "modify", "update", "reply", "forward", "draft")
        assert not [name for name in dir(implementation) if any(word in name.lower() for word in forbidden)]


# -- busca paginada -----------------------------------------------------------

def test_search_pages_have_variable_size_and_last_page_has_no_cursor(connector):
    pages = _all_pages(connector, query="")
    sizes = [len(page.items) for page in pages]
    assert sizes == [3, 2, 4, 2]            # tamanhos variam; total = 11 mensagens
    assert pages[-1].next_cursor is None
    assert all(page.next_cursor for page in pages[:-1])
    ids = [item.message_id for page in pages for item in page.items]
    assert len(ids) == len(set(ids)) == 11
    # Mais recentes primeiro.
    dates = [item.date for page in pages for item in page.items]
    assert dates == sorted(dates, reverse=True)


def test_cursor_is_opaque_and_bound_to_the_query(connector):
    first = connector.search(CTX, query="")
    cursor = first.next_cursor
    # Opaco: não revela posição nem a consulta.
    assert "3" != cursor and "offset" not in cursor and len(cursor) >= 20
    with pytest.raises(AiError) as excinfo:
        connector.search(CTX, query="extrato", cursor=cursor)
    assert excinfo.value.code == "invalid_request"
    with pytest.raises(AiError) as excinfo:
        connector.search(CTX, query="", cursor=cursor + "x")
    assert excinfo.value.code == "invalid_request"
    # O mesmo cursor, na mesma consulta, continua de onde parou.
    second = connector.search(CTX, query="", cursor=cursor)
    assert {item.message_id for item in first.items}.isdisjoint({item.message_id for item in second.items})


def test_cursor_from_another_mailbox_is_rejected(connector, tmp_path):
    other_dir = helpers.copy_mailbox(tmp_path / "outra")
    document = json.loads((other_dir / "mailbox.json").read_text(encoding="utf-8"))
    document["mailbox"] = "outra-caixa"
    (other_dir / "mailbox.json").write_text(json.dumps(document), encoding="utf-8")
    other = FixtureEmailConnector(other_dir)
    cursor = connector.search(CTX, query="").next_cursor
    with pytest.raises(AiError) as excinfo:
        other.search(CTX, query="", cursor=cursor)
    assert excinfo.value.code == "invalid_request"


def test_search_filters_by_terms_period_and_sender(connector):
    found = [item.message_id for page in _all_pages(connector, query="extrato has:attachment") for item in page.items]
    assert "m-2026-09-30-extrato" in found and "m-2026-08-15-agosto" not in found
    assert "m-2026-09-10-novidades" not in found

    # ``after`` inclui o dia; ``before`` exclui.
    in_september = [
        item.message_id
        for page in _all_pages(connector, query="", after=date(2026, 9, 30), before=date(2026, 10, 1))
        for item in page.items
    ]
    assert in_september == ["m-2026-09-30-extrato"]

    from_bank = [
        item.message_id
        for page in _all_pages(connector, query="", sender="bancoficticio.example")
        for item in page.items
    ]
    assert len(from_bank) == 5 and all("golpe" not in message_id for message_id in from_bank)

    assert _all_pages(connector, query="termo-que-nao-existe")[0].items == []


# -- leitura -------------------------------------------------------------------

def test_get_message_returns_limited_body_and_declared_attachment_metadata(connector):
    message = connector.get_message(CTX, "m-2026-10-10-extrato")
    assert message.subject == "Extrato parcial de outubro de 2026"
    assert len(message.body_text) <= base.MAX_BODY_CHARS
    (attachment,) = message.attachments
    assert attachment.attachment_id == "att-out-ofx"
    assert attachment.declared_mime == "application/octet-stream"
    # Tamanho DECLARADO, diferente do real: o conector não o corrige.
    real = len(helpers.file_bytes("extrato-outubro-1252.ofx"))
    assert attachment.size_hint == 999999 and attachment.size_hint != real


def test_body_is_truncated_at_the_connector_limit(tmp_path):
    long_body = "linha de texto sintetico\n" * 2000   # ~48 mil caracteres
    directory = helpers.copy_mailbox(tmp_path / "caixa", [
        {"id": "m-longa", "from": "a@b.example", "subject": "longa", "date": "2026-10-11T00:00:00Z",
         "body": long_body, "attachments": []},
    ])
    message = FixtureEmailConnector(directory).get_message(CTX, "m-longa")
    assert len(message.body_text) == base.MAX_BODY_CHARS and message.body_truncated is True


def test_unknown_message_and_attachment_are_not_found(connector):
    with pytest.raises(AiError) as excinfo:
        connector.get_message(CTX, "m-inexistente")
    assert excinfo.value.code == "not_found"
    with pytest.raises(AiError) as excinfo:
        connector.download_attachment(CTX, "m-2026-09-30-extrato", "att-out-ofx")
    assert excinfo.value.code == "not_found"


def test_malicious_text_comes_back_as_plain_data(connector):
    message = connector.get_message(CTX, "m-2026-09-18-injecao")
    assert "finance.apply_change" in message.subject and "financial_space_id" in message.body_text
    # Caracteres de controle e de largura zero são removidos na borda.
    assert "​" not in message.body_text and "\x07" not in message.body_text
    names = [attachment.filename for attachment in message.attachments]
    assert names[0].startswith("../../../../") and names[1].startswith("..\\..\\")


# -- anexos --------------------------------------------------------------------

@pytest.mark.parametrize(
    "message_id, attachment_id, filename",
    [
        ("m-2026-09-30-extrato", "att-set-ofx", "extrato-setembro-sgml.ofx"),     # base64url sem padding
        ("m-2026-10-10-extrato", "att-out-ofx", "extrato-outubro-1252.ofx"),      # base64 padrão
        ("m-2026-09-25-comprovante", "att-png", "foto-comprovante.png"),
    ],
)
def test_download_returns_exact_bytes_for_both_wire_encodings(connector, message_id, attachment_id, filename):
    blob = connector.download_attachment(CTX, message_id, attachment_id)
    assert hashlib.sha256(blob.content).hexdigest() == hashlib.sha256(helpers.file_bytes(filename)).hexdigest()
    # O objeto não mostra o conteúdo ao ser impresso.
    assert "OFXHEADER" not in repr(blob) and "PNG" not in repr(blob)


def test_download_over_limit_is_rejected(tmp_path):
    small = FixtureEmailConnector(helpers.FIXTURE_DIR, max_attachment_bytes=100)
    with pytest.raises(AiError) as excinfo:
        small.download_attachment(CTX, "m-2026-09-30-extrato", "att-set-ofx")
    assert excinfo.value.code == "payload_too_large"


def test_base64_decoder_accepts_both_alphabets_with_and_without_padding():
    raw = bytes(range(256)) * 3 + b"\xfb\xff\xfe"   # produz '+', '/', '-' e '_' nos dois alfabetos
    standard = base64.b64encode(raw).decode("ascii")
    url_safe = base64.urlsafe_b64encode(raw).decode("ascii")
    assert "+" in standard and "/" in standard and "-" in url_safe and "_" in url_safe
    for encoded in (standard, standard.rstrip("="), url_safe, url_safe.rstrip("=")):
        assert decode_base64_payload(encoded, 10_000) == raw
    for tail in (b"a", b"ab", b"abc"):   # 2, 1 e 0 caracteres de padding
        expected = raw + tail
        assert decode_base64_payload(base64.b64encode(expected).decode().rstrip("="), 10_000) == expected
    # Quebras de linha no estilo MIME também são aceitas.
    assert decode_base64_payload(base64.encodebytes(raw).decode("ascii"), 10_000) == raw
    assert decode_base64_payload("", 10) == b""


@pytest.mark.parametrize("encoded", ["ab+c_d==", "a", "abc=====", "YWJj!!!!", 12345, None, b"YWJj"])
def test_base64_decoder_rejects_invalid_payloads(encoded):
    with pytest.raises(AiError) as excinfo:
        decode_base64_payload(encoded, 1000)
    assert excinfo.value.code == "connector_unavailable"


def test_encoded_size_is_checked_before_decoding():
    """Texto grande demais E indecodificável: vence o limite de tamanho.

    Se a decodificação viesse antes, o erro seria "anexo ilegível".
    """
    limit = 300
    too_long_and_invalid = "!" * (max_encoded_length(limit) + 1)
    with pytest.raises(AiError) as excinfo:
        decode_base64_payload(too_long_and_invalid, limit)
    assert excinfo.value.code == "payload_too_large"

    # No limite exato passa; um byte acima é recusado.
    assert len(decode_base64_payload(base64.b64encode(b"x" * limit).decode(), limit)) == limit
    with pytest.raises(AiError) as excinfo:
        decode_base64_payload(base64.b64encode(b"x" * (limit + 1)).decode(), limit)
    assert excinfo.value.code == "payload_too_large"


def test_broken_mailbox_directory_is_connector_unavailable(tmp_path):
    with pytest.raises(AiError) as excinfo:
        FixtureEmailConnector(tmp_path / "nao-existe")
    assert excinfo.value.code == "connector_unavailable"
    # Anexo que aponta para fora do diretório da caixa não é lido.
    directory = helpers.copy_mailbox(tmp_path / "caixa", [
        {"id": "m-fora", "from": "a@b.example", "subject": "fora", "date": "2026-10-12T00:00:00Z", "body": "x",
         "attachments": [{"id": "att-fora", "filename": "x.ofx", "file": "../segredo.txt"}]},
    ])
    (tmp_path / "segredo.txt").write_text("fora da caixa", encoding="utf-8")
    with pytest.raises(AiError) as excinfo:
        FixtureEmailConnector(directory).download_attachment(CTX, "m-fora", "att-fora")
    assert excinfo.value.code == "connector_unavailable"


# -- cofre de credenciais ------------------------------------------------------

def test_secret_never_exposes_its_value(caplog):
    value = helpers.FAKE_CREDENTIAL
    secret = Secret(value)
    assert secret.reveal() == value
    rendered = [repr(secret), str(secret), "%s" % secret, "{}".format(secret), f"{secret!r}", repr([secret]),
                repr({"token": secret})]
    assert all(value not in text for text in rendered)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("ai.email").info("credencial=%s", secret)
    assert value not in caplog.text
    # Não serializa: nem JSON da plataforma, nem pickle, nem cópia profunda.
    with pytest.raises(TypeError):
        json_safe({"token": secret})
    with pytest.raises(TypeError):
        json.dumps({"token": secret})
    with pytest.raises(TypeError):
        pickle.dumps(secret)
    with pytest.raises(TypeError):
        copy.deepcopy(secret)
    assert not hasattr(secret, "__dict__")
    with pytest.raises(AttributeError):
        secret.value = "outro"
    with pytest.raises(ValueError):
        Secret("")


def test_env_store_reads_at_use_time_and_only_prefixed_names():
    env = {"AI_EMAIL_CREDENTIAL_CAIXA": helpers.FAKE_CREDENTIAL, "DATABASE_URL": "valor-de-outra-finalidade"}
    store = EnvCredentialStore(env)
    assert store.get("env:AI_EMAIL_CREDENTIAL_CAIXA").reveal() == helpers.FAKE_CREDENTIAL
    # Lido no momento do uso: trocar ou remover a variável vale na chamada seguinte.
    env["AI_EMAIL_CREDENTIAL_CAIXA"] = "rodada-rodada-rodada-rodada"
    assert store.get("env:AI_EMAIL_CREDENTIAL_CAIXA").reveal() == "rodada-rodada-rodada-rodada"
    del env["AI_EMAIL_CREDENTIAL_CAIXA"]
    for reference in ("env:AI_EMAIL_CREDENTIAL_CAIXA", "env:DATABASE_URL", "env:ai_email_credential_x",
                      "vault:qualquer", "sem-esquema", "", None):
        with pytest.raises(AiError) as excinfo:
            store.get(reference)
        assert excinfo.value.code == "connector_unavailable" and excinfo.value.retryable is False
        assert "DATABASE_URL" not in excinfo.value.safe_message
        assert "valor-de-outra-finalidade" not in str(excinfo.value)
    assert helpers.FAKE_CREDENTIAL not in repr(store)


def test_memory_store_and_reference_validation():
    store = helpers.make_store()
    assert store.get(helpers.CREDENTIAL_REF).reveal() == helpers.FAKE_CREDENTIAL
    assert helpers.FAKE_CREDENTIAL not in repr(store) and helpers.FAKE_CREDENTIAL not in str(vars(store))
    store.remove(helpers.CREDENTIAL_REF)
    with pytest.raises(AiError) as excinfo:
        store.get(helpers.CREDENTIAL_REF)
    assert excinfo.value.code == "connector_unavailable"

    assert validate_credential_ref(" env:AI_EMAIL_CREDENTIAL_X ") == "env:AI_EMAIL_CREDENTIAL_X"
    # Um token colado no lugar da referência é recusado (e não ecoado no erro).
    for pasted in ("um token colado por engano com espacos", helpers.FAKE_CREDENTIAL, "env:", "Env:NOME", 123):
        with pytest.raises(AiError) as excinfo:
            validate_credential_ref(pasted)
        assert excinfo.value.code == "invalid_request"
        assert str(pasted) not in excinfo.value.safe_message
    with pytest.raises(AiError):
        InMemoryCredentialStore({"sem esquema": "x"})
