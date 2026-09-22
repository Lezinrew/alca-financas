import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import {
  planningAPI,
  type PlanningMonthResponse,
  type PlanningCategoriesResponse,
} from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import PlanningForm from './PlanningForm';
import PlanningMonthOverview from './PlanningMonthOverview';
import PlanningExpenseProgress from './PlanningExpenseProgress';
import PlanningIncomeTracking from './PlanningIncomeTracking';
import PlanningAlerts from './PlanningAlerts';

interface PlanningMonthData {
  planning: PlanningMonthResponse | null;
  categories: PlanningCategoriesResponse | null;
}

const MONTH_LABELS = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

const PLANNING_LOAD_ERROR = 'Não foi possível carregar o planejamento. Tente novamente.';
const PLANNING_COPY_ERROR = 'Não foi possível copiar o planejamento do mês anterior. Tente novamente.';
const PLANNING_PREVIOUS_MISSING = 'Nenhum planejamento encontrado para o mês anterior.';

/** Lê a resposta do backend sem expor mensagens técnicas ao usuário. */
const apiMessage = (err: unknown): string | undefined => {
  const data = (err as { response?: { data?: { error?: unknown; message?: unknown } } })?.response?.data;
  const text = data?.error ?? data?.message;
  return typeof text === 'string' && text.trim() ? text : undefined;
};

const Planning: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [revision, setRevision] = useState(0);
  const [actionError, setActionError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [confirmCopy, setConfirmCopy] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [showGuide, setShowGuide] = useState(true);
  const copyLock = useRef(false);

  const currentMonth = currentDate.getMonth() + 1;
  const currentYear = currentDate.getFullYear();

  const request = useKeyedRequest<PlanningMonthData>(
    `${currentYear}-${currentMonth}:${revision}`,
    isAuthenticated && !authLoading,
    async () => {
      const [monthRes, categoriesRes] = await Promise.all([
        planningAPI.getMonth(currentMonth, currentYear),
        planningAPI.getMonthCategories(),
      ]);
      const data = monthRes?.data;
      const catData = categoriesRes?.data;
      return {
        data: {
          planning: data && typeof data === 'object' && 'summary' in data ? (data as PlanningMonthResponse) : null,
          categories: catData && typeof catData === 'object' ? (catData as PlanningCategoriesResponse) : null,
        },
      };
    },
  );
  const loading = request.loading;
  const loadError = request.error;
  const planningData = request.data?.planning ?? null;
  const categoriesForForm = request.data?.categories ?? null;

  const reload = () => setRevision((value) => value + 1);
  const hasConfiguredPlan = Boolean(
    planningData &&
      (planningData.summary.planned_income > 0 || planningData.summary.planned_expenses > 0)
  );

  const handleFormSubmit = async (formData: any) => {
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
    setShowForm(false);
    setActionError('');
    reload();
  };

  /** Copia o mês anterior; lança em caso de falha para o ConfirmDialog manter-se aberto. */
  const copyPreviousMonth = async () => {
    if (copyLock.current) return;
    copyLock.current = true;
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1;
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear;
    try {
      setActionError('');
      const res = await planningAPI.getMonth(prevMonth, prevYear);
      const prev = res?.data as PlanningMonthResponse | undefined;
      if (!prev?.summary) {
        setActionError(PLANNING_PREVIOUS_MISSING);
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
      reload();
    } catch (err) {
      setActionError(apiMessage(err) || PLANNING_COPY_ERROR);
      throw err;
    } finally {
      copyLock.current = false;
    }
  };

  const handleCopyPreviousMonth = () => {
    if (copyLock.current) return;
    if (hasConfiguredPlan) {
      setConfirmCopy(true);
      return;
    }
    void copyPreviousMonth().catch(() => undefined);
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

  const plannedCategoryCount = planningData
    ? [...(planningData.expense_categories || []), ...(planningData.income_categories || [])]
        .filter((category) => (category.planned_amount ?? 0) > 0).length
    : 0;

  useEffect(() => {
    if (hasConfiguredPlan) setShowGuide(false);
  }, [hasConfiguredPlan]);

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" role="status" aria-busy="true">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando planejamento...</p>
        </div>
      </div>
    );
  }

  const monthLabel = `${MONTH_LABELS[currentMonth - 1]} de ${currentYear}`;

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

      {actionError && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" aria-hidden="true" />
          <span className="text-red-800 dark:text-red-200">{actionError}</span>
        </div>
      )}

      {loadError ? (
        <div role="alert" className="card-base p-8 text-center border border-red-200 dark:border-red-800">
          <i className="bi bi-exclamation-triangle-fill text-3xl text-red-600 dark:text-red-400 block mb-3" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Planejamento indisponível</h2>
          <p className="mt-2 text-slate-600 dark:text-slate-300">{PLANNING_LOAD_ERROR}</p>
          <button
            type="button"
            onClick={reload}
            className="mt-4 inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
          >
            <i className="bi bi-arrow-clockwise" aria-hidden="true" />
            Tentar novamente
          </button>
        </div>
      ) : (
        <>
      <section className="card-base overflow-hidden border border-blue-200 dark:border-blue-900/50">
        <button
          type="button"
          onClick={() => setShowGuide((visible) => !visible)}
          className="flex w-full items-center justify-between gap-4 p-5 text-left hover:bg-slate-50 dark:hover:bg-slate-800/40"
          aria-expanded={showGuide}
        >
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
              <i className="bi bi-compass" aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-semibold text-slate-900 dark:text-white">
                {hasConfiguredPlan ? 'Como usar seu planejamento' : 'Configure o mês em 3 passos'}
              </h2>
              <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
                Planejamento define limites; Contas a pagar registra vencimentos e pagamentos reais.
              </p>
            </div>
          </div>
          <i className={`bi bi-chevron-${showGuide ? 'up' : 'down'} text-slate-500`} aria-hidden="true" />
        </button>
        {showGuide && (
          <div className="grid gap-3 border-t border-slate-200 p-5 dark:border-slate-700 md:grid-cols-3">
            {[
              { step: 1, title: 'Confirme sua renda', text: 'Informe quanto espera receber no mês.', done: Boolean(planningData?.summary.planned_income) },
              { step: 2, title: 'Revise as contas fixas', text: 'Cadastre aluguel, escola, serviços e vencimentos.', done: false, action: () => navigate('/financial-expenses'), actionLabel: 'Abrir contas a pagar' },
              { step: 3, title: 'Defina limites', text: 'Distribua quanto pode gastar por categoria.', done: plannedCategoryCount > 0 },
            ].map((item) => (
              <article key={item.step} className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/50">
                <div className="flex items-start gap-3">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${item.done ? 'bg-emerald-500 text-white' : 'bg-blue-600 text-white'}`}>
                    {item.done ? <i className="bi bi-check-lg" /> : item.step}
                  </span>
                  <div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">{item.title}</h3>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{item.text}</p>
                    {item.action && (
                      <button type="button" onClick={item.action} className="mt-3 text-sm font-semibold text-blue-600 hover:underline dark:text-blue-400">
                        {item.actionLabel} <i className="bi bi-arrow-right" />
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
            <div className="md:col-span-3 flex flex-wrap gap-3 pt-1">
              <button type="button" onClick={() => setShowForm(true)} className="btn-base min-h-[44px] bg-brand-500 px-4 py-2 text-sm text-white hover:bg-brand-600">
                <i className="bi bi-pencil-square mr-2" />{hasConfiguredPlan ? 'Ajustar planejamento' : 'Começar planejamento'}
              </button>
              <button type="button" onClick={handleCopyPreviousMonth} className="btn-base min-h-[44px] border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700">
                <i className="bi bi-copy mr-2" />Usar mês anterior como base
              </button>
            </div>
          </div>
        )}
      </section>

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

        </>
      )}
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

      {confirmCopy && (
        <ConfirmDialog
          title="Substituir planejamento do mês?"
          subject={monthLabel}
          consequence={<p>Os valores planejados deste mês serão substituídos pelos do mês anterior. Os lançamentos reais não são alterados.</p>}
          confirmLabel="Substituir"
          errorMessage={PLANNING_COPY_ERROR}
          onConfirm={async () => {
            await copyPreviousMonth();
            setConfirmCopy(false);
          }}
          onClose={() => setConfirmCopy(false)}
        />
      )}
    </div>
  );
};

export default Planning;
