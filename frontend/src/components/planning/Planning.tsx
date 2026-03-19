import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  planningAPI,
  type PlanningMonthResponse,
  type PlanningCategoriesResponse,
} from '../../utils/api';
import PlanningForm from './PlanningForm';
import PlanningMonthOverview from './PlanningMonthOverview';
import PlanningExpenseProgress from './PlanningExpenseProgress';
import PlanningIncomeTracking from './PlanningIncomeTracking';
import PlanningAlerts from './PlanningAlerts';

const Planning: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [planningData, setPlanningData] = useState<PlanningMonthResponse | null>(null);
  const [categoriesForForm, setCategoriesForForm] = useState<PlanningCategoriesResponse | null>(null);

  const currentMonth = currentDate.getMonth() + 1;
  const currentYear = currentDate.getFullYear();

  const loadData = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      setLoading(true);
      setError('');
      const [monthRes, categoriesRes] = await Promise.all([
        planningAPI.getMonth(currentMonth, currentYear),
        planningAPI.getMonthCategories(),
      ]);
      const data = monthRes?.data;
      if (data && typeof data === 'object' && 'summary' in data) {
        setPlanningData(data as PlanningMonthResponse);
      } else {
        setPlanningData(null);
      }
      const catData = categoriesRes?.data;
      if (catData && typeof catData === 'object') {
        setCategoriesForForm(catData as PlanningCategoriesResponse);
      } else {
        setCategoriesForForm(null);
      }
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.error ||
        err.response?.data?.message ||
        err.message ||
        'Erro ao carregar planejamento';
      setError(errorMessage);
      setPlanningData(null);
      setCategoriesForForm(null);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, currentMonth, currentYear]);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadData();
    }
  }, [isAuthenticated, authLoading, loadData]);

  const handleFormSubmit = async (formData: any) => {
    try {
      const planned_income =
        typeof formData.monthly_income === 'number'
          ? formData.monthly_income
          : parseFloat(String(formData.monthly_income).replace(/\D/g, '')) / 100 || 0;
      const category_plans = (formData.category_budgets || []).map((cb: { category_id: string; amount: number }) => ({
        category_id: cb.category_id,
        planned_amount: cb.amount,
      }));
      await planningAPI.saveMonth({
        month: currentMonth,
        year: currentYear,
        planned_income,
        savings_percentage: formData.savings_percentage ?? 20,
        category_plans,
      });
      await loadData();
      setShowForm(false);
      setError('');
    } catch (err: any) {
      throw err;
    }
  };

  const handleCopyPreviousMonth = async () => {
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    try {
      setError('');
      const res = await planningAPI.getMonth(prevMonth, prevYear);
      const prev = res?.data as PlanningMonthResponse | undefined;
      if (!prev?.summary) {
        setError('Nenhum planejamento encontrado para o mês anterior.');
        return;
      }
      const category_plans = [
        ...(prev.expense_categories || []),
        ...(prev.income_categories || []),
      ]
        .filter((c) => (c.planned_amount ?? 0) > 0)
        .map((c) => ({
          category_id: c.category_id,
          planned_amount: c.planned_amount,
        }));
      await planningAPI.saveMonth({
        month: currentMonth,
        year: currentYear,
        planned_income: prev.summary.planned_income,
        savings_percentage: 20,
        category_plans,
      });
      await loadData();
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao copiar planejamento');
    }
  };

  const handlePreviousMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth - 2, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth, 1));
  };

  const formBudget = planningData
    ? {
        monthly_income: planningData.summary.planned_income,
        savings_percentage: 20,
        category_budgets: [
          ...(planningData.expense_categories || []),
          ...(planningData.income_categories || []),
        ]
          .filter((c) => (c.planned_amount ?? 0) > 0)
          .map((c) => ({ category_id: c.category_id, amount: c.planned_amount })),
      }
    : null;

  const formCategories = categoriesForForm
    ? [
        ...(categoriesForForm.expense || []).map((c) => ({
          id: c.id,
          name: c.name,
          type: 'expense',
          color: c.color,
          icon: c.icon,
        })),
        ...(categoriesForForm.income || []).map((c) => ({
          id: c.id,
          name: c.name,
          type: 'income',
          color: c.color,
          icon: c.icon,
        })),
      ]
    : [];

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando planejamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Planejamento</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
            Orçamento mensal e acompanhamento (planejado x realizado)
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" />
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {!planningData ? (
        <div className="card-base p-12 text-center shadow-sm">
          <div className="max-w-md mx-auto">
            <div className="mb-8 relative">
              <div className="w-48 h-48 mx-auto bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 rounded-full flex items-center justify-center relative animate-float">
                <div className="absolute inset-0 rounded-full bg-purple-500/10 dark:bg-purple-400/10 blur-2xl animate-glow-pulse"></div>
                <i className="bi bi-graph-up-arrow text-6xl text-purple-600 dark:text-purple-400 relative" />
              </div>
            </div>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">
              Nenhum planejamento encontrado
            </h3>
            <p className="text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
              Crie seu primeiro planejamento mensal para acompanhar receitas, despesas e metas financeiras.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 dark:from-purple-500 dark:to-purple-600 dark:hover:from-purple-600 dark:hover:to-purple-700 text-white rounded-lg font-medium transition-all shadow-lg shadow-purple-500/30 hover:shadow-xl hover:shadow-purple-500/40"
              >
                <i className="bi bi-plus-circle mr-2"></i>
                Definir planejamento
              </button>
              <button
                type="button"
                onClick={loadData}
                className="px-6 py-3 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 rounded-lg font-medium transition-all shadow-sm hover:shadow"
              >
                <i className="bi bi-arrow-clockwise mr-2"></i>
                Tentar novamente
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Zona 1 — Resumo mensal */}
          <PlanningMonthOverview
            summary={planningData.summary}
            month={currentMonth}
            year={currentYear}
            onPrevMonth={handlePreviousMonth}
            onNextMonth={handleNextMonth}
            onOpenForm={() => setShowForm(true)}
          />

          {/* Zona 2 — Despesas por categoria */}
          <PlanningExpenseProgress
            categories={planningData.expense_categories || []}
            onEdit={() => setShowForm(true)}
          />

          {/* Zona 3 — Receitas por categoria */}
          <PlanningIncomeTracking
            categories={planningData.income_categories || []}
            onEdit={() => setShowForm(true)}
          />

          {/* Zona 4 — Alertas */}
          <PlanningAlerts alerts={planningData.alerts || []} />

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleCopyPreviousMonth}
              className="px-4 py-2.5 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 rounded-lg font-medium transition-all shadow-sm hover:shadow flex items-center gap-2"
            >
              <i className="bi bi-copy" />
              Copiar mês anterior
            </button>
          </div>
        </>
      )}

      {showForm && (
        <PlanningForm
          show={showForm}
          onHide={() => setShowForm(false)}
          onSubmit={handleFormSubmit}
          categories={formCategories}
          budget={formBudget}
          defaultIncome={planningData?.summary?.real_income ?? 0}
        />
      )}
    </div>
  );
};

export default Planning;
