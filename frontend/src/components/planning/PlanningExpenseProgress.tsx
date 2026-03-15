import React from 'react';
import { formatCurrency } from '../../utils/api';
import type { PlanningExpenseCategory } from '../../utils/api';

const STATUS_CONFIG: Record<PlanningExpenseCategory['status'], { label: string; color: string; bar: string }> = {
  safe: { label: 'Dentro do orçamento', color: 'text-emerald-600 dark:text-emerald-400', bar: 'bg-emerald-500' },
  warning: { label: 'Atenção', color: 'text-amber-600 dark:text-amber-400', bar: 'bg-amber-500' },
  exceeded: { label: 'Acima do orçamento', color: 'text-red-600 dark:text-red-400', bar: 'bg-red-500' },
  unplanned: { label: 'Gasto sem orçamento', color: 'text-slate-600 dark:text-slate-400', bar: 'bg-slate-500' },
};

interface PlanningExpenseProgressProps {
  categories: PlanningExpenseCategory[];
  onEdit?: () => void;
}

export const PlanningExpenseProgress: React.FC<PlanningExpenseProgressProps> = ({ categories, onEdit }) => {
  if (categories.length === 0) {
    return (
      <div className="card-base p-8 text-center">
        <i className="bi bi-credit-card-2-back text-4xl text-slate-400 dark:text-slate-500 mb-3 block" />
        <p className="text-slate-600 dark:text-slate-400">Nenhuma categoria de despesa com orçamento neste mês.</p>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="mt-4 px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium"
          >
            Definir orçamento de despesas
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="card-base overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Despesas por categoria</h2>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="text-sm text-purple-600 dark:text-purple-400 hover:underline"
          >
            Editar
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-800/50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Categoria</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Planejado</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Gasto</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Restante</th>
              <th className="px-6 py-3 text-center text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Progresso</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
            {categories.map((cat) => {
              const config = STATUS_CONFIG[cat.status];
              const progressPct = Math.min(cat.progress_percent, 100);
              return (
                <tr key={cat.category_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0"
                        style={{ backgroundColor: cat.category_color || '#6b7280' }}
                      >
                        <i className={`bi bi-${cat.category_icon || 'circle'} text-base`} />
                      </div>
                      <span className="font-medium text-slate-900 dark:text-white">{cat.category_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                    {formatCurrency(cat.planned_amount)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-medium text-slate-900 dark:text-white">
                    {formatCurrency(cat.spent_amount)}
                  </td>
                  <td className="px-6 py-4 text-right text-sm text-slate-700 dark:text-slate-300">
                    {formatCurrency(cat.remaining_amount)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden min-w-[80px]">
                        <div
                          className={`h-full ${config.bar} rounded-full transition-all`}
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-slate-600 dark:text-slate-400 w-10 text-right">
                        {cat.planned_amount > 0 ? cat.progress_percent.toFixed(0) : '—'}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-medium ${config.color}`}>{config.label}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PlanningExpenseProgress;
