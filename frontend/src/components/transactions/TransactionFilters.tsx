import { FC } from 'react';
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
    onChange({ search: e.target.value || undefined, page: 1 });
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

          {/* Conta */}
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

        {/* Search + Limpar */}
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
            onClick={onClear}
            className="h-9 px-3 text-xs font-medium text-slate-600 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            {t('common.clear') || 'Limpar filtros'}
          </button>
        </div>
      </div>
    </div>
  );
};

