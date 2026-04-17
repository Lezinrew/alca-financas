import { FC } from 'react';
import { TransactionFilterState } from '../../hooks/useTransactionFilters';

interface QuickFiltersProps {
  filters: TransactionFilterState;
  onChange: (partial: Partial<TransactionFilterState>) => void;
}

export const QuickFilters: FC<QuickFiltersProps> = ({ filters, onChange }) => {
  const applyPreset = (preset: 'today' | '7d' | 'this_month') => {
    onChange({
      datePreset: preset,
      page: 1,
    });
  };

  const applyType = (type: 'income' | 'expense') => {
    // toggle: se já está único, limpa; senão, aplica só aquele
    const already =
      filters.types.length === 1 && filters.types[0] === type;
    onChange({
      types: already ? [] : [type],
      page: 1,
    });
  };

  const pillBase =
    'h-8 px-3 rounded-full text-xs font-medium border border-slate-200 dark:border-slate-700 transition-colors flex items-center gap-1';

  return (
    <div className="flex flex-wrap gap-2 mb-2">
      {/* Período rápido */}
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === 'today'
            ? ' bg-blue-600 text-white border-blue-600 dark:bg-blue-300 dark:text-slate-900 dark:border-blue-300'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700')
        }
        onClick={() => applyPreset('today')}
      >
        Hoje
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === '7d'
            ? ' bg-blue-600 text-white border-blue-600 dark:bg-blue-300 dark:text-slate-900 dark:border-blue-300'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700')
        }
        onClick={() => applyPreset('7d')}
      >
        7 dias
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === 'this_month'
            ? ' bg-blue-600 text-white border-blue-600 dark:bg-blue-300 dark:text-slate-900 dark:border-blue-300'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700')
        }
        onClick={() => applyPreset('this_month')}
      >
        Este mês
      </button>

      {/* Tipo rápido */}
      <button
        type="button"
        className={
          pillBase +
          (filters.types.includes('income')
            ? ' bg-emerald-500 text-white border-emerald-500 dark:bg-emerald-300 dark:text-slate-900 dark:border-emerald-300'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700')
        }
        onClick={() => applyType('income')}
      >
        + Receitas
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.types.includes('expense')
            ? ' bg-red-500 text-white border-red-500 dark:bg-red-300 dark:text-slate-900 dark:border-red-300'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700')
        }
        onClick={() => applyType('expense')}
      >
        − Despesas
      </button>

    </div>
  );
};

