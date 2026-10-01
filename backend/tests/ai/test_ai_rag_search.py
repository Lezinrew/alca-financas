"""RAG lexical: isolamento (AC-01), revogação, versão e ferramentas auxiliares.

Contrato, seção 10: o filtro acontece antes da busca e de novo antes da
entrega; fonte revogada sai do índice; conteúdo antigo não prevalece.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from services.ai import rag, runs
from services.ai.db import scoped_tx
from services.ai.errors import AiError
from services.ai.misc_tools import build_misc_tools
from services.ai.registry import ToolRegistry
from services.ai.scope import resolve_scope

from .support import orchestrator_kit as kit
from .support import seed
from .support.orchestrator_kit import ScriptedGateway, call, response


pytestmark = pytest.mark.integration

RULE = (
    "Regra da casa sobre reembolso de viagens: toda despesa de viagem precisa de comprovante "
    "e deve ser lançada na categoria Transporte até o dia cinco do mês seguinte."
)
QUESTION = "Qual é a regra para reembolso de viagens?"


def _index(pool, ctx, content=RULE, source_ref="nota:regra-viagens", **extra):
    params = dict(source_kind="rule", source_ref=source_ref, title="Regra de viagens", content=content,
                  document_date=date(2026, 9, 15))
    params.update(extra)
    return rag.index_document(pool, ctx, **params)


def _member(pool, world, space_id):
    user_id = seed.create_user(pool, "membro-%s@example.test" % seed.new_id()[:8], "Membro Teste")
    seed.add_tenant_member(pool, world.tenant_id, user_id, "member")
    seed.add_space_member(pool, world.tenant_id, space_id, user_id, "member")
    return resolve_scope(pool, user_id=user_id, requested_tenant_id=world.tenant_id, requested_space_id=space_id)


# ---------------------------------------------------------- indexar e buscar

def test_search_returns_chunks_with_source_date_and_version(pool, world):
    ctx = world.context(pool)
    indexed = _index(pool, ctx)
    assert indexed["version"] == 1 and indexed["chunks"] == 1 and indexed["unchanged"] is False

    results = rag.search(pool, ctx, QUESTION)

    assert len(results) == 1
    chunk = results[0]
    assert set(chunk) == {
        "chunk_id", "document_id", "seq", "content", "title", "source_kind", "source_ref", "version",
        "document_date", "indexed_at", "content_hash", "score",
    }
    assert chunk["document_id"] == indexed["document_id"] and chunk["content"] == RULE
    assert chunk["source_kind"] == "rule" and chunk["source_ref"] == "nota:regra-viagens"
    assert chunk["version"] == 1 and chunk["document_date"] == "2026-09-15"
    assert chunk["indexed_at"].endswith("Z") and chunk["content_hash"] == indexed["content_hash"]
    assert isinstance(chunk["score"], str) and float(chunk["score"]) > 0     # nunca float no resultado

    # Auditoria por referência: hash e contagens, sem o texto indexado.
    event = kit.audit_events(pool, world.tenant_id, "ai.rag.document.indexed")[0]
    assert event["metadata"]["content_hash"] == indexed["content_hash"]
    assert "reembolso" not in str(event["metadata"])


def test_search_ranks_the_most_relevant_document_first_and_respects_limit(pool, world):
    ctx = world.context(pool)
    _index(pool, ctx)
    _index(pool, ctx, content="Lista de compras do mercado: arroz, feijão e café.", source_ref="nota:mercado",
           title="Mercado")
    for index in range(4):
        _index(pool, ctx, content="Viagens de trabalho número %d: guardar recibos de táxi." % index,
               source_ref="nota:viagem-%d" % index, title="Viagem %d" % index)

    results = rag.search(pool, ctx, QUESTION, limit=3)

    assert len(results) == 3
    assert results[0]["source_ref"] == "nota:regra-viagens"          # casa mais termos da pergunta
    assert all("mercado" not in item["source_ref"] for item in results)


@pytest.mark.parametrize("question", ["o que de para", "xilofone quântico", "???"])
def test_search_without_matching_terms_returns_nothing(pool, world, question):
    ctx = world.context(pool)
    _index(pool, ctx)
    assert rag.search(pool, ctx, question) == []


def test_long_document_is_split_into_chunks(pool, world):
    ctx = world.context(pool)
    paragraphs = ["Parágrafo %d sobre orçamento doméstico. %s" % (index, "palavra " * 60) for index in range(6)]
    indexed = _index(pool, ctx, content="\n\n".join(paragraphs), source_ref="nota:longa")
    assert indexed["chunks"] >= 4
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT seq, length(content) AS size FROM ai_rag_chunks ORDER BY seq")
        rows = cursor.fetchall()
    assert [row["seq"] for row in rows] == list(range(indexed["chunks"]))
    assert all(row["size"] <= rag.CHUNK_TARGET_CHARS for row in rows)


@pytest.mark.unit
def test_split_chunks_keeps_all_words_and_handles_oversized_tokens():
    text = "primeiro bloco curto\n\n" + "longo " * 400 + "\n\n" + "x" * 2000
    chunks = rag.split_chunks(text, target=200)
    assert all(0 < len(chunk) <= 200 for chunk in chunks)
    joined = " ".join(chunks)
    assert joined.count("longo") == 400 and joined.count("x") >= 2000
    assert rag.split_chunks("   \n\n  ") == []


# ------------------------------------------------------------------ AC-01

def test_document_of_another_tenant_is_never_returned(pool, world, other_world):
    mine, theirs = world.context(pool), other_world.context(pool)
    my_doc = _index(pool, mine)
    their_doc = _index(pool, theirs, content=RULE + " Segredo sintético da organização beta.")

    assert [item["document_id"] for item in rag.search(pool, mine, QUESTION)] == [my_doc["document_id"]]
    assert [item["document_id"] for item in rag.search(pool, theirs, QUESTION)] == [their_doc["document_id"]]
    assert "beta" not in str(rag.search(pool, mine, "segredo sintético organização beta"))
    with pytest.raises(AiError) as excinfo:
        rag.revoke_document(pool, mine, their_doc["document_id"])
    assert excinfo.value.code == "not_found"
    assert len(rag.search(pool, theirs, QUESTION)) == 1


def test_document_of_another_space_is_never_returned(pool, world):
    personal, business = world.context(pool, "personal"), world.context(pool, "business")
    business_doc = _index(pool, business, content=RULE + " Margem sintética do negócio.")

    assert rag.search(pool, personal, QUESTION) == []
    assert rag.search(pool, personal, "margem sintética negócio") == []
    assert len(rag.search(pool, business, QUESTION)) == 1
    with pytest.raises(AiError) as excinfo:
        rag.revoke_document(pool, personal, business_doc["document_id"])
    assert excinfo.value.code == "not_found"


def test_acl_restricts_document_to_listed_members(pool, world):
    owner = world.context(pool)
    partner = _member(pool, world, world.personal_space_id)
    restricted = _index(pool, owner, source_ref="nota:so-titular", acl_user_ids=[world.user_id])
    shared = _index(pool, owner, source_ref="nota:familia", content=RULE + " Vale para a família toda.")

    owner_docs = {item["document_id"] for item in rag.search(pool, owner, QUESTION)}
    partner_docs = {item["document_id"] for item in rag.search(pool, partner, QUESTION)}

    assert owner_docs == {restricted["document_id"], shared["document_id"]}
    assert partner_docs == {shared["document_id"]}          # ACL nula = todos do espaço
    with pytest.raises(AiError) as excinfo:
        rag.revoke_document(pool, partner, restricted["document_id"])
    assert excinfo.value.code == "not_found"


def test_member_outside_the_acl_cannot_replace_a_restricted_document(pool, world):
    """Reindexar a mesma ``source_ref`` revoga a versão vigente e apaga seus
    trechos. Quem não está na ACL não pode fazer isso: trocaria — e tornaria
    público — um documento que não consegue nem ler."""
    owner = world.context(pool)
    partner = _member(pool, world, world.personal_space_id)
    private = _index(pool, owner, source_ref="nota:privada", acl_user_ids=[world.user_id])
    assert rag.search(pool, partner, QUESTION) == []

    attempts = [
        dict(content="Conteúdo trocado pelo outro membro sobre viagens."),      # texto novo, ACL aberta
        dict(content=RULE, acl_user_ids=[world.user_id]),                       # cópia idêntica: nem "unchanged"
        dict(content=RULE, acl_user_ids=[partner.actor_id]),                    # tomar o documento para si
    ]
    for extra in attempts:
        with pytest.raises(AiError) as excinfo:
            _index(pool, partner, source_ref="nota:privada", **extra)
        assert excinfo.value.code == "conflict"
        assert private["document_id"] not in str(excinfo.value.to_dict())

    # A versão do titular continua vigente, inteira e restrita a ele.
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT id, version, revoked_at FROM ai_rag_documents")
        rows = cursor.fetchall()
    assert [(str(row["id"]), row["version"], row["revoked_at"]) for row in rows] == [(private["document_id"], 1, None)]
    found = rag.search(pool, owner, QUESTION)
    assert [(item["document_id"], item["version"], item["content"]) for item in found] == [
        (private["document_id"], 1, RULE)
    ]
    assert rag.search(pool, partner, QUESTION) == []
    assert rag.search(pool, partner, "conteúdo trocado outro membro") == []


def test_members_of_the_acl_and_open_documents_can_still_be_replaced(pool, world):
    owner = world.context(pool)
    partner = _member(pool, world, world.personal_space_id)
    # Documento restrito aos dois: qualquer um dos dois pode atualizar.
    shared = _index(pool, owner, source_ref="nota:casal", acl_user_ids=[world.user_id, partner.actor_id])
    updated = _index(pool, partner, source_ref="nota:casal", content=RULE + " Atualizada pelo casal.",
                     acl_user_ids=[world.user_id, partner.actor_id])
    assert updated["version"] == 2 and updated["document_id"] != shared["document_id"]
    # Documento aberto (ACL nula) é de todos os membros do espaço.
    _index(pool, owner, source_ref="nota:aberta")
    assert _index(pool, partner, source_ref="nota:aberta", content=RULE + " Nova redação.")["version"] == 2
    # Depois de revogado pelo dono, o nome fica livre: a restrição protege o
    # documento vigente, não reserva a referência para sempre.
    private = _index(pool, owner, source_ref="nota:privada", acl_user_ids=[world.user_id])
    rag.revoke_document(pool, owner, private["document_id"])
    assert _index(pool, partner, source_ref="nota:privada", content="Nota nova do outro membro.")["version"] == 2


def test_text_the_database_refuses_never_escapes_as_a_driver_error(pool, world):
    """Texto extraído de PDF pode trazer NUL. No conteúdo ele é ruído (é limpo);
    em título, referência e pergunta é pedido inválido — nunca ValueError."""
    ctx = world.context(pool)
    dirty = "Regra de reembolso\u0000 de viagens\u000c exige comprovante\ud800 fiscal."
    indexed = _index(pool, ctx, content=dirty, source_ref="nota:pdf")

    assert indexed["chunks"] == 1
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT content FROM ai_rag_chunks")
        assert cursor.fetchone()["content"] == "Regra de reembolso  de viagens  exige comprovante  fiscal."
    assert len(rag.search(pool, ctx, "reembolso comprovante fiscal")) == 1
    # O mesmo arquivo reindexado dá o mesmo hash: nada muda.
    assert _index(pool, ctx, content=dirty, source_ref="nota:pdf")["unchanged"] is True

    for extra in ({"title": "Regra\u0000"}, {"title": "Regra\nem duas linhas"}, {"title": "Regra \ud800"},
                  {"source_ref": "nota:x\n"}, {"source_ref": "nota:\ud800"}, {"source_ref": "nota:\u007f"}):
        with pytest.raises(AiError) as excinfo:
            _index(pool, ctx, **extra)
        assert excinfo.value.code == "invalid_request", extra
    for question in ("pergunta\u0000x", "reembolso \ud800", "reembolso\u0007"):
        with pytest.raises(AiError) as excinfo:
            rag.search(pool, ctx, question)
        assert excinfo.value.code == "invalid_request"
    # Quebra de linha na pergunta é texto normal.
    assert len(rag.search(pool, ctx, "reembolso\nde viagens")) == 1
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_documents") == 1


def test_acl_must_list_members_of_the_space(pool, world, other_world):
    ctx = world.context(pool)
    for acl in ([other_world.user_id], [], ["nao-e-uuid"]):
        with pytest.raises(AiError) as excinfo:
            _index(pool, ctx, acl_user_ids=acl)
        assert excinfo.value.code == "invalid_request"
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_documents") == 0


# ------------------------------------------------- pré-filtro e rechecagem

def _seed_out_of_scope_documents(pool, world, other_world):
    """Documentos com o MESMO texto em todos os lugares em que o ator não pode ler."""
    owner = world.context(pool, "personal")
    partner = _member(pool, world, world.personal_space_id)
    visible = _index(pool, owner, source_ref="nota:visivel")
    hidden = {
        "outro tenant": _index(pool, other_world.context(pool), source_ref="nota:tenant"),
        "outro espaço": _index(pool, world.context(pool, "business"), source_ref="nota:espaco"),
        "fora da ACL": _index(pool, owner, source_ref="nota:acl", acl_user_ids=[world.user_id]),
    }
    revoked = _index(pool, owner, source_ref="nota:revogada")
    return owner, partner, visible, hidden, revoked


def test_prefilter_excludes_out_of_scope_documents_from_the_search_itself(pool, world, other_world):
    owner, partner, visible, hidden, revoked = _seed_out_of_scope_documents(pool, world, other_world)
    rag.revoke_document(pool, owner, revoked["document_id"])

    # Só a primeira barreira, sem a rechecagem.
    candidates = rag._candidates(pool, partner, QUESTION, 50)

    assert {str(item["document_id"]) for item in candidates} == {visible["document_id"]}


def test_recheck_drops_candidates_that_are_no_longer_deliverable(pool, world, other_world):
    owner, partner, visible, hidden, revoked = _seed_out_of_scope_documents(pool, world, other_world)

    def candidate(document_id, version=1):
        return {"chunk_id": seed.new_id(), "document_id": document_id, "seq": 0, "content": "x",
                "title": "t", "source_kind": "rule", "source_ref": "r", "version": version,
                "document_date": None, "indexed_at": None, "content_hash": "0" * 64, "score": "1"}

    rag.revoke_document(pool, owner, revoked["document_id"])
    # Só a segunda barreira: candidatos "vindos de um índice desatualizado".
    stale = [candidate(visible["document_id"])]
    stale += [candidate(item["document_id"]) for item in hidden.values()]
    stale += [candidate(revoked["document_id"]), candidate(seed.new_id()),
              candidate(visible["document_id"], version=9)]

    delivered = rag._recheck(pool, partner, stale)

    assert [(item["document_id"], item["version"]) for item in delivered] == [(visible["document_id"], 1)]


def test_document_revoked_between_search_and_delivery_is_not_delivered(pool, world, monkeypatch):
    ctx = world.context(pool)
    kept = _index(pool, ctx, source_ref="nota:fica")
    gone = _index(pool, ctx, source_ref="nota:some")
    real_candidates = rag._candidates

    def racing(pool_, ctx_, question, limit):
        found = real_candidates(pool_, ctx_, question, limit)
        # A busca já enxergou os dois; a revogação é confirmada antes da entrega.
        assert {str(item["document_id"]) for item in found} == {kept["document_id"], gone["document_id"]}
        rag.revoke_document(pool_, ctx_, gone["document_id"])
        return found

    monkeypatch.setattr(rag, "_candidates", racing)

    results = rag.search(pool, ctx, QUESTION)

    assert [item["document_id"] for item in results] == [kept["document_id"]]


def test_acl_tightened_between_search_and_delivery_is_respected(pool, world, monkeypatch):
    owner = world.context(pool)
    partner = _member(pool, world, world.personal_space_id)
    document = _index(pool, owner)
    real_candidates = rag._candidates

    def racing(pool_, ctx_, question, limit):
        found = real_candidates(pool_, ctx_, question, limit)
        with scoped_tx(pool_, world.tenant_id) as cursor:
            cursor.execute("UPDATE ai_rag_documents SET acl_user_ids = %s::uuid[] WHERE id = %s",
                           ([world.user_id], document["document_id"]))
        return found

    monkeypatch.setattr(rag, "_candidates", racing)
    assert rag.search(pool, partner, QUESTION) == []


# --------------------------------------------------- revogação e versões

def test_revoked_document_disappears_from_search_and_index(pool, world):
    ctx = world.context(pool)
    indexed = _index(pool, ctx)
    assert len(rag.search(pool, ctx, QUESTION)) == 1

    revoked = rag.revoke_document(pool, ctx, indexed["document_id"])

    assert revoked["revoked"] is True and revoked["revoked_at"].endswith("Z")
    assert rag.search(pool, ctx, QUESTION) == []
    # Fonte revogada sai do índice: os trechos são apagados, não só escondidos.
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_chunks") == 0
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_documents", "revoked_at IS NOT NULL") == 1
    again = rag.revoke_document(pool, ctx, indexed["document_id"])           # idempotente
    assert again["revoked_at"] == revoked["revoked_at"]
    assert len(kit.audit_events(pool, world.tenant_id, "ai.rag.document.revoked")) == 1
    for bad in ("nao-e-uuid", seed.new_id()):
        with pytest.raises(AiError) as excinfo:
            rag.revoke_document(pool, ctx, bad)
        assert excinfo.value.code == "not_found"


def test_reindexing_creates_a_new_version_and_old_content_stops_matching(pool, world):
    ctx = world.context(pool)
    first = _index(pool, ctx)
    assert _index(pool, ctx)["unchanged"] is True                 # mesmo conteúdo: nada muda
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_documents") == 1

    updated = "Nova orientação: despesas com hospedagem exigem aprovação prévia do titular."
    second = _index(pool, ctx, content=updated)

    assert second["version"] == 2 and second["document_id"] != first["document_id"]
    assert rag.search(pool, ctx, QUESTION) == []                  # o texto antigo não responde mais
    results = rag.search(pool, ctx, "hospedagem aprovação prévia")
    assert [(item["document_id"], item["version"]) for item in results] == [(second["document_id"], 2)]
    with scoped_tx(pool, world.tenant_id) as cursor:
        cursor.execute("SELECT version, revoked_at IS NOT NULL AS revoked FROM ai_rag_documents ORDER BY version")
        assert [(row["version"], row["revoked"]) for row in cursor.fetchall()] == [(1, True), (2, False)]
        cursor.execute("SELECT DISTINCT document_id FROM ai_rag_chunks")
        assert [str(row["document_id"]) for row in cursor.fetchall()] == [second["document_id"]]


def test_changing_only_the_acl_creates_a_new_version(pool, world):
    owner = world.context(pool)
    partner = _member(pool, world, world.personal_space_id)
    first = _index(pool, owner, acl_user_ids=[world.user_id])
    # Mesmo conteúdo e mesma ACL: nada muda (a ACL gravada é comparada como lista).
    assert _index(pool, owner, acl_user_ids=[world.user_id])["unchanged"] is True
    assert rag.search(pool, partner, QUESTION) == []

    opened = _index(pool, owner, acl_user_ids=None)

    assert opened["unchanged"] is False and opened["version"] == 2
    assert opened["content_hash"] == first["content_hash"]
    assert [item["version"] for item in rag.search(pool, partner, QUESTION)] == [2]


@pytest.mark.parametrize(
    "extra, code",
    [
        ({"source_kind": "segredo"}, "invalid_request"),
        ({"source_ref": "com espaco"}, "invalid_request"),
        ({"source_ref": ""}, "invalid_request"),
        ({"title": "  "}, "invalid_request"),
        ({"content": "   "}, "invalid_request"),
        ({"content": 123}, "invalid_request"),
        ({"document_date": "2026-09-15"}, "invalid_request"),
        ({"content": "x" * (rag.CONTENT_MAX_CHARS + 1)}, "payload_too_large"),
    ],
)
def test_index_document_validation(pool, world, extra, code):
    with pytest.raises(AiError) as excinfo:
        _index(pool, world.context(pool), **extra)
    assert excinfo.value.code == code
    assert seed.count_rows(pool, world.tenant_id, "ai_rag_documents") == 0


@pytest.mark.parametrize("question, limit", [("", 5), ("   ", 5), ("x" * 501, 5), (QUESTION, 0), (QUESTION, 11)])
def test_search_validation(pool, world, question, limit):
    with pytest.raises(AiError) as excinfo:
        rag.search(pool, world.context(pool), question, limit=limit)
    assert excinfo.value.code == "invalid_request"


# -------------------------------------------------------- ferramentas

def _registry(pool, settings):
    registry = ToolRegistry(settings)
    registry.register_all(build_misc_tools(pool, settings))
    return registry


def test_rag_tool_requires_grant_and_returns_sources_without_facts(pool, world, settings):
    ctx = world.context(pool)
    indexed = _index(pool, ctx)
    registry = _registry(pool, settings)
    assert registry.get("rag.search_personal").effect == "read"

    with pytest.raises(AiError) as excinfo:
        registry.execute("rag.search_personal", {"question": QUESTION}, ctx, [])
    assert excinfo.value.code == "capability_denied"

    kit.grant(pool, world, ["rag.search_personal"])
    with scoped_tx(pool, world.tenant_id) as cursor:
        from services.ai import policy
        grants = policy.load_active_grants(cursor, ctx)
    result = registry.execute("rag.search_personal", {"question": QUESTION, "limit": 2}, ctx, grants).to_dict()

    ref = "rag:%s:v1" % indexed["document_id"]
    assert result["facts"] == []                      # trecho de nota não é fato financeiro
    assert result["data"]["count"] == 1 and result["data"]["chunks"][0]["source"] == ref
    assert result["data"]["chunks"][0]["content"] == RULE
    assert [(s["ref"], s["kind"], s["label"]) for s in result["sources"]] == [(ref, "rag", "Regra de viagens")]
    assert result["sources"][0]["extra"]["document_date"] == "2026-09-15"
    assert result["sources"][0]["extra"]["version"] == 1

    for bad in ({"question": QUESTION, "financial_space_id": world.business_space_id},
                {"question": QUESTION, "limit": 99}, {"question": ""}, {}):
        with pytest.raises(AiError) as excinfo:
            registry.execute("rag.search_personal", bad, ctx, grants)
        assert excinfo.value.code == "invalid_request"


def test_whatsapp_respond_never_simulates_delivery(pool, world, settings):
    ctx = world.context(pool)
    grant_id = kit.grant(pool, world, ["whatsapp.respond"])
    assert grant_id
    with scoped_tx(pool, world.tenant_id) as cursor:
        from services.ai import policy
        grants = policy.load_active_grants(cursor, ctx)
    args = {"conversation_ref": "conversa-sintetica-1", "content": "Olá"}

    # Flag desligada (padrão): a capacidade nem existe para o modelo.
    off = _registry(pool, settings)
    definition = off.get("whatsapp.respond")
    assert definition.effect == "message" and tuple(definition.requires_flags) == ("whatsapp_enabled",)
    assert [spec["name"] for spec in off.specs_for(grants)] == []
    with pytest.raises(AiError) as excinfo:
        off.execute("whatsapp.respond", args, ctx, grants)
    assert excinfo.value.code == "capability_denied"

    # Flag ligada: sem vínculo de remetente verificado, falha explícita.
    on = _registry(pool, replace(settings, whatsapp_enabled=True))
    with pytest.raises(AiError) as excinfo:
        on.execute("whatsapp.respond", args, ctx, grants)
    assert excinfo.value.code == "connector_unavailable" and excinfo.value.retryable is False
    assert seed.count_rows(pool, world.tenant_id, "ai_outbox") == 0


def test_finance_question_uses_real_rag_tool_through_the_orchestrator(pool, world, other_world, settings):
    ctx = world.context(pool)
    indexed = _index(pool, ctx)
    _index(pool, other_world.context(pool), content=RULE + " Dado sintético de outra organização.")
    kit.grant(pool, world, ["rag.search_personal"])
    registry = _registry(pool, settings)
    gateway = ScriptedGateway([
        response(tool_calls=[call("rag.search_personal", {"question": QUESTION})]),
        response(summary="A regra pede comprovante e lançamento em Transporte."),
    ])
    run_id = kit.enqueue(pool, ctx, settings, message=QUESTION)

    done = kit.execute_next(pool, settings, registry, gateway)

    assert done["outcome"]["status"] == "completed"
    view = runs.get_run_view(pool, ctx, run_id)
    assert [source["ref"] for source in view["sources"]] == ["rag:%s:v1" % indexed["document_id"]]
    assert view["facts"] == [] and view["progress"]["steps"][1]["label"] == "Buscando nos seus documentos"
    assert gateway.tool_names_offered()[0] == ["rag.search_personal"]
    assert "outra organização" not in kit.tool_messages(gateway.requests[1])[0].content
