import React from 'react';
import { formatCurrency } from '../../utils/api';
import type { PlanningAlert } from '../../utils/api';

const ALERT_CONFIG: Record<string, { icon: string; label: string; bg: string; text: string }> = {
  unplanned_expense: {
    icon: 'bi-exclamation-triangle',
    label: 'Gasto sem orçamento',
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-800 dark:text-amber-200',
  },
  above_budget: {
    icon: 'bi-graph-up-arrow',
    label: 'Acima do orçamento',
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-800 dark:text-red-200',
  },
  close_to_limit: {
    icon: 'bi-lightning',
    label: 'Perto do limite',
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-800 dark:text-amber-200',
  },
};

interface PlanningAlertsProps {
  alerts: PlanningAlert[];
}

export const PlanningAlerts: React.FC<PlanningAlertsProps> = ({ alerts }) => {
  if (alerts.length === 0) {
    return (
      <div className="card-base p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Alertas e insights</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm">Nenhum alerta neste mês.</p>
      </div>
    );
  }

  return (
    <div className="card-base overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Alertas e insights</h2>
      </div>
      <ul className="divide-y divide-slate-200 dark:divide-slate-700/50">
        {alerts.map((alert, i) => {
          const config = ALERT_CONFIG[alert.type] || {
            icon: 'bi-info-circle',
            label: alert.type,
            bg: 'bg-slate-100 dark:bg-slate-800',
            text: 'text-slate-800 dark:text-slate-200',
          };
          return (
            <li key={`${alert.category_id}-${i}`} className={`px-6 py-4 flex items-center gap-3 ${config.bg}`}>
              <i className={`bi ${config.icon} text-xl ${config.text} flex-shrink-0`} />
              <div className="flex-1 min-w-0">
                <p className={`font-medium ${config.text}`}>{config.label}</p>
                <p className="text-sm text-slate-600 dark:text-slate-400 truncate">{alert.category_name}</p>
              </div>
              {alert.spent_amount != null && (
                <span className={`font-semibold ${config.text} flex-shrink-0`}>
                  {formatCurrency(alert.spent_amount)}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default PlanningAlerts;
