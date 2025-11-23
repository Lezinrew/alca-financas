import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, reportsAPI, ReportOverviewResponse } from '../../utils/api';
import ReportChart, { ChartDisplayType } from './ReportChart';
import ReportFilters from './ReportFilters';

type ReportTypeOption =
  | 'expenses_by_category'
  | 'expenses_by_account'
  | 'income_by_category'
  | 'income_by_account'
  | 'balance_by_account';

interface ReportFiltersState {
  month: number;
  year: number;
  report_type: ReportTypeOption;
  chart_type: ChartDisplayType;
  account_id: string;
}

const Reports = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [reportData, setReportData] = useState<ReportOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [filters, setFilters] = useState<ReportFiltersState>({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
    report_type: 'expenses_by_category',
    chart_type: 'pie',
    account_id: ''
  });
  
  const [accounts, setAccounts] = useState<any[]>([]);

  const reportTypes: Array<{ value: ReportTypeOption; label: string; icon: string }> = [
    { value: 'expenses_by_category', label: 'Despesas por categorias', icon: 'bi-arrow-down-circle' },
    { value: 'expenses_by_account', label: 'Despesas por contas', icon: 'bi-wallet2' },
    { value: 'income_by_category', label: 'Receitas por categorias', icon: 'bi-arrow-up-circle' },
    { value: 'income_by_account', label: 'Receitas por contas', icon: 'bi-bank' },
    { value: 'balance_by_account', label: 'Saldos por conta', icon: 'bi-graph-up' }
  ];

  const chartTypes: Array<{ value: ChartDisplayType; label: string; icon: string }> = [
    { value: 'pie', label: 'Gráfico de Pizza', icon: 'bi-pie-chart-fill' },
    { value: 'doughnut', label: 'Gráfico Rosca', icon: 'bi-circle-fill' },
    { value: 'bar', label: 'Gráfico de Barras', icon: 'bi-bar-chart-fill' },
    { value: 'line', label: 'Gráfico de Linha', icon: 'bi-graph-up' }
  ];

  useEffect(() => {
    // Carrega contas quando autenticado
    if (isAuthenticated && !authLoading) {
      loadAccounts();
    }
  }, [isAuthenticated, authLoading]);

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      loadReportData();
    }
  }, [filters, isAuthenticated, authLoading]);

  const loadAccounts = async () => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/accounts`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        const accountsArray = Array.isArray(data) ? data : [];
        // Filtra apenas contas ativas
        const activeAccounts = accountsArray
          .filter((acc: any) => acc.is_active !== false)
          .map((acc: any) => ({
            ...acc,
            id: acc.id || acc._id || '',
            name: acc.name || 'Sem nome'
          }))
          .filter((acc: any) => acc.id);
        setAccounts(activeAccounts);
      } else {
        if (response.status === 429) {
          console.warn('Reports: Rate limit atingido. Aguardando antes de tentar novamente...');
          // Tenta novamente após 5 segundos
          setTimeout(() => {
            if (isAuthenticated && !authLoading) {
              loadAccounts();
            }
          }, 5000);
          return;
        }
        console.error('Reports: Erro ao carregar contas - resposta não OK:', response.status);
      }
    } catch (err) {
      console.error('Reports: Erro ao carregar contas:', err);
    }
  };

  const loadReportData = async () => {
    setLoading(true);
    setError('');

    try {
      const params: any = {
        month: filters.month.toString(),
        year: filters.year.toString(),
        type: filters.report_type
      };
      
      // Adiciona account_id se selecionado
      if (filters.account_id) {
        params.account_id = filters.account_id;
      }
      
      const response = await reportsAPI.getOverview(params);
      
      // Garante que a resposta tenha a estrutura esperada
      if (response.data) {
        setReportData(response.data);
      } else {
        throw new Error('Resposta inválida do servidor');
      }
    } catch (err: any) {
      console.error('Report error:', err);
      
      // Extrai mensagem de erro mais específica
      let errorMessage = 'Erro ao carregar dados do relatório';
      
      if (err?.response?.data?.error) {
        errorMessage = err.response.data.error;
      } else if (err?.message) {
        errorMessage = err.message;
      } else if (err?.response?.status === 401) {
        errorMessage = 'Sessão expirada. Por favor, faça login novamente.';
      } else if (err?.response?.status === 500) {
        errorMessage = 'Erro no servidor. Tente novamente mais tarde.';
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = <K extends keyof ReportFiltersState>(field: K, value: ReportFiltersState[K]) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handlePeriodChange = (field: 'month' | 'year', value: number) => {
    handleFilterChange(field, value);
  };

  const getCurrentReportLabel = () => {
    const reportType = reportTypes.find(type => type.value === filters.report_type);
    return reportType ? reportType.label : 'Relatório';
  };

  const handleItemClick = (item: any) => {
    // Determina o tipo de transação baseado no tipo de relatório
    const transactionType = filters.report_type.includes('income') ? 'income' : 'expense';
    
    // Constrói os parâmetros de filtro
    const params = new URLSearchParams();
    params.append('month', filters.month.toString());
    params.append('year', filters.year.toString());
    params.append('type', transactionType);
    
    // Adiciona filtro específico baseado no tipo de relatório
    if (filters.report_type.includes('_by_account')) {
      // Se for relatório por conta, filtra por account_id
      if (item.account_id) {
        params.append('account_id', item.account_id);
      }
      // Se não tiver account_id (Sem conta associada), não adiciona o filtro
      // mas ainda filtra por tipo e período
    } else if (filters.report_type.includes('_by_category')) {
      // Se for relatório por categoria, filtra por category_id
      if (item.category_id) {
        params.append('category_id', item.category_id);
      }
    }
    
    // Navega para a página de transações com os filtros
    navigate(`/transactions?${params.toString()}`);
  };

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-200 dark:border-blue-800 border-t-blue-600 dark:border-t-blue-400"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <i className="bi bi-pie-chart text-blue-600 dark:text-blue-400 text-xl"></i>
            </div>
          </div>
          <p className="text-slate-700 dark:text-slate-300 font-medium">Gerando relatório...</p>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">Aguarde enquanto processamos os dados</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Relatórios</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Visualize e analise suas transações</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400 text-xl"></i>
          <div className="flex-1">
            <span className="text-red-800 dark:text-red-200 font-medium block">{error}</span>
            <span className="text-red-600 dark:text-red-300 text-sm">Tente atualizar a página ou verificar sua conexão</span>
          </div>
          <button
            onClick={() => loadReportData()}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Tentar novamente
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart Area */}
        <div className="lg:col-span-2 space-y-6">
          {/* Chart Type Selector */}
          <div className="card-base p-6 transition-all duration-200 hover:shadow-lg">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">{getCurrentReportLabel()}</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Análise detalhada do período selecionado
                </p>
              </div>

              {/* Chart Type Buttons */}
              <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
                {chartTypes.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    className={`p-2.5 rounded-md transition-all duration-200 ${
                      filters.chart_type === type.value
                        ? 'bg-blue-600 text-white shadow-md scale-105'
                        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 hover:scale-105'
                    }`}
                    onClick={() => handleFilterChange('chart_type', type.value)}
                    title={type.label}
                  >
                    <i className={`${type.icon} text-lg`}></i>
                  </button>
                ))}
              </div>
            </div>

            {/* Period Selector */}
            <div className="mb-6">
              <ReportFilters
                filters={{ month: filters.month, year: filters.year }}
                onFilterChange={handlePeriodChange}
              />
            </div>

            {/* Account Filter */}
            <div className="mb-6">
              <label htmlFor="report-account-filter" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                <i className="bi bi-wallet2 me-2"></i>
                Filtrar por conta (opcional)
              </label>
              <select
                id="report-account-filter"
                className="w-full px-4 py-2.5 bg-white dark:bg-[#1a1d29] border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                value={filters.account_id}
                onChange={(e) => handleFilterChange('account_id', e.target.value)}
                disabled={loading}
              >
                <option value="">Todas as contas</option>
                {accounts.length > 0 ? (
                  accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} {account.type === 'credit_card' && '(Cartão de Crédito)'}
                    </option>
                  ))
                ) : (
                  <option value="" disabled>Carregando contas...</option>
                )}
              </select>
              {filters.account_id && (
                <p className="mt-2 text-sm text-blue-600 dark:text-blue-400">
                  <i className="bi bi-info-circle me-1"></i>
                  Mostrando apenas transações da conta selecionada
                </p>
              )}
            </div>

            {/* Chart and Legend */}
            {reportData && reportData.data && reportData.data.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="lg:col-span-2">
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 border border-slate-200 dark:border-slate-700/50">
                    <ReportChart
                      data={reportData.data}
                      chartType={filters.chart_type}
                    />
                  </div>
                </div>

                {/* Legend */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide">Detalhes</h3>
                    <span className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded-full">
                      {reportData.data.length} {reportData.data.length === 1 ? 'item' : 'itens'}
                    </span>
                  </div>
                  <div className="space-y-2 max-h-[350px] overflow-y-auto pr-2 custom-scrollbar">
                    {reportData.data.map((item, index) => {
                      const percentage = item.percentage?.toFixed(1) || '0.0';
                      const value = item.total ?? item.current_balance ?? 0;
                      const color = item.category_color || item.account_color || '#6b7280';
                      const name = item.category_name || item.account_name || 'Sem nome';
                      
                      return (
                        <div 
                          key={index} 
                          onClick={() => handleItemClick(item)}
                          className="flex items-start justify-between gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group cursor-pointer"
                          title="Clique para ver as transações"
                        >
                          <div className="flex items-start gap-3 min-w-0 flex-1">
                            <div
                              className="w-4 h-4 rounded-full flex-shrink-0 mt-1 shadow-sm ring-2 ring-white dark:ring-slate-800"
                              style={{ backgroundColor: color }}
                            ></div>
                            <div className="min-w-0 flex-1">
                              <div className="font-semibold text-sm text-slate-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                {name}
                              </div>
                              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                {percentage}% · {item.count || 0} {item.count === 1 ? 'transação' : 'transações'}
                              </div>
                              {item.percentage && (
                                <div className="mt-2 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                  <div
                                    className="h-full rounded-full transition-all duration-500"
                                    style={{ 
                                      width: `${Math.min(parseFloat(percentage), 100)}%`,
                                      backgroundColor: color
                                    }}
                                  ></div>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <div className="font-bold text-sm text-slate-900 dark:text-white">
                              {formatCurrency(value)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {reportData.total_amount && (
                    <div className="border-t-2 border-slate-200 dark:border-slate-700 pt-4 mt-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg p-4">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-slate-900 dark:text-white">Total:</span>
                        <span className="font-bold text-xl text-blue-600 dark:text-blue-400">{formatCurrency(reportData.total_amount)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-16 animate-in fade-in">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
                  <i className="bi bi-pie-chart text-4xl text-slate-400 dark:text-slate-600"></i>
                </div>
                <h5 className="text-lg font-semibold text-slate-700 dark:text-slate-300 mb-2">Nenhum dado encontrado</h5>
                <p className="text-slate-500 dark:text-slate-400 mb-4">
                  Não há transações para o período selecionado
                </p>
                <button
                  onClick={() => {
                    const today = new Date();
                    handleFilterChange('month', today.getMonth() + 1);
                    handleFilterChange('year', today.getFullYear());
                  }}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Ver mês atual
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Report Type Filter */}
          <div className="card-base overflow-hidden transition-all duration-200 hover:shadow-lg">
            <div className="card-header px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
              <div className="flex items-center gap-2">
                <i className="bi bi-funnel text-blue-600 dark:text-blue-400"></i>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide">Tipo de Relatório</h3>
              </div>
            </div>
            <div className="p-3">
              <div className="space-y-1">
                {reportTypes.map((type) => (
                  <button
                    key={type.value}
                    className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 flex items-center gap-3 group ${
                      filters.report_type === type.value
                        ? 'bg-blue-600 dark:bg-blue-500 text-white shadow-md scale-[1.02]'
                        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:scale-[1.01]'
                    }`}
                    onClick={() => handleFilterChange('report_type', type.value)}
                  >
                    <i className={`bi ${type.icon} text-lg ${filters.report_type === type.value ? 'text-white' : 'text-slate-400 dark:text-slate-500 group-hover:text-blue-600 dark:group-hover:text-blue-400'}`}></i>
                    <span className="text-sm font-medium">{type.label}</span>
                    {filters.report_type === type.value && (
                      <i className="bi bi-check-circle-fill ml-auto text-white"></i>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Summary */}
          {reportData && (
            <div className="card-base overflow-hidden transition-all duration-200 hover:shadow-lg">
              <div className="card-header px-6 py-4 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20">
                <div className="flex items-center gap-2">
                  <i className="bi bi-info-circle text-emerald-600 dark:text-emerald-400"></i>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide">Resumo do Período</h3>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-6">
                  <div className="text-center pb-4 border-b border-slate-200 dark:border-slate-700">
                    <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wide">Período</div>
                    <div className="font-bold text-lg text-slate-900 dark:text-white">
                      {reportData.period
                        ? `${String(reportData.period.month).padStart(2, '0')}/${reportData.period.year}`
                        : `${String(filters.month).padStart(2, '0')}/${filters.year}`}
                    </div>
                  </div>

                  {reportData.total_amount && (
                    <div className="text-center pb-4 border-b border-slate-200 dark:border-slate-700">
                      <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wide">Valor Total</div>
                      <div className="font-bold text-3xl text-emerald-600 dark:text-emerald-400">
                        {formatCurrency(reportData.total_amount)}
                      </div>
                    </div>
                  )}

                  <div className="text-center">
                    <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wide">Itens</div>
                    <div className="font-bold text-2xl text-slate-900 dark:text-white">
                      {reportData.data ? reportData.data.length : 0}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      {reportData.data && reportData.data.length > 0 
                        ? `${reportData.data.reduce((sum, item) => sum + (item.count || 0), 0)} transações`
                        : 'Nenhuma transação'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Reports;
