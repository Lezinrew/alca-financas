import React, { useState, useEffect, useRef, useId } from 'react';
import CurrencyInput from '../ui/CurrencyInput';
import { parseCurrencyString, formatNumberToBR } from '../../lib/utils';
import { CreditCard, CreditCardPayload } from '../../types/credit-card';
import { accountsAPI } from '../../utils/api';
import { AppDialog } from '../shared/AppDialog';
import { AccountRecord, apiErrorMessage } from './creditCardUtils';
import './credit-cards.css';

interface CreditCardFormData {
  name: string;
  limit: string;
  closingDay: string;
  dueDay: string;
  color: string;
  icon: string;
  is_active: boolean;
  account_id: string;
  card_type: string;
}

interface CreditCardFormProps {
  onHide: () => void;
  onSubmit: (card: CreditCardPayload) => Promise<void>;
  card?: CreditCard | null;
}

const cardTypes = [
  { value: 'visa', label: 'Visa' },
  { value: 'mastercard', label: 'Mastercard' },
  { value: 'elo', label: 'Elo' },
  { value: 'amex', label: 'American Express' },
  { value: 'other', label: 'Outro' },
];

const emptyForm = (accountId = ''): CreditCardFormData => ({
  name: '', limit: '', closingDay: '1', dueDay: '5', color: '#6366f1', icon: 'credit-card',
  is_active: true, account_id: accountId, card_type: 'visa',
});

const fromCard = (card: CreditCard): CreditCardFormData => ({
  name: card.name || '',
  limit: formatNumberToBR(card.limit),
  closingDay: card.closingDay?.toString() || '1',
  dueDay: card.dueDay?.toString() || '5',
  color: card.color || '#6366f1',
  icon: card.icon || 'credit-card',
  is_active: card.is_active !== false,
  account_id: card.account_id || '',
  card_type: card.card_type || 'visa',
});

/** Diálogo de criação/edição de cartão. Monte apenas enquanto estiver aberto. */
const CreditCardForm: React.FC<CreditCardFormProps> = ({ onHide, onSubmit, card }) => {
  const prefix = useId();
  const [formData, setFormData] = useState<CreditCardFormData>(() => (card ? fromCard(card) : emptyForm()));
  const initialRef = useRef(formData);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [limitError, setLimitError] = useState('');
  const [accounts, setAccounts] = useState<AccountRecord[]>([]);
  const submitting = useRef(false);
  const limitRef = useRef<HTMLInputElement>(null);

  // Carrega contas (carteiras) para o vínculo do cartão
  useEffect(() => {
    let active = true;
    accountsAPI.getAll().then(response => {
      if (!active) return;
      const list: AccountRecord[] = Array.isArray(response.data) ? response.data : [];
      const filtered = list.filter(acc => acc.type !== 'credit_card' && acc.is_active);
      setAccounts(filtered);
      if (filtered.length > 0) {
        setFormData(prev => {
          if (prev.account_id) return prev;
          const next = { ...prev, account_id: filtered[0].id };
          if (JSON.stringify(prev) === JSON.stringify(initialRef.current)) initialRef.current = next;
          return next;
        });
      }
    }).catch(() => { if (active) setError('Não foi possível carregar as carteiras. Feche e tente novamente.'); });
    return () => { active = false; };
  }, []);

  const isDirty = () => JSON.stringify(formData) !== JSON.stringify(initialRef.current);

  const close = () => {
    if (busy) return;
    if (isDirty() && !window.confirm('Descartar as alterações não salvas deste cartão?')) return;
    onHide();
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target;
    const fieldName = target.name as keyof CreditCardFormData;
    const nextValue: string | boolean = target instanceof HTMLInputElement && target.type === 'checkbox' ? target.checked : target.value;
    setFormData(prev => ({ ...prev, [fieldName]: nextValue }));
  };

  const handleLimitChange = (value?: string) => {
    const nextValue = value ?? '';
    setFormData(prev => ({ ...prev, limit: nextValue }));
    setLimitError(nextValue && parseCurrencyString(nextValue) <= 0 ? 'Deve ter um valor diferente de 0' : '');
  };

  const submit = async (createAnother: boolean) => {
    if (submitting.current) return;
    setError('');
    try {
      if (!formData.name.trim()) throw new Error('Nome do cartão é obrigatório');
      if (!formData.limit || parseCurrencyString(formData.limit) <= 0) throw new Error('Limite deve ser um número válido maior que zero');
      const closingDay = parseInt(formData.closingDay, 10);
      const dueDay = parseInt(formData.dueDay, 10);
      if (closingDay < 1 || closingDay > 31) throw new Error('Dia de fechamento deve estar entre 1 e 31');
      if (dueDay < 1 || dueDay > 31) throw new Error('Dia de vencimento deve estar entre 1 e 31');
      if (!formData.account_id) throw new Error('Selecione uma carteira para vincular o cartão');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dados inválidos');
      return;
    }

    submitting.current = true;
    setBusy(true);
    try {
      await onSubmit({
        name: formData.name.trim(),
        limit: parseCurrencyString(formData.limit),
        closingDay: parseInt(formData.closingDay, 10),
        dueDay: parseInt(formData.dueDay, 10),
        color: formData.color,
        icon: formData.icon,
        is_active: formData.is_active,
        account_id: formData.account_id,
        card_type: formData.card_type,
      });
      if (createAnother) {
        const next = emptyForm(accounts.length > 0 ? accounts[0].id : '');
        initialRef.current = next;
        setFormData(next);
        setLimitError('');
        limitRef.current?.focus();
      } else {
        initialRef.current = formData;
        onHide();
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível salvar o cartão. Seus dados foram mantidos. Tente novamente.'));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    void submit(false);
  };

  return (
    <AppDialog title={card ? 'Editar cartão de crédito' : 'Novo cartão de crédito'} onClose={close} busy={busy} initialFocus={limitRef} size="lg">
      <form onSubmit={handleSubmit} className="cc" noValidate>
        <div className="app-dialog-body">
          {error && (
            <p className="app-dialog-error mb-4" role="alert" style={{ marginTop: 0 }}>{error}</p>
          )}

          <div className="cc-form-grid">
            <div className="cc-field cc-span-2">
              <label htmlFor={`${prefix}-limit`}>Limite *</label>
              <CurrencyInput
                ref={limitRef}
                id={`${prefix}-limit`}
                name="limit"
                className="native-input-themed w-full"
                value={formData.limit}
                onValueChange={handleLimitChange}
                required
                disabled={busy}
                placeholder="0,00"
                autoComplete="off"
                aria-invalid={!!limitError}
                aria-describedby={limitError ? `${prefix}-limit-error` : undefined}
              />
              {limitError && <span id={`${prefix}-limit-error`} className="cc-field-hint" role="alert">{limitError}</span>}
            </div>

            <div className="cc-field cc-span-2">
              <label htmlFor={`${prefix}-name`}>Descrição *</label>
              <input
                type="text"
                id={`${prefix}-name`}
                name="name"
                className="native-input-themed w-full"
                value={formData.name}
                onChange={handleChange}
                required
                disabled={busy}
                placeholder="Ex: Nubank, Inter, Itaú"
                autoComplete="off"
              />
            </div>

            <div className="cc-field">
              <label htmlFor={`${prefix}-type`}>Tipo de cartão</label>
              <select id={`${prefix}-type`} name="card_type" className="native-select-themed !w-full" value={formData.card_type} onChange={handleChange} disabled={busy}>
                {cardTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
              </select>
            </div>

            <div className="cc-field">
              <label htmlFor={`${prefix}-account`}>Carteira *</label>
              <select
                id={`${prefix}-account`}
                name="account_id"
                className="native-select-themed !w-full"
                value={formData.account_id}
                onChange={handleChange}
                disabled={busy || accounts.length === 0}
                required
              >
                {accounts.length === 0
                  ? <option value="">Nenhuma conta disponível</option>
                  : accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}
              </select>
            </div>

            <div className="cc-field">
              <label htmlFor={`${prefix}-closing-day`}>Dia de fechamento</label>
              <select id={`${prefix}-closing-day`} name="closingDay" className="native-select-themed !w-full" value={formData.closingDay} onChange={handleChange} disabled={busy}>
                {Array.from({ length: 31 }, (_, i) => i + 1).map(day => <option key={day} value={day.toString()}>{day}</option>)}
              </select>
            </div>

            <div className="cc-field">
              <label htmlFor={`${prefix}-due-day`}>Dia do vencimento</label>
              <select id={`${prefix}-due-day`} name="dueDay" className="native-select-themed !w-full" value={formData.dueDay} onChange={handleChange} disabled={busy}>
                {Array.from({ length: 31 }, (_, i) => i + 1).map(day => <option key={day} value={day.toString()}>{day}</option>)}
              </select>
            </div>
          </div>

          <div className="app-dialog-actions">
            <button type="button" className="app-dialog-button" onClick={close} disabled={busy}>Cancelar</button>
            {!card && (
              <button type="button" className="app-dialog-button" onClick={() => void submit(true)} disabled={busy || !!limitError}>
                Salvar e criar novo
              </button>
            )}
            <button type="submit" className="app-dialog-button app-dialog-button-primary" disabled={busy || !!limitError}>
              {busy ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </div>
      </form>
    </AppDialog>
  );
};

export default CreditCardForm;
