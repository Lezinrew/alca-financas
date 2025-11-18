import React from 'react';
import { formatCurrency } from '../../utils/api';

interface Budget {
  monthly_income: number;
  savings_percentage: number;
  category_budgets?: Array<{ category_id: string; amount: number }>;
}

interface ActualSummary {
  totalIncome: number;
  totalExpenses: number;
  balance: number;
  savingsRate: number;
}

interface PlanningSummaryProps {
  budget: Budget | null;
  actuals: ActualSummary;
}

const PlanningSummary: React.FC<PlanningSummaryProps> = ({ budget, actuals }) => {
  const monthlyIncome = budget?.monthly_income || 0;
  const savingsPercentage = budget?.savings_percentage || 0;
  const plannedExpenses = budget?.category_budgets?.reduce((sum, cb) => sum + (cb.amount || 0), 0) || 0;
  const plannedSavings = (monthlyIncome * savingsPercentage) / 100;
  const plannedBalance = monthlyIncome - plannedExpenses - plannedSavings;
  const savingsPercentageDisplay = savingsPercentage || 0;

  const actualCards = [
    {
      title: 'Receitas reais',
      value: formatCurrency(actuals.totalIncome),
      subtitle: 'Com base nas transações do mês',
      icon: 'bi-cash-stack',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30'
    },
    {
      title: 'Despesas reais',
      value: formatCurrency(actuals.totalExpenses),
      subtitle: 'Somatório das saídas do período',
      icon: 'bi-credit-card-2-back',
      iconColor: 'text-red-600 dark:text-red-400',
      bgColor: 'bg-red-100 dark:bg-red-900/30'
    },
    {
      title: 'Balanço real',
      value: formatCurrency(actuals.balance),
      subtitle: 'Receitas - Despesas',
      icon: 'bi-activity',
      iconColor: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-100 dark:bg-blue-900/30'
    },
    {
      title: 'Taxa de economia real',
      value: `${actuals.savingsRate.toFixed(2)}%`,
      subtitle: 'Percentual economizado',
      icon: 'bi-piggy-bank',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30'
    }
  ];

  const plannedCards = [
    {
      title: 'Receitas planejadas',
      value: formatCurrency(monthlyIncome),
      subtitle: 'Metas definidas no planejamento',
      icon: 'bi-flag',
      iconColor: 'text-purple-600 dark:text-purple-400',
      bgColor: 'bg-purple-100 dark:bg-purple-900/30'
    },
    {
      title: 'Gastos planejados',
      value: formatCurrency(plannedExpenses),
      subtitle: 'Limites por categoria',
      icon: 'bi-list-check',
      iconColor: 'text-orange-600 dark:text-orange-400',
      bgColor: 'bg-orange-100 dark:bg-orange-900/30'
    },
    {
      title: 'Balanço planejado',
      value: formatCurrency(plannedBalance),
      subtitle: 'Receitas - Gastos - Economia',
      icon: 'bi-scale',
      iconColor: 'text-indigo-600 dark:text-indigo-400',
      bgColor: 'bg-indigo-100 dark:bg-indigo-900/30'
    },
    {
      title: 'Economia planejada',
      value: `${savingsPercentageDisplay.toFixed(2)}%`,
      subtitle: 'Meta definida por você',
      icon: 'bi-wallet2',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30'
    }
  ];

  const cards = [
    ...actualCards.map(card => ({ ...card, badge: 'Real' })),
    ...plannedCards.map(card => ({ ...card, badge: 'Planejado' }))
  ];

  return (
    <>
      {cards.map((card, index) => (
        <div
          key={index}
          className="card-base p-5 space-y-2"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                {card.title}
              </p>
              {card.subtitle && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{card.subtitle}</p>
              )}
            </div>
            <div className={`w-10 h-10 ${card.bgColor} rounded-full flex items-center justify-center flex-shrink-0`}>
              <i className={`bi ${card.icon} ${card.iconColor} text-base`}></i>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{card.value}</p>
            <span className="text-xs font-semibold px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-200">
              {card.badge}
            </span>
          </div>
        </div>
      ))}
    </>
  );
};

export default PlanningSummary;

