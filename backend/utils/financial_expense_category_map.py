"""
Mapeia nome de categoria do plano (transações) para slug de contas a pagar.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

ALLOWED_PAYABLE_CATEGORIES = frozenset(
    {
        "moradia",
        "educação",
        "saúde",
        "transporte",
        "veículos",
        "cartões",
        "dívidas",
        "família",
        "serviços",
        "utilidades",
        "impostos",
        "alimentação",
        "pessoal",
        "outros",
    }
)


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFD", text.strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def map_category_name_to_payable(category_name: Optional[str]) -> str:
    """
    Converte nome livre (ex.: categoria do utilizador) para uma categoria permitida
    em financial_expenses.category.
    """
    if not category_name or not str(category_name).strip():
        return "outros"
    raw = str(category_name).strip().lower()
    if raw in ALLOWED_PAYABLE_CATEGORIES:
        return raw
    folded = _fold(category_name)

    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("moradia", ("moradia", "casa", "aluguel", "condomin", "iptu", "luz", "agua", "energia")),
        ("utilidades", ("utilidade", "internet", "telefone", "celular", "fibra")),
        ("alimentação", ("aliment", "mercado", "supermercado", "ifood", "restaurant", "lanche", "padaria")),
        ("transporte", ("transport", "uber", "99", "onibus", "metro", "combustivel", "gasolina", "estacion")),
        ("veículos", ("veiculo", "carro", "ipva", "licenci", "mecanica", "oficina")),
        ("saúde", ("saude", "plano", "medico", "farmacia", "hospital", "dentista")),
        ("educação", ("educac", "escola", "faculdade", "curso", "mensalidade")),
        ("cartões", ("cartao", "credito", "fatura")),
        ("dívidas", ("divida", "emprestimo", "financiamento", "banco")),
        ("impostos", ("imposto", "irpf", "das", "darf", "tribut")),
        ("serviços", ("servico", "assinatura", "netflix", "spotify", "software", "saas")),
        ("família", ("familia", "filho", "escola infantil")),
        ("pessoal", ("pessoal", "cabele", "roupa", "academia")),
    )
    for slug, needles in rules:
        for n in needles:
            if n in folded:
                return slug
    # Heurística: token único próximo do slug
    tokens = re.split(r"[^\w]+", folded, flags=re.UNICODE)
    for t in tokens:
        if t in ALLOWED_PAYABLE_CATEGORIES:
            return t
    return "outros"
