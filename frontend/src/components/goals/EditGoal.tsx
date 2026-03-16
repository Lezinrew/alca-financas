import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { goalsAPI, type Goal } from '../../utils/api';
import GoalForm from './GoalForm';

const EditGoal: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const navigate = useNavigate();
  const [goal, setGoal] = useState<Goal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!goalId) return;
    goalsAPI
      .get(goalId)
      .then((res) => {
        const g = res?.data;
        setGoal(g && typeof g === 'object' ? (g as Goal) : null);
      })
      .catch(() => setGoal(null))
      .finally(() => setLoading(false));
  }, [goalId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (!goal) {
    return (
      <div className="card-base p-6">
        <p className="text-slate-600 dark:text-slate-400">Meta não encontrada.</p>
        <button
          type="button"
          onClick={() => navigate('/goals')}
          className="mt-4 text-indigo-600 dark:text-indigo-400 hover:underline"
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
