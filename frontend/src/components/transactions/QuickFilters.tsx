import { FC } from 'react';
import { TransactionFilterState } from '../../hooks/useTransactionFilters';

interface QuickFiltersProps {
  filters: TransactionFilterState;
  onChange: (partial: Partial<TransactionFilterState>) => void;
}

export const QuickFilters: FC<QuickFiltersProps> = ({ filters, onChange }) => {
  const applyPreset = (preset: 'today' | '7d' | 'year_to_date' | 'this_month') => {
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
  const inactivePill =
    ' bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-white dark:hover:bg-slate-600';
  const activeDatePill =
    ' bg-blue-600 text-white border-blue-600 dark:bg-blue-400 dark:text-slate-900 dark:border-blue-400';
  const activeIncomePill =
    ' bg-emerald-500 text-white border-emerald-500 dark:bg-emerald-400 dark:text-slate-900 dark:border-emerald-400';
  const activeExpensePill =
    ' bg-red-500 text-white border-red-500 dark:bg-red-400 dark:text-slate-900 dark:border-red-400';

  return (
    <div className="flex flex-wrap gap-2 mb-2">
      {/* Período rápido */}
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === 'today'
            ? activeDatePill
            : inactivePill)
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
            ? activeDatePill
            : inactivePill)
        }
        onClick={() => applyPreset('7d')}
      >
        7 dias
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === 'year_to_date'
            ? activeDatePill
            : inactivePill)
        }
        onClick={() => applyPreset('year_to_date')}
      >
        Ano atual
      </button>
      <button
        type="button"
        className={
          pillBase +
          (filters.datePreset === 'this_month'
            ? activeDatePill
            : inactivePill)
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
            ? activeIncomePill
            : inactivePill)
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
            ? activeExpensePill
            : inactivePill)
        }
        onClick={() => applyType('expense')}
      >
        − Despesas
      </button>

    </div>
  );
};

