import React from 'react';
import { useNavigate } from 'react-router-dom';
import GoalForm from './GoalForm';
import type { Goal } from '../../utils/api';

const NewGoal: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Nova meta</h1>
        <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
          Defina um objetivo financeiro e acompanhe o progresso.
        </p>
      </div>
      <GoalForm
        onSuccess={(goal: Goal) => navigate(`/goals/${goal.id}`)}
        onCancel={() => navigate('/goals')}
      />
    </div>
  );
};

export default NewGoal;
