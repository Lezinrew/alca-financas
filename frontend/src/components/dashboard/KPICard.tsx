import type { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string;
  /** Variação vs. mês anterior. Omitida quando não há comparação real. */
  change?: number;
  changeType?: 'increase' | 'decrease';
  icon: LucideIcon;
  variant: 'primary' | 'success' | 'danger' | 'warning';
  onClick?: () => void;
  /** Texto auxiliar abaixo do valor (escopo, indisponibilidade, ação de retry). */
  note?: ReactNode;
}

const variantStyles = {
  primary: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300',
  success: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300',
  danger: 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-300',
  warning: 'bg-orange-50 text-orange-600 dark:bg-orange-900/30 dark:text-orange-300'
};

export const KPICard = ({ title, value, change, changeType = 'increase', icon: Icon, variant, onClick, note }: KPICardProps) => {
  const isPositive = changeType === 'increase';

  return (
    <div
      className={`card-base p-6 transition-all ${
        onClick ? 'cursor-pointer hover:shadow-md hover:scale-[1.02]' : 'hover:shadow-md'
      }`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">{title}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mb-1">{value}</p>
          {note !== undefined && <div className="text-sm text-slate-600 dark:text-slate-300">{note}</div>}
          {change !== undefined && (
            <div className="flex items-center text-sm mt-2">
              {isPositive ? (
                <ArrowUpRight className="w-4 h-4 text-emerald-600 dark:text-emerald-400 mr-1" />
              ) : (
                <ArrowDownRight className="w-4 h-4 text-red-600 dark:text-red-400 mr-1" />
              )}
              <span className={isPositive ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                {Math.abs(change).toFixed(1)}%
              </span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">vs mês anterior</span>
            </div>
          )}
        </div>
        <div className={`w-12 h-12 rounded-xl ${variantStyles[variant]} flex items-center justify-center flex-shrink-0`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
};
