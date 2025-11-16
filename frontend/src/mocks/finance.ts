import { format, subMonths, eachMonthOfInterval, startOfMonth } from 'date-fns';

export interface FinanceKPI {
  title: string;
  value: number;
  change: number;
  changeType: 'increase' | 'decrease';
  icon: string;
}

export interface MonthlyData {
  month: string;
  income: number;
  expenses: number;
  net: number;
}

export interface CategoryExpense {
  name: string;
  value: number;
  color: string;
  percentage: number;
}

export interface Transaction {
  id: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  category: string;
  date: Date;
}

// Utility function for stable random numbers (seeded)
const seededRandom = (seed: number) => {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

// Generate consistent mock data
export const generateFinancialData = () => {
  const currentDate = new Date();
  const last12Months = eachMonthOfInterval({
    start: subMonths(currentDate, 11),
    end: currentDate,
  });

  // KPIs
  const currentBalance = 25847.32;
  const monthlyIncome = 8500.00;
  const monthlyExpenses = 6234.56;
  const creditCards = 2;

  const kpis: FinanceKPI[] = [
    {
      title: 'Saldo Atual',
      value: currentBalance,
      change: 12.5,
      changeType: 'increase',
      icon: 'wallet',
    },
    {
      title: 'Receitas',
      value: monthlyIncome,
      change: 8.2,
      changeType: 'increase',
      icon: 'trending-up',
    },
    {
      title: 'Despesas',
      value: monthlyExpenses,
      change: -3.1,
      changeType: 'decrease',
      icon: 'trending-down',
    },
    {
      title: 'Cartões de Crédito',
      value: creditCards,
      change: 0,
      changeType: 'increase',
      icon: 'credit-card',
    },
  ];

  // Monthly data for line chart
  const monthlyData: MonthlyData[] = last12Months.map((month, index) => {
    const baseIncome = 8000;
    const baseExpenses = 6000;
    const seed = index + 1;
    
    const income = baseIncome + (seededRandom(seed * 7) * 2000 - 1000);
    const expenses = baseExpenses + (seededRandom(seed * 11) * 1500 - 750);
    
    return {
      month: format(month, 'MMM'),
      income: Math.round(income),
      expenses: Math.round(expenses),
      net: Math.round(income - expenses),
    };
  });

  // Category expenses for pie chart
  const categories: CategoryExpense[] = [
    { name: 'Alimentação', value: 1850.00, color: '#ef4444', percentage: 29.7 },
    { name: 'Transporte', value: 980.50, color: '#f97316', percentage: 15.7 },
    { name: 'Moradia', value: 2100.00, color: '#eab308', percentage: 33.7 },
    { name: 'Saúde', value: 450.75, color: '#22c55e', percentage: 7.2 },
    { name: 'Educação', value: 320.00, color: '#3b82f6', percentage: 5.1 },
    { name: 'Entretenimento', value: 533.31, color: '#8b5cf6', percentage: 8.6 },
  ];

  // Recent transactions
  const transactionTemplates = [
    { description: 'Salário', type: 'income' as const, category: 'Salário' },
    { description: 'Supermercado Extra', type: 'expense' as const, category: 'Alimentação' },
    { description: 'Uber', type: 'expense' as const, category: 'Transporte' },
    { description: 'Aluguel', type: 'expense' as const, category: 'Moradia' },
    { description: 'Freelance Design', type: 'income' as const, category: 'Trabalho' },
    { description: 'Academia', type: 'expense' as const, category: 'Saúde' },
    { description: 'Netflix', type: 'expense' as const, category: 'Entretenimento' },
    { description: 'Dividendos', type: 'income' as const, category: 'Investimentos' },
    { description: 'Farmácia', type: 'expense' as const, category: 'Saúde' },
    { description: 'Gasolina', type: 'expense' as const, category: 'Transporte' },
  ];

  const recentTransactions: Transaction[] = transactionTemplates.map((template, index) => {
    const seed = index + 100;
    const daysAgo = Math.floor(seededRandom(seed) * 30);
    const baseAmount = template.type === 'income' ? 2000 : 150;
    const amount = baseAmount + (seededRandom(seed * 13) * baseAmount * 0.8);
    
    return {
      id: `tx-${index + 1}`,
      description: template.description,
      amount: Math.round(amount * 100) / 100,
      type: template.type,
      category: template.category,
      date: new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000),
    };
  }).sort((a, b) => b.date.getTime() - a.date.getTime());

  return {
    kpis,
    monthlyData,
    categories,
    recentTransactions,
  };
};

// Helper functions for formatting
export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

export const formatNumber = (value: number): string => {
  return new Intl.NumberFormat('pt-BR').format(value);
};

export const formatPercent = (value: number): string => {
  const signal = value >= 0 ? '+' : '';
  return `${signal}${value.toFixed(1)}%`;
};