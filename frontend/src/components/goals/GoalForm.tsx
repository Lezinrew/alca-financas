import React, { useState, useEffect } from 'react';
import { goalsAPI, type Goal } from '../../utils/api';

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

  const parseAmount = (v: string) => {
    if (!v || !v.trim()) return 0;
    const normalized = v.trim().replace(/\./g, '').replace(',', '.');
    const n = parseFloat(normalized);
    return isNaN(n) ? 0 : n;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const amount = parseAmount(targetAmount) || parseFloat(targetAmount) || 0;
    if (!title.trim()) {
      setError('Título é obrigatório');
      return;
    }
    if (amount <= 0) {
      setError('Valor da meta deve ser maior que zero');
      return;
    }
    try {
      setLoading(true);
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
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao salvar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card-base p-6 space-y-5 max-w-xl shadow-lg">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
        {goal ? 'Editar meta' : 'Nova meta'}
      </h2>
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200 text-sm flex items-center gap-2 animate-shake">
          <i className="bi bi-exclamation-triangle-fill"></i>
          {error}
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Título *
        </label>
        <div className="relative">
          <i className="bi bi-bullseye absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex: Viagem para Porto de Galinhas"
            className="w-full h-11 pl-10 pr-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
            required
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Descrição (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-chat-left-text absolute left-3 top-3 text-slate-400 pointer-events-none"></i>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Descreva sua meta..."
            className="w-full pl-10 pr-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all resize-none"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Valor da meta (R$) *
        </label>
        <div className="relative">
          <i className="bi bi-currency-dollar absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg pointer-events-none"></i>
          <input
            type="text"
            value={targetAmount}
            onChange={(e) => setTargetAmount(e.target.value)}
            placeholder="0,00"
            className="w-full h-11 pl-10 pr-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white font-semibold focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
            required
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          Data alvo (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-calendar3 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            className="w-full h-11 pl-10 pr-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
          URL da imagem inspiracional (opcional)
        </label>
        <div className="relative">
          <i className="bi bi-image absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          <input
            type="url"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="https://..."
            className="w-full h-11 pl-10 pr-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all"
          />
        </div>
      </div>
      {goal && (
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Status
          </label>
          <div className="relative">
            <i className="bi bi-flag absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as GoalStatus)}
              className="w-full h-11 pl-10 pr-10 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-all appearance-none"
            >
              <option value="active">Em andamento</option>
              <option value="paused">Pausada</option>
              <option value="completed">Concluída</option>
            </select>
            <i className="bi bi-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
          </div>
        </div>
      )}
      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 dark:from-indigo-500 dark:to-indigo-600 dark:hover:from-indigo-600 dark:hover:to-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40 disabled:shadow-none flex items-center gap-2"
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
          className="px-6 py-2.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-all"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
};

export default GoalForm;
