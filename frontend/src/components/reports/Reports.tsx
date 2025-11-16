import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency } from '../../utils/api';
import ReportChart from './ReportChart';
import ReportFilters from './ReportFilters';

const Reports = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [filters, setFilters] = useState({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
    report_type: 'expenses_by_category',
    chart_type: 'pie'
  });

  const reportTypes = [
    { value: 'expenses_by_category', label: 'Despesas por categorias', icon: 'bi-arrow-down-circle' },
    { value: 'expenses_by_account', label: 'Despesas por contas', icon: 'bi-wallet2' },
    { value: 'income_by_category', label: 'Receitas por categorias', icon: 'bi-arrow-up-circle' },
    { value: 'income_by_account', label: 'Receitas por contas', icon: 'bi-bank' },
    { value: 'balance_by_account', label: 'Saldos por conta', icon: 'bi-graph-up' }
  ];

  const chartTypes = [
    { value: 'pie', label: 'Gráfico de Pizza', icon: 'bi-pie-chart-fill' },
    { value: 'doughnut', label: 'Gráfico Rosca', icon: 'bi-circle-fill' },
    { value: 'bar', label: 'Gráfico de Barras', icon: 'bi-bar-chart-fill' },
    { value: 'line', label: 'Gráfico de Linha', icon: 'bi-graph-up' }
  ];

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      loadReportData();
    }
  }, [filters, isAuthenticated, authLoading]);

  const loadReportData = async () => {
    setLoading(true);
    setError('');

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const params = new URLSearchParams({
        month: filters.month,
        year: filters.year,
        type: filters.report_type
      });

      const response = await fetch(`${API_URL}/api/reports/overview?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Erro ao carregar relatório');
      }

      const data = await response.json();
      setReportData(data);
    } catch (err) {
      setError('Erro ao carregar dados do relatório');
      console.error('Report error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const getCurrentReportLabel = () => {
    const reportType = reportTypes.find(type => type.value === filters.report_type);
    return reportType ? reportType.label : 'Relatório';
  };

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600">Gerando relatório...</p>
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
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600"></i>
          <span className="text-red-800">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart Area */}
        <div className="lg:col-span-2 space-y-6">
          {/* Chart Type Selector */}
          <div className="card-base p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{getCurrentReportLabel()}</h2>

              {/* Chart Type Buttons */}
              <div className="flex items-center gap-2">
                {chartTypes.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    className={`p-2.5 rounded-lg transition-colors ${
                      filters.chart_type === type.value
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
                    }`}
                    onClick={() => handleFilterChange('chart_type', type.value)}
                    title={type.label}
                  >
                    <i className={type.icon}></i>
                  </button>
                ))}
              </div>
            </div>

            {/* Period Selector */}
            <div className="mb-6">
              <ReportFilters
                filters={filters}
                onFilterChange={handleFilterChange}
              />
            </div>

            {/* Chart and Legend */}
            {reportData && reportData.data && reportData.data.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <ReportChart
                    data={reportData.data}
                    chartType={filters.chart_type}
                    reportType={filters.report_type}
                  />
                </div>

                {/* Legend */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-900 mb-3">Detalhes</h3>
                  <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                    {reportData.data.map((item, index) => (
                      <div key={index} className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2 min-w-0 flex-1">
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0 mt-1"
                            style={{
                              backgroundColor: item.category_color || item.account_color
                            }}
                          ></div>
                          <div className="min-w-0 flex-1">
                            <div className="font-medium text-sm text-slate-900 truncate">
                              {item.category_name || item.account_name}
                            </div>
                            <div className="text-xs text-slate-500">
                              {item.percentage?.toFixed(1)}% · {item.count} {item.count === 1 ? 'transação' : 'transações'}
                            </div>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className="font-semibold text-sm text-slate-900">
                            {formatCurrency(item.total)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {reportData.total_amount && (
                    <div className="border-t border-slate-200 pt-3 mt-3">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-slate-900">Total:</span>
                        <span className="font-bold text-lg text-slate-900">{formatCurrency(reportData.total_amount)}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <i className="bi bi-pie-chart text-6xl text-slate-300 mb-4 block"></i>
                <h5 className="text-lg font-semibold text-slate-700 mb-2">Nenhum dado encontrado</h5>
                <p className="text-slate-500">
                  Não há transações para o período selecionado
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Report Type Filter */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-funnel text-slate-600 dark:text-slate-300"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Tipo de Relatório</h3>
              </div>
            </div>
            <div className="p-3">
              <div className="space-y-1">
                {reportTypes.map((type) => (
                  <button
                    key={type.value}
                    className={`w-full text-left px-4 py-3 rounded-lg transition-colors flex items-center gap-3 ${
                      filters.report_type === type.value
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                    }`}
                    onClick={() => handleFilterChange('report_type', type.value)}
                  >
                    <i className={`bi ${type.icon} ${filters.report_type === type.value ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-slate-500'}`}></i>
                    <span className="text-sm">{type.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Summary */}
          {reportData && (
            <div className="card-base overflow-hidden">
              <div className="card-header px-6 py-4">
                <div className="flex items-center gap-2">
                  <i className="bi bi-info-circle text-slate-600 dark:text-slate-300"></i>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Resumo do Período</h3>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">Período</div>
                    <div className="font-semibold text-slate-900 dark:text-white">
                      {reportData.period.month}/{reportData.period.year}
                    </div>
                  </div>

                  {reportData.total_amount && (
                    <div className="text-center">
                      <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">Valor Total</div>
                      <div className="font-bold text-2xl text-slate-900 dark:text-white">
                        {formatCurrency(reportData.total_amount)}
                      </div>
                    </div>
                  )}

                  <div className="text-center">
                    <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">Itens</div>
                    <div className="font-semibold text-slate-900 dark:text-white">
                      {reportData.data ? reportData.data.length : 0}
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
