import React, { useState, useEffect, useCallback } from 'react';
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

const GoalDetail: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [goal, setGoal] = useState<Goal | null>(null);
  const [contributions, setContributions] = useState<GoalContribution[]>([]);
  const [showAddContribution, setShowAddContribution] = useState(false);
  const [contributionAmount, setContributionAmount] = useState('');
  const [contributionNotes, setContributionNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const loadGoal = useCallback(async () => {
    if (!goalId) return;
    try {
      setLoading(true);
      setError('');
      const [goalRes, contribRes] = await Promise.all([
        goalsAPI.get(goalId),
        goalsAPI.listContributions(goalId),
      ]);
      const g = goalRes?.data;
      const c = contribRes?.data;
      setGoal(g && typeof g === 'object' ? (g as Goal) : null);
      setContributions(Array.isArray(c) ? c : []);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao carregar meta');
      setGoal(null);
      setContributions([]);
    } finally {
      setLoading(false);
    }
  }, [goalId]);

  useEffect(() => {
    if (isAuthenticated && !authLoading && goalId) {
      loadGoal();
    }
  }, [isAuthenticated, authLoading, goalId, loadGoal]);

  const handleAddContribution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalId || contributionAmount === '') return;
    const amount = parseFloat(contributionAmount.replace(',', '.')) || 0;
    if (amount <= 0) return;
    try {
      setSaving(true);
      await goalsAPI.addContribution(goalId, {
        amount,
        notes: contributionNotes.trim() || undefined,
      });
      setContributionAmount('');
      setContributionNotes('');
      setShowAddContribution(false);
      await loadGoal();
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao adicionar aporte');
    } finally {
      setSaving(false);
    }
  };

  const handleBack = () => navigate('/goals');
  const handleEdit = () => navigate(`/goals/${goalId}/edit`);

  if (authLoading || (loading && !goal)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando meta...</p>
        </div>
      </div>
    );
  }

  if (!goal) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={handleBack}
          className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center gap-2"
        >
          <i className="bi bi-arrow-left" /> Voltar
        </button>
        <div className="card-base p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">{error || 'Meta não encontrada.'}</p>
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
          className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center gap-2"
        >
          <i className="bi bi-arrow-left" /> Voltar às metas
        </button>
        <button
          type="button"
          onClick={handleEdit}
          className="px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600"
        >
          Editar
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" />
          <span className="text-red-800 dark:text-red-200">{error}</span>
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
              <i className="bi bi-bullseye text-6xl text-slate-400 dark:text-slate-500" />
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
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white rounded-lg font-medium flex items-center gap-2"
                >
                  <i className="bi bi-plus-lg" /> Adicionar aporte
                </button>
              ) : (
                <form onSubmit={handleAddContribution} className="flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Valor (R$)
                    </label>
                    <input
                      type="text"
                      value={contributionAmount}
                      onChange={(e) => setContributionAmount(e.target.value)}
                      placeholder="0,00"
                      className="input-base w-40"
                    />
                  </div>
                  <div className="flex-1 min-w-[200px]">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Observação (opcional)
                    </label>
                    <input
                      type="text"
                      value={contributionNotes}
                      onChange={(e) => setContributionNotes(e.target.value)}
                      placeholder="Ex: bônus trabalho"
                      className="input-base w-full"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={saving || !contributionAmount.trim()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium"
                    >
                      {saving ? 'Salvando...' : 'Salvar'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowAddContribution(false);
                        setContributionAmount('');
                        setContributionNotes('');
                      }}
                      className="px-4 py-2 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg font-medium"
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
    </div>
  );
};

export default GoalDetail;
