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
    <form onSubmit={handleSubmit} className="card-base p-6 space-y-4 max-w-xl">
      <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
        {goal ? 'Editar meta' : 'Nova meta'}
      </h2>
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200 text-sm">
          {error}
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Título *
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Ex: Viagem para Porto de Galinhas"
          className="input-base w-full"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Descrição (opcional)
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="input-base w-full"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Valor da meta (R$) *
        </label>
        <input
          type="text"
          value={targetAmount}
          onChange={(e) => setTargetAmount(e.target.value)}
          placeholder="0,00"
          className="input-base w-full"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Data alvo (opcional)
        </label>
        <input
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
          className="input-base w-full"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          URL da imagem inspiracional (opcional)
        </label>
        <input
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="https://..."
          className="input-base w-full"
        />
      </div>
      {goal && (
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            Status
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as GoalStatus)}
            className="input-base w-full"
          >
            <option value="active">Em andamento</option>
            <option value="paused">Pausada</option>
            <option value="completed">Concluída</option>
          </select>
        </div>
      )}
      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-medium"
        >
          {loading ? 'Salvando...' : goal ? 'Salvar' : 'Criar meta'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg font-medium"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
};

export default GoalForm;
