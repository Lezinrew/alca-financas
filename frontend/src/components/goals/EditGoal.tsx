import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { goalsAPI, type Goal } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import GoalForm from './GoalForm';
import { GoalLoadError } from './GoalLoadError';
import { GOAL_LOAD_ERROR, isNotFound } from './goalCurrency';

const EditGoal: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();
  const [revision, setRevision] = useState(0);
  const request = useKeyedRequest<Goal | null>(`${goalId ?? ''}:${revision}`, Boolean(goalId), async () => {
    try {
      const res = await goalsAPI.get(goalId!);
      const g = res?.data;
      return { data: g && typeof g === 'object' ? (g as Goal) : null };
    } catch (err) {
      if (isNotFound(err)) return { data: null };
      throw err;
    }
  });
  const { loading, error } = request;
  const goal = request.data;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]" role="status" aria-busy="true">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (error) {
    return (
      <GoalLoadError
        title="Meta indisponível"
        message={GOAL_LOAD_ERROR}
        onRetry={() => setRevision((value) => value + 1)}
        onBack={() => navigate('/goals')}
      />
    );
  }

  if (!goal) {
    return (
      <div className="card-base p-6">
        <p className="text-slate-600 dark:text-slate-400">Meta não encontrada.</p>
        <button
          type="button"
          onClick={() => navigate('/goals')}
          className="mt-4 inline-flex min-h-[44px] items-center text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          Voltar às metas
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Editar meta</h1>
        <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{goal.title}</p>
      </div>
      <GoalForm
        goal={goal}
        onSuccess={(updated) => navigate(`/goals/${updated.id}`)}
        onCancel={() => navigate(`/goals/${goalId}`)}
      />
    </div>
  );
};

export default EditGoal;
