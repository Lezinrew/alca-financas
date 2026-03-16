import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatCurrency, formatDate, goalsAPI, type Goal } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';

const STATUS_LABELS: Record<string, string> = {
  active: 'Em andamento',
  completed: 'Concluída',
  paused: 'Pausada',
};

const Goals: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [goals, setGoals] = useState<Goal[]>([]);
  const [filter, setFilter] = useState<string>('');

  const loadGoals = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const res = await goalsAPI.list(filter || undefined);
      const data = res?.data;
      setGoals(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao carregar metas');
      setGoals([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadGoals();
    }
  }, [isAuthenticated, authLoading, loadGoals]);

  const handleCreate = () => {
    navigate('/goals/new');
  };

  const handleCardClick = (id: string) => {
    navigate(`/goals/${id}`);
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando metas...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Metas</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
            Objetivos financeiros de longo prazo
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white text-sm"
          >
            <option value="">Todas</option>
            <option value="active">Em andamento</option>
            <option value="completed">Concluídas</option>
            <option value="paused">Pausadas</option>
          </select>
          <button
            type="button"
            onClick={handleCreate}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <i className="bi bi-plus-lg" />
            Nova meta
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" />
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {goals.length === 0 ? (
        <div className="card-base p-12 text-center">
          <div className="max-w-md mx-auto">
            <div className="w-32 h-32 mx-auto bg-indigo-100 dark:bg-indigo-900/30 rounded-full flex items-center justify-center mb-4">
              <i className="bi bi-bullseye text-5xl text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              Nenhuma meta ainda
            </h3>
            <p className="text-slate-600 dark:text-slate-300 mb-6">
              Crie uma meta (viagem, reserva de emergência, carro, etc.) e acompanhe seu progresso.
            </p>
            <button
              type="button"
              onClick={handleCreate}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 text-white rounded-lg font-medium transition-colors"
            >
              Criar primeira meta
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {goals.map((goal) => (
            <button
              type="button"
              key={goal.id}
              onClick={() => handleCardClick(goal.id)}
              className="card-base p-0 overflow-hidden text-left hover:ring-2 hover:ring-indigo-500 dark:hover:ring-indigo-400 transition-all"
            >
              <div className="aspect-[2/1] bg-slate-200 dark:bg-slate-700 relative overflow-hidden">
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
                    <i className="bi bi-bullseye text-4xl text-slate-400 dark:text-slate-500" />
                  </div>
                )}
                <span className="absolute top-2 right-2 px-2 py-0.5 rounded text-xs font-medium bg-white/90 dark:bg-slate-800/90 text-slate-700 dark:text-slate-300">
                  {STATUS_LABELS[goal.status] || goal.status}
                </span>
              </div>
              <div className="p-4">
                <h3 className="font-semibold text-slate-900 dark:text-white truncate">
                  {goal.title}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Meta: {formatCurrency(goal.target_amount)}
                  {goal.target_date && ` · ${formatDate(goal.target_date)}`}
                </p>
                <div className="mt-3 flex items-center justify-between text-sm">
                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                    {formatCurrency(goal.current_amount)} guardados
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">
                    {goal.progress_percent != null ? `${goal.progress_percent.toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div className="mt-2 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 dark:bg-indigo-400 rounded-full transition-all"
                    style={{
                      width: `${Math.min(goal.progress_percent ?? 0, 100)}%`,
                    }}
                  />
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default Goals;
