import React, { useCallback, useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  financialExpensesAPI,
  formatCurrency,
  formatDate,
  formatDateTime,
  type FinancialExpense,
  type FinancialExpenseDisplayStatus,
} from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';

const CATEGORY_OPTIONS = [
  'moradia',
  'educação',
  'saúde',
  'transporte',
  'veículos',
  'cartões',
  'dívidas',
  'família',
  'serviços',
  'utilidades',
  'impostos',
  'alimentação',
  'pessoal',
  'outros',
] as const;

const STATUS_FILTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Todos (armazenado)' },
  { value: 'pending', label: 'Pendente' },
  { value: 'partial', label: 'Parcial' },
  { value: 'paid', label: 'Pago' },
  { value: 'canceled', label: 'Cancelado' },
  { value: 'overdue', label: 'Vencido (derivado)' },
];

function num(v: number | string | undefined | null): number {
  if (v === undefined || v === null || v === '') return 0;
  const n = typeof v === 'number' ? v : parseFloat(String(v));
  return Number.isFinite(n) ? n : 0;
}

function statusLabel(s: FinancialExpenseDisplayStatus | undefined): string {
  const map: Record<string, string> = {
    pending: 'Pendente',
    partial: 'Parcial',
    paid: 'Pago',
    canceled: 'Cancelado',
    overdue: 'Vencido',
  };
  return s ? map[s] || s : '';
}

function statusBadgeClass(s: FinancialExpenseDisplayStatus | undefined): string {
  switch (s) {
    case 'overdue':
      return 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-100';
    case 'paid':
      return 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100';
    case 'partial':
      return 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100';
    case 'canceled':
      return 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200';
    default:
      return 'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-100';
  }
}

const emptyForm = (): Record<string, unknown> => ({
  title: '',
  description: '',
  category: 'moradia',
  subcategory: '',
  amount_expected: '',
  amount_paid: '0',
  due_date: '',
  paid_at: '',
  competency_month: String(new Date().getMonth() + 1),
  competency_year: String(new Date().getFullYear()),
  is_recurring: false,
  recurrence_type: '',
  installment_current: '',
  installment_total: '',
  payment_method: '',
  source_type: 'manual',
  responsible_person: '',
  vehicle_name: '',
  notes: '',
  status: 'pending',
});

const FinancialExpensesPage: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const now = useMemo(() => new Date(), []);
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [year, setYear] = useState(String(now.getFullYear()));
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [responsible, setResponsible] = useState('');
  const [recurringFilter, setRecurringFilter] = useState<'all' | 'yes' | 'no'>('all');

  const [rows, setRows] = useState<FinancialExpense[]>([]);
  const [outstanding, setOutstanding] = useState<FinancialExpense[]>([]);
  const [pagination, setPagination] = useState({ total: 0, page: 1, per_page: 50, pages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const base: Record<string, string | number | boolean | undefined> = {
        page: 1,
        limit: 100,
      };
      if (month) base.month = month;
      if (year) base.year = year;
      if (status) base.status = status;
      if (category) base.category = category;
      if (responsible.trim()) base.responsible = responsible.trim();
      if (recurringFilter === 'yes') base.is_recurring = true;
      if (recurringFilter === 'no') base.is_recurring = false;

      const [listRes, outRes] = await Promise.all([
        financialExpensesAPI.list(base),
        financialExpensesAPI.list({ outstanding_only: true, limit: 100 }),
      ]);

      const listBody = listRes.data as unknown as { data?: FinancialExpense[]; pagination?: typeof pagination };
      setRows(Array.isArray(listBody?.data) ? listBody.data : []);
      setPagination(listBody?.pagination || { total: 0, page: 1, per_page: 50, pages: 0 });

      const outBody = outRes.data as unknown as { data?: FinancialExpense[] };
      const outData = Array.isArray(outBody?.data) ? outBody.data : [];
      const sorted = [...outData].sort((a, b) => {
        const da = a.due_date || '9999-12-31';
        const db = b.due_date || '9999-12-31';
        return da.localeCompare(db);
      });
      setOutstanding(sorted);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      setError(err.response?.data?.error || err.message || 'Erro ao carregar despesas');
      setRows([]);
      setOutstanding([]);
    } finally {
      setLoading(false);
    }
  }, [month, year, status, category, responsible, recurringFilter]);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      void load();
    }
  }, [isAuthenticated, authLoading, load]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setModalOpen(true);
  };

  const openEdit = (row: FinancialExpense) => {
    setEditingId(row.id);
    setForm({
      title: row.title,
      description: row.description ?? '',
      category: row.category,
      subcategory: row.subcategory ?? '',
      amount_expected: String(num(row.amount_expected)),
      amount_paid: String(num(row.amount_paid)),
      due_date: row.due_date ?? '',
      paid_at: row.paid_at ? String(row.paid_at).slice(0, 16) : '',
      competency_month: row.competency_month != null ? String(row.competency_month) : '',
      competency_year: row.competency_year != null ? String(row.competency_year) : '',
      is_recurring: !!row.is_recurring,
      recurrence_type: row.recurrence_type ?? '',
      installment_current: row.installment_current != null ? String(row.installment_current) : '',
      installment_total: row.installment_total != null ? String(row.installment_total) : '',
      payment_method: row.payment_method ?? '',
      source_type: row.source_type ?? 'manual',
      responsible_person: row.responsible_person ?? '',
      vehicle_name: row.vehicle_name ?? '',
      notes: row.notes ?? '',
      status: row.status,
    });
    setModalOpen(true);
  };

  const buildPayload = (): Record<string, unknown> => {
    let paidAt: string | null = null;
    if (String(form.paid_at || '').trim()) {
      const d = new Date(String(form.paid_at));
      paidAt = Number.isNaN(d.getTime()) ? String(form.paid_at).trim() : d.toISOString();
    }
    const payload: Record<string, unknown> = {
      title: String(form.title || '').trim(),
      description: String(form.description || '').trim() || null,
      category: form.category,
      subcategory: String(form.subcategory || '').trim() || null,
      amount_expected: parseFloat(String(form.amount_expected || '0')) || 0,
      amount_paid: parseFloat(String(form.amount_paid || '0')) || 0,
      due_date: String(form.due_date || '').trim() || null,
      paid_at: paidAt,
      competency_month: form.competency_month ? parseInt(String(form.competency_month), 10) : null,
      competency_year: form.competency_year ? parseInt(String(form.competency_year), 10) : null,
      is_recurring: !!form.is_recurring,
      recurrence_type: String(form.recurrence_type || '').trim() || null,
      installment_current: form.installment_current ? parseInt(String(form.installment_current), 10) : null,
      installment_total: form.installment_total ? parseInt(String(form.installment_total), 10) : null,
      payment_method: String(form.payment_method || '').trim() || null,
      source_type: String(form.source_type || '').trim() || null,
      responsible_person: String(form.responsible_person || '').trim() || null,
      vehicle_name: String(form.vehicle_name || '').trim() || null,
      notes: String(form.notes || '').trim() || null,
      status: form.status,
    };
    return payload;
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const payload = buildPayload();
      if (editingId) {
        await financialExpensesAPI.update(editingId, payload);
        toast.success('Despesa atualizada');
      } else {
        await financialExpensesAPI.create(payload);
        toast.success('Despesa criada');
      }
      setModalOpen(false);
      await load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      toast.error(err.response?.data?.error || err.message || 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  };

  const handleMarkPaid = async (row: FinancialExpense) => {
    if (row.status === 'canceled') return;
    if (!window.confirm('Marcar esta despesa como paga (valor previsto integral)?')) return;
    try {
      await financialExpensesAPI.markPaid(row.id);
      toast.success('Pagamento registrado');
      await load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      toast.error(err.response?.data?.error || err.message || 'Erro ao marcar pago');
    }
  };

  const handleDelete = async (row: FinancialExpense) => {
    if (!window.confirm(`Remover "${row.title}"?`)) return;
    try {
      await financialExpensesAPI.delete(row.id);
      toast.success('Removida');
      await load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      toast.error(err.response?.data?.error || err.message || 'Erro ao remover');
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400">Carregando contas a pagar...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Contas a pagar</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
            Controle familiar — vencimento e status (vencido é calculado automaticamente)
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 text-white rounded-lg font-medium shadow-lg shadow-indigo-500/25"
        >
          Nova despesa
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-800 dark:text-red-200">
          {error}
        </div>
      )}

      <section className="card-base p-4 md:p-6 shadow-sm border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-[#1a1d29]">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">O que falta pagar</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
          Itens com status pendente ou parcial, ordenados por vencimento. Destaque vermelho = vencido.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300">
                <th className="py-2 pr-2">Descrição</th>
                <th className="py-2 pr-2">Categoria</th>
                <th className="py-2 pr-2 text-right">Previsto</th>
                <th className="py-2 pr-2 text-right">Pago</th>
                <th className="py-2 pr-2">Vencimento</th>
                <th className="py-2 pr-2">Responsável</th>
                <th className="py-2 pr-2">Status</th>
                <th className="py-2">Ações</th>
              </tr>
            </thead>
            <tbody>
              {outstanding.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-slate-500 dark:text-slate-400">
                    Nada pendente neste momento.
                  </td>
                </tr>
              ) : (
                outstanding.map((row) => {
                  const display = row.display_status || row.status;
                  const overdue = row.is_overdue || display === 'overdue';
                  return (
                    <tr
                      key={row.id}
                      className={`border-b border-slate-100 dark:border-slate-700/80 ${
                        overdue ? 'bg-red-50/80 dark:bg-red-950/20' : ''
                      }`}
                    >
                      <td className="py-2 pr-2 font-medium text-slate-900 dark:text-white">{row.title}</td>
                      <td className="py-2 pr-2 text-slate-700 dark:text-slate-300">{row.category}</td>
                      <td className="py-2 pr-2 text-right tabular-nums">{formatCurrency(num(row.amount_expected))}</td>
                      <td className="py-2 pr-2 text-right tabular-nums">{formatCurrency(num(row.amount_paid))}</td>
                      <td className="py-2 pr-2">{row.due_date ? formatDate(row.due_date) : '—'}</td>
                      <td className="py-2 pr-2">{row.responsible_person || '—'}</td>
                      <td className="py-2 pr-2">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadgeClass(display)}`}>
                          {statusLabel(display)}
                        </span>
                      </td>
                      <td className="py-2 whitespace-nowrap">
                        <button type="button" className="text-indigo-600 dark:text-indigo-400 mr-2" onClick={() => openEdit(row)}>
                          Editar
                        </button>
                        <button
                          type="button"
                          className="text-emerald-600 dark:text-emerald-400"
                          onClick={() => void handleMarkPaid(row)}
                          disabled={row.status === 'paid'}
                        >
                          Marcar pago
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card-base p-4 md:p-6 shadow-sm border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-[#1a1d29]">
        <div className="flex flex-wrap gap-3 items-end mb-4">
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Mês</label>
            <select
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={String(i + 1)}>
                  {i + 1}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Ano</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="w-28 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm min-w-[200px]"
            >
              {STATUS_FILTER_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Categoria</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm min-w-[160px]"
            >
              <option value="">Todas</option>
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Responsável</label>
            <input
              type="text"
              value={responsible}
              onChange={(e) => setResponsible(e.target.value)}
              placeholder="contém…"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Recorrência</label>
            <select
              value={recurringFilter}
              onChange={(e) => setRecurringFilter(e.target.value as 'all' | 'yes' | 'no')}
              className="px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
            >
              <option value="all">Todas</option>
              <option value="yes">Só recorrentes</option>
              <option value="no">Só avulsas</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300">
                <th className="py-2 pr-2">Descrição</th>
                <th className="py-2 pr-2">Categoria</th>
                <th className="py-2 pr-2 text-right">Previsto</th>
                <th className="py-2 pr-2 text-right">Pago</th>
                <th className="py-2 pr-2">Vencimento</th>
                <th className="py-2 pr-2">Pago em</th>
                <th className="py-2 pr-2">Responsável</th>
                <th className="py-2 pr-2">Status</th>
                <th className="py-2">Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500 dark:text-slate-400">
                    Nenhuma despesa neste filtro.
                  </td>
                </tr>
              ) : (
                rows.map((row) => {
                  const display = row.display_status || row.status;
                  const overdue = row.is_overdue || display === 'overdue';
                  return (
                    <tr
                      key={row.id}
                      className={`border-b border-slate-100 dark:border-slate-700/80 ${
                        overdue ? 'bg-red-50/50 dark:bg-red-950/15' : ''
                      }`}
                    >
                      <td className="py-2 pr-2">
                        <div className="font-medium text-slate-900 dark:text-white">{row.title}</div>
                        {row.description ? (
                          <div className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1">{row.description}</div>
                        ) : null}
                      </td>
                      <td className="py-2 pr-2 text-slate-700 dark:text-slate-300">{row.category}</td>
                      <td className="py-2 pr-2 text-right tabular-nums">{formatCurrency(num(row.amount_expected))}</td>
                      <td className="py-2 pr-2 text-right tabular-nums">{formatCurrency(num(row.amount_paid))}</td>
                      <td className="py-2 pr-2">{row.due_date ? formatDate(row.due_date) : '—'}</td>
                      <td className="py-2 pr-2">{row.paid_at ? formatDateTime(row.paid_at) : '—'}</td>
                      <td className="py-2 pr-2">{row.responsible_person || '—'}</td>
                      <td className="py-2 pr-2">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadgeClass(display)}`}>
                          {statusLabel(display)}
                        </span>
                      </td>
                      <td className="py-2 whitespace-nowrap">
                        <button type="button" className="text-indigo-600 dark:text-indigo-400 mr-2" onClick={() => openEdit(row)}>
                          Editar
                        </button>
                        <button
                          type="button"
                          className="text-emerald-600 dark:text-emerald-400 mr-2"
                          onClick={() => void handleMarkPaid(row)}
                          disabled={row.status === 'paid' || row.status === 'canceled'}
                        >
                          Pagar
                        </button>
                        <button type="button" className="text-red-600 dark:text-red-400" onClick={() => void handleDelete(row)}>
                          Excluir
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        {pagination.total > 0 && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-3">
            Total no filtro: {pagination.total} (mostrando até {pagination.per_page})
          </p>
        )}
      </section>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" role="dialog" aria-modal="true">
          <div className="bg-white dark:bg-[#1a1d29] rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto border border-slate-200 dark:border-slate-600">
            <div className="p-4 border-b border-slate-200 dark:border-slate-600 flex justify-between items-center">
              <h3 className="font-semibold text-lg text-slate-900 dark:text-white">
                {editingId ? 'Editar despesa' : 'Nova despesa'}
              </h3>
              <button
                type="button"
                className="text-slate-500 hover:text-slate-800 dark:hover:text-white"
                onClick={() => setModalOpen(false)}
                aria-label="Fechar"
              >
                ✕
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Título *</label>
                <input
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                  value={String(form.title || '')}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Descrição</label>
                <textarea
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                  rows={2}
                  value={String(form.description || '')}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Categoria *</label>
                  <select
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.category || 'moradia')}
                    onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Subcategoria</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.subcategory || '')}
                    onChange={(e) => setForm((f) => ({ ...f, subcategory: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Valor previsto *</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.amount_expected ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, amount_expected: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Valor pago</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.amount_paid ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, amount_paid: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Vencimento</label>
                  <input
                    type="date"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.due_date || '')}
                    onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Pago em (opcional)</label>
                  <input
                    type="datetime-local"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.paid_at || '')}
                    onChange={(e) => setForm((f) => ({ ...f, paid_at: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Competência (mês)</label>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.competency_month ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, competency_month: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Competência (ano)</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.competency_year ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, competency_year: e.target.value }))}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="rec"
                  type="checkbox"
                  checked={!!form.is_recurring}
                  onChange={(e) => setForm((f) => ({ ...f, is_recurring: e.target.checked }))}
                />
                <label htmlFor="rec" className="text-sm text-slate-700 dark:text-slate-300">
                  Recorrente
                </label>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Tipo de recorrência</label>
                <input
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                  placeholder="mensal, anual…"
                  value={String(form.recurrence_type || '')}
                  onChange={(e) => setForm((f) => ({ ...f, recurrence_type: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Parcela atual</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.installment_current ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, installment_current: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Parcelas total</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.installment_total ?? '')}
                    onChange={(e) => setForm((f) => ({ ...f, installment_total: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Meio de pagamento</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.payment_method || '')}
                    onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Origem</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.source_type || '')}
                    onChange={(e) => setForm((f) => ({ ...f, source_type: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Responsável</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.responsible_person || '')}
                    onChange={(e) => setForm((f) => ({ ...f, responsible_person: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Veículo</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                    value={String(form.vehicle_name || '')}
                    onChange={(e) => setForm((f) => ({ ...f, vehicle_name: e.target.value }))}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Observações</label>
                <textarea
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                  rows={2}
                  value={String(form.notes || '')}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Status armazenado</label>
                <select
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
                  value={String(form.status || 'pending')}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                >
                  <option value="pending">pending</option>
                  <option value="partial">partial</option>
                  <option value="paid">paid</option>
                  <option value="canceled">canceled</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  Ao salvar, o servidor recalcula a partir dos valores exceto se cancelado.
                </p>
              </div>
            </div>
            <div className="p-4 border-t border-slate-200 dark:border-slate-600 flex justify-end gap-2">
              <button
                type="button"
                className="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200"
                onClick={() => setModalOpen(false)}
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium disabled:opacity-50"
                onClick={() => void handleSave()}
              >
                {saving ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FinancialExpensesPage;
