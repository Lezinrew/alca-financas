"""Registro versionado de capacidades e schemas (contrato, seção 5).

Cada ferramenta declara nome, versão, schema de argumentos (pydantic com
``extra="forbid"``) e o tipo de efeito. O registro:

* rejeita argumentos fora do schema e propriedades inesperadas;
* entrega ao handler o ``ExecutionContext`` resolvido pelo servidor, fora dos
  argumentos do modelo;
* confere flags e grants antes de executar;
* garante que o resultado é JSON sem float.

O modelo só enxerga nome, descrição e schema das ferramentas autorizadas para
aquela execução. Não há ferramenta de SQL, shell ou URL arbitrária.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Type

from pydantic import BaseModel, ConfigDict, ValidationError

from .errors import AiError
from .policy import CAPABILITIES, Grant, allowed_capabilities, authorize
from .settings import AiSettings
from .types import ExecutionContext, Fact, Source, canonical_json, json_safe


class ToolArgs(BaseModel):
    """Base dos argumentos de ferramenta: propriedades extras são rejeitadas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@dataclass
class ToolResult:
    """Resultado estruturado de uma ferramenta.

    ``data`` volta ao modelo como DADO não confiável (nunca como instrução).
    ``facts`` e ``sources`` são a verdade usada na resposta ao titular.
    """

    data: Dict[str, Any] = field(default_factory=dict)
    facts: List[Fact] = field(default_factory=list)
    sources: List[Source] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    proposal_ids: List[str] = field(default_factory=list)
    operation_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return json_safe(
            {
                "data": self.data,
                "facts": [fact.to_dict() for fact in self.facts],
                "sources": [source.to_dict() for source in self.sources],
                "warnings": list(self.warnings),
                "proposal_ids": [str(item) for item in self.proposal_ids],
                "operation_ids": [str(item) for item in self.operation_ids],
            }
        )

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ToolResult":
        return cls(
            data=dict(payload.get("data") or {}),
            facts=[Fact(**item) for item in payload.get("facts") or []],
            sources=[Source(**item) for item in payload.get("sources") or []],
            warnings=list(payload.get("warnings") or []),
            proposal_ids=list(payload.get("proposal_ids") or []),
            operation_ids=list(payload.get("operation_ids") or []),
        )


ToolHandler = Callable[[ExecutionContext, Any], ToolResult]

# Tipos de efeito: leitura interna, leitura em conector externo, preparo de
# proposta (sem efeito financeiro), efeito financeiro durável, mensagem.
EFFECTS = ("read", "external_read", "prepare", "write", "message")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    version: str
    description: str
    args_model: Type[ToolArgs]
    effect: str
    handler: ToolHandler
    # Flags de ``AiSettings`` que precisam estar ligadas (ex.: "email_enabled").
    requires_flags: Sequence[str] = ()

    def __post_init__(self) -> None:
        if self.name not in CAPABILITIES:
            raise ValueError("ferramenta fora do contrato: %s" % self.name)
        if self.effect not in EFFECTS:
            raise ValueError("efeito inválido: %s" % self.effect)
        if not issubclass(self.args_model, ToolArgs):
            raise ValueError("args_model deve herdar de ToolArgs")

    def json_schema(self) -> Dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        schema["additionalProperties"] = False
        return schema

    def spec(self) -> Dict[str, Any]:
        """Descrição entregue ao modelo."""
        return {"name": self.name, "description": self.description, "parameters": self.json_schema()}


class ToolRegistry:
    def __init__(self, settings: AiSettings) -> None:
        self._settings = settings
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError("ferramenta já registrada: %s" % definition.name)
        self._tools[definition.name] = definition

    def register_all(self, definitions: Iterable[ToolDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolDefinition:
        definition = self._tools.get(name)
        if definition is None:
            # Nome inventado pelo modelo ou injetado por conteúdo não confiável.
            raise AiError("capability_denied", "Ferramenta desconhecida.")
        return definition

    def manifest(self) -> List[Dict[str, Any]]:
        """Registro versionado completo (para documentação e auditoria)."""
        return [
            {
                "name": tool.name,
                "version": tool.version,
                "effect": tool.effect,
                "requires_flags": list(tool.requires_flags),
                "schema": tool.json_schema(),
            }
            for _, tool in sorted(self._tools.items())
        ]

    def _flags_ok(self, definition: ToolDefinition) -> bool:
        return all(bool(getattr(self._settings, flag)) for flag in definition.requires_flags)

    def specs_for(self, grants: Iterable[Grant], only: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
        """Ferramentas que o modelo pode ver nesta execução."""
        allowed = allowed_capabilities(grants)
        specs = []
        for name, definition in sorted(self._tools.items()):
            if only is not None and name not in only:
                continue
            if name not in allowed or not self._flags_ok(definition):
                continue
            specs.append(definition.spec())
        return specs

    def validate_args(self, name: str, raw_args: Any) -> ToolArgs:
        definition = self.get(name)
        if not isinstance(raw_args, dict):
            raise AiError("invalid_request", "Argumentos de ferramenta inválidos.")
        try:
            return definition.args_model.model_validate(raw_args)
        except ValidationError as exc:
            fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
            raise AiError(
                "invalid_request",
                "Argumentos de ferramenta fora do schema.",
                details={"tool": name, "fields": fields[:10]},
            )

    def execute(
        self,
        name: str,
        raw_args: Any,
        ctx: ExecutionContext,
        grants: Iterable[Grant],
    ) -> ToolResult:
        """Valida flags, autorização e argumentos; executa; valida a saída."""
        definition = self.get(name)
        if not self._flags_ok(definition):
            raise AiError("capability_denied", "Esta capacidade está desativada.")
        authorize(grants, name)
        args = self.validate_args(name, raw_args)
        result = definition.handler(ctx, args)
        if not isinstance(result, ToolResult):
            raise AiError("internal_error")
        # Falha cedo se algum handler devolver float ou tipo não serializável.
        result.to_dict()
        return result

    @staticmethod
    def args_hash(name: str, version: str, raw_args: Any) -> str:
        import hashlib

        material = canonical_json({"tool": name, "version": version, "args": raw_args})
        return hashlib.sha256(material.encode("utf-8")).hexdigest()
