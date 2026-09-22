import React, { useState, useRef, useId } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  goalsAPI,
  type Goal,
  type GoalContribution,
} from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { GoalLoadError } from './GoalLoadError';
import {
  GOAL_AMOUNT_ERROR,
  GOAL_CONTRIBUTION_ERROR,
  GOAL_DELETE_ERROR,
  GOAL_LOAD_ERROR,
  goalApiMessage,
  isNotFound,
  parseGoalAmount,
} from './goalCurrency';

interface GoalDetailData {
  goal: Goal | null;
  contributions: GoalContribution[];
}

const GoalDetail: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [revision, setRevision] = useState(0);
  const [actionError, setActionError] = useState('');
  const [showAddContribution, setShowAddContribution] = useState(false);
  const [contributionAmount, setContributionAmount] = useState('');
  const [contributionNotes, setContributionNotes] = useState('');
  const [amountError, setAmountError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const submitLock = useRef(false);
  const amountId = useId();
  const amountErrorId = useId();
  const notesId = useId();

  const request = useKeyedRequest<GoalDetailData>(
    `${goalId ?? ''}:${revision}`,
    isAuthenticated && !authLoading && Boolean(goalId),
    async () => {
      try {
        const [goalRes, contribRes] = await Promise.all([
          goalsAPI.get(goalId!),
          goalsAPI.listContributions(goalId!),
        ]);
        const g = goalRes?.data;
        const c = contribRes?.data;
        return {
          data: {
            goal: g && typeof g === 'object' ? (g as Goal) : null,
            contributions: Array.isArray(c) ? c : [],
          },
        };
      } catch (err) {
        if (isNotFound(err)) return { data: { goal: null, contributions: [] } };
        throw err;
      }
    },
  );
  const loading = request.loading;
  const loadError = request.error;
  const goal = request.data?.goal ?? null;
  const contributions = request.data?.contributions ?? [];
  const reload = () => setRevision((value) => value + 1);

  const handleAddContribution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalId || submitLock.current) return;
    const amount = parseGoalAmount(contributionAmount);
    if (amount <= 0) {
      setAmountError(GOAL_AMOUNT_ERROR);
      return;
    }
    setAmountError('');
    submitLock.current = true;
    setSaving(true);
    setActionError('');
    try {
      await goalsAPI.addContribution(goalId, {
        amount,
        notes: contributionNotes.trim() || undefined,
      });
      setContributionAmount('');
      setContributionNotes('');
      setShowAddContribution(false);
      reload();
    } catch (err) {
      setActionError(goalApiMessage(err) || GOAL_CONTRIBUTION_ERROR);
    } finally {
      submitLock.current = false;
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!goalId) return;
    await goalsAPI.delete(goalId);
    setConfirmDelete(false);
    navigate('/goals');
  };

  const handleBack = () => navigate('/goals');
  const handleEdit = () => navigate(`/goals/${goalId}/edit`);

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" role="status" aria-busy="true">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando meta...</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <GoalLoadError title="Meta indisponível" message={GOAL_LOAD_ERROR} onRetry={reload} onBack={handleBack} />
    );
  }

  if (!goal) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex min-h-[44px] items-center gap-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        >
          <i className="bi bi-arrow-left" aria-hidden="true" /> Voltar
        </button>
        <div className="card-base p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">Meta não encontrada.</p>
        </div>
      </div>
    );
  }

  const progressPct = Math.min(goal.progress_percent ?? 0, 100);
  const isCompleted = goal.status === 'completed';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex min-h-[44px] items-center gap-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        >
          <i className="bi bi-arrow-left" aria-hidden="true" /> Voltar às metas
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleEdit}
            className="inline-flex min-h-[44px] items-center gap-2 px-4 text-sm bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600"
          >
            <i className="bi bi-pencil" aria-hidden="true" />
            Editar
          </button>
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="inline-flex min-h-[44px] items-center gap-2 px-4 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-50 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/20"
          >
            <i className="bi bi-trash" aria-hidden="true" />
            Excluir meta
          </button>
        </div>
      </div>

      {actionError && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" aria-hidden="true" />
          <span className="text-red-800 dark:text-red-200">{actionError}</span>
        </div>
      )}

      <div className="card-base overflow-hidden p-0">
        <div className="aspect-[3/1] min-h-[180px] bg-slate-200 dark:bg-slate-700 relative">
          {goal.image_url ? (
            <img
              src={goal.image_url}
              alt=""
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <i className="bi bi-bullseye text-6xl text-slate-400 dark:text-slate-500" aria-hidden="true" />
            </div>
          )}
        </div>
        <div className="p-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{goal.title}</h1>
          {goal.description && (
            <p className="text-slate-600 dark:text-slate-300 mt-2">{goal.description}</p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">Meta</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">
                {formatCurrency(goal.target_amount)}
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">Guardado</p>
              <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                {formatCurrency(goal.current_amount)}
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">Restante</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">
                {formatCurrency(goal.remaining_amount ?? 0)}
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">
                {goal.target_date ? 'Prazo' : 'Progresso'}
              </p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">
                {goal.target_date
                  ? formatDate(goal.target_date)
                  : `${goal.progress_percent?.toFixed(0) ?? 0}%`}
              </p>
            </div>
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-sm text-slate-600 dark:text-slate-400 mb-1">
              <span>Progresso</span>
              <span>{goal.progress_percent?.toFixed(1) ?? 0}%</span>
            </div>
            <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  isCompleted ? 'bg-emerald-500' : 'bg-indigo-500 dark:bg-indigo-400'
                }`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
          {goal.monthly_needed != null && goal.months_remaining != null && goal.months_remaining > 0 && (
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
              Para atingir a meta no prazo: <strong>{formatCurrency(goal.monthly_needed)}</strong>/mês
              ({goal.months_remaining} meses restantes).
            </p>
          )}
          {!isCompleted && (
            <div className="mt-6">
              {!showAddContribution ? (
                <button
                  type="button"
                  onClick={() => setShowAddContribution(true)}
                  className="inline-flex min-h-[44px] items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white rounded-lg font-medium"
                >
                  <i className="bi bi-plus-lg" aria-hidden="true" /> Adicionar aporte
                </button>
              ) : (
                <form onSubmit={handleAddContribution} noValidate className="flex flex-wrap items-start gap-3">
                  <div>
                    <label htmlFor={amountId} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Valor (R$)
                    </label>
                    <input
                      id={amountId}
                      type="text"
                      inputMode="decimal"
                      value={contributionAmount}
                      onChange={(e) => {
                        setContributionAmount(e.target.value);
                        if (amountError) setAmountError('');
                      }}
                      placeholder="0,00"
                      aria-invalid={amountError ? true : undefined}
                      aria-describedby={amountError ? amountErrorId : undefined}
                      className="input-base w-40 min-h-[44px]"
                    />
                    {amountError && (
                      <p id={amountErrorId} role="alert" className="mt-1 text-sm text-red-700 dark:text-red-300">
                        {amountError}
                      </p>
                    )}
                  </div>
                  <div className="flex-1 min-w-[200px]">
                    <label htmlFor={notesId} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Observação (opcional)
                    </label>
                    <input
                      id={notesId}
                      type="text"
                      value={contributionNotes}
                      onChange={(e) => setContributionNotes(e.target.value)}
                      placeholder="Ex: bônus trabalho"
                      className="input-base w-full min-h-[44px]"
                    />
                  </div>
                  <div className="flex gap-2 pt-6">
                    <button
                      type="submit"
                      disabled={saving}
                      className="min-h-[44px] px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium"
                    >
                      {saving ? 'Salvando...' : 'Salvar'}
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => {
                        setShowAddContribution(false);
                        setContributionAmount('');
                        setContributionNotes('');
                        setAmountError('');
                      }}
                      className="min-h-[44px] px-4 py-2 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg font-medium disabled:opacity-50"
                    >
                      Cancelar
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="card-base">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Histórico de aportes</h2>
        {contributions.length === 0 ? (
          <p className="text-slate-600 dark:text-slate-400 text-sm">Nenhum aporte registrado.</p>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-700/50">
            {contributions.map((c) => (
              <li
                key={c.id}
                className="py-3 flex items-center justify-between gap-4"
              >
                <div>
                  <p className="font-medium text-emerald-600 dark:text-emerald-400">
                    + {formatCurrency(c.amount)}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {formatDateTime(c.date)}
                    {c.notes && ` · ${c.notes}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Excluir meta?"
          subject={goal.title}
          details={[
            ['Guardado', formatCurrency(goal.current_amount)],
            ['Aportes', String(contributions.length)],
          ]}
          consequence={<p>A meta e todo o histórico de aportes serão removidos permanentemente. Esta ação não pode ser desfeita.</p>}
          confirmLabel="Excluir meta"
          danger
          errorMessage={GOAL_DELETE_ERROR}
          onConfirm={handleDelete}
          onClose={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
};

export default GoalDetail;
