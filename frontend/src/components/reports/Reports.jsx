import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '../../utils/api';
import ReportChart from './ReportChart';
import ReportFilters from './ReportFilters';

const Reports = () => {
  const { t } = useTranslation();
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
    { value: 'expenses_by_category', label: 'Despesas por categorias' },
    { value: 'expenses_by_account', label: 'Despesas por contas' },
    { value: 'income_by_category', label: 'Receitas por categorias' },
    { value: 'income_by_account', label: 'Receitas por contas' },
    { value: 'balance_by_account', label: 'Saldos por conta' }
  ];

  const chartTypes = [
    { value: 'pie', label: 'Gráfico de Pizza', icon: 'bi-pie-chart' },
    { value: 'doughnut', label: 'Gráfico Rosca', icon: 'bi-circle' },
    { value: 'bar', label: 'Gráfico de Barras', icon: 'bi-bar-chart' },
    { value: 'line', label: 'Gráfico de Linha', icon: 'bi-graph-up' }
  ];

  useEffect(() => {
    loadReportData();
  }, [filters]);

  const loadReportData = async () => {
    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams({
        month: filters.month,
        year: filters.year,
        type: filters.report_type
      });

      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/reports/overview?${params}`, {
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

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner mb-3"></div>
          <p className="text-muted">Gerando relatório...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="reports">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">Relatórios</h2>
      </div>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}
        </div>
      )}

      <div className="row">
        {/* Área Principal do Relatório */}
        <div className="col-lg-8">
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              {/* Botões de Tipo de Gráfico */}
              <div className="btn-group" role="group">
                {chartTypes.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    className={`btn ${filters.chart_type === type.value ? 'btn-primary' : 'btn-outline-secondary'}`}
                    onClick={() => handleFilterChange('chart_type', type.value)}
                    title={type.label}
                  >
                    <i className={type.icon}></i>
                  </button>
                ))}
              </div>

              {/* Seletor de Período */}
              <div className="d-flex align-items-center">
                <ReportFilters
                  filters={filters}
                  onFilterChange={handleFilterChange}
                />
              </div>
            </div>
            
            <div className="card-body">
              <h5 className="card-title text-center mb-4">
                {getCurrentReportLabel()}
              </h5>
              
              {reportData && reportData.data && reportData.data.length > 0 ? (
                <div className="row">
                  <div className="col-lg-8">
                    <ReportChart
                      data={reportData.data}
                      chartType={filters.chart_type}
                      reportType={filters.report_type}
                    />
                  </div>
                  
                  <div className="col-lg-4">
                    <div className="report-legend">
                      <h6 className="mb-3">Detalhes</h6>
                      {reportData.data.map((item, index) => (
                        <div key={index} className="d-flex align-items-center justify-content-between mb-3">
                          <div className="d-flex align-items-center">
                            <div 
                              className="rounded-circle me-3"
                              style={{
                                width: '12px',
                                height: '12px',
                                backgroundColor: item.category_color || item.account_color
                              }}
                            ></div>
                            <div>
                              <div className="fw-medium">
                                {item.category_name || item.account_name}
                              </div>
                              <small className="text-muted">
                                {item.percentage?.toFixed(1)}%
                              </small>
                            </div>
                          </div>
                          <div className="text-end">
                            <div className="fw-bold">
                              {formatCurrency(item.total)}
                            </div>
                            <small className="text-muted">
                              {item.count} {item.count === 1 ? 'transação' : 'transações'}
                            </small>
                          </div>
                        </div>
                      ))}
                      
                      {reportData.total_amount && (
                        <div className="border-top pt-3 mt-3">
                          <div className="d-flex justify-content-between align-items-center">
                            <strong>Total:</strong>
                            <strong>{formatCurrency(reportData.total_amount)}</strong>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-5">
                  <i className="bi bi-pie-chart display-4 text-muted mb-3"></i>
                  <h5 className="text-muted">Nenhum dado encontrado</h5>
                  <p className="text-muted">
                    Não há transações para o período selecionado
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar com Filtros e Opções */}
        <div className="col-lg-4">
          <div className="card mb-4">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-funnel me-2"></i>
                Tipo de Relatório
              </h6>
            </div>
            <div className="card-body">
              <div className="list-group list-group-flush">
                {reportTypes.map((type) => (
                  <button
                    key={type.value}
                    className={`list-group-item list-group-item-action ${
                      filters.report_type === type.value ? 'active' : ''
                    }`}
                    onClick={() => handleFilterChange('report_type', type.value)}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Resumo Rápido */}
          {reportData && (
            <div className="card">
              <div className="card-header">
                <h6 className="card-title mb-0">
                  <i className="bi bi-info-circle me-2"></i>
                  Resumo do Período
                </h6>
              </div>
              <div className="card-body">
                <div className="row text-center">
                  <div className="col-12 mb-3">
                    <div className="text-muted small">Período</div>
                    <div className="fw-bold">
                      {reportData.period.month}/{reportData.period.year}
                    </div>
                  </div>
                  
                  {reportData.total_amount && (
                    <div className="col-12 mb-3">
                      <div className="text-muted small">Valor Total</div>
                      <div className="fw-bold h5 mb-0">
                        {formatCurrency(reportData.total_amount)}
                      </div>
                    </div>
                  )}
                  
                  <div className="col-12">
                    <div className="text-muted small">Itens</div>
                    <div className="fw-bold">
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