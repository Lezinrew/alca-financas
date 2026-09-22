import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { KPICard } from './KPICard';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  CreditCard,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { formatCurrency, formatDate, dashboardAPI, accountsAPI } from '../../utils/api';
import { loadPayablesSummary, formatMonthLabel } from '../../utils/payablesSummary';
import { PayablesSummaryBlock } from '../shared/PayablesSummaryBlock';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';

// Custom tooltip for line chart
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="card-base p-3 shadow-modal">
        <p className="font-medium text-primary">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {formatCurrency(entry.value)}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// Custom tooltip for pie chart
const PieTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const pct = typeof data.percentage === 'number' ? data.percentage : Number(data.percentage) || 0;
    return (
      <div className="card-base p-3 shadow-modal">
        <p className="font-medium text-primary">{data.name}</p>
        <p className="text-sm text-tertiary">
          {formatCurrency(data.value)} ({pct.toFixed(1)}%)
        </p>
      </div>
    );
  }
  return null;
};

// Tipos locais
interface MonthlyData {
  month: string;
  income: number;
  expenses: number;
  net: number;
}

interface CategoryExpense {
  name: string;
  value: number;
  color: string;
  percentage: number;
}

interface RecentTransaction {
  id: string;
  description: string;
  amount: number;
  type: string;
  category: string;
  date: string;
}

interface DashboardView {
  income: number;
  expense: number;
  monthlyData: MonthlyData[];
  categories: CategoryExpense[];
  recentTransactions: RecentTransaction[];
}

const MONTH_NAMES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const isAccountActive = (acc: any) => acc?.is_active !== false && acc?.active !== false;

function mapDashboard(raw: any): DashboardView {
  return {
    income: raw?.summary?.total_income || 0,
    expense: raw?.summary?.total_expense || 0,
    monthlyData: (raw?.monthly_evolution || []).map((item: any) => ({
      month: MONTH_NAMES[new Date(item.year, item.month - 1, 1).getMonth()],
      income: item.income || 0,
      expenses: item.expense || 0,
      net: (item.income || 0) - (item.expense || 0),
    })),
    categories: (raw?.expense_by_category || []).map((item: any) => ({
      name: item.category_name || 'Sem categoria',
      value: item.total || 0,
      color: item.category_color || '#6b7280',
      percentage: item.percentage || 0,
    })),
    recentTransactions: (raw?.recent_transactions || []).map((tx: any) => ({
      id: tx.id || tx._id,
      description: tx.description,
      amount: tx.amount,
      type: tx.type,
      category: tx.category?.name || 'Sem categoria',
      date: tx.date,
    })),
  };
}

/** Texto de indisponibilidade com ação de retry, usado dentro de cada bloco. */
const Unavailable = ({ onRetry, className = '' }: { onRetry: () => void; className?: string }) => (
  <span role="alert" className={`inline-flex flex-wrap items-center gap-2 text-slate-700 dark:text-slate-200 ${className}`}>
    Indisponível.
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onRetry(); }}
      className="min-h-[32px] rounded-md border border-slate-300 px-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
    >
      Tentar novamente
    </button>
  </span>
);

const BlockSkeleton = ({ className }: { className: string }) => (
  <div role="status" aria-busy="true" aria-label="Carregando" className={`animate-pulse bg-slate-200 dark:bg-slate-700 rounded-xl ${className}`} />
);

const NEW_TRANSACTION_OPTIONS = [
  { type: 'expense', label: 'Despesa', hint: 'Nova despesa', icon: 'bi-arrow-down-circle', color: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400' },
  { type: 'income', label: 'Receita', hint: 'Nova receita', icon: 'bi-arrow-up-circle', color: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400' },
  { type: 'card_expense', label: 'Despesa de Cartão', hint: 'Nova despesa no cartão', icon: 'bi-credit-card', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' },
  { type: 'transfer', label: 'Transferência', hint: 'Transferir entre contas', icon: 'bi-arrow-left-right', color: 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400' },
] as const;

type NewTransactionType = (typeof NEW_TRANSACTION_OPTIONS)[number]['type'];

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [showNewMenu, setShowNewMenu] = useState(false);
  const fabRef = useRef<HTMLButtonElement>(null);
  const firstMenuItemRef = useRef<HTMLButtonElement>(null);

  // Mês exibido: fixado na montagem para que os três blocos usem a mesma competência.
  const [{ month, year }] = useState(() => {
    const now = new Date();
    return { month: now.getMonth() + 1, year: now.getFullYear() };
  });
  const [revision, setRevision] = useState(0);
  const retry = () => setRevision((r) => r + 1);

  const enabled = isAuthenticated && !authLoading;
  const key = `${year}-${month}:${revision}`;

  const dashboard = useKeyedRequest<any>(key, enabled, (signal) =>
    dashboardAPI.getAdvanced(month.toString(), year.toString(), true, { signal }),
  );
  const accounts = useKeyedRequest<any[]>(key, enabled, (signal) => accountsAPI.getAll({ signal }));
  const payables = useKeyedRequest(key, enabled, async (signal) => ({ data: await loadPayablesSummary(month, year, signal) }));

  const view = useMemo(() => (dashboard.data ? mapDashboard(dashboard.data) : null), [dashboard.data]);
  const accountsView = useMemo(() => {
    if (!accounts.data) return null;
    const list = Array.isArray(accounts.data) ? accounts.data : [];
    const active = list.filter(isAccountActive);
    return {
      totalBalance: active
        .filter((acc: any) => acc.type !== 'credit_card')
        .reduce((sum: number, acc: any) => sum + (acc.current_balance || 0), 0),
      creditCardCount: active.filter((acc: any) => acc.type === 'credit_card').length,
    };
  }, [accounts.data]);

  const monthLabel = formatMonthLabel(month, year);

  const handleNewTransaction = (type: NewTransactionType) => {
    setShowNewMenu(false);
    // Navega para a página de transações com o tipo pré-selecionado
    navigate('/transactions', {
      state: {
        openForm: true,
        transactionType: type === 'card_expense' ? 'expense' : type === 'transfer' ? 'expense' : type,
        isCardExpense: type === 'card_expense',
        isTransfer: type === 'transfer'
      }
    });
  };

  // Fecha o menu ao clicar fora ou com Escape; foco vai para o primeiro item ao abrir e volta ao botão ao fechar
  useEffect(() => {
    if (!showNewMenu) return;
    firstMenuItemRef.current?.focus();
    const handleClickOutside = (event: MouseEvent) => {
      if (!(event.target as HTMLElement).closest('.new-transaction-menu')) setShowNewMenu(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowNewMenu(false);
        fabRef.current?.focus();
      }
    };
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showNewMenu]);

  if (authLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-200 dark:bg-slate-700 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  const openTransactions = (filterType: 'income' | 'expense') =>
    navigate('/transactions', { state: { filterType, datePreset: 'this_month' } });

  const accountsNote = accounts.error
    ? <span role="alert" className="inline-flex flex-wrap items-center gap-2">Contas indisponíveis. <button type="button" onClick={(e) => { e.stopPropagation(); retry(); }} className="min-h-[32px] rounded-md border border-slate-300 px-2 text-sm font-medium dark:border-slate-600">Tentar novamente</button></span>
    : undefined;
  const dashboardNote = dashboard.error ? <Unavailable onRetry={retry} /> : undefined;
  const pending = '…';

  return (
    <div className="space-y-6 pb-40">
      {/* Botão Novo - Fixo no canto inferior direito (ajustado para não sobrepor o chatbot) */}
      <div className="fixed bottom-24 right-8 z-40 new-transaction-menu">
        <div className="relative">
          <button
            ref={fabRef}
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowNewMenu(!showNewMenu);
            }}
            className="w-16 h-16 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all transform hover:scale-110"
            aria-label="Nova transação"
            aria-haspopup="menu"
            aria-expanded={showNewMenu}
          >
            <i className="bi bi-plus-lg text-2xl"></i>
          </button>

          {showNewMenu && (
            <div role="menu" aria-label="Nova transação" className="dropdown-menu absolute bottom-full right-0 mb-3 w-56 py-2 z-50">
              {NEW_TRANSACTION_OPTIONS.map((option, index) => (
                <button
                  key={option.type}
                  ref={index === 0 ? firstMenuItemRef : undefined}
                  type="button"
                  role="menuitem"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleNewTransaction(option.type);
                  }}
                  className="w-full text-left px-4 py-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-3 transition-colors"
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${option.color}`}>
                    <i className={`bi ${option.icon} text-lg`}></i>
                  </div>
                  <div>
                    <div className="font-medium">{option.label}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">{option.hint}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Saldo hoje (contas)"
          value={accounts.error ? '—' : accountsView ? formatCurrency(accountsView.totalBalance) : pending}
          note={accountsNote}
          icon={Wallet}
          variant="primary"
          onClick={() => navigate('/accounts')}
        />
        <KPICard
          title={`Receitas · ${monthLabel}`}
          value={dashboard.error ? '—' : view ? formatCurrency(view.income) : pending}
          note={dashboardNote}
          icon={TrendingUp}
          variant="success"
          onClick={() => openTransactions('income')}
        />
        <KPICard
          title={`Despesas · ${monthLabel}`}
          value={dashboard.error ? '—' : view ? formatCurrency(view.expense) : pending}
          note={dashboardNote}
          icon={TrendingDown}
          variant="danger"
          onClick={() => openTransactions('expense')}
        />
        <KPICard
          title="Cartões de crédito"
          value={accounts.error ? '—' : accountsView ? String(accountsView.creditCardCount) : pending}
          note={accountsNote}
          icon={CreditCard}
          variant="warning"
          onClick={() => navigate('/credit-cards')}
        />
      </div>

      <PayablesSummaryBlock summary={payables.data} loading={payables.loading} onRetry={retry} titleId="dashboard-payables-title" />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Line Chart - Income vs Expenses */}
        <div className="card-base p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Receitas vs. Despesas</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Últimos 12 meses</p>
          </div>
          <div>
            {dashboard.loading ? (
              <BlockSkeleton className="h-80" />
            ) : dashboard.error || !view ? (
              <div className="h-80 flex items-center justify-center"><Unavailable onRetry={retry} /></div>
            ) : view.monthlyData.length === 0 ? (
              <div className="h-80 flex items-center justify-center">
                <div className="text-center">
                  <i className="bi bi-graph-up text-4xl text-slate-300 dark:text-slate-600 mb-3 block"></i>
                  <p className="text-slate-500 dark:text-slate-400">Nenhum dado disponível</p>
                  <p className="text-sm text-slate-400 dark:text-slate-500">Adicione transações para visualizar</p>
                </div>
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={view.monthlyData}>
                    <defs>
                      <linearGradient id="income" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="expenses" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-slate-700" />
                    <XAxis
                      dataKey="month"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: '#64748b' }}
                      className="dark:[&_text]:fill-slate-400"
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: '#64748b' }}
                      tickFormatter={(value) => `R$ ${(value / 1000).toFixed(0)}k`}
                      className="dark:[&_text]:fill-slate-400"
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend formatter={(value) => <span className="text-sm text-slate-700 dark:text-slate-300">{value}</span>} />
                    <Area
                      type="monotone"
                      dataKey="income"
                      stroke="#10b981"
                      strokeWidth={2}
                      fill="url(#income)"
                      name="Receitas"
                    />
                    <Area
                      type="monotone"
                      dataKey="expenses"
                      stroke="#ef4444"
                      strokeWidth={2}
                      fill="url(#expenses)"
                      name="Despesas"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* Pie Chart - Category Distribution */}
        <div className="card-base p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Gastos por Categoria</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Distribuição das despesas</p>
          </div>
          <div>
            {dashboard.loading ? (
              <BlockSkeleton className="h-80" />
            ) : dashboard.error || !view ? (
              <div className="h-80 flex items-center justify-center"><Unavailable onRetry={retry} /></div>
            ) : view.categories.length === 0 ? (
              <div className="h-80 flex items-center justify-center">
                <div className="text-center">
                  <i className="bi bi-pie-chart text-4xl text-slate-300 dark:text-slate-600 mb-3 block"></i>
                  <p className="text-slate-500 dark:text-slate-400">Nenhuma categoria disponível</p>
                  <p className="text-sm text-slate-400 dark:text-slate-500">Adicione categorias e transações para visualizar</p>
                </div>
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={view.categories}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={120}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {view.categories.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      formatter={(value, entry: any) => (
                        <span className="text-sm text-slate-700 dark:text-slate-300">
                          {value} ({Number(entry?.payload?.percentage ?? 0).toFixed(1)}%)
                        </span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="card-base p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Transações Recentes</h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">Últimas movimentações da conta</p>
        </div>
        <div>
          {dashboard.loading ? (
            <BlockSkeleton className="h-40" />
          ) : dashboard.error || !view ? (
            <div className="py-6 flex justify-center"><Unavailable onRetry={retry} /></div>
          ) : view.recentTransactions.length === 0 ? (
            <p className="py-6 text-center text-slate-500 dark:text-slate-400">Nenhuma transação recente</p>
          ) : (
            <div className="space-y-2">
              {view.recentTransactions.slice(0, 5).map((transaction) => (
                <div key={transaction.id} className="flex items-center justify-between p-4 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      transaction.type === 'income' ? 'bg-emerald-50 dark:bg-emerald-900/30' : 'bg-red-50 dark:bg-red-900/30'
                    }`}>
                      {transaction.type === 'income' ? (
                        <TrendingUp className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                      ) : (
                        <TrendingDown className="w-5 h-5 text-red-600 dark:text-red-400" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-slate-900 dark:text-slate-100">{transaction.description}</p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {transaction.category} • {formatDate(transaction.date)}
                      </p>
                    </div>
                  </div>
                  <div className={`text-lg font-semibold ${
                    transaction.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                  }`}>
                    {transaction.type === 'income' ? '+' : '-'}{formatCurrency(Math.abs(Number(transaction.amount) || 0))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
