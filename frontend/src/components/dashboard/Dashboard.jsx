import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { dashboardAPI, formatCurrency, formatDate } from '../../utils/api';
import DashboardCard from './DashboardCard';
import RecentTransactions from './RecentTransactions';
import CategoryChart from './CategoryChart';

const Dashboard = () => {
  const { t } = useTranslation();
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear()
  });

  useEffect(() => {
    loadDashboardData();
  }, [selectedPeriod]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await dashboardAPI.getData(selectedPeriod.month, selectedPeriod.year);
      setDashboardData(response.data);
    } catch (err) {
      setError('Erro ao carregar dados do dashboard');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (field, value) => {
    setSelectedPeriod(prev => ({
      ...prev,
      [field]: parseInt(value)
    }));
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner mb-3"></div>
          <p className="text-muted">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        <i className="bi bi-exclamation-triangle-fill me-2"></i>
        {error}
      </div>
    );
  }

  const months = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ];

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);

  return (
    <div className="dashboard">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('dashboard.title')}</h2>
        
        <div className="d-flex gap-2">
          <select
            className="form-select form-select-sm"
            value={selectedPeriod.month}
            onChange={(e) => handlePeriodChange('month', e.target.value)}
          >
            {months.map((month, index) => (
              <option key={index} value={index + 1}>
                {month}
              </option>
            ))}
          </select>
          
          <select
            className="form-select form-select-sm"
            value={selectedPeriod.year}
            onChange={(e) => handlePeriodChange('year', e.target.value)}
          >
            {years.map(year => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </div>
      </div>

      {dashboardData && (
        <>
          {/* Cards de Resumo */}
          <div className="row mb-4">
            <div className="col-lg-4 col-md-6 mb-3">
              <DashboardCard
                title={t('dashboard.totalIncome')}
                value={formatCurrency(dashboardData.summary.total_income)}
                icon="bi-arrow-up-circle-fill"
                type="income"
                subtitle={`${dashboardData.income_by_category?.length || 0} categorias`}
              />
            </div>
            
            <div className="col-lg-4 col-md-6 mb-3">
              <DashboardCard
                title={t('dashboard.totalExpense')}
                value={formatCurrency(dashboardData.summary.total_expense)}
                icon="bi-arrow-down-circle-fill"
                type="expense"
                subtitle={`${dashboardData.expense_by_category?.length || 0} categorias`}
              />
            </div>
            
            <div className="col-lg-4 col-md-12 mb-3">
              <DashboardCard
                title={t('dashboard.monthlyBalance')}
                value={formatCurrency(dashboardData.summary.balance)}
                icon="bi-wallet2"
                type="balance"
                subtitle={`${dashboardData.summary.transactions_count} transações`}
              />
            </div>
          </div>

          <div className="row">
            {/* Transações Recentes */}
            <div className="col-lg-6 mb-4">
              <div className="card h-100">
                <div className="card-header">
                  <h5 className="card-title mb-0">
                    <i className="bi bi-clock-history me-2"></i>
                    {t('dashboard.recentTransactions')}
                  </h5>
                </div>
                <div className="card-body">
                  <RecentTransactions transactions={dashboardData.recent_transactions} />
                </div>
              </div>
            </div>

            {/* Gráfico de Despesas por Categoria */}
            <div className="col-lg-6 mb-4">
              <div className="card h-100">
                <div className="card-header">
                  <h5 className="card-title mb-0">
                    <i className="bi bi-pie-chart-fill me-2"></i>
                    {t('dashboard.expensesByCategory')}
                  </h5>
                </div>
                <div className="card-body">
                  <CategoryChart data={dashboardData.expense_by_category} type="expense" />
                </div>
              </div>
            </div>
          </div>

          {/* Receitas por Categoria */}
          {dashboardData.income_by_category && dashboardData.income_by_category.length > 0 && (
            <div className="row">
              <div className="col-12">
                <div className="card">
                  <div className="card-header">
                    <h5 className="card-title mb-0">
                      <i className="bi bi-bar-chart-fill me-2"></i>
                      {t('dashboard.incomesByCategory')}
                    </h5>
                  </div>
                  <div className="card-body">
                    <CategoryChart data={dashboardData.income_by_category} type="income" />
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Dashboard;