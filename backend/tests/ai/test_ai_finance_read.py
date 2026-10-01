"""finance.read: fatos com fonte, escopo declarado e isolamento (AC-01, AC-08, AC-14)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from services.ai.errors import AiError
from services.ai.finance import read, repository

from .support import finance_helpers as fh
from .support import seed


MONEY = re.compile(r"^-?\d+\.\d{2}$")


def _error(function, *args, **kwargs) -> AiError:
    with pytest.raises(AiError) as excinfo:
        function(*args, **kwargs)
    return excinfo.value


# ---------------------------------------------------------------------------
# AC-08: valores exatos, com fonte.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_realized_totals_match_independent_numeric_aggregation(pool, world):
    ctx = world.context(pool)
    account, expense_cat, income_cat = world.personal_account_id, world.expense_category_id, world.income_category_id
    # 0.10 + 0.20 é o caso clássico em que float dá 0.30000000000000004.
    fh.bulk_transactions(pool, world.tenant_id, account, expense_cat, ["0.10", "0.20"])
    many = [Decimal(index * 37 % 9973 + 1) / Decimal(100) for index in range(1500)]
    fh.bulk_transactions(pool, world.tenant_id, account, expense_cat, many)
    incomes = ["1234.56", "0.01", "9999999.99"]
    fh.bulk_transactions(pool, world.tenant_id, account, income_cat, incomes, tx_type="income")

    result = read.realized_totals(pool, ctx, month=10, year=2026)
    facts = fh.facts_by_key(result)

    # Segunda opinião: agregação NUMERIC escrita aqui, sem código do repositório.
    independent = {
        row["type"]: row["total"]
        for row in fh.fetch_all(
            pool, world.tenant_id,
            """
            SELECT type, sum(amount)::numeric AS total FROM transactions
            WHERE tenant_id = %s AND account_id = %s AND status = 'paid'
              AND source_file ILIKE %s AND occurred_on BETWEEN %s AND %s
            GROUP BY type
            """,
            (world.tenant_id, account, "%.ofx", date(2026, 10, 1), date(2026, 10, 31)),
        )
    }
    expected_expense = fh.decimal_sum(["0.10", "0.20"]) + fh.decimal_sum(many)
    expected_income = fh.decimal_sum(incomes)
    assert Decimal(facts["realized.expense"].value) == independent["expense"] == expected_expense
    assert Decimal(facts["realized.income"].value) == independent["income"] == expected_income
    assert Decimal(facts["realized.net"].value) == expected_income - expected_expense
    # String decimal com duas casas, moeda ISO e nada de float.
    for key in ("realized.expense", "realized.income", "realized.net"):
        assert MONEY.match(facts[key].value) and facts[key].currency == "BRL"
    result.to_dict()


@pytest.mark.integration
def test_point_ten_plus_point_twenty_is_exactly_point_thirty(pool, world):
    ctx = world.context(pool)
    fh.bulk_transactions(pool, world.tenant_id, world.personal_account_id, world.expense_category_id, ["0.10", "0.20"])
    facts = fh.facts_by_key(read.realized_totals(pool, ctx, month=10, year=2026))
    assert facts["realized.expense"].value == "0.30"


@pytest.mark.integration
def test_realized_ignores_csv_manual_legacy_and_non_paid(pool, world):
    ctx = world.context(pool)
    account, category = world.personal_account_id, world.expense_category_id
    tenant = world.tenant_id
    fh.bulk_transactions(pool, tenant, account, category, ["100.00"])  # canônica
    # Sufixo em maiúsculas e entry_source 'manual': o critério é o source_file.
    fh.bulk_transactions(pool, tenant, account, category, ["7.00"], source_file="EXTRATO.OFX", entry_source="manual")
    # Tudo abaixo fica de fora.
    fh.bulk_transactions(pool, tenant, account, category, ["11.00"], source_file="planilha.csv", entry_source="csv")
    fh.bulk_transactions(pool, tenant, account, category, ["13.00"], source_file=None, entry_source="manual")
    # OFX rebaixado pelo script de sincronização: entry_source continua 'ofx'.
    fh.bulk_transactions(pool, tenant, account, category, ["17.00"], source_file="legacy:extrato.ofx:excluded")
    fh.bulk_transactions(pool, tenant, account, category, ["19.00"], status="pending")
    fh.bulk_transactions(pool, tenant, account, category, ["23.00"], status="canceled")

    facts = fh.facts_by_key(read.realized_totals(pool, ctx, month=10, year=2026))
    assert facts["realized.expense"].value == "107.00"

    by_category = read.spending_by_category(pool, ctx, month=10, year=2026)
    assert fh.facts_by_key(by_category)["spending.total"].value == "107.00"


@pytest.mark.integration
def test_missing_data_is_none_with_reason_never_zero(pool, world):
    ctx = world.context(pool)
    for result in (
        read.realized_totals(pool, ctx, month=10, year=2026),
        read.spending_by_category(pool, ctx, month=10, year=2026),
        read.payables_overview(pool, ctx, month=10, year=2026),
        read.payables_list(pool, ctx, month=10, year=2026),
    ):
        assert result.facts, "consulta sem fatos"
        for fact in result.facts:
            assert fact.value is None, fact.key
            assert fact.missing_reason and len(fact.missing_reason) > 10
            assert fact.currency is None

    # Só receita no período: a despesa continua AUSENTE (não vira 0.00).
    fh.bulk_transactions(
        pool, world.tenant_id, world.personal_account_id, world.income_category_id, ["50.00"], tx_type="income"
    )
    facts = fh.facts_by_key(read.realized_totals(pool, ctx, month=10, year=2026))
    assert facts["realized.income"].value == "50.00"
    assert facts["realized.expense"].value is None and facts["realized.expense"].missing_reason
    assert facts["realized.transfers"].value is None
    assert facts["realized.net"].value == "50.00"


@pytest.mark.integration
def test_zero_is_reported_only_when_it_is_a_real_number(pool, world):
    """Conta sem pagamento tem 'pago = 0.00' de verdade; isso não é ausência."""
    ctx = world.context(pool)
    seed.create_payable(
        pool, world.tenant_id, world.personal_space_id, title="Internet", amount_expected="120.00",
        competency_month=fh.OCT,
    )
    facts = fh.facts_by_key(read.payables_overview(pool, ctx, month=10, year=2026))
    assert facts["payables.paid"].value == "0.00" and facts["payables.paid"].missing_reason is None
    assert facts["payables.remaining"].value == "120.00"
    assert facts["payables.count.paid"].value == "0"


@pytest.mark.integration
def test_every_fact_has_a_resolvable_source_and_declared_scope(pool, world):
    ctx = world.context(pool)
    business = world.context(pool, "business")
    fh.grant(pool, world, "personal")
    fh.grant(pool, world, "business")
    fh.bulk_transactions(pool, world.tenant_id, world.personal_account_id, world.expense_category_id, ["10.00"])
    fh.bulk_transactions(pool, world.tenant_id, world.business_account_id, world.income_category_id, ["30.00"],
                         tx_type="income")
    seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Aluguel", amount_expected="900.00",
                        competency_month=fh.OCT, due_date=date(2026, 10, 10))

    results = [read.run_query(pool, ctx, query, month=10, year=2026) for query in read.QUERIES if query != "accounts"]
    results.append(read.run_query(pool, ctx, "accounts"))
    results.append(read.run_query(pool, business, "realized_totals", date_from="2026-10-01", date_to="2026-10-31"))
    assert len(results) == len(read.QUERIES) + 1
    for result in results:
        refs = {source.ref for source in result.sources}
        assert result.facts
        for fact in result.facts:
            assert fact.source_refs, fact.key
            assert set(fact.source_refs) <= refs, fact.key
            assert fact.as_of.endswith("Z")
            assert fact.scope["declared"] and "kind" in fact.scope and "financial_space_id" in fact.scope
            assert set(fact.period) == {"kind", "start", "end", "label"}
            assert (fact.value is None) != (fact.missing_reason is None)
            if fact.value is not None and fact.unit == "money":
                assert MONEY.match(fact.value) and fact.currency == "BRL"
        for source in result.sources:
            assert source.kind == "sql" and source.as_of
        result.to_dict()  # falha se houver float


# ---------------------------------------------------------------------------
# AC-14: mensal x anual x global; status derivado.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_monthly_annual_and_global_scopes_are_declared_and_never_mixed(pool, world):
    ctx = world.context(pool)
    tenant, space = world.tenant_id, world.personal_space_id
    october = seed.create_payable(pool, tenant, space, title="Aluguel out", amount_expected="300.10",
                                  competency_month=fh.OCT)
    seed.create_payable(pool, tenant, space, title="Aluguel nov", amount_expected="500.20", competency_month=fh.NOV)
    seed.create_payable(pool, tenant, space, title="Seguro 2025", amount_expected="700.30",
                        competency_month=date(2025, 1, 1))
    fh.add_payment(pool, tenant, october, "100.05")

    monthly = read.payables_overview(pool, ctx, month=10, year=2026)
    annual = read.payables_overview(pool, ctx, year=2026)
    overall = read.payables_overview(pool, ctx)

    def numbers(result):
        facts = fh.facts_by_key(result)
        return tuple(facts[key].value for key in ("payables.expected", "payables.paid", "payables.remaining"))

    assert numbers(monthly) == ("300.10", "100.05", "200.05")
    assert numbers(annual) == ("800.30", "100.05", "700.25")
    assert numbers(overall) == ("1500.60", "100.05", "1400.55")

    # Agregação independente do total global.
    independent = fh.fetch_value(
        pool, tenant,
        "SELECT sum(p.amount_expected)::numeric FROM payables p JOIN financial_space_payables l "
        "ON l.payable_id = p.id WHERE p.tenant_id = %s AND l.financial_space_id = %s",
        (tenant, space),
    )
    assert Decimal(numbers(overall)[0]) == independent

    declared = [result.facts[0].scope["declared"] for result in (monthly, annual, overall)]
    assert declared == ["competência mensal", "competência anual", "global (todas as competências)"]
    kinds = [result.facts[0].period["kind"] for result in (monthly, annual, overall)]
    assert kinds == ["month", "year", "all"]
    assert monthly.facts[0].period["start"] == "2026-10-01" and monthly.facts[0].period["end"] == "2026-10-31"
    assert overall.facts[0].period["start"] is None
    # Cada escopo tem a própria referência de fonte: não dá para citar um pelo outro.
    refs = {result.sources[0].ref for result in (monthly, annual, overall)}
    assert len(refs) == 3
    assert all(fact.scope["declared"] == "competência mensal" for fact in monthly.facts)


@pytest.mark.integration
def test_month_without_year_and_inapplicable_filters_are_rejected(pool, world):
    ctx = world.context(pool)
    assert _error(read.payables_overview, pool, ctx, month=10).code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "payables_overview", date_from="2026-10-01",
                  date_to="2026-10-31").code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "payables_overview", month=10, year=2026,
                  account_id=world.personal_account_id).code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "realized_totals", month=10, year=2026, limit=5).code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "realized_totals", month=10, year=2026,
                  date_from="2026-10-01", date_to="2026-10-02").code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "realized_totals", date_from="2026-10-01").code == "invalid_request"
    assert _error(read.run_query, pool, ctx, "select * from payables").code == "invalid_request"


@pytest.mark.integration
def test_payable_status_is_derived_from_valid_payments(pool, world):
    ctx = world.context(pool)
    tenant, space = world.tenant_id, world.personal_space_id

    def payable(title, amount):
        return seed.create_payable(pool, tenant, space, title=title, amount_expected=amount, competency_month=fh.OCT)

    pending = payable("Pendente", "100.00")
    partial = payable("Parcial", "100.00")
    paid = payable("Quitada", "100.00")
    canceled = payable("Cancelada", "100.00")
    reversed_only = payable("Só pagamento revertido", "100.00")
    fh.add_payment(pool, tenant, partial, "40.00")
    fh.add_payment(pool, tenant, partial, "0.50")
    fh.add_payment(pool, tenant, paid, "60.00")
    fh.add_payment(pool, tenant, paid, "40.00")
    fh.add_payment(pool, tenant, canceled, "30.00")
    fh.cancel_payable(pool, tenant, canceled)
    fh.add_payment(pool, tenant, reversed_only, "100.00", reversed_reason="lançado por engano")

    items = {item["payable_id"]: item for item in read.payables_list(pool, ctx, month=10, year=2026).data["items"]}
    assert items[pending]["status"] == "pending" and items[pending]["remaining"] == "100.00"
    assert items[partial]["status"] == "partial"
    assert (items[partial]["paid"], items[partial]["remaining"]) == ("40.50", "59.50")
    assert items[paid]["status"] == "paid" and items[paid]["remaining"] == "0.00"
    assert items[canceled]["status"] == "canceled" and items[canceled]["remaining"] is None
    # Pagamento revertido não conta: a conta volta a pendente.
    assert items[reversed_only]["status"] == "pending" and items[reversed_only]["paid"] == "0.00"

    # A regra em Python (usada no "depois" das propostas) é a mesma do SQL.
    for item in items.values():
        assert item["status"] == repository.derive_payable_status(
            Decimal(item["amount_expected"]), Decimal(item["paid"]), item["status"] == "canceled"
        )

    facts = fh.facts_by_key(read.payables_overview(pool, ctx, month=10, year=2026))
    counts = {status: facts["payables.count.%s" % status].value for status in repository.PAYABLE_STATUSES}
    assert counts == {"pending": "2", "partial": "1", "paid": "1", "canceled": "1"}
    # Cancelada fora das somas; restante só de pendente e parcial.
    assert facts["payables.expected"].value == "400.00"
    assert facts["payables.paid"].value == "140.50"
    assert facts["payables.remaining"].value == "259.50"


@pytest.mark.integration
def test_payables_list_pagination_with_scope_bound_cursor(pool, world):
    ctx = world.context(pool)
    tenant, space = world.tenant_id, world.personal_space_id
    created = [
        seed.create_payable(pool, tenant, space, title="Conta %d" % index, amount_expected="10.00",
                            competency_month=fh.OCT, due_date=date(2026, 10, due) if due else None)
        for index, due in enumerate([20, 5, None, 5, 12])
    ]
    seed.create_payable(pool, tenant, space, title="Novembro", amount_expected="10.00", competency_month=fh.NOV)

    seen, cursor, pages = [], None, 0
    while True:
        page = read.payables_list(pool, ctx, month=10, year=2026, cursor=cursor, limit=2)
        seen.extend(item["payable_id"] for item in page.data["items"])
        pages += 1
        cursor = page.data["next_cursor"]
        if cursor is None:
            break
        assert len(page.data["items"]) == 2
    assert pages == 3 and sorted(seen) == sorted(created) and len(set(seen)) == 5
    # Ordenado por vencimento; sem vencimento vai para o fim.
    assert seen[-1] == created[2]
    assert fh.facts_by_key(page)["payables.list.total"].value == "5"

    first = read.payables_list(pool, ctx, month=10, year=2026, limit=2)
    token = first.data["next_cursor"]
    assert token and tenant not in token and space not in token  # opaco
    # Cursor de outra consulta (outro período) ou de outro escopo: recusado.
    assert _error(read.payables_list, pool, ctx, month=11, year=2026, cursor=token).code == "invalid_request"
    assert _error(read.payables_list, pool, ctx, cursor=token).code == "invalid_request"
    business = world.context(pool, "business")
    assert _error(read.payables_list, pool, business, month=10, year=2026, cursor=token).code == "invalid_request"
    assert _error(read.payables_list, pool, ctx, month=10, year=2026, cursor="não-é-cursor").code == "invalid_request"
    assert _error(read.payables_list, pool, ctx, month=10, year=2026, limit=0).code == "invalid_request"
    assert _error(read.payables_list, pool, ctx, month=10, year=2026, limit=101).code == "invalid_request"


# ---------------------------------------------------------------------------
# AC-01: isolamento.
# ---------------------------------------------------------------------------
def _seed_isolation(pool, world, other_world):
    """Dados no espaço pessoal (os únicos que devem aparecer) e 'ruído' fora dele."""
    tenant = world.tenant_id
    fh.bulk_transactions(pool, tenant, world.personal_account_id, world.expense_category_id, ["10.00"])
    seed.create_payable(pool, tenant, world.personal_space_id, title="Minha conta", amount_expected="50.00",
                        competency_month=fh.OCT)
    # Outro espaço do mesmo tenant.
    fh.bulk_transactions(pool, tenant, world.business_account_id, world.expense_category_id, ["1000.00"])
    seed.create_payable(pool, tenant, world.business_space_id, title="Do negócio", amount_expected="5000.00",
                        competency_month=fh.OCT)
    # Conta e conta a pagar SEM vínculo com espaço algum.
    loose_account = seed.create_account(pool, tenant, None, "Conta sem vínculo")
    fh.bulk_transactions(pool, tenant, loose_account, world.expense_category_id, ["20000.00"])
    seed.create_payable(pool, tenant, None, title="Sem vínculo", amount_expected="30000.00", competency_month=fh.OCT)
    # Outro tenant.
    fh.bulk_transactions(pool, other_world.tenant_id, other_world.personal_account_id,
                         other_world.expense_category_id, ["400000.00"])
    seed.create_payable(pool, other_world.tenant_id, other_world.personal_space_id, title="De outro tenant",
                        amount_expected="500000.00", competency_month=fh.OCT)
    return loose_account


def _assert_only_personal(database_pool, ctx):
    monthly = read.realized_totals(database_pool, ctx, month=10, year=2026)
    assert fh.facts_by_key(monthly)["realized.expense"].value == "10.00"
    assert fh.facts_by_key(read.realized_totals(database_pool, ctx))["realized.expense"].value == "10.00"
    spending = read.spending_by_category(database_pool, ctx, month=10, year=2026)
    assert fh.facts_by_key(spending)["spending.total"].value == "10.00"
    assert fh.facts_by_key(read.payables_overview(database_pool, ctx))["payables.expected"].value == "50.00"
    listing = read.payables_list(database_pool, ctx)
    assert [item["title"] for item in listing.data["items"]] == ["Minha conta"]
    assert fh.facts_by_key(read.accounts(database_pool, ctx))["accounts.count"].value == "1"


@pytest.mark.integration
def test_other_space_unlinked_account_and_other_tenant_never_enter_totals(pool, world, other_world):
    ctx = world.context(pool)
    loose_account = _seed_isolation(pool, world, other_world)
    _assert_only_personal(pool, ctx)

    # Filtro por conta de outro espaço, sem vínculo ou de outro tenant: inexistente.
    for account in (world.business_account_id, loose_account, other_world.personal_account_id):
        assert _error(read.realized_totals, pool, ctx, month=10, year=2026, account_id=account).code == "not_found"
        assert _error(read.spending_by_category, pool, ctx, account_id=account).code == "not_found"
    own = read.realized_totals(pool, ctx, month=10, year=2026, account_id=world.personal_account_id)
    assert fh.facts_by_key(own)["realized.expense"].value == "10.00"


@pytest.mark.integration
def test_service_filters_hold_even_when_rls_is_bypassed(pool, admin_pool, world, other_world):
    """Com papel administrativo (RLS ignorado) os filtros do serviço bastam.

    As tabelas financeiras de 0001 não têm RLS; e mesmo nas que têm, o serviço
    não pode depender só dela.
    """
    ctx = world.context(pool)
    _seed_isolation(pool, world, other_world)
    _assert_only_personal(admin_pool, ctx)


@pytest.mark.integration
def test_totals_need_both_current_link_and_context_allowed_account(pool, world):
    """O contexto é resolvido antes; o vínculo é reconferido em cada consulta."""
    ctx = world.context(pool)
    fh.bulk_transactions(pool, world.tenant_id, world.personal_account_id, world.expense_category_id, ["10.00"])
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value == "10.00"
    # Conta vinculada ao espaço DEPOIS de o contexto ser resolvido: fora de
    # ``ctx.allowed_account_ids``, então não entra com o contexto antigo.
    late = seed.create_account(pool, world.tenant_id, world.personal_space_id, "Conta vinculada depois")
    fh.bulk_transactions(pool, world.tenant_id, late, world.expense_category_id, ["5.00"])
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value == "10.00"
    assert fh.facts_by_key(read.spending_by_category(pool, ctx))["spending.total"].value == "10.00"
    assert fh.facts_by_key(read.accounts(pool, ctx))["accounts.count"].value == "1"
    assert fh.facts_by_key(read.realized_totals(pool, world.context(pool)))["realized.expense"].value == "15.00"

    # Conta movida para OUTRO espaço depois de o contexto ser resolvido: ainda
    # consta no contexto antigo, mas o vínculo atual não é mais deste espaço.
    fh.execute(pool, world.tenant_id, "UPDATE financial_space_accounts SET financial_space_id = %s "
               "WHERE account_id = %s", (world.business_space_id, world.personal_account_id))
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value is None
    assert fh.facts_by_key(read.spending_by_category(pool, ctx))["spending.total"].value is None
    assert fh.facts_by_key(read.accounts(pool, ctx))["accounts.count"].value is None
    fh.execute(pool, world.tenant_id, "UPDATE financial_space_accounts SET financial_space_id = %s "
               "WHERE account_id = %s", (world.personal_space_id, world.personal_account_id))
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value == "10.00"

    # Vínculo removido depois: mesmo constando no contexto antigo, sai dos totais.
    fh.execute(pool, world.tenant_id, "DELETE FROM financial_space_accounts WHERE account_id = %s",
               (world.personal_account_id,))
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value is None


# ---------------------------------------------------------------------------
# AC-14: pessoal x negócio e consolidado.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_consolidated_requires_read_grant_in_every_space(pool, world):
    ctx = world.context(pool)
    fh.bulk_transactions(pool, world.tenant_id, world.personal_account_id, world.expense_category_id, ["10.00"])
    # Sem grant algum.
    assert _error(read.consolidated_realized_totals, pool, ctx, month=10, year=2026).code == "capability_denied"
    # Grant só no espaço pessoal.
    fh.grant(pool, world, "personal", capabilities=["finance.read"])
    assert _error(read.consolidated_realized_totals, pool, ctx, month=10, year=2026).code == "capability_denied"
    # Grant no negócio, mas sem finance.read.
    other = fh.grant(pool, world, "business", capabilities=["finance.prepare_change"])
    assert _error(read.consolidated_realized_totals, pool, ctx, month=10, year=2026).code == "capability_denied"
    fh.execute(pool, world.tenant_id, "UPDATE ai_grants SET revoked_at = now(), revocation_reason = 'teste' "
               "WHERE id = %s", (other,))
    business_grant = fh.grant(pool, world, "business", capabilities=["finance.read"])
    assert read.consolidated_realized_totals(pool, ctx, month=10, year=2026).facts
    # Grant revogado volta a negar.
    fh.execute(pool, world.tenant_id, "UPDATE ai_grants SET revoked_at = now(), revocation_reason = 'teste' "
               "WHERE id = %s", (business_grant,))
    assert _error(read.consolidated_realized_totals, pool, ctx, month=10, year=2026).code == "capability_denied"


@pytest.mark.integration
def test_consolidated_denied_when_actor_is_not_member_of_a_space(pool, world):
    ctx = world.context(pool)
    fh.grant(pool, world, "personal", capabilities=["finance.read"])
    fh.grant(pool, world, "business", capabilities=["finance.read"])
    assert read.consolidated_realized_totals(pool, ctx, month=10, year=2026).facts
    # Um terceiro espaço do tenant de que o titular não participa. Nem um
    # grant de leitura nesse espaço substitui a participação.
    third = seed.create_space(pool, world.tenant_id, "Espaço de outra pessoa", "personal")
    seed.create_grant(pool, world.tenant_id, third, world.user_id, capabilities=["finance.read"])
    assert _error(read.consolidated_realized_totals, pool, ctx, month=10, year=2026).code == "capability_denied"
    seed.add_space_member(pool, world.tenant_id, third, world.user_id, "member")
    assert read.consolidated_realized_totals(pool, ctx, month=10, year=2026).facts


@pytest.mark.integration
def test_consolidated_reports_composition_and_keeps_spaces_separate(pool, world, other_world):
    ctx = world.context(pool)
    tenant = world.tenant_id
    fh.grant(pool, world, "personal", capabilities=["finance.read"])
    fh.grant(pool, world, "business", capabilities=["finance.read"])
    fh.bulk_transactions(pool, tenant, world.personal_account_id, world.income_category_id, ["5000.00"],
                         tx_type="income")
    fh.bulk_transactions(pool, tenant, world.personal_account_id, world.expense_category_id, ["1200.10", "0.20"])
    fh.bulk_transactions(pool, tenant, world.business_account_id, world.income_category_id, ["800.05"],
                         tx_type="income")
    fh.bulk_transactions(pool, tenant, world.business_account_id, world.expense_category_id, ["300.00"])
    # Transferência do negócio para o pessoal: não é receita nem despesa de ninguém.
    fh.create_transfer(pool, tenant, world.business_account_id, world.personal_account_id, "700.00", date(2026, 10, 9))
    # Ruído: conta sem vínculo e outro tenant.
    loose = seed.create_account(pool, tenant, None, "Conta sem vínculo")
    fh.bulk_transactions(pool, tenant, loose, world.income_category_id, ["99999.00"], tx_type="income")
    fh.bulk_transactions(pool, other_world.tenant_id, other_world.personal_account_id,
                         other_world.income_category_id, ["88888.00"], tx_type="income")
    # Fora do mês consultado (véspera e dia seguinte): não entram no mensal.
    fh.bulk_transactions(pool, tenant, world.personal_account_id, world.income_category_id, ["777.00"],
                         tx_type="income", occurred_on=date(2026, 9, 30))
    fh.bulk_transactions(pool, tenant, world.business_account_id, world.expense_category_id, ["55.55"],
                         occurred_on=date(2026, 11, 1))

    result = read.consolidated_realized_totals(pool, ctx, month=10, year=2026)

    def value(key, space_id):
        matches = [fact for fact in result.facts if fact.key == key and fact.scope["financial_space_id"] == space_id]
        assert len(matches) == 1, (key, space_id)
        return matches[0]

    personal, business = world.personal_space_id, world.business_space_id
    assert value("realized.income", personal).value == "5000.00"
    assert value("realized.expense", personal).value == "1200.30"
    assert value("realized.income", business).value == "800.05"
    assert value("realized.expense", business).value == "300.00"
    assert value("realized.income", personal).scope["kind"] == "personal"
    assert value("realized.income", business).scope["kind"] == "business"

    # Consolidado: soma exata, com receita, transferência e resultado em fatos distintos.
    assert value("consolidated.realized.income", None).value == "5800.05"
    assert value("consolidated.realized.expense", None).value == "1500.30"
    assert value("consolidated.realized.net", None).value == "4299.75"
    assert value("consolidated.realized.transfers", None).value == "700.00"
    consolidated_scope = value("consolidated.realized.income", None).scope
    assert consolidated_scope["kind"] == "consolidated"
    assert {entry["kind"] for entry in consolidated_scope["composition"]} == {"personal", "business"}
    assert "Pessoal" in consolidated_scope["declared"] and "Marketing digital" in consolidated_scope["declared"]
    assert {entry["financial_space_id"] for entry in result.data["composition"]} == {personal, business}
    # Fonte do consolidado aponta para as fontes de cada espaço.
    consolidated_source = [source for source in result.sources if ":consolidated:" in source.ref][0]
    assert len(consolidated_source.extra["composition"]) == 2

    # O consolidado anual é outro número (inclui os meses vizinhos) e declara outro escopo.
    annual = read.consolidated_realized_totals(pool, ctx, year=2026)
    annual_facts = {fact.key: fact for fact in annual.facts if fact.scope["financial_space_id"] is None}
    assert annual_facts["consolidated.realized.income"].value == "6577.05"
    assert annual_facts["consolidated.realized.expense"].value == "1555.85"
    assert "ocorrência anual" in annual_facts["consolidated.realized.income"].scope["declared"]
    assert "mês de ocorrência" in consolidated_scope["declared"]

    # A consulta de UM espaço continua mostrando só aquele espaço.
    only_personal = fh.facts_by_key(read.realized_totals(pool, ctx, month=10, year=2026))
    assert only_personal["realized.income"].value == "5000.00"
    only_business = fh.facts_by_key(read.realized_totals(pool, world.context(pool, "business"), month=10, year=2026))
    assert only_business["realized.income"].value == "800.05"
    assert only_business["realized.transfers"].value == "700.00"


@pytest.mark.integration
def test_spending_by_category_matches_independent_aggregation(pool, world):
    ctx = world.context(pool)
    tenant, account = world.tenant_id, world.personal_account_id
    market = seed.create_category(pool, tenant, "Mercado", "expense")
    fh.bulk_transactions(pool, tenant, account, world.expense_category_id, ["900.00", "0.10", "0.20"])
    fh.bulk_transactions(pool, tenant, account, market, ["45.67", "12.33", "100.01"])
    fh.bulk_transactions(pool, tenant, account, market, ["500.00"], source_file="planilha.csv", entry_source="csv")
    fh.bulk_transactions(pool, tenant, account, world.income_category_id, ["3000.00"], tx_type="income")

    result = read.spending_by_category(pool, ctx, date_from="2026-10-01", date_to="2026-10-31")
    facts = fh.facts_by_key(result)
    independent = {
        str(row["category_id"]): row["total"]
        for row in fh.fetch_all(
            pool, tenant,
            "SELECT category_id, sum(amount)::numeric AS total FROM transactions "
            "WHERE tenant_id = %s AND account_id = %s AND type = 'expense' AND status = 'paid' "
            "AND source_file ILIKE %s GROUP BY category_id",
            (tenant, account, "%.ofx"),
        )
    }
    assert Decimal(facts["spending.category.%s" % market].value) == independent[market] == Decimal("158.01")
    assert Decimal(facts["spending.category.%s" % world.expense_category_id].value) == Decimal("900.30")
    assert Decimal(facts["spending.total"].value) == sum(independent.values()) == Decimal("1058.31")
    assert [entry["name"] for entry in result.data["categories"]] == ["Moradia", "Mercado"]  # maior primeiro
    assert facts["spending.total"].scope["declared"] == "intervalo de datas de ocorrência"


@pytest.mark.integration
def test_realized_period_filters_match_independent_aggregation_per_period(pool, world):
    """Mensal, anual, intervalo e global do REALIZADO: cada um soma só o seu período.

    Há lançamentos antes, dentro, nas bordas e depois de cada período. Se o
    filtro de datas sumisse, o "mês" devolveria o histórico inteiro.
    """
    ctx = world.context(pool)
    tenant, account = world.tenant_id, world.personal_account_id
    housing, salary = world.expense_category_id, world.income_category_id
    market = seed.create_category(pool, tenant, "Mercado", "expense")
    entries = [
        (date(2025, 9, 30), "11.11", housing, "expense"),
        (date(2025, 10, 1), "0.10", housing, "expense"),     # primeiro dia do mês
        (date(2025, 10, 15), "0.20", market, "expense"),
        (date(2025, 10, 31), "200.00", market, "expense"),   # último dia do mês
        (date(2025, 11, 1), "33.33", housing, "expense"),
        (date(2026, 1, 10), "44.44", market, "expense"),     # outro ano
        (date(2025, 9, 5), "1000.00", salary, "income"),
        (date(2025, 10, 20), "2000.05", salary, "income"),
        (date(2025, 11, 25), "3000.00", salary, "income"),
        (date(2026, 1, 2), "4000.00", salary, "income"),
    ]
    for occurred_on, amount, category, tx_type in entries:
        fh.bulk_transactions(pool, tenant, account, category, [amount], occurred_on=occurred_on, tx_type=tx_type)

    def independent(start, end):
        """Agregação NUMERIC escrita aqui, sem nada do repositório."""
        rows = fh.fetch_all(
            pool, tenant,
            """
            SELECT type, category_id, sum(amount)::numeric AS total FROM transactions
            WHERE tenant_id = %s AND account_id = %s AND status = 'paid' AND source_file ILIKE %s
              AND (%s::date IS NULL OR occurred_on >= %s::date)
              AND (%s::date IS NULL OR occurred_on <= %s::date)
            GROUP BY type, category_id
            """,
            (tenant, account, "%.ofx", start, start, end, end),
        )
        by_type, by_category = {}, {}
        for row in rows:
            by_type[row["type"]] = by_type.get(row["type"], Decimal("0")) + row["total"]
            if row["type"] == "expense":
                by_category[str(row["category_id"])] = row["total"]
        return by_type, by_category

    # (filtros, início, fim, escopo declarado, despesa, receita, despesa por categoria)
    periods = [
        ({"month": 10, "year": 2025}, date(2025, 10, 1), date(2025, 10, 31), "mês de ocorrência",
         "200.30", "2000.05", {housing: "0.10", market: "200.20"}),
        ({"year": 2025}, date(2025, 1, 1), date(2025, 12, 31), "ocorrência anual",
         "244.74", "6000.05", {housing: "44.54", market: "200.20"}),
        # As duas pontas do intervalo são inclusivas; não há receita dentro dele.
        ({"date_from": "2025-09-30", "date_to": "2025-10-15"}, date(2025, 9, 30), date(2025, 10, 15),
         "intervalo de datas de ocorrência", "11.41", None, {housing: "11.21", market: "0.20"}),
        ({}, None, None, "global (todo o histórico)",
         "289.18", "10000.05", {housing: "44.54", market: "244.64"}),
    ]
    refs = set()
    for filters, start, end, declared, expense, income, by_category in periods:
        by_type, independent_categories = independent(start, end)
        totals = read.realized_totals(pool, ctx, **filters)
        facts = fh.facts_by_key(totals)
        assert Decimal(facts["realized.expense"].value) == by_type["expense"] == Decimal(expense), filters
        if income is None:
            assert "income" not in by_type
            assert facts["realized.income"].value is None and facts["realized.income"].missing_reason, filters
        else:
            assert Decimal(facts["realized.income"].value) == by_type["income"] == Decimal(income), filters
        assert facts["realized.expense"].scope["declared"] == declared
        assert facts["realized.expense"].period["start"] == (start.isoformat() if start else None)
        assert facts["realized.expense"].period["end"] == (end.isoformat() if end else None)

        spending = read.spending_by_category(pool, ctx, **filters)
        spending_facts = fh.facts_by_key(spending)
        assert Decimal(spending_facts["spending.total"].value) == Decimal(expense), filters
        categories = {entry["category_id"]: entry["total"] for entry in spending.data["categories"]}
        assert categories == by_category, filters
        assert {key: Decimal(value) for key, value in categories.items()} == independent_categories, filters
        assert spending_facts["spending.total"].scope["declared"] == declared
        refs.update({totals.sources[0].ref, spending.sources[0].ref})
    # Cada período e cada consulta tem a própria referência de fonte.
    assert len(refs) == 8


@pytest.mark.integration
def test_account_filter_limits_realized_to_the_requested_account(pool, world):
    """Com duas contas com lançamentos no mesmo espaço, o filtro só soma a conta pedida."""
    tenant = world.tenant_id
    first = world.personal_account_id
    second = seed.create_account(pool, tenant, world.personal_space_id, "Segunda conta pessoal")
    ctx = world.context(pool)  # o contexto passa a incluir a segunda conta
    housing, salary = world.expense_category_id, world.income_category_id
    market = seed.create_category(pool, tenant, "Mercado", "expense")
    fh.bulk_transactions(pool, tenant, first, housing, ["100.10", "0.20"])
    fh.bulk_transactions(pool, tenant, first, salary, ["900.00"], tx_type="income")
    fh.bulk_transactions(pool, tenant, second, housing, ["7.07"])
    fh.bulk_transactions(pool, tenant, second, market, ["30.03"])
    fh.bulk_transactions(pool, tenant, second, salary, ["55.55"], tx_type="income")

    def independent(accounts):
        rows = fh.fetch_all(
            pool, tenant,
            "SELECT type, sum(amount)::numeric AS total FROM transactions WHERE tenant_id = %s "
            "AND account_id = ANY(%s::uuid[]) AND status = 'paid' AND source_file ILIKE %s GROUP BY type",
            (tenant, accounts, "%.ofx"),
        )
        return {row["type"]: row["total"] for row in rows}

    cases = [
        (first, [first], "100.30", "900.00", {housing: "100.30"}),
        (second, [second], "37.10", "55.55", {housing: "7.07", market: "30.03"}),
        (None, [first, second], "137.40", "955.55", {housing: "107.37", market: "30.03"}),
    ]
    refs = set()
    for account_id, accounts, expense, income, by_category in cases:
        expected = independent(accounts)
        totals = read.realized_totals(pool, ctx, month=10, year=2026, account_id=account_id)
        facts = fh.facts_by_key(totals)
        assert Decimal(facts["realized.expense"].value) == expected["expense"] == Decimal(expense), account_id
        assert Decimal(facts["realized.income"].value) == expected["income"] == Decimal(income), account_id
        # O escopo do fato declara a conta quando há filtro (e só quando há).
        assert facts["realized.expense"].scope.get("account_id") == account_id
        assert totals.sources[0].extra["account_id"] == account_id

        spending = read.spending_by_category(pool, ctx, month=10, year=2026, account_id=account_id)
        assert fh.facts_by_key(spending)["spending.total"].value == expense, account_id
        assert {entry["category_id"]: entry["total"] for entry in spending.data["categories"]} == by_category
        assert fh.facts_by_key(spending)["spending.total"].scope.get("account_id") == account_id
        refs.update({totals.sources[0].ref, spending.sources[0].ref})
    assert len(refs) == 6


@pytest.mark.integration
def test_non_numeric_limit_month_and_year_are_invalid_request_not_raw_errors(pool, world):
    """Chamadas diretas (sem o schema da ferramenta) também respondem pelo catálogo de erros."""
    ctx = world.context(pool)
    for index in range(3):
        seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Conta %d" % index,
                            amount_expected="10.00", competency_month=fh.OCT, due_date=date(2026, 10, 1 + index))
    for bad in ("abc", "", "2.5", 2.5, True, [], "1e2"):
        error = _error(read.payables_list, pool, ctx, month=10, year=2026, limit=bad)
        assert error.code == "invalid_request" and error.details == {"field": "limit"}, bad
    assert _error(read.run_query, pool, ctx, "payables_list", limit="abc").code == "invalid_request"
    for kwargs, field in (
        ({"month": "dez", "year": 2026}, "month"),
        ({"month": 10.0, "year": 2026}, "month"),
        ({"month": 10, "year": "dois mil"}, "year"),
        ({"year": True}, "year"),
    ):
        for function in (read.payables_overview, read.payables_list, read.realized_totals):
            error = _error(function, pool, ctx, **kwargs)
            assert error.code == "invalid_request" and error.details == {"field": field}, (function.__name__, kwargs)
    # Texto numérico (query string) é aceito e vale o mesmo que o número.
    page = read.payables_list(pool, ctx, month="10", year="2026", limit="2")
    assert len(page.data["items"]) == 2 and page.data["next_cursor"]
    assert page.facts[0].scope["declared"] == "competência mensal"
    assert read.payables_list(pool, ctx, month=10, year=2026, limit=2).data["next_cursor"] == page.data["next_cursor"]


@pytest.mark.integration
def test_query_failure_raises_instead_of_returning_empty(pool, world, ai_database):
    """Falha de consulta nunca vira "não há dados"."""
    from psycopg2 import pool as pg_pool

    ctx = world.context(pool)
    fh.bulk_transactions(pool, world.tenant_id, world.personal_account_id, world.expense_category_id, ["10.00"])
    seed.create_payable(pool, world.tenant_id, world.personal_space_id, title="Conta", amount_expected="10.00",
                        competency_month=fh.OCT)
    functions = (
        read.realized_totals, read.spending_by_category, read.payables_overview, read.payables_list, read.accounts
    )

    # Falha real de SQL: nesta conexão as tabelas não são encontradas.
    broken = pg_pool.ThreadedConnectionPool(1, 2, dsn=ai_database.app_dsn, options="-c search_path=pg_catalog")
    try:
        for function in functions:
            error = _error(function, broken, ctx)
            assert error.code == "internal_error", function.__name__
            # A mensagem ao titular não carrega detalhe do driver nem do SQL.
            assert "relation" not in error.safe_message and "payables" not in error.safe_message
    finally:
        broken.closeall()

    # Banco inacessível: o pool já foi fechado.
    closed = pg_pool.ThreadedConnectionPool(1, 2, dsn=ai_database.app_dsn)
    closed.closeall()
    for function in functions:
        assert _error(function, closed, ctx).code == "internal_error", function.__name__

    # Com o banco de volta, os dados aparecem: não era ausência.
    assert fh.facts_by_key(read.realized_totals(pool, ctx))["realized.expense"].value == "10.00"


@pytest.mark.integration
def test_amounts_in_different_currencies_are_never_added_together(pool, world):
    ctx = world.context(pool)
    tenant, space = world.tenant_id, world.personal_space_id
    seed.create_payable(pool, tenant, space, title="Em reais", amount_expected="100.00", competency_month=fh.OCT)
    dollars = seed.create_payable(pool, tenant, space, title="Em dólares", amount_expected="50.00",
                                  competency_month=fh.OCT)
    fh.execute(pool, tenant, "UPDATE payables SET currency = 'USD' WHERE id = %s", (dollars,))
    usd_account = seed.create_account(pool, tenant, space, "Conta em dólar")
    fh.execute(pool, tenant, "UPDATE accounts SET currency = 'USD' WHERE id = %s", (usd_account,))
    ctx = world.context(pool)  # o contexto passa a incluir a conta nova
    fh.bulk_transactions(pool, tenant, world.personal_account_id, world.expense_category_id, ["30.00"])
    fh.bulk_transactions(pool, tenant, usd_account, world.expense_category_id, ["7.00"])

    def by_currency(result, key):
        return {fact.currency: fact.value for fact in result.facts if fact.key == key}

    overview = read.payables_overview(pool, ctx, month=10, year=2026)
    assert by_currency(overview, "payables.expected") == {"BRL": "100.00", "USD": "50.00"}
    assert by_currency(overview, "payables.remaining") == {"BRL": "100.00", "USD": "50.00"}
    realized = read.realized_totals(pool, ctx, month=10, year=2026)
    assert by_currency(realized, "realized.expense") == {"BRL": "30.00", "USD": "7.00"}
    spending = read.spending_by_category(pool, ctx, month=10, year=2026)
    assert by_currency(spending, "spending.total") == {"BRL": "30.00", "USD": "7.00"}


# ---------------------------------------------------------------------------
# Unidade.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_period_resolution_is_explicit():
    month = read.resolve_period(month=2, year=2028, competency=True)
    assert (month.start, month.end) == (date(2028, 2, 1), date(2028, 2, 29))  # ano bissexto
    assert month.label == "fevereiro/2028" and month.ref == "2028-02"
    year = read.resolve_period(year=2026)
    assert (year.start, year.end, year.kind) == (date(2026, 1, 1), date(2026, 12, 31), "year")
    everything = read.resolve_period()
    assert everything.kind == "all" and everything.start is None and everything.end is None
    span = read.resolve_period(date_from="2026-10-03", date_to=date(2026, 10, 9))
    assert span.kind == "range" and span.ref == "2026-10-03..2026-10-09"
    for kwargs in (
        {"month": 13, "year": 2026},
        {"month": 5},
        {"year": 1800},
        {"date_from": "2026-10-09", "date_to": "2026-10-03"},
        {"date_from": "09/10/2026", "date_to": "2026-10-10"},
        {"date_from": "2026-10-01", "date_to": "2026-10-31", "competency": True},
        {"month": "outubro", "year": 2026},
        {"year": 2026.0},
        {"year": "20x6"},
    ):
        with pytest.raises(AiError) as excinfo:
            read.resolve_period(**kwargs)
        assert excinfo.value.code == "invalid_request", kwargs


@pytest.mark.unit
def test_canonical_source_file_is_decided_by_suffix_only():
    assert repository.is_canonical_source_file("extrato-setembro.ofx")
    assert repository.is_canonical_source_file("EXTRATO.OFX")
    assert not repository.is_canonical_source_file("legacy:extrato.ofx:excluded")
    assert not repository.is_canonical_source_file("planilha.csv")
    assert not repository.is_canonical_source_file("extrato.ofx ")
    assert not repository.is_canonical_source_file(None)
