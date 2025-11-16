import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  LineChart,
  Line,
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
import { formatCurrency, formatPercent, dashboardAPI } from '../../utils/api';

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
    return (
      <div className="card-base p-3 shadow-modal">
        <p className="font-medium text-primary">{data.name}</p>
        <p className="text-sm text-tertiary">
          {formatCurrency(data.value)} ({data.percentage.toFixed(1)}%)
        </p>
      </div>
    );
  }
  return null;
};

const iconMap = {
  wallet: Wallet,
  'trending-up': TrendingUp,
  'trending-down': TrendingDown,
  'credit-card': CreditCard,
};

const variantMap = ['primary', 'success', 'danger', 'warning'] as const;

// Tipos locais
interface FinanceKPI {
  title: string;
  value: number;
  change: number;
  changeType: 'increase' | 'decrease';
  icon: string;
}

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

const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [showNewMenu, setShowNewMenu] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [financeData, setFinanceData] = useState<{
    kpis: FinanceKPI[];
    monthlyData: MonthlyData[];
    categories: CategoryExpense[];
    recentTransactions: any[];
  } | null>(null);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadDashboardData();
    }
  }, [isAuthenticated, authLoading]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError('');
      
      const currentDate = new Date();
      const month = currentDate.getMonth() + 1;
      const year = currentDate.getFullYear();

      // Busca dados do dashboard avançado (inclui evolução mensal)
      const [dashboardRes, accountsRes] = await Promise.all([
        dashboardAPI.getAdvanced(month.toString(), year.toString(), true),
        fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/api/accounts`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        }).then(res => res.ok ? res.json() : [])
      ]);

      const dashboardData = dashboardRes.data;
      const accounts = Array.isArray(accountsRes) ? accountsRes : [];

      // Calcula saldo total das contas ativas
      const totalBalance = accounts
        .filter((acc: any) => acc.is_active)
        .reduce((sum: number, acc: any) => sum + (acc.current_balance || 0), 0);

      // Calcula variação de receitas e despesas (comparando com mês anterior)
      const currentIncome = dashboardData.summary?.total_income || 0;
      const currentExpense = dashboardData.summary?.total_expense || 0;
      
      // Para calcular variação, precisaríamos dos dados do mês anterior
      // Por enquanto, deixamos como 0
      const incomeChange = 0;
      const expenseChange = 0;

      // Mapeia KPIs
      const kpis: FinanceKPI[] = [
        {
          title: 'Saldo Atual',
          value: totalBalance,
          change: 0,
          changeType: 'increase',
          icon: 'wallet',
        },
        {
          title: 'Receitas',
          value: currentIncome,
          change: incomeChange,
          changeType: 'increase',
          icon: 'trending-up',
        },
        {
          title: 'Despesas',
          value: currentExpense,
          change: expenseChange,
          changeType: 'decrease',
          icon: 'trending-down',
        },
        {
          title: 'Cartões de Crédito',
          value: accounts.filter((acc: any) => acc.type === 'credit_card').length,
          change: 0,
          changeType: 'increase',
          icon: 'credit-card',
        },
      ];

      // Mapeia dados mensais (últimos 12 meses)
      const monthlyData: MonthlyData[] = (dashboardData.monthly_evolution || []).map((item: any) => {
        const date = new Date(item.year, item.month - 1, 1);
        const monthNames = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
        return {
          month: monthNames[date.getMonth()],
          income: item.income || 0,
          expenses: item.expense || 0,
          net: (item.income || 0) - (item.expense || 0),
        };
      });

      // Mapeia categorias de despesas para o gráfico de pizza
      const categories: CategoryExpense[] = (dashboardData.expense_by_category || []).map((item: any) => ({
        name: item.category_name || 'Sem categoria',
        value: item.total || 0,
        color: item.category_color || '#6b7280',
        percentage: item.percentage || 0,
      }));

      // Mapeia transações recentes
      const recentTransactions = (dashboardData.recent_transactions || []).map((tx: any) => ({
        id: tx.id || tx._id,
        description: tx.description,
        amount: tx.amount,
        type: tx.type,
        category: tx.category?.name || 'Sem categoria',
        date: tx.date,
      }));

      setFinanceData({
        kpis,
        monthlyData,
        categories,
        recentTransactions,
      });
    } catch (err: any) {
      console.error('Load dashboard error:', err);
      setError('Erro ao carregar dados do dashboard');
      
      // Define dados vazios em caso de erro
      setFinanceData({
        kpis: [
          { title: 'Saldo Atual', value: 0, change: 0, changeType: 'increase', icon: 'wallet' },
          { title: 'Receitas', value: 0, change: 0, changeType: 'increase', icon: 'trending-up' },
          { title: 'Despesas', value: 0, change: 0, changeType: 'decrease', icon: 'trending-down' },
          { title: 'Cartões de Crédito', value: 0, change: 0, changeType: 'increase', icon: 'credit-card' },
        ],
        monthlyData: [],
        categories: [],
        recentTransactions: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleNewTransaction = (type: 'expense' | 'income' | 'card_expense' | 'transfer') => {
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

  // Fecha o menu ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showNewMenu && !(event.target as HTMLElement).closest('.new-transaction-menu')) {
        setShowNewMenu(false);
      }
    };

    if (showNewMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showNewMenu]);

  if (authLoading || loading || !financeData) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-200 dark:bg-slate-700 rounded-xl"></div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-96 bg-slate-200 dark:bg-slate-700 rounded-xl"></div>
          <div className="h-96 bg-slate-200 dark:bg-slate-700 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-base p-6">
        <div className="text-center">
          <i className="bi bi-exclamation-triangle text-4xl text-red-500 mb-3 block"></i>
          <p className="text-red-600 dark:text-red-400">{error}</p>
          <button
            onClick={loadDashboardData}
            className="mt-4 btn-base bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded-lg"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Botão Novo - Fixo no canto inferior direito */}
      <div className="fixed bottom-8 right-8 z-40 new-transaction-menu">
        <div className="relative">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowNewMenu(!showNewMenu);
            }}
            className="w-16 h-16 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all transform hover:scale-110"
            aria-label="Nova transação"
          >
            <i className="bi bi-plus-lg text-2xl"></i>
          </button>

          {showNewMenu && (
            <div className="dropdown-menu absolute bottom-full right-0 mb-3 w-56 py-2 z-50">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleNewTransaction('expense');
                }}
                className="w-full text-left px-4 py-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-3 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center flex-shrink-0">
                  <i className="bi bi-arrow-down-circle text-red-600 dark:text-red-400 text-lg"></i>
                </div>
                <div>
                  <div className="font-medium">Despesa</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Nova despesa</div>
                </div>
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleNewTransaction('income');
                }}
                className="w-full text-left px-4 py-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-3 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center flex-shrink-0">
                  <i className="bi bi-arrow-up-circle text-emerald-600 dark:text-emerald-400 text-lg"></i>
                </div>
                <div>
                  <div className="font-medium">Receita</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Nova receita</div>
                </div>
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleNewTransaction('card_expense');
                }}
                className="w-full text-left px-4 py-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-3 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                  <i className="bi bi-credit-card text-blue-600 dark:text-blue-400 text-lg"></i>
                </div>
                <div>
                  <div className="font-medium">Despesa de Cartão</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Nova despesa no cartão</div>
                </div>
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleNewTransaction('transfer');
                }}
                className="w-full text-left px-4 py-3 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-3 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center flex-shrink-0">
                  <i className="bi bi-arrow-left-right text-purple-600 dark:text-purple-400 text-lg"></i>
                </div>
                <div>
                  <div className="font-medium">Transferência</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Transferir entre contas</div>
                </div>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {financeData.kpis.map((kpi, index) => {
          const titleLower = kpi.title.toLowerCase();
          let onClickHandler: (() => void) | undefined;

          if (titleLower.includes('saldo')) {
            onClickHandler = () => navigate('/accounts');
          } else if (titleLower.includes('receita')) {
            onClickHandler = () => navigate('/transactions', {
              state: { filterType: 'income' }
            });
          } else if (titleLower.includes('despesa')) {
            onClickHandler = () => navigate('/transactions', {
              state: { filterType: 'expense' }
            });
          } else if (titleLower.includes('cartão') || titleLower.includes('cartões') || titleLower.includes('cartao') || titleLower.includes('cartaes') || (titleLower.includes('cart') && titleLower.includes('crédito'))) {
            onClickHandler = () => navigate('/credit-cards');
          }

          return (
            <KPICard
              key={kpi.title}
              title={kpi.title}
              value={kpi.title.includes('Cartão') || kpi.title.includes('Cartao') ? kpi.value.toString() : formatCurrency(kpi.value)}
              change={kpi.change}
              changeType={kpi.changeType}
              icon={iconMap[kpi.icon as keyof typeof iconMap] || Wallet}
              variant={variantMap[index]}
              onClick={onClickHandler}
            />
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Line Chart - Income vs Expenses */}
        <div className="card-base p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Receitas vs. Despesas</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">Últimos 12 meses</p>
          </div>
          <div>
            {financeData.monthlyData.length === 0 ? (
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
                  <AreaChart data={financeData.monthlyData}>
                  <defs>
                    <linearGradient id="income" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="expenses" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
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
                  <Legend />
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
            {financeData.categories.length === 0 ? (
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
                      data={financeData.categories}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={120}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {financeData.categories.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<PieTooltip />} />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      formatter={(value, entry: any) => (
                        <span className="text-sm text-slate-600">
                          {value} ({entry.payload.percentage.toFixed(1)}%)
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
          <div className="space-y-2">
            {financeData.recentTransactions.slice(0, 5).map((transaction) => (
              <div key={transaction.id} className="flex items-center justify-between p-4 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    transaction.type === 'income' ? 'bg-emerald-50' : 'bg-red-50'
                  }`}>
                    {transaction.type === 'income' ? (
                      <TrendingUp className="w-5 h-5 text-emerald-600" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-600" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-slate-900 dark:text-slate-100">{transaction.description}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {transaction.category} • {new Date(transaction.date).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                </div>
                <div className={`text-lg font-semibold ${
                  transaction.type === 'income' ? 'text-emerald-600' : 'text-red-600'
                }`}>
                  {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;