import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { transactionsAPI, categoriesAPI, accountsAPI } from '../../utils/api';
import TransactionForm from './TransactionForm';
import TransactionList from './TransactionList';
import { TransactionFilters as TransactionFiltersBar } from './TransactionFilters';
import { FilterChipsBar } from './FilterChipsBar';
import { QuickFilters } from './QuickFilters';
import {
  TransactionCategory,
  TransactionRecord,
  TransactionSubmitPayload,
  TransactionType,
} from '../../types/transaction';
import { useTransactionFilters } from '../../hooks/useTransactionFilters';

const Transactions = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const { filters, updateFilters, clearFilters } = useTransactionFilters();
  const [transactions, setTransactions] = useState<TransactionRecord[]>([]);
  const [categories, setCategories] = useState<TransactionCategory[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined);
  const [facets, setFacets] = useState<{
    categories: Array<{ id: string; name: string; count: number }>;
    accounts: Array<{ id: string; name: string; count: number }>;
    types: Array<{ type: string; count: number }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<TransactionRecord | null>(null);
  const [initialTransactionType, setInitialTransactionType] = useState<TransactionType | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // Carrega transações e categorias primeiro (essenciais)
      const [transactionsRes, categoriesRes] = await Promise.all([
        transactionsAPI.getAll({
          date_preset: filters.datePreset,
          date_from: filters.dateFrom,
          date_to: filters.dateTo,
          types: filters.types.join(','),
          account_ids: filters.accountIds.join(','),
          category_ids: filters.categoryIds.join(','),
          min_amount: filters.minAmount,
          max_amount: filters.maxAmount,
          search: filters.search,
          status: filters.status,
          page: filters.page,
          limit: filters.limit,
          sort: filters.sort,
        }),
        categoriesAPI.getAll()
      ]);

      // Carrega contas separadamente (não crítico - se falhar, não quebra a página)
      let accountsRes: any[] = [];
      try {
        const accountsResponse = await accountsAPI.getAll();
        if (accountsResponse.data) {
          accountsRes = Array.isArray(accountsResponse.data) ? accountsResponse.data : [];
        }
      } catch (accountsErr) {
        console.warn('Erro ao carregar contas (não crítico):', accountsErr);
        // Não quebra o fluxo se falhar ao carregar contas
      }

      // Garante que transactions seja sempre um array
      // O backend retorna {data: [...], pagination: {...}}
      const transactionsData = transactionsRes.data;
      let transactionsArray: TransactionRecord[] = [];
      
      if (Array.isArray(transactionsData)) {
        // Se já é um array direto
        transactionsArray = transactionsData;
      } else if (transactionsData?.data && Array.isArray(transactionsData.data)) {
        // Se está dentro de um objeto com propriedade 'data'
        transactionsArray = transactionsData.data;
      } else {
        // Se não encontrou dados, usa array vazio
        transactionsArray = [];
      }

      setTransactions(transactionsArray as TransactionRecord[]);

      // Captura total de resultados para UX
      const pagination = (transactionsData as any)?.pagination;
      if (pagination && typeof pagination.total === 'number') {
        setTotalCount(pagination.total);
      } else {
        setTotalCount(transactionsArray.length);
      }

      // Garante que categories seja sempre um array
      const categoriesData = categoriesRes.data;
      const categoriesArray = Array.isArray(categoriesData)
        ? categoriesData
        : (categoriesData?.data && Array.isArray(categoriesData.data))
          ? categoriesData.data
          : [];

      // Filtra apenas categorias válidas (não contas)
      const validCategories = categoriesArray
        .filter((c: any) => {
          // Categorias devem ter type (income ou expense) e não devem ter campos de conta
          return c.type && (c.type === 'income' || c.type === 'expense') && !c.account_id;
        })
        .map((c: TransactionCategory) => ({
          ...c,
          id: String(c.id),
        }));

      // Enriquecer categorias com contagem (facets)
      if (facets?.categories?.length) {
        const withCounts = validCategories.map((cat: TransactionCategory) => {
          const facet = facets.categories.find((f) => f.id === cat.id);
          return facet ? { ...cat, count: facet.count } : cat;
        });
        setCategories(withCounts as any);
      } else {
        setCategories(validCategories);
      }

      // Processa contas (se foram carregadas com sucesso)
      if (accountsRes) {
        const accountsArray = Array.isArray(accountsRes) ? accountsRes : [];
        // Filtra apenas contas ativas (incluindo cartões de crédito para o filtro)
        // E garante que não há contas duplicadas ou inválidas
        const activeAccounts = accountsArray
          .filter((acc: any) => {
            // Filtra contas ativas e válidas
            const isActive = acc.is_active !== false;
            const hasId = acc.id || acc._id;
            const hasName = acc.name && acc.name.trim() !== '';
            return isActive && hasId && hasName;
          })
          .map((acc: any) => ({
            ...acc,
            id: String(acc.id || acc._id || ''),
            name: String(acc.name || 'Sem nome').trim()
          }))
          .filter((acc: any) => acc.id && acc.name !== 'Sem nome')
          // Remove duplicatas baseado no ID
          .filter((acc: any, index: number, self: any[]) => 
            index === self.findIndex((a: any) => a.id === acc.id)
          );
        
        // Enriquecer contas com contagem (facets)
        if (facets?.accounts?.length) {
          const withCounts = activeAccounts.map((acc: any) => {
            const facet = facets.accounts.find((f) => f.id === acc.id);
            return facet ? { ...acc, count: facet.count } : acc;
          });
          setAccounts(withCounts);
        } else {
          setAccounts(activeAccounts);
        }
      } else {
        // Se não conseguiu carregar, mantém o array vazio
        setAccounts([]);
      }
    } catch (err) {
      setError('Erro ao carregar transações');
      console.error('Load transactions error:', err);
      // Garante que transactions seja um array vazio em caso de erro
      setTransactions([]);
      // Mantém contas vazias em caso de erro
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      // Primeiro carrega facets para enriquecer filtros, depois dados
      const fetchFacetsAndData = async () => {
        try {
          const facetsRes = await transactionsAPI.getFacets({
            date_from: filters.dateFrom,
            date_to: filters.dateTo,
            types: filters.types.join(','),
            account_ids: filters.accountIds.join(','),
            category_ids: filters.categoryIds.join(','),
            min_amount: filters.minAmount,
            max_amount: filters.maxAmount,
            search: filters.search,
            status: filters.status,
            is_recurring: filters.isRecurring,
          });
          setFacets(facetsRes.data);
        } catch (e) {
          console.warn('Erro ao carregar facets de transações (não crítico):', e);
          setFacets(null);
        }
        await loadData();
      };
      fetchFacetsAndData();
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

      // Se veio com filtro de tipo (Receitas ou Despesas)
      if (state.filterType && (state.filterType === 'income' || state.filterType === 'expense')) {
        updateFilters({
          types: [state.filterType],
          page: 1,
        } as any);
      }

      // Limpa o state para não aplicar novamente ao navegar
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const handleAddTransaction = () => {
    setEditingTransaction(null);
    setShowForm(true);
  };

  const handleEditTransaction = (transaction: TransactionRecord) => {
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

  const handleFormSubmit = async (formData: TransactionSubmitPayload) => {
    try {
      setError(''); // Limpa erros anteriores
      if (editingTransaction) {
        await transactionsAPI.update(editingTransaction.id, formData);
        toast.success('Transação atualizada com sucesso!');
      } else {
        await transactionsAPI.create(formData);
        toast.success('Transação criada com sucesso!');
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

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (!transactions.length && loading && isAuthenticated)) {
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
      <TransactionFiltersBar
        filters={filters}
        onChange={updateFilters}
        onClear={clearFilters}
        categories={categories}
        accounts={accounts}
      />

      <QuickFilters filters={filters} onChange={updateFilters} />

      <FilterChipsBar
        filters={filters}
        onChange={updateFilters}
        onClear={clearFilters}
        total={totalCount}
      />

      {/* Lista de Transações */}
      <TransactionList
        transactions={transactions}
        onEdit={handleEditTransaction}
        onDelete={handleDeleteTransaction}
        loading={loading}
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
          transaction={editingTransaction}
          defaultType={initialTransactionType ?? 'expense'}
        />
      )}
    </div>
  );
};

export default Transactions;