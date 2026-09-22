import React, { useState, useRef, useId } from 'react';
import CurrencyInput from '../ui/CurrencyInput';
import { parseCurrencyString } from '../../lib/utils';
import { CreditCard } from '../../types/credit-card';
import { AppDialog } from '../shared/AppDialog';
import { apiErrorMessage, getNextDueDate } from './creditCardUtils';
import './credit-cards.css';

interface Category {
  id: string;
  name: string;
  type: string;
  color: string;
  icon: string;
}

/** Dados enviados ao salvar; apenas campos que o backend persiste. */
export interface CreditCardExpenseSubmit {
  description: string;
  amount: number;
  date: string;
  category_id: string;
  account_id: string;
  is_recurring: boolean;
  installments?: number;
}

interface CreditCardExpenseFormProps {
  onHide: () => void;
  onSubmit: (data: CreditCardExpenseSubmit) => Promise<void>;
  card: CreditCard;
  categories: Category[];
}

interface FormState {
  amount: string;
  date: string;
  description: string;
  category_id: string;
  is_fixed: boolean;
  is_installment: boolean;
  installments: string;
}

const emptyForm: FormState = { amount: '', date: 'today', description: '', category_id: '', is_fixed: false, is_installment: false, installments: '2' };
const dateOptions = [{ value: 'today', label: 'Hoje' }, { value: 'yesterday', label: 'Ontem' }, { value: 'other', label: 'Outra data' }];

/** Diálogo de nova despesa no cartão. Monte apenas enquanto estiver aberto. */
const CreditCardExpenseForm: React.FC<CreditCardExpenseFormProps> = ({ onHide, onSubmit, card, categories }) => {
  const prefix = useId();
  const [formData, setFormData] = useState<FormState>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showMoreDetails, setShowMoreDetails] = useState(false);
  const submitting = useRef(false);
  const amountRef = useRef<HTMLInputElement>(null);

  const isDirty = () => JSON.stringify(formData) !== JSON.stringify(emptyForm);
  const close = () => {
    if (busy) return;
    if (isDirty() && !window.confirm('Descartar esta despesa não salva?')) return;
    onHide();
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target;
    const name = target.name as keyof FormState;
    const nextValue: string | boolean = target instanceof HTMLInputElement && target.type === 'checkbox' ? target.checked : target.value;
    setFormData(prev => ({ ...prev, [name]: nextValue }));
    setError('');
  };

  const usesCustomDate = !['today', 'yesterday'].includes(formData.date);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting.current) return;
    setError('');

    const amountValue = parseCurrencyString(formData.amount);
    if (amountValue <= 0) { setError('Deve ter um valor diferente de 0'); return; }
    if (!formData.category_id) { setError('Categoria é obrigatória'); return; }
    if (!formData.date || formData.date === 'other') { setError('Data é obrigatória'); return; }
    const installments = formData.is_installment ? Number(formData.installments) : undefined;
    if (formData.is_installment && (!installments || installments < 2 || installments > 60)) { setError('Número de parcelas deve estar entre 2 e 60'); return; }

    const date = formData.date === 'today' ? new Date().toISOString()
      : formData.date === 'yesterday' ? new Date(Date.now() - 86400000).toISOString()
        : new Date(formData.date).toISOString();

    submitting.current = true;
    setBusy(true);
    try {
      await onSubmit({
        description: formData.description.trim(),
        amount: amountValue,
        date,
        category_id: formData.category_id,
        account_id: card.id,
        is_recurring: formData.is_fixed,
        ...(installments ? { installments } : {}),
      });
      onHide();
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível salvar a despesa. Seus dados foram mantidos. Tente novamente.'));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  const expenseCategories = categories.filter(cat => cat.type === 'expense');
  const dueDate = getNextDueDate(card).toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <AppDialog title="Nova despesa no cartão de crédito" onClose={close} busy={busy} initialFocus={amountRef} size="md">
      <form onSubmit={handleSubmit} className="cc" noValidate>
        <div className="app-dialog-body">
          {error && <p className="app-dialog-error mb-4" role="alert" style={{ marginTop: 0 }}>{error}</p>}

          <div className="space-y-4">
            <div className="cc-field">
              <label htmlFor={`${prefix}-amount`}>Valor *</label>
              <CurrencyInput
                ref={amountRef}
                id={`${prefix}-amount`}
                name="amount"
                className="native-input-themed w-full text-2xl font-bold"
                value={formData.amount}
                onValueChange={value => { setFormData(prev => ({ ...prev, amount: value ?? '' })); setError(''); }}
                placeholder="0,00"
                disabled={busy}
                required
                autoComplete="transaction-amount"
              />
            </div>

            <fieldset className="cc-field" disabled={busy}>
              <legend className="text-sm font-semibold mb-2">Data *</legend>
              <div className="cc-date-options">
                {dateOptions.map(option => {
                  const checked = option.value === 'other' ? usesCustomDate : formData.date === option.value;
                  return (
                    <React.Fragment key={option.value}>
                      <input type="radio" className="cc-sr-only" name="date" id={`${prefix}-date-${option.value}`} value={option.value} checked={checked} onChange={handleChange} />
                      <label htmlFor={`${prefix}-date-${option.value}`}>{option.label}</label>
                    </React.Fragment>
                  );
                })}
              </div>
              {usesCustomDate && (
                <>
                  <label htmlFor={`${prefix}-date-custom`} className="cc-sr-only">Escolha a data</label>
                  <input
                    type="date"
                    id={`${prefix}-date-custom`}
                    name="date"
                    className="native-input-themed mt-2 w-full"
                    value={formData.date === 'other' ? '' : formData.date}
                    onChange={handleChange}
                    required
                  />
                </>
              )}
            </fieldset>

            <div className="cc-field">
              <label htmlFor={`${prefix}-description`}>Descrição</label>
              <input
                type="text"
                id={`${prefix}-description`}
                name="description"
                className="native-input-themed w-full"
                value={formData.description}
                onChange={handleChange}
                placeholder="Digite a descrição"
                disabled={busy}
                autoComplete="off"
              />
            </div>

            <div className="cc-field">
              <label htmlFor={`${prefix}-category`}>Categoria *</label>
              <select id={`${prefix}-category`} name="category_id" className="native-select-themed !w-full" value={formData.category_id} onChange={handleChange} required disabled={busy}>
                <option value="">Selecionar categoria</option>
                {expenseCategories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </div>

            <div className="cc-field">
              <span className="text-sm font-semibold">Cartão de crédito</span>
              <div className="cc-card-preview">
                <span className="cc-card-chip" style={{ backgroundColor: card.color }} aria-hidden="true"><i className="bi bi-credit-card-fill"></i></span>
                <div>
                  <div className="font-medium">{card.name}</div>
                  <div className="cc-field-hint">Fecha dia {card.closingDay} · Vencimento previsto: {dueDate}</div>
                </div>
              </div>
            </div>

            <button
              type="button"
              className="app-dialog-button"
              aria-expanded={showMoreDetails}
              onClick={() => setShowMoreDetails(value => !value)}
            >
              {showMoreDetails ? 'Menos detalhes' : 'Mais detalhes'}
              <i className={`bi bi-chevron-${showMoreDetails ? 'up' : 'down'}`} aria-hidden="true"></i>
            </button>

            {showMoreDetails && (
              <>
                <label className="cc-check" htmlFor={`${prefix}-fixed`}>
                  <input type="checkbox" id={`${prefix}-fixed`} name="is_fixed" checked={formData.is_fixed} onChange={handleChange} disabled={busy} />
                  <span className="text-sm font-medium">Despesa fixa (recorrente)</span>
                </label>
                <label className="cc-check" htmlFor={`${prefix}-installment`}>
                  <input type="checkbox" id={`${prefix}-installment`} name="is_installment" checked={formData.is_installment} onChange={handleChange} disabled={busy} />
                  <span className="text-sm font-medium">Parcelado</span>
                </label>
                {formData.is_installment && (
                  <div className="cc-field">
                    <label htmlFor={`${prefix}-installments`}>Número de parcelas</label>
                    <input
                      type="number"
                      id={`${prefix}-installments`}
                      name="installments"
                      className="native-input-themed w-full"
                      value={formData.installments}
                      onChange={handleChange}
                      min={2}
                      max={60}
                      disabled={busy}
                    />
                    <span className="cc-field-hint">O valor informado é dividido em parcelas iguais.</span>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="app-dialog-actions">
            <button type="button" onClick={close} disabled={busy} className="app-dialog-button">Cancelar</button>
            <button type="submit" disabled={busy} className="app-dialog-button app-dialog-button-primary">
              {busy ? 'Salvando…' : 'Salvar despesa'}
            </button>
          </div>
        </div>
      </form>
    </AppDialog>
  );
};

export default CreditCardExpenseForm;
