import { FC, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TransactionFilterState } from '../../hooks/useTransactionFilters';

interface TransactionFiltersProps {
  filters: TransactionFilterState;
  onChange: (partial: Partial<TransactionFilterState>) => void;
  onClear: () => void;
  categories: Array<{ id: string; name: string; type: string }>;
  accounts: Array<{ id: string; name: string }>;
}

export const TransactionFilters: FC<TransactionFiltersProps> = ({
  filters,
  onChange,
  onClear,
  categories,
  accounts,
}) => {
  const { t } = useTranslation();
  const [searchInput, setSearchInput] = useState(filters.search || '');
  const [showMore, setShowMore] = useState(false);

  // Debounce da busca
  useEffect(() => {
    const handler = setTimeout(() => {
      onChange({ search: searchInput || undefined, page: 1 });
    }, 400);
    return () => clearTimeout(handler);
  }, [searchInput]);

  useEffect(() => {
    setSearchInput(filters.search || '');
  }, [filters.search]);

  const handleDatePresetChange = (value: string) => {
    if (value === 'today' || value === '7d' || value === 'this_month' || value === 'last_month') {
      onChange({ datePreset: value as any, page: 1 });
    }
  };

  const handleTypeToggle = (type: 'income' | 'expense') => {
    let next: ('income' | 'expense' | 'transfer')[] = [...filters.types];
    if (next.includes(type)) {
      next = next.filter((t) => t !== type);
    } else {
      next.push(type);
    }
    onChange({ types: next as any, page: 1 });
  };

  const handleAccountChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onChange({ accountIds: value ? [value] : [], page: 1 });
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onChange({ categoryIds: value ? [value] : [], page: 1 });
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(e.target.value);
  };

  return (
    <div className="card-base mb-4">
      <div className="p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-3 items-center">
          {/* Período */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-secondary uppercase">
              {t('transactions.period') || 'Período'}
            </span>
            <select
              className="select-base h-9"
              value={filters.datePreset}
              onChange={(e) => handleDatePresetChange(e.target.value)}
            >
              <option value="today">Hoje</option>
              <option value="7d">Últimos 7 dias</option>
              <option value="this_month">Este mês</option>
              <option value="last_month">Mês passado</option>
            </select>
          </div>

          {/* Conta (multi em UX simples: still single select, mas pronto para evoluir) */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-secondary uppercase">
              {t('accounts.title') || 'Conta'}
            </span>
            <select
              className="select-base h-9 min-w-[160px]"
              value={filters.accountIds[0] || ''}
              onChange={handleAccountChange}
            >
              <option value="">{t('common.all') || 'Todas'}</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                </option>
              ))}
            </select>
          </div>

          {/* Categoria */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-secondary uppercase">
              {t('categories.title') || 'Categoria'}
            </span>
            <select
              className="select-base h-9 min-w-[160px]"
              value={filters.categoryIds[0] || ''}
              onChange={handleCategoryChange}
            >
              <option value="">{t('common.all') || 'Todas'}</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          {/* Tipo */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-secondary uppercase">
              {t('transactions.type') || 'Tipo'}
            </span>
            <div className="inline-flex rounded-md border border-slate-200 dark:border-slate-700 overflow-hidden">
              <button
                type="button"
                className={
                  'px-3 py-1.5 text-xs font-medium ' +
                  (filters.types.includes('income')
                    ? 'bg-emerald-500 text-white'
                    : 'bg-transparent text-slate-600 dark:text-slate-300')
                }
                onClick={() => handleTypeToggle('income')}
              >
                Receita
              </button>
              <button
                type="button"
                className={
                  'px-3 py-1.5 text-xs font-medium border-l border-slate-200 dark:border-slate-700 ' +
                  (filters.types.includes('expense')
                    ? 'bg-red-500 text-white'
                    : 'bg-transparent text-slate-600 dark:text-slate-300')
                }
                onClick={() => handleTypeToggle('expense')}
              >
                Despesa
              </button>
            </div>
          </div>
        </div>

        {/* Search + Mais filtros + Limpar */}
        <div className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:flex-none md:w-64">
            <i className="bi bi-search absolute left-3 top-2.5 text-slate-400 text-sm" />
            <input
              type="text"
              className="input-base pl-8 h-9"
              placeholder={t('common.search') || 'Buscar descrição...'}
              value={filters.search || ''}
              onChange={handleSearchChange}
            />
          </div>
          <button
            type="button"
            onClick={() => setShowMore((prev) => !prev)}
            className="h-9 px-3 text-xs font-medium text-slate-600 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-1"
          >
            <i className="bi bi-funnel" />
            Mais filtros
          </button>
          <button
            type="button"
            onClick={onClear}
            className="h-9 px-3 text-xs font-medium text-slate-600 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            {t('common.clear') || 'Limpar filtros'}
          </button>
        </div>
      </div>
      {showMore && (
        <div className="border-t border-slate-100 dark:border-slate-800 px-4 pb-4">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3 mt-3">
            {/* Valor mínimo */}
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">
                Valor mínimo
              </label>
              <input
                type="number"
                className="input-base h-9"
                value={filters.minAmount ?? ''}
                onChange={(e) =>
                  onChange({
                    minAmount: e.target.value ? Number(e.target.value) : undefined,
                    page: 1,
                  })
                }
              />
            </div>
            {/* Valor máximo */}
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">
                Valor máximo
              </label>
              <input
                type="number"
                className="input-base h-9"
                value={filters.maxAmount ?? ''}
                onChange={(e) =>
                  onChange({
                    maxAmount: e.target.value ? Number(e.target.value) : undefined,
                    page: 1,
                  })
                }
              />
            </div>
            {/* Status */}
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">
                Status
              </label>
              <select
                className="select-base h-9"
                value={filters.status || ''}
                onChange={(e) =>
                  onChange({
                    status: e.target.value || undefined,
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="paid">Pago</option>
                <option value="pending">Pendente</option>
                <option value="overdue">Atrasado</option>
                <option value="cancelled">Cancelado</option>
              </select>
            </div>
            {/* Método */}
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">
                Método
              </label>
              <select
                className="select-base h-9"
                value={filters.method || ''}
                onChange={(e) =>
                  onChange({
                    method: e.target.value || undefined,
                    page: 1,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="pix">Pix</option>
                <option value="card">Cartão</option>
                <option value="debit">Débito</option>
                <option value="transfer">Transferência</option>
                <option value="cash">Dinheiro</option>
              </select>
            </div>
            {/* Recorrente + Ordenação */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs font-medium text-secondary">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  checked={!!filters.isRecurring}
                  onChange={(e) =>
                    onChange({
                      isRecurring: e.target.checked || undefined,
                      page: 1,
                    })
                  }
                />
                Somente recorrentes
              </label>
              <div>
                <label className="block text-xs font-medium text-secondary mb-1">
                  Ordenação
                </label>
                <select
                  className="select-base h-9"
                  value={filters.sort}
                  onChange={(e) =>
                    onChange({
                      sort: e.target.value,
                    })
                  }
                >
                  <option value="date:desc">Data (mais recente)</option>
                  <option value="date:asc">Data (mais antiga)</option>
                  <option value="amount:desc">Valor (maior)</option>
                  <option value="amount:asc">Valor (menor)</option>
                  <option value="created_at:desc">Criação (mais recente)</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

