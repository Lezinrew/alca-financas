import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { categoriesAPI, transactionsAPI, formatCurrency } from '../../utils/api';
import PlanningForm from './PlanningForm';
import PlanningSummary from './PlanningSummary';

interface Budget {
  id?: number;
  month: number;
  year: number;
  monthly_income: number;
  savings_percentage: number;
  category_budgets: CategoryBudget[];
  credit_card_visualization?: 'purchase_date' | 'invoice_date';
}

interface CategoryBudget {
  category_id: string;
  amount: number;
}

interface ActualSummary {
  totalIncome: number;
  totalExpenses: number;
  balance: number;
  savingsRate: number;
}

const Planning: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [budget, setBudget] = useState<Budget | null>(null);
  const [categories, setCategories] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [actualSummary, setActualSummary] = useState<ActualSummary>({
    totalIncome: 0,
    totalExpenses: 0,
    balance: 0,
    savingsRate: 0
  });

  const currentMonth = currentDate.getMonth() + 1;
  const currentYear = currentDate.getFullYear();

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadData();
    }
  }, [isAuthenticated, authLoading, currentMonth, currentYear]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // Carrega categorias e transações
      const [categoriesRes, transactionsRes] = await Promise.all([
        categoriesAPI.getAll(),
        transactionsAPI.getAll({
          month: currentMonth,
          year: currentYear
        })
      ]);
      setCategories(categoriesRes.data);
      setTransactions(transactionsRes.data);

      const totalIncome = transactionsRes.data
        .filter((tx: any) => tx.type === 'income')
        .reduce((sum: number, tx: any) => sum + (tx.amount || 0), 0);

      const totalExpenses = transactionsRes.data
        .filter((tx: any) => tx.type === 'expense')
        .reduce((sum: number, tx: any) => sum + (tx.amount || 0), 0);

      const balance = totalIncome - totalExpenses;
      const savingsRate = totalIncome > 0 ? ((totalIncome - totalExpenses) / totalIncome) * 100 : 0;

      setActualSummary({
        totalIncome,
        totalExpenses,
        balance,
        savingsRate
      });

      // TODO: Carregar orçamento do backend quando a API estiver pronta
      // Por enquanto, verifica se há orçamento salvo localmente
      const savedBudget = localStorage.getItem(`budget_${currentYear}_${currentMonth}`);
      if (savedBudget) {
        setBudget(JSON.parse(savedBudget));
      } else {
        setBudget(null);
      }
    } catch (err) {
      setError('Erro ao carregar dados');
      console.error('Load planning error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePlanning = () => {
    setShowForm(true);
  };

  const handleCopyPreviousMonth = () => {
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    const prevBudget = localStorage.getItem(`budget_${prevYear}_${prevMonth}`);
    
    if (prevBudget) {
      const budgetData = JSON.parse(prevBudget);
      budgetData.month = currentMonth;
      budgetData.year = currentYear;
      setBudget(budgetData);
      localStorage.setItem(`budget_${currentYear}_${currentMonth}`, JSON.stringify(budgetData));
      setError('');
    } else {
      setError('Nenhum planejamento encontrado para o mês anterior');
    }
  };

  const handleFormSubmit = async (formData: any) => {
    try {
      const newBudget: Budget = {
        month: currentMonth,
        year: currentYear,
        monthly_income: formData.monthly_income,
        savings_percentage: formData.savings_percentage,
        category_budgets: formData.category_budgets || []
      };

      // TODO: Salvar no backend quando a API estiver pronta
      localStorage.setItem(`budget_${currentYear}_${currentMonth}`, JSON.stringify(newBudget));
      setBudget(newBudget);
      setShowForm(false);
      setError('');
    } catch (err: any) {
      throw err;
    }
  };

  const handleDeletePlanning = () => {
    if (!window.confirm('Tem certeza que deseja excluir este planejamento? Esta ação não pode ser desfeita.')) {
      return;
    }

    try {
      // TODO: Excluir do backend quando a API estiver pronta
      localStorage.removeItem(`budget_${currentYear}_${currentMonth}`);
      setBudget(null);
      setError('');
    } catch (err: any) {
      console.error('Delete planning error:', err);
      setError('Erro ao excluir planejamento');
    }
  };

  const handlePreviousMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth - 2, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth, 1));
  };

  const months = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600 dark:text-slate-400">Carregando planejamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Planejamento</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie seus orçamentos mensais</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {/* Layout Principal */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Coluna Esquerda - Conteúdo Principal */}
        <div className="lg:col-span-3 space-y-4">
          {/* Seletor de Tipo e Navegação */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between">
              {/* Tipo de Planejamento */}
              <div className="relative">
                <button
                  type="button"
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-full text-sm font-medium flex items-center gap-2"
                >
                  Planejamento Mensal
                  <i className="bi bi-chevron-down text-xs"></i>
                </button>
              </div>

              {/* Navegação de Mês/Ano */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handlePreviousMonth}
                  className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                  aria-label="Mês anterior"
                >
                  <i className="bi bi-chevron-left"></i>
                </button>
                <div className="px-4 py-2 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-sm font-medium">
                  {months[currentMonth - 1]} {currentYear}
                </div>
                <button
                  type="button"
                  onClick={handleNextMonth}
                  className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                  aria-label="Próximo mês"
                >
                  <i className="bi bi-chevron-right"></i>
                </button>
              </div>
            </div>
          </div>

          {/* Conteúdo Principal */}
          {!budget ? (
            <div className="card-base p-12 text-center">
              <div className="max-w-md mx-auto">
                {/* Ilustração */}
                <div className="mb-6">
                  <div className="w-48 h-48 mx-auto bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 rounded-full flex items-center justify-center">
                    <i className="bi bi-graph-up-arrow text-6xl text-purple-600 dark:text-purple-400"></i>
                  </div>
                </div>
                
                <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                  Nenhum orçamento definido para este mês.
                </h3>
                <p className="text-slate-600 dark:text-slate-300 mb-6">
                  Comece criando um novo planejamento mensal para organizar suas finanças.
                </p>

                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <button
                    type="button"
                    onClick={handleCreatePlanning}
                    className="px-6 py-3 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium transition-colors"
                  >
                    Definir Novo Planejamento
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyPreviousMonth}
                    className="px-6 py-3 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 rounded-lg font-medium transition-colors"
                  >
                    Copiar Planejamento do Mês Anterior
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Resumo Geral */}
              <div className="card-base p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Restam</p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">
                      {formatCurrency(
                        (budget.monthly_income * (1 - budget.savings_percentage / 100)) -
                        (budget.category_budgets?.reduce((sum, cb) => sum + (cb.amount || 0), 0) || 0)
                      )}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-600 dark:text-slate-300">
                      {formatCurrency(
                        budget.category_budgets?.reduce((sum, cb) => {
                          const categoryTransactions = transactions.filter(
                            (t: any) => String(t.category_id) === cb.category_id
                          );
                          const totalSpent = categoryTransactions.reduce(
                            (sum: number, t: any) => sum + (t.amount || 0),
                            0
                          );
                          return sum + totalSpent;
                        }, 0) || 0
                      )}{' '}
                      de {formatCurrency(
                        budget.category_budgets?.reduce((sum, cb) => sum + (cb.amount || 0), 0) || 0
                      )}{' '}
                      gastos
                    </p>
                  </div>
                </div>
              </div>

              {/* Tabela de Categorias */}
              <div className="table-container overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="table-header">
                      <tr>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Categoria
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Meta planejada
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Despesas pagas
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Despesas previstas
                        </th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Total gasto
                        </th>
                        <th className="px-6 py-4 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                          Ações
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
                      {categories
                        .filter((cat: any) => 
                          budget.category_budgets?.some(cb => cb.category_id === String(cat.id))
                        )
                        .map((category: any) => {
                          const categoryBudget = budget.category_budgets?.find(
                            (cb) => cb.category_id === String(category.id)
                          );
                          const categoryTransactions = transactions.filter(
                            (t: any) => String(t.category_id) === String(category.id)
                          );
                          const paidTransactions = categoryTransactions.filter(
                            (t: any) => t.status === 'paid'
                          );
                          const pendingTransactions = categoryTransactions.filter(
                            (t: any) => t.status !== 'paid'
                          );
                          const paidAmount = paidTransactions.reduce(
                            (sum: number, t: any) => sum + (t.amount || 0),
                            0
                          );
                          const pendingAmount = pendingTransactions.reduce(
                            (sum: number, t: any) => sum + (t.amount || 0),
                            0
                          );
                          const totalSpent = paidAmount + pendingAmount;
                          const remaining = (categoryBudget?.amount || 0) - totalSpent;
                          const paidPercentage = categoryBudget?.amount 
                            ? (paidAmount / categoryBudget.amount) * 100 
                            : 0;
                          const pendingPercentage = categoryBudget?.amount 
                            ? (pendingAmount / categoryBudget.amount) * 100 
                            : 0;

                          return (
                            <tr key={category.id} className="table-row">
                              <td className="px-6 py-4">
                                <div className="flex items-center gap-3">
                                  <div
                                    className="w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0"
                                    style={{ backgroundColor: category.color }}
                                  >
                                    <i className={`bi bi-${category.icon || 'circle'} text-base`}></i>
                                  </div>
                                  <span className="font-semibold text-slate-900 dark:text-white text-sm">
                                    {category.name}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-sm font-medium text-slate-900 dark:text-white">
                                  {formatCurrency(categoryBudget?.amount || 0)}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                  {formatCurrency(paidAmount)}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                  {formatCurrency(pendingAmount)}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-sm font-semibold text-slate-900 dark:text-white">
                                  {formatCurrency(totalSpent)}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <div className="flex items-center justify-end gap-4">
                                  <div className="text-right min-w-[120px]">
                                    <p className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                                      Restam {formatCurrency(remaining)}
                                    </p>
                                    <div className="flex gap-0.5 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                      {paidPercentage > 0 && (
                                        <div
                                          className="h-full bg-emerald-500 rounded-l-full"
                                          style={{ width: `${Math.min(paidPercentage, 100)}%` }}
                                          title={`${paidPercentage.toFixed(1)}% pago`}
                                        ></div>
                                      )}
                                      {pendingPercentage > 0 && (
                                        <div
                                          className="h-full bg-emerald-400 dark:bg-emerald-600 rounded-r-full"
                                          style={{ width: `${Math.min(pendingPercentage, 100)}%` }}
                                          title={`${pendingPercentage.toFixed(1)}% previsto`}
                                        ></div>
                                      )}
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => setShowForm(true)}
                                    className="p-2 text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded-lg transition-colors"
                                    title="Editar"
                                  >
                                    <i className="bi bi-pencil text-base"></i>
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={handleDeletePlanning}
                  className="px-4 py-2 bg-white dark:bg-slate-700 border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  <i className="bi bi-trash"></i>
                  Excluir Planejamento
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(true)}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  <i className="bi bi-pencil"></i>
                  Editar Planejamento
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Coluna Direita - Resumo */}
        <div className="space-y-3">
          <PlanningSummary budget={budget} actuals={actualSummary} />
        </div>
      </div>

      {/* Modal do Formulário */}
      {showForm && (
        <PlanningForm
          show={showForm}
          onHide={() => setShowForm(false)}
          onSubmit={handleFormSubmit}
          categories={categories}
          budget={budget}
          defaultIncome={actualSummary.totalIncome}
        />
      )}
    </div>
  );
};

export default Planning;

