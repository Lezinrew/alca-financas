import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, formatDate, categoriesAPI } from '../../utils/api';
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
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [sortField, setSortField] = useState<'date' | 'description' | 'amount'>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    if (isAuthenticated && !authLoading && cardId) {
      loadCardData();
      loadCategories();
    }
  }, [isAuthenticated, authLoading, cardId, selectedMonth, selectedYear]);

  const loadCardData = async () => {
    try {
      setLoading(true);
      setError('');

      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

      // Carrega o cartão
      const cardResponse = await fetch(`${API_URL}/api/accounts/${cardId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!cardResponse.ok) {
        throw new Error('Cartão não encontrado');
      }

      const accountData = await cardResponse.json();

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
      const expensesResponse = await fetch(
        `${API_URL}/api/transactions?account_id=${cardId}&month=${selectedMonth}&year=${selectedYear}&type=expense`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        }
      );

      if (expensesResponse.ok) {
        try {
          const expensesData = await expensesResponse.json();
          // Garante que expenses seja sempre um array
          const expensesArray = Array.isArray(expensesData)
            ? expensesData
            : (expensesData?.data && Array.isArray(expensesData.data))
              ? expensesData.data
              : [];
          setExpenses(expensesArray);
        } catch (parseError) {
          console.error('Erro ao processar despesas:', parseError);
          setExpenses([]);
        }
      } else {
        // Se a resposta não for OK, define expenses como array vazio
        setExpenses([]);
      }
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar dados do cartão');
      console.error('Load card data error:', err);
    } finally {
      setLoading(false);
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
      // TODO: Implementar criação de despesa
      console.log('Despesa salva:', expenseData);
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
    month: selectedMonth,
    year: selectedYear,
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImportModal(true)}
            className="px-4 py-2 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <i className="bi bi-upload"></i>
            Importar Fatura
          </button>
          <button
            onClick={() => setShowExpenseForm(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <i className="bi bi-plus-circle"></i>
            Adicionar Despesa
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Month Navigation */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
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
          </div>

          {/* Expenses Table */}
          <div className="card-base overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Situação
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
                      onClick={() => handleSort('date')}
                    >
                      <div className="flex items-center gap-2">
                        Data
                        {sortField === 'date' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'}`}></i>
                        )}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
                      onClick={() => handleSort('description')}
                    >
                      <div className="flex items-center gap-2">
                        Descrição
                        {sortField === 'description' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'}`}></i>
                        )}
                      </div>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
                      Categoria
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
                      onClick={() => handleSort('amount')}
                    >
                      <div className="flex items-center gap-2">
                        Valor
                        {sortField === 'amount' && (
                          <i className={`bi bi-arrow-${sortDirection === 'asc' ? 'up' : 'down'}`}></i>
                        )}
                      </div>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider">
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
                        <tr key={expense.id} className="table-row">
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                              {expense.status === 'paid' ? 'Pago' : 'Pendente'}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-secondary">
                            {expense.date ? formatDate(expense.date) : '-'}
                          </td>
                          <td className="px-4 py-3 text-sm text-primary font-medium">
                            {expense.description || 'Sem descrição'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {expense.category && expense.category.name ? (
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-6 h-6 rounded-full flex items-center justify-center"
                                  style={{ backgroundColor: expense.category.color || '#6b7280' }}
                                >
                                  <i className={`bi bi-${expense.category.icon || 'circle'} text-white text-xs`}></i>
                                </div>
                                <span className="text-sm text-secondary">{expense.category.name}</span>
                              </div>
                            ) : (
                              <span className="text-sm text-slate-400">Sem categoria</span>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-red-600 dark:text-red-400">
                            {formatCurrency(expense.amount || 0)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm">
                            <button className="text-blue-600 dark:text-blue-400 hover:underline">
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
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-secondary mb-1">Valor da fatura</p>
                <p className="text-2xl font-bold text-primary">{formatCurrency(totalExpenses)}</p>
              </div>
              <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <i className="bi bi-currency-dollar text-blue-600 dark:text-blue-400 text-xl"></i>
              </div>
            </div>
          </div>

          {/* Limite disponível */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-secondary mb-1">Limite disponível</p>
                <p className={`text-2xl font-bold ${
                  availableLimit >= 0 
                    ? 'text-emerald-600 dark:text-emerald-400' 
                    : 'text-red-600 dark:text-red-400'
                }`}>
                  {formatCurrency(availableLimit)}
                </p>
                <p className="text-xs text-secondary mt-1">
                  Limite total: {formatCurrency(card.limit)} | Usado: {formatCurrency(totalUsed)}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                <i className="bi bi-speedometer text-amber-600 dark:text-amber-400 text-xl"></i>
              </div>
            </div>
            <div className="mt-4 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  availableLimit >= 0 
                    ? 'bg-gradient-to-r from-emerald-500 to-blue-500' 
                    : 'bg-red-500'
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

          {/* Status */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-secondary mb-1">Status</p>
                <p className="text-lg font-semibold text-primary">Fatura aberta</p>
              </div>
              <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <i className="bi bi-file-text text-green-600 dark:text-green-400 text-xl"></i>
              </div>
            </div>
          </div>

          {/* Dia de Fechamento */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-secondary mb-1">Dia de fechamento</p>
                <p className="text-lg font-semibold text-primary">
                  {getNextClosingDate()?.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                <i className="bi bi-calendar text-purple-600 dark:text-purple-400 text-xl"></i>
              </div>
            </div>
          </div>

          {/* Data Vencimento */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-secondary mb-1">Data vencimento</p>
                <p className="text-lg font-semibold text-primary">
                  {getNextDueDate()?.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' })}
                </p>
              </div>
              <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
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

