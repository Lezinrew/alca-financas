"""Registro de modelos e regras de elegibilidade (contrato, seções 7 e 11).

O registro é um arquivo JSON versionado no repositório (``config/models.json``)
com uma entrada por ROTA: um alias estável apontando para um modelo fixado em
um provedor. Duas responsabilidades ficam aqui:

1. **Carga com validação** (``load_model_routes``): uma rota mal configurada
   quebra no carregamento, com mensagem clara, em vez de falhar no meio de uma
   execução. É aqui que "``latest`` não entra em produção" vira regra de
   código, e não só de documento.
2. **Elegibilidade estática** (``ModelRegistry.eligible``): dado um pedido e o
   contexto autenticado, quais rotas PODEM atender, em ordem de prioridade, e
   por que as outras ficaram de fora. O que muda em tempo de execução
   (circuito aberto, credencial suspensa, orçamento) é assunto do gateway.

Por que a privacidade é decidida aqui, antes de qualquer tentativa: a lista de
candidatas que o gateway percorre em caso de falha já sai sem rotas externas
quando a política é ``local_only``. Não existe caminho de failover que chegue a
um provedor externo "porque o local caiu" (AC-07).
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence
from urllib.parse import urlsplit

from ..settings import AiSettings
from ..types import ExecutionContext, Privacy
from .base import (
    LOCALITY_EXTERNAL,
    LOCALITY_LOCAL,
    PURPOSE_READ,
    PURPOSE_WRITE,
    TASK_CLASSES,
    ModelRequest,
    ModelRoute,
    privacy_allows_external,
)


PROVIDERS = ("ollama", "openai_compatible", "anthropic")
STATES = ("candidate", "approved", "suspended")
STATE_CANDIDATE = "candidate"
STATE_APPROVED = "approved"
STATE_SUSPENDED = "suspended"
PURPOSES = (PURPOSE_READ, PURPOSE_WRITE)
AGGREGATORS = ("openrouter",)

# Marcador usado no arquivo de exemplo: a versão comercial só é escrita depois
# da homologação. Uma rota com este model_id nunca é elegível.
PLACEHOLDER_MODEL_ID = "DEFINIR_APOS_HOMOLOGACAO"

_PRIVACY_VALUES = tuple(item.value for item in Privacy)
_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")
# Nome de variável de ambiente. Serve também de trava: se alguém colar o VALOR
# de uma chave no JSON, ele dificilmente passa por este formato e o
# carregamento falha antes de o segredo ir parar em um commit.
_ENV_NAME = re.compile(r"\A[A-Z][A-Z0-9_]{1,63}\Z")
_ALIAS = re.compile(r"\A[a-z0-9][a-z0-9._-]{0,63}\Z")
# Nome de serviço de um único rótulo (rede interna do Docker): começa por letra,
# sem ponto. Sublinhado é aceito porque o Docker Compose permite em nomes de
# serviço. Ver ``is_private_host`` para o motivo de exigir a letra inicial.
_SINGLE_LABEL_HOST = re.compile(r"\A[a-z](?:[a-z0-9_-]{0,61}[a-z0-9])?\Z")

_ROUTE_KEYS = frozenset(
    {
        "alias",
        "provider",
        "model_id",
        "locality",
        "priority",
        "task_classes",
        "supports_tools",
        "supports_json",
        "supports_vision",
        "context_window",
        "state",
        "approved_purposes",
        "privacy",
        "base_url",
        "digest",
        "credential_env",
        "upstream_provider",
        "max_cost_micros_per_call",
        "input_cost_micros_per_mtok",
        "output_cost_micros_per_mtok",
        "evidence",
        "extra",
    }
)
_REQUIRED_KEYS = (
    "alias",
    "provider",
    "model_id",
    "locality",
    "priority",
    "task_classes",
    "supports_tools",
    "supports_json",
    "supports_vision",
    "context_window",
    "state",
)


class ModelConfigError(ValueError):
    """Registro de modelos inválido. A mensagem cita o alias e a regra violada."""


def _fail(alias: Any, message: str) -> ModelConfigError:
    return ModelConfigError("rota %s: %s" % (alias if alias else "<sem alias>", message))


def _without_comments(raw: Dict[str, Any]) -> Dict[str, Any]:
    # JSON não tem comentário; chaves iniciadas por "_" fazem esse papel.
    return {key: value for key, value in raw.items() if not str(key).startswith("_")}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _str_tuple(alias: Any, field: str, value: Any, allowed: Sequence[str]) -> tuple:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise _fail(alias, "%s deve ser uma lista de textos" % field)
    unknown = [item for item in value if item not in allowed]
    if unknown:
        raise _fail(alias, "%s tem valor desconhecido: %s" % (field, ", ".join(unknown)))
    if len(set(value)) != len(value):
        raise _fail(alias, "%s repete valores" % field)
    return tuple(value)


def _optional_text(alias: Any, field: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _fail(alias, "%s deve ser texto não vazio ou null" % field)
    return value.strip()


def _optional_cost(alias: Any, field: str, value: Any) -> Optional[int]:
    if value is None:
        return None
    if not _is_int(value) or value < 0:
        raise _fail(alias, "%s deve ser inteiro (micros) maior ou igual a zero, ou null" % field)
    return value


def route_from_dict(raw: Any) -> ModelRoute:
    """Converte uma entrada do JSON em ``ModelRoute`` e valida a rota."""
    if not isinstance(raw, dict):
        raise ModelConfigError("cada rota deve ser um objeto JSON")
    data = _without_comments(raw)
    alias = data.get("alias")
    unknown = sorted(set(data) - _ROUTE_KEYS)
    if unknown:
        # Chave desconhecida quase sempre é erro de digitação ("suports_tools"),
        # e erro de digitação em capacidade vira rota escolhida errado.
        raise _fail(alias, "chave desconhecida: %s" % ", ".join(unknown))
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise _fail(alias, "campos obrigatórios ausentes: %s" % ", ".join(missing))

    for flag in ("supports_tools", "supports_json", "supports_vision"):
        if not isinstance(data[flag], bool):
            raise _fail(alias, "%s deve ser true ou false" % flag)
    if not _is_int(data["priority"]):
        raise _fail(alias, "priority deve ser inteiro")
    if not _is_int(data["context_window"]) or data["context_window"] <= 0:
        raise _fail(alias, "context_window deve ser inteiro positivo")
    extra = data.get("extra") or {}
    if not isinstance(extra, dict):
        raise _fail(alias, "extra deve ser um objeto")

    locality = data["locality"]
    privacy = data.get("privacy")
    if privacy is None:
        if locality != LOCALITY_LOCAL:
            # Rota externa só atende as políticas que o titular listou
            # explicitamente; não existe "padrão" para tráfego externo.
            raise _fail(alias, "rota externa deve declarar privacy explicitamente")
        privacy = list(_PRIVACY_VALUES)

    def cost(field: str) -> Optional[int]:
        return _optional_cost(alias, field, data.get(field))

    route = ModelRoute(
        alias=alias,
        provider=data["provider"],
        model_id=data["model_id"],
        locality=locality,
        priority=data["priority"],
        task_classes=_str_tuple(alias, "task_classes", data["task_classes"], TASK_CLASSES),
        supports_tools=data["supports_tools"],
        supports_json=data["supports_json"],
        supports_vision=data["supports_vision"],
        context_window=data["context_window"],
        state=data["state"],
        approved_purposes=_str_tuple(alias, "approved_purposes", data.get("approved_purposes") or [], PURPOSES),
        privacy=_str_tuple(alias, "privacy", privacy, _PRIVACY_VALUES),
        base_url=_optional_text(alias, "base_url", data.get("base_url")),
        digest=_optional_text(alias, "digest", data.get("digest")),
        credential_env=_optional_text(alias, "credential_env", data.get("credential_env")),
        upstream_provider=_optional_text(alias, "upstream_provider", data.get("upstream_provider")),
        max_cost_micros_per_call=cost("max_cost_micros_per_call"),
        input_cost_micros_per_mtok=cost("input_cost_micros_per_mtok"),
        output_cost_micros_per_mtok=cost("output_cost_micros_per_mtok"),
        evidence=_optional_text(alias, "evidence", data.get("evidence")),
        extra=dict(_without_comments(extra)),
    )
    validate_route(route)
    return route


def is_private_host(host: str) -> bool:
    """O host é loopback ou de rede privada?

    Não faz consulta DNS: carregar configuração não pode depender de rede, e um
    nome público pode mudar de endereço depois da checagem. Aceita:

    * ``localhost`` e nomes terminados em ``.localhost``;
    * IP literal de loopback ou de faixa privada (10/8, 172.16/12, 192.168/16,
      fc00::/7). Link-local (169.254/16, onde vivem endpoints de metadados de
      nuvem) fica de fora;
    * nome de um único rótulo, sem ponto (ex.: ``ollama``, o nome do serviço na
      rede interna do Docker). Um nome assim não existe na internet pública.
      O rótulo precisa COMEÇAR POR LETRA: ``134744072`` e ``0x08080808`` não
      têm ponto, mas não são nomes. No Linux o ``getaddrinfo`` os lê no estilo
      ``inet_aton`` (um número de 32 bits) e conecta em 8.8.8.8, um host
      público. Tudo o que não é IP literal nem nome iniciado por letra é
      recusado.
    """
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    if any(len(part) > 1 and part.startswith("0") and part.isdigit() for part in host.split(".")):
        # Octeto com zero à esquerda ("010.0.0.1"): o Python até 3.9.4 lê como
        # decimal (10.0.0.1, privado) e o sistema lê como octal (8.0.0.1,
        # público). Na dúvida sobre quem vai interpretar, recusa.
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return bool(_SINGLE_LABEL_HOST.match(host))
    if address.is_loopback:
        return True
    return bool(
        address.is_private
        and not address.is_link_local
        and not address.is_unspecified
        and not address.is_multicast
        and not address.is_reserved
    )


def _split_base_url(alias: str, base_url: str):
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise _fail(alias, "base_url deve ser uma URL http(s) com host")
    if parts.username or parts.password:
        raise _fail(alias, "base_url não pode conter usuário ou senha")
    if parts.query or parts.fragment:
        raise _fail(alias, "base_url não pode conter query string ou fragmento")
    return parts


def looks_like_remote_model(model_id: str) -> bool:
    """Nomes de modelo que o Ollama encaminha para a nuvem (``:cloud``, ``-cloud``).

    Falar com ``localhost:11434`` não garante execução local: um modelo remoto
    é repassado pelo servidor Ollama para fora da máquina.
    """
    name = (model_id or "").strip().lower()
    return name.endswith(":cloud") or name.endswith("-cloud") or ":cloud" in name


def _is_latest(model_id: str) -> bool:
    name = (model_id or "").strip().lower()
    return name.endswith(":latest") or name.endswith("-latest") or name == "latest" or name.startswith("~")


def validate_route(route: ModelRoute) -> None:
    """Regras do registro. Levanta ``ModelConfigError`` na primeira violação."""
    alias = route.alias
    if not isinstance(alias, str) or not _ALIAS.match(alias):
        raise _fail(alias, "alias deve ter letras minúsculas, dígitos, ponto, hífen ou sublinhado")
    if route.provider not in PROVIDERS:
        raise _fail(alias, "provider desconhecido: %s" % route.provider)
    if route.locality not in (LOCALITY_LOCAL, LOCALITY_EXTERNAL):
        raise _fail(alias, "locality deve ser local ou external")
    if route.state not in STATES:
        raise _fail(alias, "state deve ser candidate, approved ou suspended")
    if not isinstance(route.model_id, str) or not route.model_id.strip():
        raise _fail(alias, "model_id é obrigatório")
    if not route.task_classes:
        raise _fail(alias, "task_classes não pode ser vazio")
    if any(item not in TASK_CLASSES for item in route.task_classes):
        raise _fail(alias, "task_classes tem classe desconhecida")
    if any(item not in PURPOSES for item in route.approved_purposes):
        raise _fail(alias, "approved_purposes tem propósito desconhecido")
    if not route.privacy or any(item not in _PRIVACY_VALUES for item in route.privacy):
        raise _fail(alias, "privacy deve listar políticas válidas")
    if not _is_int(route.context_window) or route.context_window <= 0:
        raise _fail(alias, "context_window deve ser inteiro positivo")
    if not _is_int(route.priority):
        raise _fail(alias, "priority deve ser inteiro")
    if route.credential_env is not None and not _ENV_NAME.match(route.credential_env):
        raise _fail(
            alias,
            "credential_env deve ser o NOME de uma variável de ambiente (maiúsculas, dígitos e _), nunca o valor",
        )
    if route.digest is not None and not _DIGEST.match(route.digest):
        raise _fail(alias, "digest deve ter 64 caracteres hexadecimais minúsculos")
    aggregator = route.extra.get("aggregator")
    if aggregator is not None and aggregator not in AGGREGATORS:
        raise _fail(alias, "extra.aggregator desconhecido: %s" % aggregator)
    accepted = route.extra.get("accepted_model_ids")
    if accepted is not None and (
        not isinstance(accepted, (list, tuple))
        or any(not isinstance(item, str) or not item.strip() for item in accepted)
    ):
        # Lista dos nomes de modelo que o agregador pode DEVOLVER para esta rota
        # (preenchida na homologação, quando ele devolve um nome canônico
        # diferente do pedido). Formato errado aqui desligaria a conferência.
        raise _fail(alias, "extra.accepted_model_ids deve ser uma lista de textos não vazios")

    if route.provider == "ollama" and route.locality != LOCALITY_LOCAL:
        raise _fail(alias, "rota ollama deve ser local (Ollama Cloud não é suportado por este adaptador)")
    if route.provider == "anthropic" and route.locality != LOCALITY_EXTERNAL:
        raise _fail(alias, "rota anthropic deve ser external")

    if route.is_local:
        # Vale em QUALQUER estado: com allow_candidate_models uma candidata
        # também recebe pedidos, e local_only não pode sair da máquina.
        if looks_like_remote_model(route.model_id):
            raise _fail(alias, "rota local não pode usar modelo remoto/cloud (%s)" % route.model_id)
        if aggregator is not None:
            raise _fail(alias, "rota local não pode usar agregador")
        if route.base_url is not None:
            parts = _split_base_url(alias, route.base_url)
            if not is_private_host(parts.hostname or ""):
                raise _fail(alias, "rota local exige base_url em loopback ou rede privada")
        elif route.provider != "ollama":
            raise _fail(alias, "rota local openai_compatible exige base_url")
    else:
        if Privacy.LOCAL_ONLY.value in route.privacy:
            raise _fail(alias, "rota externa não pode declarar privacy local_only")
        if route.base_url is None:
            raise _fail(alias, "rota externa exige base_url")
        parts = _split_base_url(alias, route.base_url)
        if parts.scheme != "https" and not is_private_host(parts.hostname or ""):
            # A credencial vai no cabeçalho: sem TLS ela trafegaria em claro.
            raise _fail(alias, "rota externa exige base_url https")

    if route.state == STATE_APPROVED:
        _validate_approved(route)


def _validate_approved(route: ModelRoute) -> None:
    """Só chega a ``approved`` a rota com tudo o que a homologação exige."""
    alias = route.alias
    if route.model_id.strip() == PLACEHOLDER_MODEL_ID:
        raise _fail(alias, "rota aprovada precisa de model_id definido (não o marcador de exemplo)")
    if _is_latest(route.model_id):
        raise _fail(alias, "rota aprovada não pode usar tag ou alias 'latest'")
    if not route.approved_purposes:
        raise _fail(alias, "rota aprovada precisa declarar approved_purposes (read e/ou write)")
    if not route.evidence:
        raise _fail(alias, "rota aprovada precisa de evidence (referência aos testes de homologação)")

    if route.provider == "ollama":
        name, separator, tag = route.model_id.partition(":")
        if not separator or not name.strip() or not tag.strip():
            # Sem tag o Ollama assume "latest", que é reapontada sem aviso.
            raise _fail(alias, "rota ollama aprovada precisa de tag explícita (modelo:tag)")
        if not route.digest:
            raise _fail(alias, "rota ollama aprovada precisa de digest de 64 hex")

    if not route.is_local:
        if not route.credential_env:
            raise _fail(alias, "rota externa aprovada precisa de credential_env")
        if route.max_cost_micros_per_call is None or route.max_cost_micros_per_call <= 0:
            raise _fail(alias, "rota externa aprovada precisa de max_cost_micros_per_call maior que zero")
        if route.extra.get("aggregator") and not route.upstream_provider:
            raise _fail(alias, "rota via agregador aprovada precisa de upstream_provider fixado")


def routes_from_document(document: Any) -> List[ModelRoute]:
    """Valida o documento inteiro (``{"routes": [...]}``) e devolve as rotas."""
    if not isinstance(document, dict) or not isinstance(document.get("routes"), list):
        raise ModelConfigError('o registro de modelos deve ser um objeto com a lista "routes"')
    routes = [route_from_dict(item) for item in document["routes"]]
    _check_unique(routes)
    return routes


def _check_unique(routes: Sequence[ModelRoute]) -> None:
    seen = set()
    for route in routes:
        if route.alias in seen:
            raise _fail(route.alias, "alias duplicado")
        seen.add(route.alias)


def load_model_routes(path: Any) -> List[ModelRoute]:
    """Lê o JSON do registro e devolve as rotas validadas."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        raise ModelConfigError("registro de modelos não encontrado: %s" % file_path) from None
    try:
        document = json.loads(text)
    except ValueError:
        raise ModelConfigError("registro de modelos não é JSON válido: %s" % file_path) from None
    return routes_from_document(document)


class Exclusion(NamedTuple):
    alias: str
    reason: str


class Eligibility(NamedTuple):
    """Rotas que podem atender, em ordem de prioridade, e as descartadas."""

    routes: List[ModelRoute]
    excluded: List[Exclusion]


class ModelRegistry:
    """Rotas validadas + decisão estática de elegibilidade.

    ``priority`` menor = tentada primeiro (empate decide pelo alias, para a
    ordem ser sempre a mesma).
    """

    def __init__(self, routes: Sequence[ModelRoute], settings: AiSettings) -> None:
        self._settings = settings
        resolved = []
        for route in routes:
            if route.provider == "ollama" and route.base_url is None:
                # A URL do Ollama é de implantação (settings), não do registro.
                # Resolvida aqui para passar pela MESMA checagem de rede privada.
                route = replace(route, base_url=settings.ollama_base_url)
            validate_route(route)
            resolved.append(route)
        _check_unique(resolved)
        self._routes = sorted(resolved, key=lambda item: (item.priority, item.alias))
        self._by_alias = {route.alias: route for route in self._routes}

    @classmethod
    def from_settings(cls, settings: AiSettings) -> "ModelRegistry":
        return cls(load_model_routes(settings.resolved_model_registry_path()), settings)

    @property
    def routes(self) -> List[ModelRoute]:
        return list(self._routes)

    def get(self, alias: str) -> Optional[ModelRoute]:
        return self._by_alias.get(alias)

    def exclusion_reason(self, route: ModelRoute, request: ModelRequest, ctx: ExecutionContext) -> Optional[str]:
        """Motivo pelo qual a rota NÃO pode atender, ou ``None`` se pode.

        A ordem das checagens é a do contrato: classe da tarefa, capacidades,
        privacidade, estado, propósito.
        """
        if request.task_class not in route.task_classes:
            return "task_class"
        # AC-10: capacidade exigida e ausente nunca é "tentada mesmo assim".
        if request.needs_tools and not route.supports_tools:
            return "needs_tools"
        if request.needs_json and not route.supports_json:
            return "needs_json"
        if request.needs_vision and not route.supports_vision:
            return "needs_vision"
        if not route.is_local:
            if not privacy_allows_external(ctx.privacy, request.redaction_verified):
                return "privacy"
            if not self._settings.cloud_enabled:
                return "cloud_disabled"
        if ctx.privacy.value not in route.privacy:
            return "privacy"
        if route.state == STATE_SUSPENDED:
            return "state_suspended"
        if route.state != STATE_APPROVED and not self._settings.allow_candidate_models:
            return "state_candidate"
        if route.model_id.strip() == PLACEHOLDER_MODEL_ID:
            return "model_undefined"
        if request.purpose != PURPOSE_READ and request.purpose not in route.approved_purposes:
            # Escrita nunca degrada para rota homologada só para leitura.
            # Propósito desconhecido é tratado com o mesmo rigor da escrita.
            return "purpose"
        return None

    def eligible(self, request: ModelRequest, ctx: ExecutionContext) -> Eligibility:
        routes: List[ModelRoute] = []
        excluded: List[Exclusion] = []
        for route in self._routes:
            reason = self.exclusion_reason(route, request, ctx)
            if reason is None:
                routes.append(route)
            else:
                excluded.append(Exclusion(route.alias, reason))
        return Eligibility(routes, excluded)
