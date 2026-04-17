import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, formatDate, categoriesAPI, accountsAPI, transactionsAPI } from '../../utils/api';
import CreditCardExpenseForm from './CreditCardExpenseForm';
import CreditCardImportModal from './CreditCardImportModal';
import { CreditCard } from '../../types/credit-card';

interface Expense {
  id: string;
  description: string;
  amount: number;
  date: string;
  category: {
    name: string;
    color: string;
    icon: string;
  };
  status: string;
}

type BillPreset = 'current_bill' | 'month';

const CreditCardDetail: React.FC = () => {
  const { cardId } = useParams<{ cardId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [card, setCard] = useState<CreditCard | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [billPreset, setBillPreset] = useState<BillPreset>('current_bill');
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [sortField, setSortField] = useState<'date' | 'description' | 'amount'>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const cardRequestSeqRef = useRef(0);
  const categoriesLoadedRef = useRef(false);

  useEffect(() => {
    if (isAuthenticated && !authLoading && cardId) {
      void loadCardData();
    }
  }, [isAuthenticated, authLoading, cardId, selectedMonth, selectedYear, billPreset]);

  useEffect(() => {
    if (!isAuthenticated || authLoading || !cardId || categoriesLoadedRef.current) return;
    categoriesLoadedRef.current = true;
    void loadCategories();
  }, [isAuthenticated, authLoading, cardId]);

  const toISODate = (d: Date) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  const computeCurrentBillPeriod = (closingDay: number) => {
    // Fatura aberta atual: do dia após o último fechamento até o próximo fechamento (inclusive).
    const today = new Date();
    const y = today.getFullYear();
    const m = today.getMonth(); // 0-based

    const thisClosing = new Date(y, m, closingDay);
    let start: Date;
    let end: Date;

    if (today <= thisClosing) {
      end = thisClosing;
      const prevClosing = new Date(y, m - 1, closingDay);
      start = new Date(prevClosing);
      start.setDate(prevClosing.getDate() + 1);
    } else {
      const nextClosing = new Date(y, m + 1, closingDay);
      end = nextClosing;
      start = new Date(thisClosing);
      start.setDate(thisClosing.getDate() + 1);
    }

    return { dateFrom: toISODate(start), dateTo: toISODate(end) };
  };

  const computeMonthPeriod = (month: number, year: number) => {
    const start = new Date(year, month - 1, 1);
    const end = new Date(year, month, 0);
    return { dateFrom: toISODate(start), dateTo: toISODate(end) };
  };

  const period = useMemo(() => {
    if (!card) return null;
    if (billPreset === 'current_bill') return computeCurrentBillPeriod(card.closingDay);
    return computeMonthPeriod(selectedMonth, selectedYear);
  }, [card, billPreset, selectedMonth, selectedYear]);

  const loadCardData = async () => {
    const requestId = ++cardRequestSeqRef.current;
    try {
      setLoading(true);
      setError('');

      if (!cardId) {
        setError('ID do cartão não fornecido');
        setLoading(false);
        return;
      }

      // Carrega o cartão
      const cardResponse = await accountsAPI.getById(cardId);
      if (requestId !== cardRequestSeqRef.current) return;
      const accountData = cardResponse.data;

      // Converte para formato CreditCard
      const limit = accountData.limit ?? accountData.initial_balance ?? 0; // Limite total
      const currentBalance = accountData.current_balance ?? 0;
      // Para cartões de crédito, current_balance geralmente é negativo (gasto)
      // O valor usado é o valor absoluto do current_balance
      const used = Math.abs(currentBalance);

      // Debug para verificar valores do backend
      console.log('CreditCardDetail - Dados do backend:', {
        accountData,
        limit,
        currentBalance,
        used,
        initial_balance: accountData.initial_balance
      });

      const creditCard: CreditCard = {
        id: accountData.id,
        name: accountData.name,
        limit: limit, // Limite total
        used: used, // Valor gasto (sempre positivo)
        closingDay: accountData.closing_day || 10,
        dueDay: accountData.due_day || 15,
        color: accountData.color || '#6366f1',
        icon: accountData.icon || 'credit-card',
        is_active: accountData.is_active
      };

      setCard(creditCard);

      // Carrega despesas do cartão (transações associadas)
      try {
        const p =
          (billPreset === 'current_bill'
            ? computeCurrentBillPeriod(creditCard.closingDay)
            : computeMonthPeriod(selectedMonth, selectedYear));

        const expensesResponse = await transactionsAPI.getAll({
          account_ids: cardId,
          types: 'expense',
          date_from: p.dateFrom,
          date_to: p.dateTo,
          sort: 'date:desc',
          limit: 500,
        });
        const expensesData = expensesResponse.data || [];
        const expensesArray = Array.isArray(expensesData)
          ? expensesData
          : (expensesData?.data && Array.isArray(expensesData.data))
            ? expensesData.data
            : [];
        if (requestId === cardRequestSeqRef.current) {
          setExpenses(expensesArray as any);
        }
      } catch (expensesErr) {
        // Se falhar ao carregar despesas, define como array vazio
        console.warn('Erro ao carregar despesas:', expensesErr);
        if (requestId === cardRequestSeqRef.current) {
          setExpenses([]);
        }
      }
    } catch (err: any) {
      if (requestId === cardRequestSeqRef.current) {
        setError(err.message || 'Erro ao carregar dados do cartão');
      }
      console.error('Load card data error:', err);
    } finally {
      if (requestId === cardRequestSeqRef.current) {
        setLoading(false);
      }
    }
  };

  const loadCategories = async () => {
    try {
      const response = await categoriesAPI.getAll();
      // Garante que categories seja sempre um array
      const categoriesData = response.data;
      const categoriesArray = Array.isArray(categoriesData)
        ? categoriesData
        : (categoriesData?.data && Array.isArray(categoriesData.data))
          ? categoriesData.data
          : [];
      setCategories(categoriesArray);
    } catch (err) {
      console.error('Load categories error:', err);
    }
  };

  const handleExpenseSubmit = async (expenseData: any) => {
    try {
      if (!cardId) {
        throw new Error('Cartão inválido');
      }
      await transactionsAPI.create({
        description: expenseData.description,
        amount: expenseData.amount,
        date: expenseData.date,
        type: 'expense',
        category_id: expenseData.category_id,
        account_id: cardId,
        status: 'paid',
        responsible_person: 'Leandro',
      });
      setShowExpenseForm(false);
      await loadCardData();
    } catch (err: any) {
      throw err;
    }
  };

  const handleImportSuccess = () => {
    setShowImportModal(false);
    loadCardData();
  };

  const handleSort = (field: 'date' | 'description' | 'amount') => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  // Garante que expenses seja sempre um array antes de ordenar
  const safeExpenses = Array.isArray(expenses) ? expenses : [];
  const sortedExpenses = [...safeExpenses].sort((a, b) => {
    let aValue: any = a[sortField];
    let bValue: any = b[sortField];

    if (sortField === 'date') {
      aValue = new Date(aValue).getTime();
      bValue = new Date(bValue).getTime();
    } else if (sortField === 'amount') {
      aValue = parseFloat(aValue);
      bValue = parseFloat(bValue);
    } else {
      aValue = String(aValue).toLowerCase();
      bValue = String(bValue).toLowerCase();
    }

    if (sortDirection === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  const getNextClosingDate = () => {
    if (!card) return null;
    const today = new Date();
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();
    const closingDate = new Date(currentYear, currentMonth, card.closingDay);

    if (today > closingDate) {
      closingDate.setMonth(currentMonth + 1);
    }

    return closingDate;
  };

  const getNextDueDate = () => {
    if (!card) return null;
    const closingDate = getNextClosingDate();
    if (!closingDate) return null;

    const dueDate = new Date(closingDate);
    dueDate.setDate(dueDate.getDate() + (card.dueDay - card.closingDay));
    if (dueDate.getDate() < card.dueDay) {
      dueDate.setMonth(dueDate.getMonth() + 1);
      dueDate.setDate(card.dueDay);
    }

    return dueDate;
  };

  const changeMonth = (direction: 'prev' | 'next') => {
    if (direction === 'prev') {
      if (selectedMonth === 1) {
        setSelectedMonth(12);
        setSelectedYear(selectedYear - 1);
      } else {
        setSelectedMonth(selectedMonth - 1);
      }
    } else {
      if (selectedMonth === 12) {
        setSelectedMonth(1);
        setSelectedYear(selectedYear + 1);
      } else {
        setSelectedMonth(selectedMonth + 1);
      }
    }
  };

  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  // Valor da fatura = total de despesas do mês selecionado (fatura atual)
  const totalExpenses = safeExpenses.reduce((sum, exp) => sum + (exp.amount || 0), 0);

  // Limite disponível = limite total - valor total gasto no cartão (não apenas do mês)
  // O card.used já representa o valor total gasto (sempre positivo)
  const totalUsed = card ? (card.used ?? 0) : 0;
  const availableLimit = card ? (card.limit ?? 0) - totalUsed : 0;

  // Debug para verificar valores
  console.log('CreditCardDetail - Valores:', {
    cardName: card?.name,
    limit: card?.limit,
    used: card?.used,
    totalUsed,
    availableLimit,
    totalExpenses,
    preset: billPreset,
    month: selectedMonth,
    year: selectedYear,
    period,
    expensesCount: safeExpenses.length
  });

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600 dark:text-slate-400">Carregando...</p>
        </div>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 mb-4">{error || 'Cartão não encontrado'}</p>
          <button
            onClick={() => navigate('/credit-cards')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
          >
            Voltar para Cartões
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/credit-cards')}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <i className="bi bi-arrow-left text-xl text-slate-600 dark:text-slate-400"></i>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Despesas do Cartão</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{card.name}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="px-4 py-2.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg font-medium transition-all shadow-sm hover:shadow flex items-center gap-2"
          >
            <i className="bi bi-upload"></i>
            Importar Fatura
          </button>
          <button
            onClick={() => setShowExpenseForm(true)}
            className="px-4 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 dark:from-blue-500 dark:to-blue-600 dark:hover:from-blue-600 dark:hover:to-blue-700 text-white rounded-lg font-medium transition-all shadow-sm hover:shadow-md flex items-center gap-2"
          >
            <i className="bi bi-plus-circle"></i>
            Adicionar Despesa
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Período */}
          <div className="card-base p-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={
                    'h-9 px-3 rounded-lg text-sm font-medium border transition-colors ' +
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
                  className={
                    'h-9 px-3 rounded-lg text-sm font-medium border transition-colors ' +
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
                  <button
                    onClick={() => changeMonth('prev')}
                    className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    <i className="bi bi-chevron-left text-slate-600 dark:text-slate-400"></i>
                  </button>
                  <span className="px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-full font-medium">
                    {monthNames[selectedMonth - 1]} {selectedYear}
                  </span>
                  <button
                    onClick={() => changeMonth('next')}
                    className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    <i className="bi bi-chevron-right text-slate-600 dark:text-slate-400"></i>
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

          {/* Expenses Table */}
          <div className="card-base overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Situação
                    </th>
                    <th
                      className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                      onClick={() => handleSort('date')}
                    >
                      <div className="flex items-center gap-2">
                        Data
                        {sortField === 'date' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'} text-blue-600 dark:text-blue-400`}></i>
                        )}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                      onClick={() => handleSort('description')}
                    >
                      <div className="flex items-center gap-2">
                        Descrição
                        {sortField === 'description' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'} text-blue-600 dark:text-blue-400`}></i>
                        )}
                      </div>
                    </th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Categoria
                    </th>
                    <th
                      className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                      onClick={() => handleSort('amount')}
                    >
                      <div className="flex items-center gap-2">
                        Valor
                        {sortField === 'amount' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'} text-blue-600 dark:text-blue-400`}></i>
                        )}
                      </div>
                    </th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Ações
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {sortedExpenses.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center">
                        <div className="flex flex-col items-center justify-center">
                          <i className="bi bi-credit-card text-6xl text-slate-300 dark:text-slate-600 mb-4"></i>
                          <p className="text-slate-600 dark:text-slate-400 text-lg font-medium mb-2">
                            Você não possui despesas nesse período
                          </p>
                          <p className="text-slate-500 dark:text-slate-500 text-sm">
                            Adicione uma despesa ou importe a fatura do seu cartão
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    sortedExpenses
                      .filter((expense) => expense && expense.id) // Filtra itens inválidos
                      .map((expense) => (
                        <tr key={expense.id} className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-4 py-4 whitespace-nowrap">
                            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                              {expense.status === 'paid' ? 'Pago' : 'Pendente'}
                            </span>
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                            {expense.date ? formatDate(expense.date) : '-'}
                          </td>
                          <td className="px-4 py-4 text-sm text-slate-900 dark:text-white font-medium">
                            {expense.description || 'Sem descrição'}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
                            {expense.category && expense.category.name ? (
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-7 h-7 rounded-lg flex items-center justify-center shadow-sm"
                                  style={{ backgroundColor: expense.category.color || '#6b7280' }}
                                >
                                  <i className={`bi bi-${expense.category.icon || 'circle'} text-white text-xs`}></i>
                                </div>
                                <span className="text-sm text-slate-700 dark:text-slate-300 font-medium">{expense.category.name}</span>
                              </div>
                            ) : (
                              <span className="text-sm text-slate-400">Sem categoria</span>
                            )}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm font-bold text-red-600 dark:text-red-400">
                            {formatCurrency(expense.amount || 0)}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm">
                            <button className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium transition-colors">
                              Editar
                            </button>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Valor da Fatura */}
          <div className="card-base p-5 relative overflow-hidden group hover:shadow-lg transition-shadow">
            <div className="absolute -right-8 -top-8 w-32 h-32 bg-gradient-to-br from-blue-500/10 to-transparent rounded-full blur-2xl group-hover:scale-110 transition-transform"></div>
            <div className="relative flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">Valor da fatura</p>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{formatCurrency(totalExpenses)}</p>
              </div>
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 dark:from-blue-400 dark:to-blue-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
                <i className="bi bi-currency-dollar text-white text-2xl"></i>
              </div>
            </div>
          </div>

          {/* Limite disponível */}
          <div className="card-base p-5 relative overflow-hidden group hover:shadow-lg transition-shadow">
            <div className="absolute -right-8 -top-8 w-32 h-32 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-2xl group-hover:scale-110 transition-transform"></div>
            <div className="relative">
              <div className="flex items-center justify-between mb-4">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">Limite disponível</p>
                  <p className={`text-2xl font-bold ${availableLimit >= 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-red-600 dark:text-red-400'
                    }`}>
                    {formatCurrency(availableLimit)}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-1.5">
                    Total: {formatCurrency(card.limit)} · Usado: {formatCurrency(totalUsed)}
                  </p>
                </div>
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 dark:from-emerald-400 dark:to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                  <i className="bi bi-speedometer text-white text-2xl"></i>
                </div>
              </div>
              <div className="h-2.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${availableLimit >= 0
                      ? 'bg-gradient-to-r from-emerald-500 to-blue-500'
                      : 'bg-gradient-to-r from-red-500 to-red-600'
                    }`}
                  style={{
                    width: `${Math.min(
                      card.limit > 0 ? Math.max(0, (totalUsed / card.limit) * 100) : 0,
                      100
                    )}%`
                  }}
                ></div>
              </div>
            </div>
          </div>

          {/* Status */}
          <div className="card-base p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Status</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">Fatura aberta</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <i className="bi bi-file-text text-green-600 dark:text-green-400 text-xl"></i>
              </div>
            </div>
          </div>

          {/* Dia de Fechamento */}
          <div className="card-base p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Dia de fechamento</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">
                  {getNextClosingDate()?.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <i className="bi bi-calendar text-purple-600 dark:text-purple-400 text-xl"></i>
              </div>
            </div>
          </div>

          {/* Data Vencimento */}
          <div className="card-base p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Data vencimento</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">
                  {getNextDueDate()?.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                <i className="bi bi-check-circle text-emerald-600 dark:text-emerald-400 text-xl"></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      {showExpenseForm && card && (
        <CreditCardExpenseForm
          show={showExpenseForm}
          onHide={() => setShowExpenseForm(false)}
          onSubmit={handleExpenseSubmit}
          card={card}
          categories={categories}
        />
      )}

      {showImportModal && card && (
        <CreditCardImportModal
          show={showImportModal}
          onHide={() => setShowImportModal(false)}
          onSuccess={handleImportSuccess}
          cardId={card.id}
        />
      )}
    </div>
  );
};

export default CreditCardDetail;

