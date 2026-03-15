import React from 'react';
import { formatCurrency } from '../../utils/api';
import type { PlanningSummary } from '../../utils/api';

const MONTH_LABELS = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
];

interface PlanningMonthOverviewProps {
  summary: PlanningSummary;
  month: number;
  year: number;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onOpenForm: () => void;
}

const cardClasses = 'card-base p-5 space-y-2';

export const PlanningMonthOverview: React.FC<PlanningMonthOverviewProps> = ({
  summary,
  month,
  year,
  onPrevMonth,
  onNextMonth,
  onOpenForm,
}) => {
  const cards = [
    { label: 'Receita planejada', value: formatCurrency(summary.planned_income), sub: 'Meta do mês', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: 'bi-flag' },
    { label: 'Despesas planejadas', value: formatCurrency(summary.planned_expenses), sub: 'Limite total', color: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-100 dark:bg-orange-900/30', icon: 'bi-list-check' },
    { label: 'Saldo planejado', value: formatCurrency(summary.planned_balance), sub: 'Receita - Despesas', color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-100 dark:bg-indigo-900/30', icon: 'bi-graph-up' },
    { label: 'Receita real', value: formatCurrency(summary.real_income), sub: 'Transações do mês', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: 'bi-cash-stack' },
    { label: 'Despesas reais', value: formatCurrency(summary.real_expenses), sub: 'Somatório saídas', color: 'text-red-600 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30', icon: 'bi-credit-card-2-back' },
    { label: 'Saldo real', value: formatCurrency(summary.real_balance), sub: 'Receita - Despesas', color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-100 dark:bg-blue-900/30', icon: 'bi-activity' },
    { label: 'Taxa de economia', value: `${summary.savings_rate.toFixed(1)}%`, sub: 'Percentual economizado', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: 'bi-piggy-bank' },
  ];

  return (
    <div className="space-y-4">
      <div className="card-base p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onPrevMonth}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Mês anterior"
          >
            <i className="bi bi-chevron-left" />
          </button>
          <span className="px-4 py-2 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-sm font-medium">
            {MONTH_LABELS[month - 1]} {year}
          </span>
          <button
            type="button"
            onClick={onNextMonth}
            className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Próximo mês"
          >
            <i className="bi bi-chevron-right" />
          </button>
        </div>
        <button
          type="button"
          onClick={onOpenForm}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <i className="bi bi-pencil" />
          Definir planejamento
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {cards.map((card, i) => (
          <div key={i} className={cardClasses}>
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                {card.label}
              </p>
              <div className={`w-10 h-10 ${card.bg} rounded-full flex items-center justify-center flex-shrink-0`}>
                <i className={`bi ${card.icon} ${card.color} text-base`} />
              </div>
            </div>
            {card.sub && <p className="text-xs text-slate-500 dark:text-slate-400">{card.sub}</p>}
            <p className={`text-xl font-bold text-slate-900 dark:text-white ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PlanningMonthOverview;
