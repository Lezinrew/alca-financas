import { FC } from 'react';
import { TransactionFilterState } from '../../hooks/useTransactionFilters';

interface FilterChipsBarProps {
  filters: TransactionFilterState;
  onChange: (partial: Partial<TransactionFilterState>) => void;
  onClear: () => void;
  total?: number;
}

export const FilterChipsBar: FC<FilterChipsBarProps> = ({
  filters,
  onChange,
  onClear,
  total,
}) => {
  const chips: Array<{ label: string; onRemove: () => void }> = [];

  if (filters.accountIds.length) {
    chips.push({
      label: `Conta: ${filters.accountIds.length} selecionada(s)`,
      onRemove: () => onChange({ accountIds: [], page: 1 }),
    });
  }

  if (filters.categoryIds.length) {
    chips.push({
      label: `Categoria: ${filters.categoryIds.length} selecionada(s)`,
      onRemove: () => onChange({ categoryIds: [], page: 1 }),
    });
  }

  if (filters.types.length) {
    const names = filters.types
      .map((t) => (t === 'income' ? 'Receita' : t === 'expense' ? 'Despesa' : 'Transferência'))
      .join(', ');
    chips.push({
      label: `Tipo: ${names}`,
      onRemove: () => onChange({ types: [], page: 1 }),
    });
  }

  if (filters.minAmount != null || filters.maxAmount != null) {
    const from = filters.minAmount != null ? `R$ ${filters.minAmount}` : '';
    const to = filters.maxAmount != null ? `R$ ${filters.maxAmount}` : '';
    chips.push({
      label: `Valor: ${from} – ${to}`.trim(),
      onRemove: () => onChange({ minAmount: undefined, maxAmount: undefined, page: 1 }),
    });
  }

  if (filters.search) {
    chips.push({
      label: `Busca: "${filters.search}"`,
      onRemove: () => onChange({ search: undefined, page: 1 }),
    });
  }

  if (filters.status) {
    chips.push({
      label: `Status: ${filters.status}`,
      onRemove: () => onChange({ status: undefined, page: 1 }),
    });
  }

  if (filters.method) {
    chips.push({
      label: `Método: ${filters.method}`,
      onRemove: () => onChange({ method: undefined, page: 1 }),
    });
  }

  if (filters.isRecurring) {
    chips.push({
      label: 'Recorrente',
      onRemove: () => onChange({ isRecurring: undefined, page: 1 }),
    });
  }

  if (!chips.length && typeof total !== 'number') {
    return null;
  }

  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-3">
      <div className="flex flex-wrap gap-2">
        {chips.map((chip, idx) => (
          <button
            key={idx}
            type="button"
            className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
            onClick={chip.onRemove}
          >
            <span>{chip.label}</span>
            <i className="bi bi-x-lg text-[10px]" />
          </button>
        ))}
        {chips.length > 0 && (
          <button
            type="button"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline ml-1"
            onClick={onClear}
          >
            Limpar tudo
          </button>
        )}
      </div>
      {typeof total === 'number' && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          {total === 0
            ? 'Nenhuma transação encontrada'
            : `${total} transação${total === 1 ? '' : 's'} encontradas`}
        </div>
      )}
    </div>
  );
};

