"""Registro de modelos: carga, regras de aprovação e elegibilidade (AC-07, AC-10)."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from services.ai.gateway.base import PURPOSE_WRITE, TASK_SIMPLE, TASK_VISION, ChatMessage, ModelRequest
from services.ai.gateway.models import (
    ModelConfigError,
    ModelRegistry,
    is_private_host,
    load_model_routes,
    routes_from_document,
)
from services.ai.settings import AiSettings
from services.ai.types import Privacy

from .support.gateway_harness import (
    ANSWER_SCHEMA,
    DIGEST_A,
    READ_TOOL,
    external_route,
    gateway_settings,
    local_route,
    make_ctx,
    user_request,
)


pytestmark = pytest.mark.unit

CONFIG_DIR = Path(AiSettings().resolved_model_registry_path()).parent

APPROVED_OLLAMA = {
    "alias": "local-aprovada",
    "provider": "ollama",
    "model_id": "modelo-teste:1b",
    "locality": "local",
    "priority": 10,
    "task_classes": ["simple_extraction"],
    "supports_tools": True,
    "supports_json": True,
    "supports_vision": False,
    "context_window": 8192,
    "state": "approved",
    "approved_purposes": ["read"],
    "digest": DIGEST_A,
    "evidence": "relatorio-sintetico-001",
}

APPROVED_EXTERNAL = {
    "alias": "externa-aprovada",
    "provider": "openai_compatible",
    "model_id": "modelo-externo-teste",
    "locality": "external",
    "priority": 50,
    "task_classes": ["complex_tools"],
    "supports_tools": True,
    "supports_json": True,
    "supports_vision": False,
    "context_window": 100000,
    "state": "approved",
    "approved_purposes": ["read"],
    "privacy": ["cloud_allowed"],
    "base_url": "https://api.exemplo.test/v1",
    "credential_env": "PROVEDOR_TESTE_API_KEY",
    "max_cost_micros_per_call": 5000,
    "evidence": "relatorio-sintetico-002",
}


def load(*routes):
    return routes_from_document({"routes": list(routes)})


def changed(base, **changes):
    route = copy.deepcopy(base)
    for key, value in changes.items():
        if value is ...:
            route.pop(key, None)
        else:
            route[key] = value
    return route


# ---------------------------------------------------------------------------
# Arquivos reais do repositório
# ---------------------------------------------------------------------------

def test_default_registry_file_loads_with_only_local_candidates():
    routes = load_model_routes(CONFIG_DIR / "models.json")
    by_alias = {route.alias: route for route in routes}
    assert set(by_alias) == {"local-qwen25-coder-14b", "local-gemma4"}
    assert all(route.is_local and route.provider == "ollama" and route.state == "candidate" for route in routes)

    qwen = by_alias["local-qwen25-coder-14b"]
    assert qwen.model_id == "qwen2.5-coder:14b" and qwen.context_window == 32768
    assert qwen.digest == "9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849"
    assert (qwen.supports_tools, qwen.supports_json, qwen.supports_vision) == (True, True, False)

    gemma = by_alias["local-gemma4"]
    assert gemma.model_id == "gemma4:latest"
    assert gemma.digest == "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb"
    assert (gemma.supports_tools, gemma.supports_json, gemma.supports_vision) == (True, True, True)
    # A nota sobre "latest" está no arquivo, para quem for aprovar a rota.
    raw = (CONFIG_DIR / "models.json").read_text(encoding="utf-8")
    assert "latest" in json.loads(raw)["routes"][1]["extra"]["_nota"]


def test_default_registry_serves_nothing_until_homologation():
    registry = ModelRegistry.from_settings(gateway_settings())
    assert registry.eligible(user_request(), make_ctx()).routes == []
    # E a rota "latest" não pode ser promovida a aprovada.
    document = json.loads((CONFIG_DIR / "models.json").read_text(encoding="utf-8"))
    gemma = changed(document["routes"][1], state="approved", approved_purposes=["read"], evidence="relatorio-x")
    with pytest.raises(ModelConfigError, match="latest"):
        load(gemma)


def test_example_file_loads_and_pins_no_commercial_version():
    routes = load_model_routes(CONFIG_DIR / "models.example.json")
    assert {route.provider for route in routes} == {"anthropic", "openai_compatible"}
    assert all(route.state == "candidate" and not route.is_local for route in routes)
    assert all(route.model_id == "DEFINIR_APOS_HOMOLOGACAO" for route in routes)
    assert all(route.max_cost_micros_per_call is None for route in routes)
    aggregated = [route for route in routes if route.extra.get("aggregator") == "openrouter"]
    assert len(aggregated) == 1 and aggregated[0].upstream_provider
    # Mesmo com candidatas liberadas e nuvem ligada, o marcador não é elegível.
    registry = ModelRegistry(routes, gateway_settings(cloud_enabled=True, allow_candidate_models=True))
    request = user_request(task_class="complex_tools")
    eligibility = registry.eligible(request, make_ctx(Privacy.CLOUD_ALLOWED))
    assert eligibility.routes == []
    assert {item.reason for item in eligibility.excluded} == {"model_undefined"}


# ---------------------------------------------------------------------------
# Regras de aprovação
# ---------------------------------------------------------------------------

def test_valid_approved_routes_load():
    routes = load(APPROVED_OLLAMA, APPROVED_EXTERNAL)
    assert [route.alias for route in routes] == ["local-aprovada", "externa-aprovada"]
    assert routes[0].privacy == ("local_only", "cloud_redacted", "cloud_allowed")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"model_id": "modelo-teste:latest"}, "latest"),
        ({"model_id": "modelo-teste"}, "tag explícita"),
        ({"digest": ...}, "digest"),
        ({"digest": "abc123"}, "64 caracteres"),
        ({"digest": "A" * 64}, "64 caracteres"),
        ({"evidence": ...}, "evidence"),
        ({"approved_purposes": []}, "approved_purposes"),
        ({"model_id": "DEFINIR_APOS_HOMOLOGACAO"}, "model_id"),
    ],
)
def test_approved_ollama_route_requires_pinned_tag_digest_and_evidence(changes, message):
    with pytest.raises(ModelConfigError, match=message):
        load(changed(APPROVED_OLLAMA, **changes))


def test_same_defects_are_tolerated_while_candidate():
    # A regra é sobre o que pode ser SELECIONADO em produção, não sobre rascunho.
    draft = changed(APPROVED_OLLAMA, state="candidate", model_id="modelo-teste:latest", digest=..., evidence=...)
    route = load(draft)[0]
    assert route.state == "candidate"


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"credential_env": ...}, "credential_env"),
        ({"max_cost_micros_per_call": ...}, "max_cost_micros_per_call"),
        ({"max_cost_micros_per_call": 0}, "max_cost_micros_per_call"),
        ({"evidence": ...}, "evidence"),
        ({"extra": {"aggregator": "openrouter"}}, "upstream_provider"),
        ({"model_id": "~fornecedor/modelo-latest"}, "latest"),
        ({"base_url": ...}, "base_url"),
        ({"base_url": "http://api.exemplo.test/v1"}, "https"),
        ({"privacy": ...}, "privacy"),
        ({"privacy": ["local_only", "cloud_allowed"]}, "local_only"),
    ],
)
def test_approved_external_route_requirements(changes, message):
    with pytest.raises(ModelConfigError, match=message):
        load(changed(APPROVED_EXTERNAL, **changes))


def test_aggregator_route_with_pinned_upstream_loads():
    pinned = changed(APPROVED_EXTERNAL, extra={"aggregator": "openrouter"}, upstream_provider="fornecedor-teste")
    route = load(pinned)[0]
    assert route.upstream_provider == "fornecedor-teste"


def test_credential_env_must_be_a_variable_name_not_a_value():
    with pytest.raises(ModelConfigError, match="NOME"):
        load(changed(APPROVED_EXTERNAL, credential_env="valor-colado-por-engano-no-json"))


# ---------------------------------------------------------------------------
# Rota local não sai da máquina
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "base_url",
    [
        "https://ollama.exemplo.com",
        "http://8.8.8.8:11434",
        "http://169.254.169.254",
        "http://exemplo.internal.corp:11434",
        # Sem ponto, mas não são nomes: no Linux o getaddrinfo lê as duas formas
        # como o número de 32 bits de 8.8.8.8 (estilo inet_aton).
        "http://134744072:11434",
        "http://0x08080808:11434",
        # Octeto com zero à esquerda: decimal para uns, octal para outros.
        "http://010.0.0.1:11434",
        "http://8.8.8:11434",
    ],
)
def test_local_route_pointing_to_public_host_is_rejected(base_url):
    with pytest.raises(ModelConfigError, match="loopback ou rede privada"):
        load(changed(APPROVED_OLLAMA, base_url=base_url))
    # Vale também para candidatas: com allow_candidate_models elas recebem pedidos.
    with pytest.raises(ModelConfigError, match="loopback ou rede privada"):
        load(changed(APPROVED_OLLAMA, state="candidate", base_url=base_url))


@pytest.mark.parametrize(
    "base_url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://ollama:11434",
        "http://10.0.0.5:11434",
        "http://[::1]:11434",
    ],
)
def test_local_route_accepts_loopback_and_private_network(base_url):
    assert load(changed(APPROVED_OLLAMA, base_url=base_url))[0].base_url == base_url


def test_ollama_base_url_from_settings_passes_through_the_same_check():
    routes = load(APPROVED_OLLAMA)
    resolved = ModelRegistry(routes, gateway_settings(ollama_base_url="http://127.0.0.1:11999")).routes[0]
    assert resolved.base_url == "http://127.0.0.1:11999"
    with pytest.raises(ModelConfigError, match="loopback ou rede privada"):
        ModelRegistry(routes, gateway_settings(ollama_base_url="https://ollama.exemplo.com"))


@pytest.mark.parametrize("model_id", ["gemma4:cloud", "gemma4:31b-cloud", "modelo:cloud-preview"])
def test_local_route_rejects_remote_model_names(model_id):
    with pytest.raises(ModelConfigError, match="remoto/cloud"):
        load(changed(APPROVED_OLLAMA, state="candidate", model_id=model_id))


def test_is_private_host():
    private = ("127.0.0.1", "localhost", "::1", "192.168.1.9", "172.16.0.1", "ollama", "ollama-gpu", "ollama_1", "a")
    assert all(is_private_host(host) for host in private)
    assert not any(is_private_host(host) for host in ("8.8.8.8", "exemplo.com", "169.254.169.254", "0.0.0.0", ""))
    # Rótulo único só vale como NOME (começa por letra). Formas numéricas que o
    # sistema converteria em endereço público são recusadas.
    numeric = ("134744072", "0x08080808", "0X08080808", "017700000001", "2130706433", "1", "8", "127.1", "0x7f.1")
    assert not any(is_private_host(host) for host in numeric)
    assert not any(is_private_host(host) for host in ("-ollama", "ollama-", "ollama!", "010.0.0.1", "::ffff:8.8.8.8"))


def test_accepted_model_ids_must_be_a_list_of_names():
    base = dict(APPROVED_EXTERNAL, extra={"aggregator": "openrouter"}, upstream_provider="fornecedor-teste")
    ok = changed(base, extra={"aggregator": "openrouter", "accepted_model_ids": ["fornecedor/modelo-canonico"]})
    assert load(ok)[0].extra["accepted_model_ids"] == ["fornecedor/modelo-canonico"]
    for bad in ("fornecedor/modelo", [""], [7], {"a": 1}):
        with pytest.raises(ModelConfigError, match="accepted_model_ids"):
            load(changed(base, extra={"aggregator": "openrouter", "accepted_model_ids": bad}))


# ---------------------------------------------------------------------------
# Formato do arquivo
# ---------------------------------------------------------------------------

def test_malformed_registry_is_rejected_with_clear_error(tmp_path):
    with pytest.raises(ModelConfigError, match="não encontrado"):
        load_model_routes(tmp_path / "ausente.json")
    broken = tmp_path / "quebrado.json"
    broken.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(ModelConfigError, match="JSON válido"):
        load_model_routes(broken)
    with pytest.raises(ModelConfigError, match="routes"):
        routes_from_document({"rotas": []})
    with pytest.raises(ModelConfigError, match="chave desconhecida: suports_tools"):
        load(changed(APPROVED_OLLAMA, suports_tools=True))
    with pytest.raises(ModelConfigError, match="obrigatórios ausentes: supports_vision"):
        load(changed(APPROVED_OLLAMA, supports_vision=...))
    with pytest.raises(ModelConfigError, match="alias duplicado"):
        load(APPROVED_OLLAMA, APPROVED_OLLAMA)
    with pytest.raises(ModelConfigError, match="state"):
        load(changed(APPROVED_OLLAMA, state="homologado"))
    with pytest.raises(ModelConfigError, match="true ou false"):
        load(changed(APPROVED_OLLAMA, supports_tools="sim"))


# ---------------------------------------------------------------------------
# Elegibilidade
# ---------------------------------------------------------------------------

BASE = "http://127.0.0.1:1"


def eligible_aliases(routes, request, ctx=None, **settings):
    registry = ModelRegistry(routes, gateway_settings(**settings))
    result = registry.eligible(request, ctx or make_ctx())
    return [route.alias for route in result.routes], dict(result.excluded)


def test_routes_are_ordered_by_priority_then_alias():
    routes = [local_route("c", BASE, 30), local_route("b", BASE, 10), local_route("a", BASE, 10)]
    assert eligible_aliases(routes, user_request())[0] == ["a", "b", "c"]


def test_ac10_route_without_required_capability_is_never_selected():
    plain = local_route("sem-capacidades", BASE, 1, supports_tools=False, supports_json=False, supports_vision=False)
    full = local_route("completa", BASE, 2)
    routes = [plain, full]

    # Sem exigência, a de maior prioridade vem primeiro.
    assert eligible_aliases(routes, user_request())[0] == ["sem-capacidades", "completa"]

    selected, excluded = eligible_aliases(routes, user_request(tools=[READ_TOOL]))
    assert selected == ["completa"] and excluded == {"sem-capacidades": "needs_tools"}

    selected, excluded = eligible_aliases(routes, user_request(response_schema=ANSWER_SCHEMA))
    assert selected == ["completa"] and excluded == {"sem-capacidades": "needs_json"}

    selected, excluded = eligible_aliases(routes, user_request(images=[b"\x89PNG\r\n\x1a\nsintetico"]))
    assert selected == ["completa"] and excluded == {"sem-capacidades": "needs_vision"}

    # Classe de tarefa "vision" exige visão mesmo sem imagem anexada.
    selected, excluded = eligible_aliases(routes, user_request(task_class=TASK_VISION))
    assert selected == ["completa"] and excluded == {"sem-capacidades": "needs_vision"}


def test_ac10_only_capable_route_missing_means_no_route_at_all():
    routes = [local_route("sem-tools", BASE, 1, supports_tools=False)]
    selected, excluded = eligible_aliases(routes, user_request(tools=[READ_TOOL]))
    assert selected == [] and excluded == {"sem-tools": "needs_tools"}


def test_task_class_filters_routes():
    routes = [local_route("so-complexa", BASE, 1, task_classes=("complex_tools",)), local_route("simples", BASE, 2)]
    selected, excluded = eligible_aliases(routes, user_request(task_class=TASK_SIMPLE))
    assert selected == ["simples"] and excluded == {"so-complexa": "task_class"}


def test_candidate_needs_explicit_flag_and_suspended_is_never_used():
    routes = [
        local_route("candidata", BASE, 1, state="candidate"),
        local_route("suspensa", BASE, 2, state="suspended"),
        local_route("aprovada", BASE, 3),
    ]
    selected, excluded = eligible_aliases(routes, user_request())
    assert selected == ["aprovada"]
    assert excluded == {"candidata": "state_candidate", "suspensa": "state_suspended"}

    selected, excluded = eligible_aliases(routes, user_request(), allow_candidate_models=True)
    assert selected == ["candidata", "aprovada"] and excluded == {"suspensa": "state_suspended"}


def test_write_purpose_never_degrades_to_read_only_route():
    routes = [local_route("so-leitura", BASE, 1, approved_purposes=("read",)), local_route("escrita", BASE, 2)]
    assert eligible_aliases(routes, user_request())[0] == ["so-leitura", "escrita"]
    selected, excluded = eligible_aliases(routes, user_request(purpose=PURPOSE_WRITE))
    assert selected == ["escrita"] and excluded == {"so-leitura": "purpose"}
    # Sem rota de escrita não há rota: a de leitura não "quebra o galho".
    selected, _ = eligible_aliases(routes[:1], user_request(purpose=PURPOSE_WRITE))
    assert selected == []
    # Propósito desconhecido é tratado com o rigor da escrita.
    assert eligible_aliases(routes[:1], user_request(purpose="admin"))[0] == []


def test_ac07_privacy_decides_external_routes_before_any_attempt():
    routes = [local_route("local", BASE, 1), external_route("externa", "http://127.0.0.1:2", 2)]

    def check(privacy, redaction=False, cloud=True):
        request = user_request(redaction_verified=redaction)
        return eligible_aliases(routes, request, make_ctx(privacy), cloud_enabled=cloud)

    assert check(Privacy.LOCAL_ONLY) == (["local"], {"externa": "privacy"})
    assert check(Privacy.LOCAL_ONLY, redaction=True) == (["local"], {"externa": "privacy"})
    assert check(Privacy.CLOUD_REDACTED) == (["local"], {"externa": "privacy"})
    assert check(Privacy.CLOUD_REDACTED, redaction=True) == (["local", "externa"], {})
    assert check(Privacy.CLOUD_ALLOWED) == (["local", "externa"], {})
    assert check(Privacy.CLOUD_ALLOWED, cloud=False) == (["local"], {"externa": "cloud_disabled"})


def test_external_route_only_serves_the_policies_it_lists():
    routes = [external_route("so-redigido", "http://127.0.0.1:2", 1, privacy=("cloud_redacted",))]
    selected, excluded = eligible_aliases(routes, user_request(), make_ctx(Privacy.CLOUD_ALLOWED), cloud_enabled=True)
    assert selected == [] and excluded == {"so-redigido": "privacy"}


def test_registry_revalidates_routes_built_in_code():
    bad = replace(local_route("local", BASE), model_id="modelo-teste:latest")
    with pytest.raises(ModelConfigError, match="latest"):
        ModelRegistry([bad], gateway_settings())
    request = ModelRequest(task_class=TASK_SIMPLE, messages=[ChatMessage(role="user", content="oi")])
    registry = ModelRegistry([local_route("local", BASE)], gateway_settings())
    assert registry.get("local") is not None and registry.get("outra") is None
    assert [route.alias for route in registry.eligible(request, make_ctx()).routes] == ["local"]
