import React from 'react';
import { formatCurrency } from '../../utils/api';

interface Budget {
  monthly_income: number;
  savings_percentage: number;
  category_budgets?: Array<{ category_id: string; amount: number }>;
}

interface PlanningSummaryProps {
  budget: Budget | null;
}

const PlanningSummary: React.FC<PlanningSummaryProps> = ({ budget }) => {
  const monthlyIncome = budget?.monthly_income || 0;
  const savingsPercentage = budget?.savings_percentage || 0;
  const plannedExpenses = budget?.category_budgets?.reduce((sum, cb) => sum + (cb.amount || 0), 0) || 0;
  const plannedSavings = (monthlyIncome * savingsPercentage) / 100;
  const plannedBalance = monthlyIncome - plannedExpenses - plannedSavings;
  const savingsPercentageDisplay = savingsPercentage || 0;

  const summaryCards = [
    {
      title: 'Receitas do mês',
      value: formatCurrency(monthlyIncome),
      icon: 'bi-arrow-up-circle',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30'
    },
    {
      title: 'Gastos planejados',
      value: formatCurrency(plannedExpenses),
      icon: 'bi-arrow-down-circle',
      iconColor: 'text-red-600 dark:text-red-400',
      bgColor: 'bg-red-100 dark:bg-red-900/30'
    },
    {
      title: 'Balanço planejado',
      value: formatCurrency(plannedBalance),
      icon: 'bi-scale',
      iconColor: 'text-purple-600 dark:text-purple-400',
      bgColor: 'bg-purple-100 dark:bg-purple-900/30'
    },
    {
      title: 'Economia planejada',
      value: `${savingsPercentageDisplay.toFixed(2)}%`,
      icon: 'bi-wallet2',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30'
    }
  ];

  return (
    <>
      {summaryCards.map((card, index) => (
        <div
          key={index}
          className="card-base p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
              {card.title}
            </p>
            <div className={`w-10 h-10 ${card.bgColor} rounded-full flex items-center justify-center flex-shrink-0`}>
              <i className={`bi ${card.icon} ${card.iconColor} text-base`}></i>
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{card.value}</p>
        </div>
      ))}
    </>
  );
};

export default PlanningSummary;

