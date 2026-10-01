"""Parse de JSON e validação de schema da saída dos modelos."""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.ai.gateway.validation import (
    JsonObjectError,
    SchemaNotSupportedError,
    parse_json_object,
    unsupported_keywords,
    validate_schema,
    validate_structured_output,
)
from services.ai.types import canonical_json


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# parse_json_object
# ---------------------------------------------------------------------------

def test_parse_accepts_plain_object_and_fenced_block():
    assert parse_json_object('  {"valor": "10.00", "itens": [1, 2]}  ') == {"valor": "10.00", "itens": [1, 2]}
    assert parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}
    assert parse_json_object('```\n{"ok": null}\n```\n') == {"ok": None}


@pytest.mark.parametrize(
    "text, code",
    [
        ('Claro! Segue o resultado: {"ok": true}', "not_object"),
        ('{"ok": true}\nEspero ter ajudado.', "not_object"),
        ('Aqui está:\n```json\n{"ok": true}\n```', "not_object"),
        ('```json\n{"ok": true}\n```\nQualquer dúvida, avise.', "not_object"),
        ("[1, 2, 3]", "not_object"),
        ('"apenas texto"', "not_object"),
        ("", "empty"),
        ("   \n ", "empty"),
        ('{"ok": true,}', "invalid_json"),
        ('{"a": 1} {"b": 2}', "invalid_json"),
        ('{"valor": NaN}', "non_finite_number"),
        ('{"valor": 1, "valor": 2}', "duplicate_key"),
        (None, "not_text"),
        ({"ok": True}, "not_text"),
    ],
)
def test_parse_rejects_prose_and_malformed(text, code):
    with pytest.raises(JsonObjectError) as excinfo:
        parse_json_object(text)
    assert excinfo.value.code == code


def test_parse_error_never_carries_the_received_text():
    marker = "conteudo-sintetico-sensivel-12345"
    with pytest.raises(JsonObjectError) as excinfo:
        parse_json_object('{"extrato": "%s",}' % marker)
    assert marker not in str(excinfo.value)
    assert marker not in repr(excinfo.value)
    # Nem encadeado: o JSONDecodeError original guarda o texto inteiro em
    # ``.doc`` e ``from None`` só o esconderia do traceback.
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None


def test_parse_uses_decimal_instead_of_float():
    parsed = parse_json_object('{"valor": 1234.56, "quantidade": 3}')
    assert parsed["valor"] == Decimal("1234.56") and isinstance(parsed["valor"], Decimal)
    assert isinstance(parsed["quantidade"], int)
    # O resto da plataforma recusa float; o resultado do parse precisa passar.
    assert canonical_json(parsed) == '{"quantidade":3,"valor":"1234.56"}'


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["despesa", "receita"]},
        "descricao": {"type": "string", "minLength": 3, "maxLength": 20},
        "valor": {"type": "number", "minimum": 0, "maximum": 1000},
        "parcelas": {"type": "integer", "minimum": 1},
        "observacao": {"type": ["string", "null"]},
        "itens": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {"nome": {"type": "string"}},
                "required": ["nome"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tipo", "valor"],
    "additionalProperties": False,
}


def valid_value():
    return {
        "tipo": "despesa",
        "descricao": "Conta de luz",
        "valor": Decimal("123.45"),
        "parcelas": 2,
        "observacao": None,
        "itens": [{"nome": "energia"}],
    }


def test_valid_value_has_no_errors():
    assert validate_schema(valid_value(), SCHEMA) == []


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda v: v.pop("valor"), "$.valor: propriedade obrigatória ausente"),
        (lambda v: v.update(extra="x"), "$.extra: propriedade não permitida"),
        (lambda v: v.update(tipo="transferencia"), "$.tipo: valor fora da lista permitida"),
        (lambda v: v.update(tipo=7), "$.tipo: tipo esperado string, recebido number"),
        (lambda v: v.update(descricao="ab"), "$.descricao: texto menor que 3"),
        (lambda v: v.update(descricao="x" * 21), "$.descricao: texto maior que 20"),
        (lambda v: v.update(valor=Decimal("-0.01")), "$.valor: número menor que 0"),
        (lambda v: v.update(valor=1000.5), "$.valor: número maior que 1000"),
        (lambda v: v.update(valor="12.00"), "$.valor: tipo esperado number, recebido string"),
        (lambda v: v.update(valor=True), "$.valor: tipo esperado number, recebido boolean"),
        (lambda v: v.update(parcelas=Decimal("1.5")), "$.parcelas: tipo esperado integer"),
        (lambda v: v.update(parcelas=0), "$.parcelas: número menor que 1"),
        (lambda v: v.update(observacao=3), "$.observacao: tipo esperado string ou null"),
        (lambda v: v.update(itens=[]), "$.itens: lista com menos de 1"),
        (lambda v: v.update(itens=[{"nome": "a"}] * 3), "$.itens: lista com mais de 2"),
        (lambda v: v.update(itens=[{"nome": "a"}, {"nome": 1}]), "$.itens[1].nome: tipo esperado string"),
        (lambda v: v.update(itens=[{"nome": "a", "x": 1}]), "$.itens[0].x: propriedade não permitida"),
        (lambda v: v.update(itens="energia"), "$.itens: tipo esperado array, recebido string"),
    ],
)
def test_each_rule_is_enforced(mutate, fragment):
    value = valid_value()
    mutate(value)
    errors = validate_schema(value, SCHEMA)
    assert any(fragment in error for error in errors), errors


def test_integer_accepts_integral_decimal_and_boolean_is_not_a_number():
    schema = {"type": "object", "properties": {"n": {"type": "integer"}, "ativo": {"type": "boolean"}}}
    assert validate_schema({"n": Decimal("3.0"), "ativo": False}, schema) == []
    assert validate_schema({"n": True}, schema) != []
    # ``true`` não é igual a 1 em JSON, embora seja em Python.
    assert validate_schema({"x": True}, {"type": "object", "properties": {"x": {"enum": [1]}}}) != []
    assert validate_schema({"x": 1}, {"type": "object", "properties": {"x": {"enum": [Decimal("1.0")]}}}) == []


def test_errors_describe_rule_and_path_but_not_the_value():
    marker = "conteudo-sintetico-sensivel-98765"
    errors = validate_schema({"tipo": marker, "valor": 1}, SCHEMA)
    assert errors and all(marker not in error for error in errors)


def test_unknown_schema_keyword_fails_closed():
    schema = {"type": "object", "properties": {"cpf": {"type": "string", "pattern": "^[0-9]{11}$"}}}
    assert unsupported_keywords(schema) == ["pattern"]
    # Ignorar "pattern" faria um valor inválido passar como válido.
    with pytest.raises(SchemaNotSupportedError):
        validate_schema({"cpf": "abc"}, schema)
    assert unsupported_keywords({"anyOf": [{"type": "string"}]}) == ["anyOf"]
    assert unsupported_keywords(SCHEMA) == []
    assert unsupported_keywords({"type": "object", "title": "t", "description": "d", "default": {}}) == []


@pytest.mark.parametrize(
    "schema, reported",
    [
        ({"type": "object", "properties": {"a": {"type": "string", "minLength": "1"}}}, "minLength (valor inválido)"),
        ({"type": "string", "maxLength": -1}, "maxLength (valor inválido)"),
        ({"type": "array", "minItems": 1.5}, "minItems (valor inválido)"),
        ({"type": "array", "maxItems": True}, "maxItems (valor inválido)"),
        ({"type": "number", "minimum": "0"}, "minimum (valor inválido)"),
        ({"type": "number", "maximum": False}, "maximum (valor inválido)"),
        ({"type": "number", "maximum": float("nan")}, "maximum (valor inválido)"),
        ({"type": "object", "required": 5}, "required (formato inválido)"),
        ({"type": "object", "required": ["a", 1]}, "required (formato inválido)"),
        ({"enum": 7}, "enum (formato inválido)"),
        ({"type": "object", "additionalProperties": "false"}, "additionalProperties (formato inválido)"),
        ({"type": []}, "type (lista vazia)"),
        ({"type": 5}, "type=int"),
        ({"type": ["string", None]}, "type=NoneType"),
    ],
)
def test_malformed_keyword_value_is_reported_instead_of_crashing_later(schema, reported):
    # A checagem prévia olha também os VALORES. Sem isso o defeito só apareceria
    # como TypeError na validação, depois de a inferência já ter sido feita.
    assert unsupported_keywords(schema) == [reported]
    for value in ("x", 1, [1], {"a": "x"}):
        with pytest.raises(SchemaNotSupportedError):
            validate_schema(value, schema)


def test_well_formed_keyword_values_are_still_accepted():
    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "number", "minimum": Decimal("0.5"), "maximum": 10.5},
            "s": {"type": "string", "minLength": 0, "maxLength": 3},
            "l": {"type": "array", "minItems": 0, "maxItems": 2, "items": {"enum": []}},
        },
        "required": [],
        "additionalProperties": {"type": "integer"},
    }
    assert unsupported_keywords(schema) == []
    assert validate_schema({"n": 1, "s": "abc", "l": [], "outro": 3}, schema) == []
    assert validate_schema({"n": Decimal("0.4"), "outro": "x"}, schema) != []


def test_validate_structured_output_combines_parse_and_schema():
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    assert validate_structured_output('{"ok": true}', schema) == ({"ok": True}, [])
    parsed, errors = validate_structured_output("resposta em prosa", schema)
    assert parsed is None and errors
    parsed, errors = validate_structured_output('{"ok": "sim"}', schema)
    assert parsed is None and "$.ok: tipo esperado boolean" in errors[0]
