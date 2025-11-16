import { LucideIcon } from 'lucide-react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string;
  change: number;
  changeType: 'increase' | 'decrease';
  icon: LucideIcon;
  variant: 'primary' | 'success' | 'danger' | 'warning';
  onClick?: () => void;
}

const variantStyles = {
  primary: 'bg-blue-50 text-blue-600',
  success: 'bg-emerald-50 text-emerald-600',
  danger: 'bg-red-50 text-red-600',
  warning: 'bg-orange-50 text-orange-600'
};

export const KPICard = ({ title, value, change, changeType, icon: Icon, variant, onClick }: KPICardProps) => {
  const isPositive = changeType === 'increase';

  return (
    <div 
      className={`card-base p-6 transition-all ${
        onClick ? 'cursor-pointer hover:shadow-md hover:scale-[1.02]' : 'hover:shadow-md'
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">{title}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mb-3">{value}</p>
          <div className="flex items-center text-sm">
            {isPositive ? (
              <ArrowUpRight className="w-4 h-4 text-emerald-600 mr-1" />
            ) : (
              <ArrowDownRight className="w-4 h-4 text-red-600 mr-1" />
            )}
            <span className={isPositive ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>
              {Math.abs(change).toFixed(1)}%
            </span>
            <span className="text-slate-500 dark:text-slate-400 ml-1">vs mês anterior</span>
          </div>
        </div>
        <div className={`w-12 h-12 rounded-xl ${variantStyles[variant]} flex items-center justify-center flex-shrink-0`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
};
