import React, { useId, useRef, useState } from 'react';
import { Account, AccountType, AccountPayload } from '../../types/account';
import CurrencyInput from '../ui/CurrencyInput';
import { parseCurrencyString, formatNumberToBR } from '../../lib/utils';
import { AppDialog } from '../shared/AppDialog';
import { ACCOUNT_SAVE_ERROR } from './accountLabels';

interface AccountFormData {
  name: string;
  type: AccountType;
  institution: string;
  initial_balance: string;
  current_balance: string;
  color: string;
  icon: string;
  is_active: boolean;
}

interface AccountFormProps {
  onHide: () => void;
  /** Deve lançar em caso de falha; o formulário permanece aberto com mensagem fixa. */
  onSubmit: (account: AccountPayload) => Promise<void>;
  account?: Account | null;
}

interface AccountTypeOption {
  value: AccountType;
  label: string;
  icon: string;
}

// Cartão de crédito fica fora da lista: cartões são criados na página de cartões.
const accountTypes: AccountTypeOption[] = [
  { value: 'wallet', label: 'Carteira', icon: 'wallet2' },
  { value: 'checking', label: 'Conta Corrente', icon: 'bank' },
  { value: 'savings', label: 'Poupança', icon: 'piggy-bank' },
  { value: 'investment', label: 'Investimento', icon: 'graph-up-arrow' },
];

const availableColors: string[] = [
  '#6366f1', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280',
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
];

const availableIcons: string[] = [
  'wallet2', 'bank', 'credit-card', 'piggy-bank', 'cash-coin',
  'currency-dollar', 'graph-up-arrow', 'briefcase', 'house',
  'car-front', 'phone', 'laptop', 'gift',
];

function initialValues(account?: Account | null): AccountFormData {
  if (!account) {
    return { name: '', type: 'wallet', institution: '', initial_balance: '', current_balance: '', color: '#6366f1', icon: 'wallet2', is_active: true };
  }
  return {
    name: account.name || '',
    type: account.type || 'wallet',
    institution: account.institution || '',
    initial_balance: formatNumberToBR(account.initial_balance),
    current_balance: formatNumberToBR(account.current_balance ?? account.initial_balance),
    color: account.color || '#6366f1',
    icon: account.icon || 'wallet2',
    is_active: account.is_active !== false,
  };
}

const labelClass = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200';
const helpClass = 'mt-1 text-xs text-slate-500 dark:text-slate-400';

/** Monte uma instância nova a cada abertura (o estado inicial vem de `account`). */
const AccountForm: React.FC<AccountFormProps> = ({ onHide, onSubmit, account }) => {
  const [formData, setFormData] = useState<AccountFormData>(() => initialValues(account));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const prefix = useId();
  const id = (field: string) => `${prefix}-${field}`;

  const updateField = (name: keyof AccountFormData, value: string | boolean) => {
    setFormData(prev => {
      const next = { ...prev, [name]: typeof prev[name] === 'boolean' ? Boolean(value) : (value as string) };
      if (name === 'type' && typeof value === 'string') {
        const typeConfig = accountTypes.find(t => t.value === value);
        if (typeConfig) next.icon = typeConfig.icon;
      }
      return next;
    });
    setError('');
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target;
    const isCheckbox = target instanceof HTMLInputElement && target.type === 'checkbox';
    updateField(target.name as keyof AccountFormData, isCheckbox ? target.checked : target.value);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitting.current) return;
    setError('');

    const trimmedName = formData.name.trim();
    if (!trimmedName) {
      setError('Informe o nome da conta.');
      nameRef.current?.focus();
      return;
    }

    const submitData: AccountPayload = {
      name: trimmedName,
      type: formData.type,
      institution: formData.institution.trim(),
      initial_balance: parseCurrencyString(formData.initial_balance || '0'),
      color: formData.color || '#6366f1',
      icon: formData.icon || 'wallet2',
      is_active: formData.is_active !== false,
    };
    // Para contas novas o backend iguala current_balance ao initial_balance; ao editar, permite ajuste.
    if (account) {
      submitData.current_balance = parseCurrencyString(formData.current_balance || formData.initial_balance || '0');
    }

    submitting.current = true;
    setSaving(true);
    try {
      await onSubmit(submitData);
    } catch {
      setError(ACCOUNT_SAVE_ERROR);
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  };

  const close = () => { if (!submitting.current) onHide(); };

  return (
    <AppDialog title={account ? 'Editar conta' : 'Nova conta'} onClose={close} busy={saving} initialFocus={nameRef} size="lg">
      <form onSubmit={handleSubmit} className="p-4" noValidate>
        {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}

        {/* Prévia */}
        <div className="mb-4 text-center" aria-hidden="true">
          <div className="mx-auto mb-2 flex h-20 w-20 items-center justify-center rounded-full text-white" style={{ backgroundColor: formData.color }}>
            <i className={`bi bi-${formData.icon}`} style={{ fontSize: '2rem' }}></i>
          </div>
          <p className="font-semibold text-slate-900 dark:text-white">{formData.name || 'Nome da conta'}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{accountTypes.find(t => t.value === formData.type)?.label}</p>
        </div>

        <fieldset disabled={saving} className="space-y-4">
          <div>
            <label htmlFor={id('name')} className={labelClass}>Nome da conta *</label>
            <input ref={nameRef} type="text" id={id('name')} name="name" value={formData.name} onChange={handleChange} required
              placeholder="Ex: Carteira Principal, Banco do Brasil" autoComplete="off" className="native-input-themed min-h-[44px] w-full" />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor={id('type')} className={labelClass}>Tipo de conta *</label>
              <select id={id('type')} name="type" value={formData.type} onChange={handleChange} className="native-select-themed min-h-[44px] w-full">
                {accountTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
              </select>
            </div>

            <div>
              <label htmlFor={id('initial-balance')} className={labelClass}>Saldo inicial</label>
              <CurrencyInput id={id('initial-balance')} name="initial_balance" value={formData.initial_balance}
                onValueChange={value => updateField('initial_balance', value ?? '')} placeholder="0,00" autoComplete="off"
                aria-describedby={id('initial-balance-help')} className="native-input-themed min-h-[44px] w-full" />
              <p id={id('initial-balance-help')} className={helpClass}>Saldo quando a conta foi criada.</p>
            </div>

            {account && (
              <div>
                <label htmlFor={id('current-balance')} className={labelClass}>Saldo atual</label>
                <CurrencyInput id={id('current-balance')} name="current_balance" value={formData.current_balance}
                  onValueChange={value => updateField('current_balance', value ?? '')} placeholder="0,00" autoComplete="off"
                  aria-describedby={id('current-balance-help')} className="native-input-themed min-h-[44px] w-full" />
                <p id={id('current-balance-help')} className={helpClass}>Ajuste se necessário. As próximas transações atualizam este valor automaticamente.</p>
              </div>
            )}

            <div className={account ? '' : 'sm:col-span-2'}>
              <label htmlFor={id('institution')} className={labelClass}>Instituição (opcional)</label>
              <input type="text" id={id('institution')} name="institution" value={formData.institution} onChange={handleChange}
                placeholder="Ex: Banco do Brasil, Nubank, Caixa" autoComplete="organization" className="native-input-themed min-h-[44px] w-full" />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <fieldset>
              <legend className={labelClass}>Cor</legend>
              <div className="mb-2 flex flex-wrap gap-2">
                {availableColors.map(color => (
                  <button key={color} type="button" aria-label={`Cor ${color}`} aria-pressed={formData.color === color}
                    className={`h-9 w-9 rounded-full border-2 ${formData.color === color ? 'border-slate-900 dark:border-white ring-2 ring-offset-2 ring-slate-400' : 'border-slate-200 dark:border-slate-600'}`}
                    style={{ backgroundColor: color }} onClick={() => updateField('color', color)} />
                ))}
              </div>
              <label htmlFor={id('color')} className="text-xs text-slate-500 dark:text-slate-400">Cor personalizada</label>
              <input type="color" id={id('color')} name="color" value={formData.color} onChange={handleChange} className="ml-2 h-9 w-12 cursor-pointer rounded border border-slate-300 dark:border-slate-600" />
            </fieldset>

            <fieldset>
              <legend className={labelClass}>Ícone</legend>
              <div className="flex flex-wrap gap-1">
                {availableIcons.map(icon => (
                  <button key={icon} type="button" aria-label={`Ícone ${icon}`} aria-pressed={formData.icon === icon}
                    className={`flex h-10 w-10 items-center justify-center rounded-lg border text-lg ${formData.icon === icon ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700'}`}
                    onClick={() => updateField('icon', icon)}>
                    <i className={`bi bi-${icon}`}></i>
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          <div>
            <label htmlFor={id('is-active')} className="flex min-h-[44px] items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
              <input type="checkbox" id={id('is-active')} name="is_active" checked={formData.is_active} onChange={handleChange} aria-describedby={id('is-active-help')} />
              Conta ativa
            </label>
            <p id={id('is-active-help')} className={helpClass}>Contas inativas não aparecem nos relatórios.</p>
          </div>
        </fieldset>

        <div className="mt-5 flex justify-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-700">
          <button type="button" onClick={close} disabled={saving} className="min-h-[44px] rounded-lg border border-slate-300 px-4 text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-100">Cancelar</button>
          <button type="submit" disabled={saving} className="min-h-[44px] rounded-lg bg-indigo-600 px-4 font-medium text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50">{saving ? 'Salvando…' : 'Salvar conta'}</button>
        </div>
      </form>
    </AppDialog>
  );
};

export default AccountForm;
