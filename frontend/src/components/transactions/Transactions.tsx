import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { transactionsAPI, categoriesAPI, formatCurrency, formatDate } from '../../utils/api';
import TransactionForm from './TransactionForm';
import TransactionList from './TransactionList';

const Transactions = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [initialTransactionType, setInitialTransactionType] = useState<'expense' | 'income' | null>(null);
  
  // Inicializa filtros com base no state da navegação (se houver)
  const getInitialFilters = () => {
    const state = location.state as any;
    const initialType = (state?.filterType && (state.filterType === 'income' || state.filterType === 'expense')) 
      ? state.filterType 
      : '';
    
    return {
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      category_id: '',
      type: initialType
    };
  };

  // Filtros
  const [filters, setFilters] = useState(getInitialFilters);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      
      const [transactionsRes, categoriesRes] = await Promise.all([
        transactionsAPI.getAll(filters),
        categoriesAPI.getAll()
      ]);
      
      setTransactions(transactionsRes.data);
      // Backend devolve categorias com 'id' string; garantir string
      setCategories(categoriesRes.data.map((c: any) => ({ ...c, id: String(c.id) })));
    } catch (err) {
      setError('Erro ao carregar transações');
      console.error('Load transactions error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, isAuthenticated, authLoading]);

  // Verifica se veio da dashboard com instrução para abrir o formulário ou aplicar filtro
  useEffect(() => {
    if (location.state) {
      const state = location.state as any;
      
      // Se veio com instrução para abrir o formulário
      if (state.openForm) {
        setInitialTransactionType(state.transactionType || 'expense');
        setShowForm(true);
      }
      
      // Se veio com filtro de tipo (Receitas ou Despesas) e ainda não foi aplicado
      if (state.filterType && (state.filterType === 'income' || state.filterType === 'expense')) {
        setFilters(prev => {
          // Só atualiza se o filtro for diferente do atual
          if (prev.type !== state.filterType) {
            return {
              ...prev,
              type: state.filterType
            };
          }
          return prev;
        });
      }
      
      // Limpa o state para não aplicar novamente ao navegar
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const handleAddTransaction = () => {
    setEditingTransaction(null);
    setShowForm(true);
  };

  const handleEditTransaction = (transaction) => {
    console.log('Transactions: Editando transação:', transaction);
    setEditingTransaction(transaction);
    setShowForm(true);
  };

  const handleDeleteTransaction = async (transactionId: string) => {
    console.log('Transactions: handleDeleteTransaction chamado para:', transactionId);
    
    if (!window.confirm('Tem certeza que deseja excluir esta transação? Esta ação não pode ser desfeita.')) {
      return;
    }

    try {
      setLoading(true);
      setError('');
      console.log('Deletando transação:', transactionId);
      
      await transactionsAPI.delete(transactionId);
      console.log('Transação deletada com sucesso');
      
      // Recarrega a lista de transações
      await loadData();
    } catch (err: any) {
      console.error('Delete transaction error:', err);
      const errorMessage = err.response?.data?.error || err.response?.data?.message || 'Erro ao deletar transação';
      setError(errorMessage);
      
      // Remove a mensagem de erro após 5 segundos
      setTimeout(() => setError(''), 5000);
    } finally {
      setLoading(false);
    }
  };

  const handleFormSubmit = async (formData) => {
    try {
      setError(''); // Limpa erros anteriores
      if (editingTransaction) {
        await transactionsAPI.update(editingTransaction.id, formData);
      } else {
        await transactionsAPI.create(formData);
      }
      
      // Fecha o modal apenas se a requisição foi bem-sucedida
      setShowForm(false);
      setEditingTransaction(null);
      await loadData(); // Recarrega lista
    } catch (err: any) {
      // Propaga o erro para o formulário exibir a mensagem
      console.error('Erro ao salvar transação:', err);
      throw err;
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const months = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('transactions.title')}</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie suas receitas e despesas</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/import')}
            className="btn-base bg-slate-600 hover:bg-slate-700 dark:bg-slate-700 dark:hover:bg-slate-600 text-white shadow-sm px-4 py-2.5 flex items-center gap-2"
          >
            <i className="bi bi-upload"></i>
            Importar dados
          </button>
          <button
            onClick={handleAddTransaction}
            className="btn-base bg-brand-500 hover:bg-brand-600 text-white shadow-sm px-4 py-2.5 flex items-center gap-2"
          >
            <i className="bi bi-plus-circle"></i>
            {t('transactions.add')}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-error-light border border-error rounded-card p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-error"></i>
          <span className="text-error-dark">{error}</span>
        </div>
      )}

      {/* Filtros */}
      <div className="card-base p-6">
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label htmlFor="filter-month" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">{t('common.filter')} por Mês</label>
              <select
                id="filter-month"
                name="month"
                className="input-base dark:bg-[#1a1d29] dark:text-white dark:border-slate-700"
                value={filters.month}
                onChange={(e) => handleFilterChange('month', e.target.value)}
              >
                {months.map((month, index) => (
                  <option key={index} value={index + 1}>
                    {month}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="filter-year" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Ano</label>
              <select
                id="filter-year"
                name="year"
                className="select-base"
                value={filters.year}
                onChange={(e) => handleFilterChange('year', e.target.value)}
              >
                {years.map(year => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="filter-category" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">{t('transactions.category')}</label>
              <select
                id="filter-category"
                name="category_id"
                className="select-base"
                value={filters.category_id}
                onChange={(e) => handleFilterChange('category_id', e.target.value)}
              >
                <option value="">Todas as categorias</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="filter-type" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">{t('transactions.type')}</label>
              <select
                id="filter-type"
                name="type"
                className="select-base"
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
              >
                <option value="">Todos os tipos</option>
                <option value="income">{t('transactions.income')}</option>
                <option value="expense">{t('transactions.expense')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Lista de Transações */}
      <TransactionList
        transactions={transactions}
        onEdit={handleEditTransaction}
        onDelete={handleDeleteTransaction}
      />

      {/* Modal do Formulário */}
      {showForm && (
        <TransactionForm
          show={showForm}
          onHide={() => {
            setShowForm(false);
            setEditingTransaction(null);
            setInitialTransactionType(null);
          }}
          onSubmit={handleFormSubmit}
          categories={categories}
          transaction={editingTransaction || (initialTransactionType ? {
            type: initialTransactionType,
            description: '',
            amount: 0,
            category_id: '',
            date: new Date().toISOString().split('T')[0]
          } as any : null)}
        />
      )}
    </div>
  );
};

export default Transactions;