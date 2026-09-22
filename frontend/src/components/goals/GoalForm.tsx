import React, { useState, useEffect, useRef, useId } from 'react';
import { goalsAPI, type Goal } from '../../utils/api';
import { GOAL_AMOUNT_ERROR, GOAL_SAVE_ERROR, goalApiMessage, parseGoalAmount } from './goalCurrency';

type GoalStatus = 'active' | 'completed' | 'paused';

interface GoalFormProps {
  goal?: Goal | null;
  onSuccess: (goal: Goal) => void;
  onCancel: () => void;
}

export const GoalForm: React.FC<GoalFormProps> = ({ goal, onSuccess, onCancel }) => {
  const [title, setTitle] = useState(goal?.title ?? '');
  const [description, setDescription] = useState(goal?.description ?? '');
  const [targetAmount, setTargetAmount] = useState(
    goal?.target_amount != null ? String(goal.target_amount) : ''
  );
  const [targetDate, setTargetDate] = useState(
    goal?.target_date ? goal.target_date.slice(0, 10) : ''
  );
  const [imageUrl, setImageUrl] = useState(goal?.image_url ?? '');
  const [status, setStatus] = useState<GoalStatus>(goal?.status ?? 'active');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const submitLock = useRef(false);
  const ids = {
    title: useId(), description: useId(), amount: useId(), date: useId(), image: useId(), status: useId(), error: useId(),
  };

  useEffect(() => {
    if (goal) {
      setTitle(goal.title);
      setDescription(goal.description ?? '');
      setTargetAmount(goal.target_amount != null ? String(goal.target_amount) : '');
      setTargetDate(goal.target_date ? goal.target_date.slice(0, 10) : '');
      setImageUrl(goal.image_url ?? '');
      setStatus((goal.status as GoalStatus) ?? 'active');
    }
  }, [goal]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitLock.current) return;
    setError('');
    const amount = parseGoalAmount(targetAmount);
    if (!title.trim()) {
      setError('Título é obrigatório');
      return;
    }
    if (amount <= 0) {
      setError(GOAL_AMOUNT_ERROR);
      return;
    }
    submitLock.current = true;
    setLoading(true);
    try {
      if (goal?.id) {
        const res = await goalsAPI.update(goal.id, {
          title: title.trim(),
          description: description.trim() || undefined,
          target_amount: amount,
          target_date: targetDate || undefined,
          image_url: imageUrl.trim() || undefined,
          status,
        });
        const updated = res?.data as Goal;
        if (updated) onSuccess(updated);
      } else {
        const res = await goalsAPI.create({
          title: title.trim(),
          description: description.trim() || undefined,
          target_amount: amount,
          current_amount: 0,
          target_date: targetDate || undefined,
          image_url: imageUrl.trim() || undefined,
          status,
        });
        const created = res?.data as Goal;
        if (created) onSuccess(created);
      }
    } catch (err) {
      setError(goalApiMessage(err) || GOAL_SAVE_ERROR);
    } finally {
      submitLock.current = false;
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="card-base p-6 space-y-5 max-w-xl shadow-lg">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
        {goal ? 'Editar meta' : 'Nova meta'}
      </h2>
      {error && (
        <div id={ids.error} role="alert" className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200 text-sm flex items-center gap-2 animate-shake">
          <i className="bi bi-exclamation-triangle-fill" aria-hidden="true"></i>
          {error}
        </div>
      )}
      <div>
        <label htmlFor={ids.title} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Título *
        </label>
        <div className="relative">
          <i className="bi bi-bullseye absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            id={ids.title}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex: Viagem para Porto de Galinhas"
            className="native-input-themed w-full h-11 pl-10 pr-4 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
            required
          />
        </div>
      </div>
      <div>
        <label htmlFor={ids.description} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Descrição (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-chat-left-text absolute left-3 top-3 text-slate-400 pointer-events-none"></i>
          <textarea
            id={ids.description}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Descreva sua meta..."
            className="native-input-themed w-full pl-10 pr-4 py-3 resize-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
          />
        </div>
      </div>
      <div>
        <label htmlFor={ids.amount} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Valor da meta (R$) *
        </label>
        <div className="relative">
          <i className="bi bi-currency-dollar absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg pointer-events-none"></i>
          <input
            id={ids.amount}
            type="text"
            value={targetAmount}
            onChange={(e) => setTargetAmount(e.target.value)}
            placeholder="0,00"
            inputMode="decimal"
            aria-invalid={error === GOAL_AMOUNT_ERROR ? true : undefined}
            aria-describedby={error ? ids.error : undefined}
            className="native-input-themed w-full h-11 pl-10 pr-4 font-semibold focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
            required
          />
        </div>
      </div>
      <div>
        <label htmlFor={ids.date} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Data alvo (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-calendar3 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            id={ids.date}
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            className="native-input-themed w-full h-11 pl-10 pr-4 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
          />
        </div>
      </div>
      <div>
        <label htmlFor={ids.image} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          URL da imagem inspiracional (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-image absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            id={ids.image}
            type="url"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="https://..."
            className="native-input-themed w-full h-11 pl-10 pr-4 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
          />
        </div>
      </div>
      {goal && (
        <div>
          <label htmlFor={ids.status} className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Status
          </label>
          <div className="relative">
            <i className="bi bi-flag absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
            <select
              id={ids.status}
              value={status}
              onChange={(e) => setStatus(e.target.value as GoalStatus)}
              className="native-select-themed !w-full min-h-[44px] py-2.5 pl-10 text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400"
            >
              <option value="active">Em andamento</option>
              <option value="paused">Pausada</option>
              <option value="completed">Concluída</option>
            </select>
          </div>
        </div>
      )}
      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={loading}
          className="min-h-[44px] px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 dark:from-indigo-500 dark:to-indigo-600 dark:hover:from-indigo-600 dark:hover:to-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40 disabled:shadow-none flex items-center gap-2"
        >
          {loading ? (
            <>
              <i className="bi bi-hourglass-split animate-spin"></i>
              Salvando...
            </>
          ) : (
            <>
              <i className="bi bi-check-lg"></i>
              {goal ? 'Salvar' : 'Criar meta'}
            </>
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="min-h-[44px] px-6 py-2.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-all"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
};

export default GoalForm;
