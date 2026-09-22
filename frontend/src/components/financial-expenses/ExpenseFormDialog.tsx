import React, { useId, useRef, useState } from 'react';
import { financialExpensesAPI, type FinancialExpense } from '../../utils/api';
import { ExpenseDialog } from './ExpenseDialog';

export interface ExpenseFormDialogProps {
  expense: FinancialExpense | null;
  onClose: () => void;
  onSaved: () => void;
  defaultMonth: number;
  defaultYear: number;
}

const categories = ['moradia', 'educação', 'saúde', 'transporte', 'veículos', 'cartões', 'dívidas', 'família', 'serviços', 'utilidades', 'impostos', 'alimentação', 'pessoal', 'outros'];
const optionalText = ['description', 'subcategory', 'recurrence_type', 'payment_method', 'source_type', 'responsible_person', 'vehicle_name', 'notes'] as const;
const optionalNumbers = ['competency_month', 'competency_year', 'installment_current', 'installment_total'] as const;

function localDateTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (number: number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function initialValues(expense: FinancialExpense | null, month: number, year: number): Record<string, string> {
  const result: Record<string, string> = {
    title: expense?.title ?? '', category: expense?.category ?? 'moradia',
    amount_expected: String(expense?.amount_expected ?? ''), amount_paid: String(expense?.amount_paid ?? 0),
    due_date: expense?.due_date ?? '', paid_at: localDateTime(expense?.paid_at),
    competency_month: String(expense ? expense.competency_month ?? '' : month),
    competency_year: String(expense ? expense.competency_year ?? '' : year),
    installment_current: String(expense?.installment_current ?? ''), installment_total: String(expense?.installment_total ?? ''),
    is_recurring: expense?.is_recurring ? 'yes' : 'no', status: expense?.status ?? 'pending',
  };
  for (const field of optionalText) result[field] = expense?.[field] ?? (field === 'source_type' ? 'manual' : '');
  return result;
}

/** Mount a fresh instance for each account. Preserves an unchanged payment timestamp exactly. */
export function ExpenseFormDialog({ expense, onClose, onSaved, defaultMonth, defaultYear }: ExpenseFormDialogProps) {
  const [initial] = useState(() => initialValues(expense, defaultMonth, defaultYear));
  const [values, setValues] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const prefix = useId();
  const close = () => {
    if (submitting.current) return;
    if (JSON.stringify(values) !== JSON.stringify(initial) && !window.confirm('Descartar as alterações não salvas desta conta?')) return;
    onClose();
  };
  const change = (field: string, value: string) => setValues(current => ({ ...current, [field]: value }));
  const field = (name: string, label: string, type = 'text', required = false, min?: number, max?: number) => (
    <div key={name}>
      <label htmlFor={`${prefix}-${name}`} className="mb-1 block text-sm font-medium">{label}{required ? ' *' : ''}</label>
      <input ref={name === 'title' ? titleRef : undefined} id={`${prefix}-${name}`} name={name} type={type}
        value={values[name]} onChange={event => change(name, event.target.value)} required={required} min={min} max={max}
        step={name.startsWith('amount_') ? '0.01' : type === 'number' ? '1' : undefined}
        className="native-input-themed min-h-[44px] w-full" />
    </div>
  );
  const textarea = (name: string, label: string) => (
    <div><label htmlFor={`${prefix}-${name}`} className="mb-1 block text-sm font-medium">{label}</label>
      <textarea id={`${prefix}-${name}`} name={name} rows={2} value={values[name]} onChange={event => change(name, event.target.value)} className="native-input-themed w-full" /></div>
  );
  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    setError('');
    if (!values.title.trim()) { setError('Informe o título da conta.'); titleRef.current?.focus(); return; }
    const expected = Number(values.amount_expected);
    const paid = Number(values.amount_paid || 0);
    if (!Number.isFinite(expected) || !Number.isFinite(paid) || expected < 0 || paid < 0) {
      setError('Informe valores monetários válidos, iguais ou maiores que zero.'); return;
    }
    if (Boolean(values.competency_month) !== Boolean(values.competency_year)) {
      setError('Informe mês e ano da competência juntos, ou deixe ambos vazios.'); return;
    }
    if (values.installment_current && values.installment_total && Number(values.installment_current) > Number(values.installment_total)) {
      setError('A parcela atual não pode superar o total de parcelas.'); return;
    }
    const payload: Record<string, unknown> = {
      title: values.title.trim(), category: values.category, amount_expected: expected, amount_paid: paid,
      due_date: values.due_date || null, is_recurring: values.is_recurring === 'yes', status: values.status,
      paid_at: values.paid_at === initial.paid_at ? expense?.paid_at ?? null : values.paid_at ? new Date(values.paid_at).toISOString() : null,
    };
    for (const name of optionalText) payload[name] = values[name].trim() || null;
    for (const name of optionalNumbers) payload[name] = values[name] ? Number(values[name]) : null;
    submitting.current = true;
    setSaving(true);
    try {
      if (expense) await financialExpensesAPI.update(expense.id, payload);
      else await financialExpensesAPI.create(payload);
      onSaved();
    } catch {
      setError('Não foi possível salvar a conta. Suas alterações foram mantidas. Tente novamente.');
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  };
  return <ExpenseDialog title={expense ? 'Editar conta' : 'Nova conta'} onClose={close} busy={saving} initialFocus={titleRef}>
    <form onSubmit={save} className="p-4" aria-describedby={`${prefix}-help`}>
      <p id={`${prefix}-help`} className="mb-4 text-sm text-slate-600 dark:text-slate-300">Campos com * são obrigatórios. A situação é atualizada de acordo com os valores pagos.</p>
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}
      <fieldset disabled={saving} className="space-y-4">
        {field('title', 'Título', 'text', true)}
        {textarea('description', 'Descrição')}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div><label htmlFor={`${prefix}-category`} className="mb-1 block text-sm font-medium">Categoria *</label>
            <select id={`${prefix}-category`} name="category" value={values.category} onChange={event => change('category', event.target.value)} required className="native-select-themed min-h-[44px] w-full">
              {[...new Set([...categories, values.category])].map(category => <option key={category} value={category}>{category}</option>)}
            </select></div>
          {field('subcategory', 'Subcategoria')}
          {field('amount_expected', 'Valor previsto', 'number', true, 0)}
          {field('amount_paid', 'Valor pago', 'number', false, 0)}
          {field('due_date', 'Vencimento', 'date')}
          {field('paid_at', 'Pago em', 'datetime-local')}
          {field('competency_month', 'Competência (mês)', 'number', false, 1, 12)}
          {field('competency_year', 'Competência (ano)', 'number', false, 1, 9999)}
        </div>
        <label className="flex min-h-[44px] items-center gap-2"><input name="is_recurring" type="checkbox" checked={values.is_recurring === 'yes'} onChange={event => change('is_recurring', event.target.checked ? 'yes' : 'no')} />Conta recorrente</label>
        {field('recurrence_type', 'Tipo de recorrência')}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {field('installment_current', 'Parcela atual', 'number', false, 1)}
          {field('installment_total', 'Total de parcelas', 'number', false, 1)}
          {field('payment_method', 'Meio de pagamento')}
          {field('source_type', 'Origem')}
          {field('responsible_person', 'Responsável')}
          {field('vehicle_name', 'Veículo')}
        </div>
        {textarea('notes', 'Observações')}
        <div><label htmlFor={`${prefix}-status`} className="mb-1 block text-sm font-medium">Situação</label>
          <select id={`${prefix}-status`} name="status" value={values.status} onChange={event => change('status', event.target.value)} className="native-select-themed min-h-[44px] w-full" aria-describedby={`${prefix}-status-help`}>
            <option value="pending">Pendente</option><option value="partial">Parcialmente paga</option><option value="paid">Paga</option><option value="canceled">Cancelada</option>
          </select>
          <p id={`${prefix}-status-help`} className="mt-1 text-sm text-slate-600 dark:text-slate-300">Exceto para contas canceladas, a situação final depende do valor pago.</p>
        </div>
      </fieldset>
      <div className="mt-5 flex justify-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-700">
        <button type="button" onClick={close} disabled={saving} className="min-h-[44px] rounded-lg border border-slate-300 px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 disabled:opacity-50">Cancelar</button>
        <button type="submit" disabled={saving} className="min-h-[44px] rounded-lg bg-indigo-600 px-4 font-medium text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50">{saving ? 'Salvando…' : 'Salvar conta'}</button>
      </div>
    </form>
  </ExpenseDialog>;
}
