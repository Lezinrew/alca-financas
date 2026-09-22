import React, { useState, useId } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatCurrency, formatDate, goalsAPI, type Goal } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { GoalLoadError } from './GoalLoadError';
import { GOALS_LOAD_ERROR } from './goalCurrency';

const STATUS_LABELS: Record<string, string> = {
  active: 'Em andamento',
  completed: 'Concluída',
  paused: 'Pausada',
};

const Goals: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<string>('');
  const [revision, setRevision] = useState(0);
  const filterId = useId();

  const request = useKeyedRequest<Goal[]>(
    `${filter}:${revision}`,
    isAuthenticated && !authLoading,
    async () => {
      const res = await goalsAPI.list(filter || undefined);
      const data = res?.data;
      return { data: Array.isArray(data) ? data : [] };
    },
  );
  const loading = request.loading;
  const error = request.error;
  const goals = request.data ?? [];
  const reload = () => setRevision((value) => value + 1);

  const handleCreate = () => {
    navigate('/goals/new');
  };

  const handleCardClick = (id: string) => {
    navigate(`/goals/${id}`);
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" role="status" aria-busy="true">
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
          <label htmlFor={filterId} className="sr-only">Filtrar por status</label>
          <select
            id={filterId}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="native-select-themed !w-auto min-h-[44px] min-w-[10rem] py-2 px-3 text-sm"
          >
            <option value="">Todas</option>
            <option value="active">Em andamento</option>
            <option value="completed">Concluídas</option>
            <option value="paused">Pausadas</option>
          </select>
          <button
            type="button"
            onClick={handleCreate}
            className="min-h-[44px] px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 dark:from-indigo-500 dark:to-indigo-600 dark:hover:from-indigo-600 dark:hover:to-indigo-700 text-white rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40 flex items-center gap-2"
          >
            <i className="bi bi-plus-lg" />
            Nova meta
          </button>
        </div>
      </div>

      {error ? (
        <GoalLoadError title="Metas indisponíveis" message={GOALS_LOAD_ERROR} onRetry={reload} />
      ) : goals.length === 0 ? (
        <div className="card-base p-12 text-center shadow-sm">
          <div className="max-w-md mx-auto">
            <div className="relative mb-8">
              <div className="w-40 h-40 mx-auto bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30 rounded-full flex items-center justify-center relative animate-float">
                <div className="absolute inset-0 rounded-full bg-indigo-500/10 dark:bg-indigo-400/10 blur-2xl animate-glow-pulse"></div>
                <i className="bi bi-bullseye text-6xl text-indigo-600 dark:text-indigo-400 relative" />
              </div>
            </div>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">
              Nenhuma meta ainda
            </h3>
            <p className="text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
              Crie metas financeiras (viagem, reserva de emergência, carro) e acompanhe seu progresso em direção aos seus objetivos.
            </p>
            <button
              type="button"
              onClick={handleCreate}
              className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 dark:from-indigo-500 dark:to-indigo-600 dark:hover:from-indigo-600 dark:hover:to-indigo-700 text-white rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40"
            >
              <i className="bi bi-plus-circle mr-2"></i>
              Criar primeira meta
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {goals.map((goal) => (
            <button
              type="button"
              key={goal.id}
              onClick={() => handleCardClick(goal.id)}
              className="card-base p-0 overflow-hidden text-left hover:shadow-xl hover:scale-[1.02] transition-all duration-200 group relative"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
              <div className="aspect-[2/1] bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-800 relative overflow-hidden">
                {goal.image_url ? (
                  <img
                    src={goal.image_url}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <i className="bi bi-bullseye text-5xl text-slate-400 dark:text-slate-500 group-hover:scale-110 transition-transform" />
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent"></div>
                <span className="absolute top-3 right-3 px-3 py-1 rounded-full text-xs font-semibold bg-white/95 dark:bg-slate-800/95 text-slate-700 dark:text-slate-300 backdrop-blur-sm shadow-lg">
                  {STATUS_LABELS[goal.status] || goal.status}
                </span>
              </div>
              <div className="p-5 relative">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white truncate mb-2">
                  {goal.title}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-2">
                  <i className="bi bi-currency-dollar"></i>
                  <span>Meta: {formatCurrency(goal.target_amount)}</span>
                  {goal.target_date && (
                    <>
                      <span className="text-slate-400">·</span>
                      <i className="bi bi-calendar3"></i>
                      <span>{formatDate(goal.target_date)}</span>
                    </>
                  )}
                </p>
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                    {formatCurrency(goal.current_amount)}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400 font-semibold">
                    {goal.progress_percent != null ? `${goal.progress_percent.toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div className="mt-2.5 h-2.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 dark:from-indigo-400 dark:to-purple-400 rounded-full transition-all duration-500"
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
