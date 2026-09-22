import React, { useMemo, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, formatDate, categoriesAPI, accountsAPI, transactionsAPI, TransactionTotals } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import CreditCardExpenseForm, { CreditCardExpenseSubmit } from './CreditCardExpenseForm';
import CreditCardImportModal from './CreditCardImportModal';
import { CreditCard } from '../../types/credit-card';
import {
  MONTH_NAMES, accountToCreditCard, computeCurrentBillPeriod, computeMonthPeriod,
  expenseStatus, getNextClosingDate, getNextDueDate,
} from './creditCardUtils';
import './credit-cards.css';

interface Expense {
  id: string;
  description: string;
  amount: number;
  date: string;
  category?: { name: string; color: string; icon: string } | null;
  status: string;
}

interface Category { id: string; name: string; type: string; color: string; icon: string }

interface ExpensesPage {
  items: Expense[];
  /** Total de lançamentos no período, segundo a paginação da API. */
  total: number;
}

type BillPreset = 'current_bill' | 'month';
type SortField = 'date' | 'description' | 'amount';

const PAGE_LIMIT = 500;

const CreditCardDetail: React.FC = () => {
  const { cardId } = useParams<{ cardId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [revision, setRevision] = useState(0);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [billPreset, setBillPreset] = useState<BillPreset>('current_bill');
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const enabled = isAuthenticated && !authLoading && !!cardId;
  const reload = () => setRevision(value => value + 1);

  const cardRequest = useCallback(async () => {
    const response = await accountsAPI.getById(cardId!);
    return { data: accountToCreditCard(response.data) };
  }, [cardId]);
  const card = useKeyedRequest<CreditCard>(`card:${cardId}:${revision}`, enabled, cardRequest);

  const period = useMemo(() => {
    if (!card.data) return null;
    if (billPreset === 'current_bill') return computeCurrentBillPeriod(card.data.closingDay);
    return computeMonthPeriod(selectedMonth, selectedYear);
  }, [card.data, billPreset, selectedMonth, selectedYear]);

  const expensesRequest = useCallback(async () => {
    const response = await transactionsAPI.getAll({
      account_ids: cardId,
      types: 'expense',
      date_from: period!.dateFrom,
      date_to: period!.dateTo,
      sort: 'date:desc',
      limit: PAGE_LIMIT,
    });
    const body = response.data;
    const items: Expense[] = Array.isArray(body) ? body : Array.isArray(body?.data) ? body.data : [];
    const total = Number(body?.pagination?.total ?? items.length);
    return { data: { items, total } };
  }, [cardId, period]);
  const periodKey = `${cardId}:${period?.dateFrom}:${period?.dateTo}:${revision}`;
  const expenses = useKeyedRequest<ExpensesPage>(`expenses:${periodKey}`, enabled && !!period, expensesRequest);

  // Valor da fatura vem do servidor, somado sobre TODOS os lançamentos do período (pendentes
  // incluídos, cancelados fora) — independente da lista, que é paginada.
  const totalsRequest = useCallback(async (signal: AbortSignal) => {
    const response = await transactionsAPI.getTotals({
      account_ids: cardId,
      date_from: period!.dateFrom,
      date_to: period!.dateTo,
    }, { signal });
    const body = response.data;
    if (!body || body.complete !== true || !Number.isFinite(Number(body.expense_total))) {
      throw new Error('Total da fatura não confirmado');
    }
    return { data: body };
  }, [cardId, period]);
  const totals = useKeyedRequest<TransactionTotals>(`totals:${periodKey}`, enabled && !!period, totalsRequest);

  const categoriesRequest = useCallback(async (signal: AbortSignal) => {
    const response = await categoriesAPI.getAll({ signal });
    return { data: (Array.isArray(response.data) ? response.data : []) as Category[] };
  }, []);
  const categories = useKeyedRequest<Category[]>('categories', enabled, categoriesRequest);

  const handleExpenseSubmit = async (expenseData: CreditCardExpenseSubmit) => {
    if (!cardId) throw new Error('Cartão inválido');
    await transactionsAPI.create({
      description: expenseData.description,
      amount: expenseData.amount,
      date: expenseData.date,
      type: 'expense',
      category_id: expenseData.category_id,
      account_id: cardId,
      status: 'paid',
      is_recurring: expenseData.is_recurring,
      ...(expenseData.installments ? { installments: expenseData.installments } : {}),
    });
    reload();
  };

  const handleImportSuccess = () => {
    setShowImportModal(false);
    reload();
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const loadedExpenses = useMemo(() => (expenses.data?.items ?? []).filter(expense => expense && expense.id), [expenses.data]);
  const sortedExpenses = useMemo(() => [...loadedExpenses].sort((a, b) => {
    let aValue: number | string;
    let bValue: number | string;
    if (sortField === 'date') {
      aValue = new Date(a.date).getTime(); bValue = new Date(b.date).getTime();
    } else if (sortField === 'amount') {
      aValue = Number(a.amount) || 0; bValue = Number(b.amount) || 0;
    } else {
      aValue = String(a.description ?? '').toLowerCase(); bValue = String(b.description ?? '').toLowerCase();
    }
    if (aValue === bValue) return 0;
    const order = aValue > bValue ? 1 : -1;
    return sortDirection === 'asc' ? order : -order;
  }), [loadedExpenses, sortField, sortDirection]);

  const changeMonth = (direction: 'prev' | 'next') => {
    if (direction === 'prev') {
      if (selectedMonth === 1) { setSelectedMonth(12); setSelectedYear(selectedYear - 1); } else setSelectedMonth(selectedMonth - 1);
    } else if (selectedMonth === 12) { setSelectedMonth(1); setSelectedYear(selectedYear + 1); } else setSelectedMonth(selectedMonth + 1);
  };

  // A lista é paginada (PAGE_LIMIT); quando há mais lançamentos do que os carregados, a lista avisa.
  const expensesTotalCount = expenses.data?.total ?? 0;
  const isPartialTotal = !!expenses.data && expensesTotalCount > loadedExpenses.length;

  if (authLoading || card.loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" role="status" aria-busy="true">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600 dark:text-slate-400">Carregando...</p>
        </div>
      </div>
    );
  }

  if (card.error || !card.data) {
    return (
      <div className="cc flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <p className="text-red-600 dark:text-red-400" role="alert">{card.error ? `Cartão indisponível. ${card.error}` : 'Cartão não encontrado'}</p>
          <div className="flex flex-wrap justify-center gap-3">
            {card.error && <button type="button" className="cc-retry text-blue-700 dark:text-blue-300" onClick={reload}>Tentar novamente</button>}
            <button type="button" onClick={() => navigate('/credit-cards')} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
              Voltar para Cartões
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentCard = card.data;
  const totalUsed = currentCard.used ?? 0;
  const availableLimit = (currentCard.limit ?? 0) - totalUsed;
  const nextClosing = getNextClosingDate(currentCard.closingDay);
  const nextDue = getNextDueDate(currentCard);
  const currentBillStart = computeCurrentBillPeriod(currentCard.closingDay).dateFrom;
  const billClosed = billPreset === 'month' && !!period && period.dateTo < currentBillStart;
  const sortIcon = (field: SortField) => sortField === field
    ? <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'} text-blue-600 dark:text-blue-400`} aria-hidden="true"></i>
    : null;
  const sortLabel = (field: SortField) => sortField === field ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';

  const renderCategory = (expense: Expense) => expense.category?.name ? (
    <span className="cc-category">
      <span className="cc-category-icon" style={{ backgroundColor: expense.category.color || '#6b7280' }} aria-hidden="true">
        <i className={`bi bi-${expense.category.icon || 'circle'}`}></i>
      </span>
      <span>{expense.category.name}</span>
    </span>
  ) : <span className="text-slate-400">Sem categoria</span>;

  const renderStatus = (expense: Expense) => {
    const status = expenseStatus(expense.status);
    return <span className={status.className}>{status.label}</span>;
  };

  const renderExpenses = () => {
    if (expenses.error) {
      return (
        <div className="cc-error m-4" role="alert">
          <span>Despesas indisponíveis. {expenses.error}</span>
          <button type="button" className="cc-retry" onClick={reload}>Tentar novamente</button>
        </div>
      );
    }
    if (expenses.loading) {
      return <div className="cc-empty" role="status" aria-busy="true">Carregando despesas…</div>;
    }
    if (sortedExpenses.length === 0) {
      return (
        <div className="cc-empty" role="status">
          <i className="bi bi-credit-card text-6xl text-slate-300 dark:text-slate-600 mb-4 block" aria-hidden="true"></i>
          <p className="text-lg font-medium mb-2">Você não possui despesas nesse período</p>
          <p className="text-sm">Adicione uma despesa ou importe a fatura do seu cartão</p>
        </div>
      );
    }
    return (
      <>
        {isPartialTotal && (
          <p className="cc-notice m-4" role="status">
            Mostrando {loadedExpenses.length} de {expensesTotalCount} lançamentos do período.
          </p>
        )}
        <div className="cc-desktop-list">
          <table className="cc-table">
            <caption className="cc-sr-only">Despesas do cartão no período selecionado. Valores em reais.</caption>
            <thead>
              <tr>
                <th scope="col" style={{ width: '12%' }}>Situação</th>
                <th scope="col" style={{ width: '14%' }} aria-sort={sortLabel('date')}>
                  <button type="button" className="cc-sort-button" onClick={() => handleSort('date')}>Data {sortIcon('date')}</button>
                </th>
                <th scope="col" aria-sort={sortLabel('description')}>
                  <button type="button" className="cc-sort-button" onClick={() => handleSort('description')}>Descrição {sortIcon('description')}</button>
                </th>
                <th scope="col" style={{ width: '22%' }}>Categoria</th>
                <th scope="col" className="cc-money" style={{ width: '16%' }} aria-sort={sortLabel('amount')}>
                  <button type="button" className="cc-sort-button" onClick={() => handleSort('amount')}>Valor {sortIcon('amount')}</button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedExpenses.map(expense => (
                <tr key={expense.id}>
                  <td>{renderStatus(expense)}</td>
                  <td>{expense.date ? formatDate(expense.date) : '-'}</td>
                  <td className="font-medium">{expense.description || 'Sem descrição'}</td>
                  <td>{renderCategory(expense)}</td>
                  <td className="cc-money text-red-600 dark:text-red-400">{formatCurrency(Number(expense.amount) || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="cc-mobile-list p-4" aria-label="Despesas do cartão no período selecionado">
          {sortedExpenses.map(expense => (
            <li key={expense.id} className="cc-expense-card">
              <div className="cc-expense-heading">
                <h3>{expense.description || 'Sem descrição'}</h3>
                {renderStatus(expense)}
              </div>
              <div className="cc-expense-meta">
                <span>{expense.date ? formatDate(expense.date) : '-'}</span>
                {renderCategory(expense)}
              </div>
              <p className="cc-expense-amount">{formatCurrency(Number(expense.amount) || 0)}</p>
            </li>
          ))}
        </ul>
      </>
    );
  };

  return (
    <div className="cc space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => navigate('/credit-cards')} className="cc-icon-button" aria-label="Voltar">
            <i className="bi bi-arrow-left text-xl" aria-hidden="true"></i>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Despesas do Cartão</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{currentCard.name}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setShowImportModal(true)}
            className="px-4 py-2.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg font-medium transition-all shadow-sm hover:shadow flex items-center gap-2"
          >
            <i className="bi bi-upload" aria-hidden="true"></i>
            Importar Fatura
          </button>
          <button
            type="button"
            onClick={() => setShowExpenseForm(true)}
            className="px-4 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 dark:from-blue-500 dark:to-blue-600 dark:hover:from-blue-600 dark:hover:to-blue-700 text-white rounded-lg font-medium transition-all shadow-sm hover:shadow-md flex items-center gap-2"
          >
            <i className="bi bi-plus-circle" aria-hidden="true"></i>
            Adicionar Despesa
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-4 min-w-0">
          {/* Período */}
          <div className="card-base p-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div className="flex items-center gap-2" role="group" aria-label="Período">
                <button
                  type="button"
                  aria-pressed={billPreset === 'current_bill'}
                  className={
                    'px-3 rounded-lg text-sm font-medium border transition-colors ' +
                    (billPreset === 'current_bill'
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
                  }
                  onClick={() => setBillPreset('current_bill')}
                >
                  Fatura atual
                </button>
                <button
                  type="button"
                  aria-pressed={billPreset === 'month'}
                  className={
                    'px-3 rounded-lg text-sm font-medium border transition-colors ' +
                    (billPreset === 'month'
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
                  }
                  onClick={() => setBillPreset('month')}
                >
                  Por mês
                </button>
              </div>

              {billPreset === 'month' && (
                <div className="flex items-center justify-between md:justify-end gap-2">
                  <button type="button" onClick={() => changeMonth('prev')} className="cc-icon-button" aria-label="Mês anterior">
                    <i className="bi bi-chevron-left" aria-hidden="true"></i>
                  </button>
                  <span className="px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-full font-medium" aria-live="polite">
                    {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                  </span>
                  <button type="button" onClick={() => changeMonth('next')} className="cc-icon-button" aria-label="Próximo mês">
                    <i className="bi bi-chevron-right" aria-hidden="true"></i>
                  </button>
                </div>
              )}

              {billPreset === 'current_bill' && period && (
                <div className="text-sm text-slate-600 dark:text-slate-300">
                  Período: {formatDate(period.dateFrom)} → {formatDate(period.dateTo)}
                </div>
              )}
            </div>
          </div>

          {/* Expenses */}
          <div className="card-base overflow-hidden shadow-sm">{renderExpenses()}</div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4 min-w-0">
          {/* Valor da Fatura */}
          <section className="card-base p-5 relative overflow-hidden" aria-label="Valor da fatura">
            <div className="relative flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">Valor da fatura</p>
                {totals.error ? (
                  <p className="text-base font-semibold text-red-600 dark:text-red-400">Indisponível</p>
                ) : totals.loading || !totals.data ? (
                  <p className="text-base font-semibold text-slate-500 dark:text-slate-400" role="status">Carregando…</p>
                ) : (
                  <>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">{formatCurrency(Number(totals.data.expense_total))}</p>
                    {Number(totals.data.income_total) > 0 && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5">
                        Estornos/créditos no período: {formatCurrency(Number(totals.data.income_total))}
                      </p>
                    )}
                  </>
                )}
              </div>
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 dark:from-blue-400 dark:to-blue-500 flex items-center justify-center shadow-lg shadow-blue-500/30 flex-none">
                <i className="bi bi-currency-dollar text-white text-2xl" aria-hidden="true"></i>
              </div>
            </div>
          </section>

          {/* Limite disponível */}
          <section className="card-base p-5 relative overflow-hidden" aria-label="Limite disponível">
            <div className="relative">
              <div className="flex items-center justify-between gap-3 mb-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">Limite disponível</p>
                  <p className={`text-2xl font-bold ${availableLimit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                    {formatCurrency(availableLimit)}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-1.5">
                    Total: {formatCurrency(currentCard.limit)} · Usado: {formatCurrency(totalUsed)}
                  </p>
                </div>
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 dark:from-emerald-400 dark:to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30 flex-none">
                  <i className="bi bi-speedometer text-white text-2xl" aria-hidden="true"></i>
                </div>
              </div>
              <div className="h-2.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${availableLimit >= 0 ? 'bg-gradient-to-r from-emerald-500 to-blue-500' : 'bg-gradient-to-r from-red-500 to-red-600'}`}
                  style={{ width: `${Math.min(currentCard.limit > 0 ? Math.max(0, (totalUsed / currentCard.limit) * 100) : 0, 100)}%` }}
                ></div>
              </div>
            </div>
          </section>

          {/* Status */}
          <section className="card-base p-5" aria-label="Situação da fatura">
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Situação</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">{billClosed ? 'Fatura fechada' : 'Fatura aberta'}</p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${billClosed ? 'bg-slate-100 dark:bg-slate-700' : 'bg-green-100 dark:bg-green-900/30'}`}>
                <i className={`bi bi-file-text text-xl ${billClosed ? 'text-slate-600 dark:text-slate-300' : 'text-green-600 dark:text-green-400'}`} aria-hidden="true"></i>
              </div>
            </div>
          </section>

          {/* Dia de Fechamento */}
          <section className="card-base p-5" aria-label="Dia de fechamento">
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Dia de fechamento</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">
                  {nextClosing.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <i className="bi bi-calendar text-purple-600 dark:text-purple-400 text-xl" aria-hidden="true"></i>
              </div>
            </div>
          </section>

          {/* Data Vencimento */}
          <section className="card-base p-5" aria-label="Data de vencimento">
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Data vencimento</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">
                  {nextDue.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                <i className="bi bi-check-circle text-emerald-600 dark:text-emerald-400 text-xl" aria-hidden="true"></i>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* Modals */}
      {showExpenseForm && (
        <CreditCardExpenseForm
          onHide={() => setShowExpenseForm(false)}
          onSubmit={handleExpenseSubmit}
          card={currentCard}
          categories={categories.data ?? []}
        />
      )}

      {showImportModal && (
        <CreditCardImportModal
          onHide={() => setShowImportModal(false)}
          onSuccess={handleImportSuccess}
          cardId={currentCard.id}
        />
      )}
    </div>
  );
};

export default CreditCardDetail;
