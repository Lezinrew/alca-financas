"""Guarda numérica do resumo e resumo determinístico (contrato, seções 6 e 9).

O modelo escreve o texto; o backend é dono dos números. Antes de entregar o
``summary_pt_br`` ao titular, todo valor monetário citado no texto (e todo
inteiro grande que possa ser um valor) precisa existir nos fatos calculados
pelas ferramentas. Se algum valor não tiver
lastro, o texto do modelo é descartado e substituído por um resumo montado só
com os fatos, e a execução ganha um aviso.

Por que substituir o texto inteiro em vez de apagar só o número? Um valor
inventado costuma vir acompanhado de uma conclusão inventada ("você
economizou..."). Remover o número deixaria a conclusão de pé.

A comparação é por ``Decimal``: "1.234,56", "1234,56", "1234.56" e
"R$ 1.234,56" são o mesmo valor. Nunca se usa float.

Limite conhecido: a guarda lê números escritos com algarismos. Um inteiro
pequeno sem marca de moeda ("deve 500 no total") é tratado como contagem, e um
inteiro entre 1900 e 2100 como ano; valores por extenso não são reconhecidos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


SUMMARY_MAX_CHARS = 2000
MAX_FACTS_IN_SUMMARY = 8

WARNING_UNBACKED = (
    "O resumo gerado pelo modelo citava valores que não constam nos dados consultados e foi "
    "substituído por um resumo calculado pelo sistema."
)
WARNING_NO_DATA = (
    "O resumo gerado pelo modelo citava números sem que nenhum dado tivesse sido consultado e foi "
    "substituído por um resumo calculado pelo sistema."
)
WARNING_EMPTY = "O modelo não devolveu um resumo válido; o texto exibido foi montado pelo sistema."

NO_DATA_TEXT = "Não há dados suficientes para responder a este pedido."

# Um número "candidato": começa e termina em dígito, com pontos e vírgulas no meio.
_NUMBER = re.compile(r"\d[\d.,]*\d|\d")
_CURRENCY_BEFORE = re.compile(r"(?:R\$|US\$|BRL|USD|\$)\s*[-−]?\s*$", re.IGNORECASE)
_NEGATIVE_BEFORE = re.compile(r"[-−]\s*(?:R\$|US\$|BRL|USD|\$)?\s*$", re.IGNORECASE)
_MULTIPLIER_AFTER = re.compile(r"^\s*(mil(?:h(?:ão|ões|ao|oes))?|bilh(?:ão|ões|ao|oes))\b", re.IGNORECASE)
_UNIT_AFTER = re.compile(r"^\s*(?:de\s+)?(reais|real|centavos?|BRL)\b", re.IGNORECASE)
# Controles C0 (menos TAB, LF e CR), DEL e substitutos isolados: nada disso é
# texto para o titular, e NUL/substituto nem podem ser gravados no banco.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]")

_MULTIPLIERS = {"mil": Decimal(1000), "milh": Decimal(1000000), "bilh": Decimal(1000000000)}

# Inteiro "solto" (sem moeda, unidade nem casas decimais) a partir deste valor
# precisa de lastro. Abaixo dele quase sempre é contagem ou dia ("3 contas",
# "120 lançamentos", "dia 15"); exigir lastro trocaria resumos corretos.
LOOSE_INTEGER_MIN = Decimal(1000)
# Inteiro solto nesta faixa é lido como ano ("em 2026").
_YEAR_MIN, _YEAR_MAX = Decimal(1900), Decimal(2100)


@dataclass(frozen=True)
class NumberClaim:
    """Um número citado no resumo que precisa de lastro nos fatos.

    ``explicit_money``: o texto o apresenta como dinheiro (símbolo de moeda,
    "reais"/"centavos" ou casas decimais) e só um fato monetário o lastreia.
    Quando falso, é um inteiro grande sem marca ("5000", "9.999", "5 mil"): pode
    ser valor ou contagem, então um fato de contagem também serve de lastro.
    """

    value: Decimal
    explicit_money: bool


def _parse(token: str) -> Optional[Tuple[Decimal, bool]]:
    """Número e se ele foi escrito COM parte decimal ("1.250,00" sim; "1.250" não)."""
    text = token.strip()
    if not text or not text[0].isdigit() or not text[-1].isdigit():
        return None
    has_decimal = False
    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
        if text.count(".") != 1:
            return None
        has_decimal = True
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        head, _, tail = text.rpartition(sep)
        # "0,125" é decimal: nenhum número com separador de milhar começa por zero.
        thousands = len(tail) == 3 and 1 <= len(head) <= 3 and not head.startswith("0")
        if text.count(sep) > 1 or thousands:
            text = text.replace(sep, "")
        else:
            text = text.replace(sep, ".")
            has_decimal = True
    try:
        return Decimal(text), has_decimal
    except InvalidOperation:
        return None


def parse_number(token: str) -> Optional[Decimal]:
    """Converte um número escrito em pt-BR ou no formato de máquina.

    Regra dos separadores: havendo ponto e vírgula, o ÚLTIMO é o decimal
    ("1.234,56" e "1,234.56"). Havendo um só tipo, ele é separador de milhar
    quando se repete ("1.234.567") ou quando vem seguido de exatamente três
    dígitos ("1.234"); caso contrário é decimal ("1234,56", "1234.5").
    """
    parsed = _parse(token)
    return parsed[0] if parsed is not None else None


def _is_composite(text: str, start: int, end: int) -> bool:
    """O número é um pedaço de data ou de identificador?

    "01/10/2026", "2026-10-01", "12345-6", "12.345.678/0001-90": o número está
    colado, por "/" ou "-", a OUTRO número. Um "/" seguido de palavra não conta
    ("9.999,99/mês" é um valor por mês), nem um "-" depois de espaço (sinal de
    negativo: "saldo de -5000").
    """
    if start >= 2 and text[start - 1] in "/-" and text[start - 2].isdigit():
        return True
    return end + 1 < len(text) and text[end] in "/-" and text[end + 1].isdigit()


def extract_claims(text: str) -> List[NumberClaim]:
    """Números do texto que só podem ser afirmados com lastro nos fatos.

    Dinheiro explícito (``explicit_money=True``):

    * depois de um símbolo de moeda ("R$ 500", "R$ 2 mil");
    * antes de "reais"/"real"/"centavos" ("500 reais", "2 mil reais");
    * com parte decimal ("1.250,00", "1250.00", "12.345,6", "9.999,99/mês"),
      desde que não seja percentual.

    Inteiro grande sem marca (``explicit_money=False``): "5000", "9.999",
    "5 mil" — a partir de ``LOOSE_INTEGER_MIN``, fora anos e pedaços de data ou
    de identificador.

    Ficam de fora contagens pequenas ("3 contas"), dias, anos, percentuais,
    datas e identificadores: exigir lastro deles derrubaria resumos corretos.
    """
    text = text or ""
    claims: List[NumberClaim] = []
    for match in _NUMBER.finditer(text):
        token = match.group(0)
        start, end = match.start(), match.end()
        previous = text[start - 1] if start > 0 else ""
        parsed = _parse(token)
        if parsed is None:
            continue
        value, has_decimal = parsed
        before = text[max(0, start - 8):start]
        after = text[end:end + 32]
        has_currency = _CURRENCY_BEFORE.search(before) is not None
        if not has_currency and (previous.isalpha() or previous == "_"):
            continue  # pedaço de identificador ("v1.25", "conta_2")
        multiplier = _MULTIPLIER_AFTER.match(after)
        after_unit = after[multiplier.end():] if multiplier else after
        unit = _UNIT_AFTER.match(after_unit)
        percent = after.lstrip().startswith("%")
        has_separator = "." in token or "," in token

        if multiplier is not None:
            word = multiplier.group(1).lower()
            value = value * _MULTIPLIERS["mil" if word == "mil" else word[:4]]
        if unit is not None and unit.group(1).lower().startswith("centavo"):
            value = value / Decimal(100)

        if has_currency or unit is not None:
            explicit = True
        elif percent:
            continue
        elif has_decimal:
            # Casas decimais em um resumo financeiro são dinheiro. A regra NÃO
            # olha a "/" seguinte: "9.999,99/mês" é valor, não data.
            explicit = True
        elif _is_composite(text, start, end):
            continue
        else:
            year_like = not has_separator and multiplier is None and _YEAR_MIN <= value <= _YEAR_MAX
            if abs(value) < LOOSE_INTEGER_MIN or year_like:
                continue
            explicit = False
        if _NEGATIVE_BEFORE.search(before) is not None:
            value = -value
        claims.append(NumberClaim(value=value, explicit_money=explicit))
    return claims


def extract_money_values(text: str) -> List[Decimal]:
    """Valores de ``extract_claims``, na ordem em que aparecem no texto."""
    return [claim.value for claim in extract_claims(text)]


def _fact_dict(fact: Any) -> Dict[str, Any]:
    return fact if isinstance(fact, dict) else fact.to_dict()


def _backed_values(facts: Iterable[Any], unit: str) -> Set[Decimal]:
    backed: Set[Decimal] = set()
    for item in facts:
        fact = _fact_dict(item)
        # Fato sem valor NÃO entra, nem como zero: "sem dado" não autoriza o
        # modelo a escrever "R$ 0,00".
        if fact.get("unit") != unit or fact.get("value") is None:
            continue
        try:
            backed.add(abs(Decimal(str(fact["value"]))))
        except InvalidOperation:
            continue
    return backed


def backed_count_values(facts: Iterable[Any]) -> Set[Decimal]:
    """Contagens calculadas pelo backend (fatos com ``unit == "count"``)."""
    return _backed_values(facts, "count")


def backed_money_values(facts: Iterable[Any]) -> Set[Decimal]:
    """Valores absolutos lastreados: fatos monetários com valor presente.

    O sinal não entra na comparação: "saldo negativo de R$ 50,00" e o fato
    "-50.00" descrevem o mesmo número. Fato sem valor (``value`` nulo) não
    lastreia nada — ausência de dado nunca vira zero.
    """
    return _backed_values(facts, "money")


def format_money_pt_br(value: Any, currency: Optional[str] = "BRL") -> str:
    """``Decimal("1250")`` -> ``"R$ 1.250,00"``."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    sign = "-" if amount < 0 else ""
    integer, _, cents = str(abs(amount)).partition(".")
    groups: List[str] = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    symbol = "R$" if (currency or "BRL").upper() == "BRL" else (currency or "").upper()
    return "%s%s %s,%s" % (sign, symbol, ".".join(groups), cents or "00")


def _fact_line(fact: Dict[str, Any]) -> str:
    label = str(fact.get("label") or fact.get("key") or "Dado")
    period = fact.get("period") if isinstance(fact.get("period"), dict) else {}
    period_label = period.get("label")
    head = "%s (%s)" % (label, period_label) if period_label else label
    if fact.get("value") is None:
        reason = fact.get("missing_reason")
        return "%s: sem dado disponível%s." % (head, " (%s)" % reason if reason else "")
    if fact.get("unit") == "money":
        try:
            return "%s: %s." % (head, format_money_pt_br(fact["value"], fact.get("currency")))
        except InvalidOperation:
            return "%s: sem dado disponível." % head
    return "%s: %s." % (head, fact["value"])


def deterministic_summary(
    facts: Sequence[Any],
    *,
    proposal_ids: Sequence[str] = (),
    operation_ids: Sequence[str] = (),
    waiting_review: bool = False,
) -> str:
    """Resumo montado só com a verdade do backend, sem texto do modelo."""
    lines: List[str] = []
    fact_dicts = [_fact_dict(item) for item in facts]
    for fact in fact_dicts[:MAX_FACTS_IN_SUMMARY]:
        lines.append(_fact_line(fact))
    extra = len(fact_dicts) - MAX_FACTS_IN_SUMMARY
    if extra > 0:
        lines.append("Há mais %d dado(s) nos detalhes desta execução." % extra)
    if operation_ids:
        total = len(operation_ids)
        lines.append(
            "1 operação foi registrada." if total == 1 else "%d operações foram registradas." % total
        )
    if proposal_ids and (waiting_review or not operation_ids):
        total = len(proposal_ids)
        lines.append(
            "Há 1 proposta aguardando a sua revisão."
            if total == 1
            else "Há %d propostas aguardando a sua revisão." % total
        )
    if not lines:
        return NO_DATA_TEXT
    return " ".join(lines)[:SUMMARY_MAX_CHARS]


def clean_summary(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return _CONTROL.sub("", text).strip()[:SUMMARY_MAX_CHARS]


@dataclass
class SummaryOutcome:
    text: str
    warnings: List[str] = field(default_factory=list)
    replaced: bool = False


def guard_summary(
    model_summary: Any,
    facts: Sequence[Any],
    *,
    tools_succeeded: bool,
    proposal_ids: Sequence[str] = (),
    operation_ids: Sequence[str] = (),
    waiting_review: bool = False,
) -> SummaryOutcome:
    """Valida o resumo do modelo contra os fatos; substitui se não tiver lastro."""

    def replaced(warning: str) -> SummaryOutcome:
        return SummaryOutcome(
            text=deterministic_summary(
                facts, proposal_ids=proposal_ids, operation_ids=operation_ids, waiting_review=waiting_review
            ),
            warnings=[warning],
            replaced=True,
        )

    text = clean_summary(model_summary)
    if not text:
        return replaced(WARNING_EMPTY)
    if not facts and not tools_succeeded and any(char.isdigit() for char in text):
        # Sem nenhuma consulta bem-sucedida, qualquer número é afirmação sem
        # origem — mesmo que não tenha "cara" de dinheiro.
        return replaced(WARNING_NO_DATA)
    money = backed_money_values(facts)
    # Inteiro grande sem marca de moeda pode ser valor ou contagem: aceita os dois lastros.
    loose = money | backed_count_values(facts)
    unbacked = [
        claim for claim in extract_claims(text)
        if abs(claim.value) not in (money if claim.explicit_money else loose)
    ]
    if unbacked:
        return replaced(WARNING_UNBACKED)
    return SummaryOutcome(text=text)
