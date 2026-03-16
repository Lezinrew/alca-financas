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

  const applyMethod = (method: string) => {
    const already = filters.method === method;
    onChange({
      method: already ? undefined : method,
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
            ? ' bg-blue-600 text-white border-blue-600'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
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
            ? ' bg-blue-600 text-white border-blue-600'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
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
            ? ' bg-blue-600 text-white border-blue-600'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
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
            ? ' bg-emerald-500 text-white border-emerald-500'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
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
            ? ' bg-red-500 text-white border-red-500'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
        }
        onClick={() => applyType('expense')}
      >
        − Despesas
      </button>

      {/* Método rápido */}
      <button
        type="button"
        className={
          pillBase +
          (filters.method === 'pix'
            ? ' bg-violet-500 text-white border-violet-500'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
        }
        onClick={() => applyMethod('pix')}
      >
        Pix
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.method === 'card'
            ? ' bg-indigo-500 text-white border-indigo-500'
            : ' bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800')
        }
        onClick={() => applyMethod('card')}
      >
        Cartão
      </button>
    </div>
  );
};

