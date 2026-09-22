import { useState, useEffect, useMemo } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { transactionsAPI, categoriesAPI, accountsAPI, formatCurrency, formatDate } from '../../utils/api';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import TransactionForm from './TransactionForm';
import TransactionList from './TransactionList';
import { TransactionFilters as TransactionFiltersBar } from './TransactionFilters';
import { FilterChipsBar } from './FilterChipsBar';
import { QuickFilters } from './QuickFilters';
import { useTransactions, type TransactionFacets } from './useTransactions';
import {
  TransactionCategory,
  TransactionRecord,
  TransactionSubmitPayload,
  TransactionType,
} from '../../types/transaction';
import { useTransactionFilters } from '../../hooks/useTransactionFilters';
import './transactions.css';

type LookupAccount = { id: string; name: string; count?: number; [key: string]: unknown };
type LookupCategory = TransactionCategory & { count?: number };

const toArray = (payload: unknown): unknown[] => {
  if (Array.isArray(payload)) return payload;
  const nested = (payload as { data?: unknown } | null)?.data;
  return Array.isArray(nested) ? nested : [];
};

/** Categorias válidas (com tipo receita/despesa e sem campos de conta). */
const normalizeCategories = (payload: unknown): TransactionCategory[] => toArray(payload)
  .filter((c): c is TransactionCategory & { account_id?: unknown } => {
    const item = c as { type?: string; account_id?: unknown };
    return (item.type === 'income' || item.type === 'expense') && !item.account_id;
  })
  .map((c) => ({ ...c, id: String(c.id) }));

/** Contas ativas com id e nome, sem duplicatas. */
const normalizeAccounts = (payload: unknown): LookupAccount[] => {
  const seen = new Set<string>();
  return toArray(payload).flatMap((raw) => {
    const acc = raw as { id?: unknown; _id?: unknown; name?: unknown; is_active?: unknown };
    const id = String(acc.id || acc._id || '');
    const name = String(acc.name || '').trim();
    if (acc.is_active === false || !id || !name || seen.has(id)) return [];
    seen.add(id);
    return [{ ...(raw as object), id, name }];
  });
};

const withCounts = <T extends { id: string }>(items: T[], facet?: Array<{ id: string; count: number }>) =>
  facet?.length ? items.map((item) => {
    const match = facet.find((f) => f.id === item.id);
    return match ? { ...item, count: match.count } : item;
  }) : items;

function SummaryBlock({ facets, fallbackCount, loading, error, retry }: {
  facets: TransactionFacets | null; fallbackCount?: number; loading: boolean; error: string; retry: () => void;
}) {
  const summary = facets?.summary;
  const value = (amount?: number) => (error || amount == null) ? '—' : formatCurrency(amount);
  const net = summary?.net_paid ?? 0;
  const cards = [
    { label: 'Entradas recebidas', value: value(summary?.paid_income), icon: 'arrow-down-left', valueClass: 'text-emerald-600 dark:text-emerald-400', iconClass: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300', hint: 'Receitas pagas no filtro' },
    { label: 'Total pago', value: value(summary?.paid_expense), icon: 'check2-circle', valueClass: 'text-blue-600 dark:text-blue-400', iconClass: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300', hint: 'Despesas efetivadas no filtro' },
    { label: 'Saldo líquido', value: value(summary?.net_paid), icon: 'activity', valueClass: net >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400', iconClass: net >= 0 ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-300', hint: 'Entradas menos pagamentos' },
  ];
  return (
    <section aria-label="Resumo das transações filtradas" aria-busy={loading} className="tx space-y-3">
      {error && (
        <div className="tx-error" role="alert">
          <span>Resumo indisponível. {error}</span>
          <button type="button" className="tx-button" onClick={retry}>Tentar novamente</button>
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map((item) => (
          <article key={item.label} className="card-base p-4 sm:p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{item.label}</p>
                <p className={`mt-2 truncate text-xl font-bold ${item.valueClass}`}>{item.value}</p>
              </div>
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${item.iconClass}`}>
                <i className={`bi bi-${item.icon}`} aria-hidden="true" />
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{item.hint}</p>
          </article>
        ))}
        <article className="card-base p-4 sm:p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Transações</p>
          <p className="mt-2 text-xl font-bold text-slate-900 dark:text-white">{summary?.transaction_count ?? fallbackCount ?? '—'}</p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">No período e filtros atuais</p>
        </article>
        <article className="card-base border-amber-200 p-4 sm:p-5 dark:border-amber-800/50">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">Revisar categoria</p>
          <p className="mt-2 text-xl font-bold text-amber-700 dark:text-amber-300">{error || !summary ? '—' : summary.uncategorized_count}</p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Sem classificação confiável</p>
        </article>
      </div>
      <p role="status" aria-live="polite" className="sr-only">{loading ? 'Atualizando resumo…' : error ? 'Resumo indisponível' : ''}</p>
    </section>
  );
}

const Transactions = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const { filters, updateFilters, clearFilters } = useTransactionFilters();
  const [revision, setRevision] = useState(0);
  const [lookups, setLookups] = useState<{ categories: TransactionCategory[]; accounts: LookupAccount[] }>({ categories: [], accounts: [] });
  const [showForm, setShowForm] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [editingTransaction, setEditingTransaction] = useState<TransactionRecord | null>(null);
  const [initialTransactionType, setInitialTransactionType] = useState<TransactionType | null>(null);
  const [pendingDelete, setPendingDelete] = useState<TransactionRecord | null>(null);
  const enabled = isAuthenticated && !authLoading;
  const { list, facets } = useTransactions(filters, revision, enabled);
  const refresh = () => setRevision((value) => value + 1);

  // Categorias e contas são carregadas uma vez; o resumo (facets) apenas enriquece as contagens.
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    void Promise.all([
      categoriesAPI.getAll().then((res) => res.data).catch(() => []),
      accountsAPI.getAll().then((res) => res.data).catch(() => []),
    ]).then(([categoriesData, accountsData]) => {
      if (active) setLookups({ categories: normalizeCategories(categoriesData), accounts: normalizeAccounts(accountsData) });
    });
    return () => { active = false; };
  }, [enabled]);

  const categories = useMemo<LookupCategory[]>(() => withCounts(lookups.categories, facets.data?.categories), [lookups.categories, facets.data]);
  const accounts = useMemo<LookupAccount[]>(() => withCounts(lookups.accounts, facets.data?.accounts), [lookups.accounts, facets.data]);
  const accountNames = useMemo(() => Object.fromEntries(lookups.accounts.map((acc) => [acc.id, acc.name])), [lookups.accounts]);

  // Verifica se veio da dashboard com instrução para abrir o formulário ou aplicar filtro
  useEffect(() => {
    if (location.state) {
      const state = location.state as { openForm?: boolean; transactionType?: TransactionType; datePreset?: string; filterType?: string };

      if (state.openForm) {
        setInitialTransactionType(state.transactionType || 'expense');
        setShowForm(true);
      }

      const allowedPresets = ['today', '7d', 'this_month', 'last_month', 'last_90_days', 'year_to_date'] as const;
      type Preset = typeof allowedPresets[number];
      const nextPreset = allowedPresets.find((preset) => preset === state.datePreset) as Preset | undefined;

      if (state.filterType === 'income' || state.filterType === 'expense') {
        updateFilters({ types: [state.filterType], page: 1, ...(nextPreset ? { datePreset: nextPreset } : {}) });
      } else if (nextPreset) {
        updateFilters({ datePreset: nextPreset, page: 1 });
      }

      // Limpa o state para não aplicar novamente ao navegar
      window.history.replaceState({}, document.title);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  const handleAddTransaction = () => {
    setEditingTransaction(null);
    setShowForm(true);
  };

  const handleEditTransaction = (transaction: TransactionRecord) => {
    setEditingTransaction(transaction);
    setShowForm(true);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    await transactionsAPI.delete(pendingDelete.id);
    toast.success('Transação excluída com sucesso!');
    setPendingDelete(null);
    // Ao excluir a última da página, volta uma página; senão apenas recarrega.
    if (list.data?.rows.length === 1 && filters.page > 1) updateFilters({ page: filters.page - 1 });
    else refresh();
  };

  const handleFormSubmit = async (formData: TransactionSubmitPayload) => {
    if (editingTransaction) {
      await transactionsAPI.update(editingTransaction.id, formData);
      toast.success('Transação atualizada com sucesso!');
    } else {
      await transactionsAPI.create(formData);
      toast.success('Transação criada com sucesso!');
    }
    // Fecha o modal apenas se a requisição foi bem-sucedida; o formulário exibe o erro caso contrário.
    setShowForm(false);
    setEditingTransaction(null);
    refresh();
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center" role="status">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  const pagination = list.data?.pagination;
  const totalPages = Math.max(1, pagination?.pages ?? 1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('transactions.title')}</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie suas receitas e despesas</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => navigate('/import')}
            className="btn-base bg-slate-600 hover:bg-slate-700 dark:bg-slate-700 dark:hover:bg-slate-600 text-white shadow-sm px-4 py-2.5 flex items-center gap-2"
          >
            <i className="bi bi-upload" aria-hidden="true"></i>
            Importar dados
          </button>
          <button
            type="button"
            onClick={handleAddTransaction}
            className="btn-base bg-brand-500 hover:bg-brand-600 text-white shadow-sm px-4 py-2.5 flex items-center gap-2"
          >
            <i className="bi bi-plus-circle" aria-hidden="true"></i>
            {t('transactions.add')}
          </button>
        </div>
      </div>

      {/* Filtros (antes dos indicadores) */}
      <section className="card-base overflow-hidden" aria-label="Filtros das transações">
        <button
          type="button"
          onClick={() => setShowFilters((current) => !current)}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
          aria-expanded={showFilters}
        >
          <span className="flex items-center gap-2 font-semibold text-slate-800 dark:text-white">
            <i className="bi bi-sliders2" aria-hidden="true" /> Filtros avançados
          </span>
          <i className={`bi bi-chevron-${showFilters ? 'up' : 'down'} text-slate-500`} aria-hidden="true" />
        </button>
        {showFilters && (
          <div className="border-t border-slate-200 p-3 dark:border-slate-700">
            <TransactionFiltersBar
              filters={filters}
              onChange={updateFilters}
              onClear={clearFilters}
              categories={categories}
              accounts={accounts}
            />
          </div>
        )}
      </section>

      <QuickFilters filters={filters} onChange={updateFilters} />

      <FilterChipsBar
        filters={filters}
        onChange={updateFilters}
        onClear={clearFilters}
        total={pagination?.total}
      />

      {/* Indicadores */}
      <SummaryBlock facets={facets.data} fallbackCount={pagination?.total} loading={facets.loading} error={facets.error} retry={refresh} />

      {/* Lista de Transações */}
      <section aria-label="Lista de transações" className="tx space-y-4">
        {list.error ? (
          <div className="tx-error" role="alert">
            <span>Lista indisponível. {list.error}</span>
            <button type="button" className="tx-button" onClick={refresh}>Tentar novamente</button>
          </div>
        ) : (
          <TransactionList
            transactions={list.data?.rows ?? []}
            accountNames={accountNames}
            onEdit={handleEditTransaction}
            onDelete={setPendingDelete}
            loading={list.loading}
          />
        )}
        {pagination && pagination.total > 0 && (
          <nav aria-label="Paginação das transações" className="tx-pagination">
            <p className="tx-muted text-sm">
              {pagination.total} {pagination.total === 1 ? 'transação' : 'transações'} · página {filters.page} de {totalPages}
            </p>
            <div className="flex gap-2">
              <button type="button" className="tx-button" disabled={filters.page <= 1 || list.loading} onClick={() => updateFilters({ page: filters.page - 1 })}>Anterior</button>
              <button type="button" className="tx-button" disabled={filters.page >= totalPages || list.loading} onClick={() => updateFilters({ page: filters.page + 1 })}>Próxima</button>
            </div>
          </nav>
        )}
      </section>

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
          responsiblePersons={facets.data?.responsible_persons ?? []}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Excluir transação"
          subject={pendingDelete.description}
          details={[
            ['Valor', formatCurrency(Math.abs(Number(pendingDelete.amount) || 0))],
            ['Data', formatDate(pendingDelete.date)],
          ]}
          consequence={<p>Esta ação não pode ser desfeita.</p>}
          confirmLabel="Excluir"
          danger
          errorMessage="Não foi possível excluir a transação. Tente novamente."
          onConfirm={confirmDelete}
          onClose={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
};

export default Transactions;
