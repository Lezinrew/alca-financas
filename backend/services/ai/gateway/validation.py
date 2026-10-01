"""Validação da saída estruturada dos modelos (contrato, seções 5 e 8).

O modelo é tratado como fonte não confiável: o que ele devolve só vira dado
depois de (1) ser um objeto JSON de verdade e (2) obedecer ao schema pedido.
Este módulo faz as duas coisas sem a biblioteca ``jsonschema`` (a plataforma
não pode ganhar dependências novas), cobrindo apenas o subconjunto de JSON
Schema que os pedidos da plataforma usam.

Três decisões que valem para o resto do gateway:

* números com casas decimais viram ``Decimal``, nunca ``float``. O restante da
  plataforma recusa ``float`` em resultados (``services.ai.types.json_safe``);
  se o gateway deixasse passar um ``float`` vindo do modelo, o erro só
  apareceria longe daqui, na hora de gravar ou calcular um hash;
* palavra-chave de schema desconhecida é ERRO, não é ignorada. Ignorar um
  ``pattern`` ou ``anyOf`` faria a validação "passar" sem ter validado nada;
* as mensagens de erro citam o caminho e a regra violada, nunca o valor
  recebido: elas voltam ao modelo no pedido de correção e não devem carregar
  conteúdo de extrato ou de e-mail para logs.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Palavras-chave que restringem valores e que este validador implementa.
SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "enum",
        "const",
        "items",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
    }
)

# Anotações: descrevem, mas não restringem. Podem ser ignoradas sem risco.
ANNOTATION_KEYWORDS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "format",
        "deprecated",
        "readOnly",
        "writeOnly",
        "$schema",
        "$id",
        "$comment",
    }
)

_JSON_TYPES = ("object", "array", "string", "number", "integer", "boolean", "null")

MAX_ERRORS = 20
_MAX_KEY_CHARS = 40

# Bloco cercado: a resposta INTEIRA precisa ser o bloco. Texto antes ou depois
# é prosa, e prosa em volta de JSON costuma ser sinal de resposta fora do
# formato (ou de instrução injetada pedindo "explique antes").
_FENCE = re.compile(r"\A```[ \t]*(?:json)?[ \t]*\r?\n(?P<body>.*?)\r?\n?[ \t]*```\Z", re.DOTALL | re.IGNORECASE)

_PARSE_MESSAGES = {
    "not_text": "a resposta não é texto",
    "empty": "a resposta veio vazia",
    "not_object": "a resposta precisa ser somente um objeto JSON, sem texto em volta",
    "invalid_json": "a resposta não é JSON válido",
    "duplicate_key": "o objeto JSON repete uma chave",
    "non_finite_number": "o JSON usa número não finito (NaN/Infinity)",
}


class JsonObjectError(ValueError):
    """Texto que não é um objeto JSON aceitável.

    Carrega apenas um código curto. O texto recebido do modelo nunca entra na
    mensagem da exceção: exceções acabam em logs e em trilhas de erro.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    @property
    def message_pt_br(self) -> str:
        return _PARSE_MESSAGES.get(self.code, "a resposta não pôde ser lida")


class SchemaNotSupportedError(ValueError):
    """O schema usa palavra-chave fora do subconjunto implementado."""

    def __init__(self, keywords: List[str]) -> None:
        self.keywords = list(keywords)
        super().__init__("schema usa palavras-chave não suportadas: %s" % ", ".join(self.keywords))


def _reject_constant(_name: str) -> Any:
    raise JsonObjectError("non_finite_number")


def _reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    # JSON permite chave repetida e o ``json`` do Python fica com a última.
    # Em dado financeiro isso é ambíguo ("valor" duas vezes: qual vale?), então
    # a resposta é recusada em vez de escolhida em silêncio.
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonObjectError("duplicate_key")
        result[key] = value
    return result


def loads_no_float(text: str) -> Any:
    """``json.loads`` que nunca produz ``float``: decimais viram ``Decimal``."""
    return json.loads(
        text,
        parse_float=Decimal,
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )


def parse_json_object(text: Any) -> Dict[str, Any]:
    """Extrai o objeto JSON de uma resposta de modelo.

    Aceita o objeto puro ou cercado por um único bloco ```json. Rejeita prosa
    antes/depois, listas, escalares, chaves repetidas e NaN/Infinity.
    Levanta ``JsonObjectError`` (com ``code`` curto) quando recusa.
    """
    if not isinstance(text, str):
        raise JsonObjectError("not_text")
    candidate = text.lstrip("﻿").strip()
    if not candidate:
        raise JsonObjectError("empty")
    fenced = _FENCE.match(candidate)
    if fenced:
        candidate = fenced.group("body").strip()
    if not (candidate.startswith("{") and candidate.endswith("}")):
        raise JsonObjectError("not_object")
    value: Any = None
    invalid = False
    try:
        value = loads_no_float(candidate)
    except JsonObjectError:
        raise
    except (ValueError, RecursionError):
        # Só marca aqui e levanta DEPOIS do bloco. A exceção original guarda o
        # texto recebido inteiro (``JSONDecodeError.doc``); levantando dentro
        # do ``except`` ela viajaria pendurada em ``__context__`` mesmo com
        # ``from None``, que esconde do traceback mas não solta a referência.
        invalid = True
    if invalid:
        raise JsonObjectError("invalid_json")
    if not isinstance(value, dict):
        raise JsonObjectError("not_object")
    return value


# ---------------------------------------------------------------------------
# Rótulos devolvidos pelo provedor (modelo efetivo, fornecedor efetivo)
# ---------------------------------------------------------------------------

MAX_LABEL_CHARS = 128
_LABEL_WORD = r"[A-Za-z0-9._:/@+-]+"
_LABEL = re.compile(r"\A%s\Z" % _LABEL_WORD)
# Nome de fornecedor pode ter espaço simples entre palavras ("Fornecedor Dois").
_LABEL_WITH_SPACES = re.compile(r"\A%s(?: %s)*\Z" % (_LABEL_WORD, _LABEL_WORD))


def safe_label(
    value: Any,
    fallback: Optional[str] = None,
    *,
    allow_spaces: bool = False,
    forbidden: Sequence[str] = (),
) -> Optional[str]:
    """Rótulo curto vindo do provedor, ou ``fallback`` se não for confiável.

    ``model`` e ``provider`` da resposta são TEXTO CONTROLADO PELO PROVEDOR e
    acabam gravados na auditoria (modelo efetivo, fornecedor efetivo). Sem este
    filtro, um provedor com defeito (ou malicioso) gravaria lá o que quisesse:
    texto longo, quebra de linha que forja linha de log, eco do pedido.

    Regra: só identificador curto (letras, dígitos e ``. _ : / @ + -``), até
    128 caracteres. ``forbidden`` recebe valores que nunca podem aparecer (a
    credencial usada na chamada): o formato de identificador sozinho não
    barraria uma chave ecoada, porque chaves também parecem identificadores.
    """
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if not text or len(text) > MAX_LABEL_CHARS:
        return fallback
    if not (_LABEL_WITH_SPACES if allow_spaces else _LABEL).match(text):
        return fallback
    if any(secret and secret in text for secret in forbidden):
        return fallback
    return text


# ---------------------------------------------------------------------------
# Subconjunto de JSON Schema
# ---------------------------------------------------------------------------

def unsupported_keywords(schema: Any) -> List[str]:
    """Palavras-chave do schema que este validador não implementa (ordenadas)."""
    found = set()
    _collect_unsupported(schema, found)
    return sorted(found)


def _is_count(value: Any) -> bool:
    """Inteiro >= 0 de verdade (``True`` é ``int`` em Python, mas não é contagem)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_bound(value: Any) -> bool:
    """Limite numérico utilizável em ``minimum``/``maximum``."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, float)):
        return False
    try:
        return Decimal(str(value)).is_finite()
    except (ArithmeticError, ValueError):
        return False


def _collect_unsupported(schema: Any, found: set) -> None:
    """Junta em ``found`` tudo o que impediria validar com este schema.

    Confere o NOME das palavras-chave e também o VALOR de cada uma. Motivo: o
    gateway chama esta checagem antes de gastar uma inferência. Um schema com
    ``minLength: "1"`` ou ``required: 5`` passaria pela conferência de nomes e
    só estouraria ``TypeError`` ao validar a resposta, isto é, DEPOIS de a
    chamada (talvez paga) já ter sido feita. Valor malformado entra na lista
    como "não suportado": falha fechada, antes de qualquer requisição.
    """
    if not isinstance(schema, dict):
        if not isinstance(schema, bool):
            found.add("<schema não é objeto>")
        return
    for keyword, value in schema.items():
        if keyword in ANNOTATION_KEYWORDS:
            continue
        if keyword not in SUPPORTED_KEYWORDS:
            found.add(str(keyword))
            continue
        if keyword == "properties":
            if not isinstance(value, dict):
                found.add("properties (formato inválido)")
                continue
            for child in value.values():
                _collect_unsupported(child, found)
        elif keyword == "items":
            # ``items`` como lista (tuplas posicionais) não faz parte do subconjunto.
            if isinstance(value, list):
                found.add("items (lista)")
            else:
                _collect_unsupported(value, found)
        elif keyword == "additionalProperties":
            if isinstance(value, dict):
                _collect_unsupported(value, found)
            elif not isinstance(value, bool):
                # Um valor como "false" (texto) seria lido como "tudo permitido".
                found.add("additionalProperties (formato inválido)")
        elif keyword == "type":
            names = value if isinstance(value, list) else [value]
            if not names:
                found.add("type (lista vazia)")
            for name in names:
                if not isinstance(name, str) or name not in _JSON_TYPES:
                    found.add("type=%s" % (name if isinstance(name, str) else type(name).__name__))
        elif keyword == "required":
            if not isinstance(value, list) or any(not isinstance(name, str) for name in value):
                found.add("required (formato inválido)")
        elif keyword == "enum":
            if not isinstance(value, list):
                found.add("enum (formato inválido)")
        elif keyword in ("minLength", "maxLength", "minItems", "maxItems"):
            if not _is_count(value):
                found.add("%s (valor inválido)" % keyword)
        elif keyword in ("minimum", "maximum"):
            if not _is_bound(value):
                found.add("%s (valor inválido)" % keyword)


def _is_number(value: Any) -> bool:
    # ``bool`` é subclasse de ``int`` em Python, mas em JSON ``true`` não é número.
    return isinstance(value, (int, Decimal, float)) and not isinstance(value, bool)


def _is_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, Decimal):
        # Em JSON Schema ``1.0`` é inteiro: o que importa é o valor, não a grafia.
        return value.is_finite() and value == value.to_integral_value()
    if isinstance(value, float):
        return value.is_integer()
    return False


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if _is_number(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return "desconhecido"


def _matches_type(value: Any, name: str) -> bool:
    if name == "integer":
        return _is_integer(value)
    if name == "number":
        return _is_number(value)
    return _type_name(value) == name


def _json_equal(left: Any, right: Any) -> bool:
    """Igualdade no sentido de JSON: ``true`` não é igual a ``1``."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if _is_number(left) and _is_number(right):
        return Decimal(str(left)) == Decimal(str(right))
    if type(left) is not type(right) and not (
        isinstance(left, (list, tuple)) and isinstance(right, (list, tuple))
    ):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def _child_path(path: str, key: Any) -> str:
    text = str(key)
    if len(text) > _MAX_KEY_CHARS:
        # Nome de propriedade vem do modelo; não deixa conteúdo longo vazar no caminho.
        text = text[:_MAX_KEY_CHARS] + "…"
    return "%s.%s" % (path, text)


def validate_schema(value: Any, schema: Dict[str, Any]) -> List[str]:
    """Valida ``value`` contra ``schema``. Lista vazia = válido.

    Cada erro é ``"<caminho>: <regra violada>"``. Levanta
    ``SchemaNotSupportedError`` se o schema usar algo fora do subconjunto
    (isso é defeito de quem escreveu o schema, não da resposta do modelo).
    """
    unknown = unsupported_keywords(schema)
    if unknown:
        raise SchemaNotSupportedError(unknown)
    errors: List[str] = []
    _validate(value, schema, "$", errors)
    return errors


def _validate(value: Any, schema: Any, path: str, errors: List[str]) -> None:
    if len(errors) >= MAX_ERRORS:
        return
    if schema is True or schema == {}:
        return
    if schema is False:
        errors.append("%s: valor não permitido" % path)
        return

    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, name) for name in names):
            errors.append(
                "%s: tipo esperado %s, recebido %s" % (path, " ou ".join(names), _type_name(value))
            )
            # Com o tipo errado as demais regras só gerariam ruído.
            return

    if "enum" in schema and not any(_json_equal(value, option) for option in schema["enum"]):
        errors.append("%s: valor fora da lista permitida" % path)
    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append("%s: valor diferente do exigido" % path)

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: texto menor que %s caracteres" % (path, schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: texto maior que %s caracteres" % (path, schema["maxLength"]))

    if _is_number(value):
        number = Decimal(str(value))
        if "minimum" in schema and number < Decimal(str(schema["minimum"])):
            errors.append("%s: número menor que %s" % (path, schema["minimum"]))
        if "maximum" in schema and number > Decimal(str(schema["maximum"])):
            errors.append("%s: número maior que %s" % (path, schema["maximum"]))

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in value:
                errors.append("%s: propriedade obrigatória ausente" % _child_path(path, name))
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if len(errors) >= MAX_ERRORS:
                return
            if key in properties:
                _validate(item, properties[key], _child_path(path, key), errors)
            elif additional is False:
                errors.append("%s: propriedade não permitida" % _child_path(path, key))
            elif isinstance(additional, dict):
                _validate(item, additional, _child_path(path, key), errors)

    if isinstance(value, (list, tuple)):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: lista com menos de %s itens" % (path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: lista com mais de %s itens" % (path, schema["maxItems"]))
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                if len(errors) >= MAX_ERRORS:
                    return
                _validate(item, item_schema, "%s[%d]" % (path, index), errors)


def validate_structured_output(text: Any, schema: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Parse + validação em um passo: ``(objeto, [])`` ou ``(None, erros)``."""
    try:
        parsed = parse_json_object(text)
    except JsonObjectError as error:
        return None, [error.message_pt_br]
    errors = validate_schema(parsed, schema)
    if errors:
        return None, errors
    return parsed, []
