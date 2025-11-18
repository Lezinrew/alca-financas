import React, { useState, useEffect } from 'react';
import CurrencyInput from '../ui/CurrencyInput';
import { parseCurrencyString } from '../../lib/utils';
import { CreditCard, CreditCardPayload } from '../../types/credit-card';

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
  show: boolean;
  onHide: () => void;
  onSubmit: (card: CreditCardPayload) => Promise<void>;
  card?: CreditCard | null;
}

const CreditCardForm: React.FC<CreditCardFormProps> = ({ show, onHide, onSubmit, card }) => {
  const [formData, setFormData] = useState<CreditCardFormData>({
    name: '',
    limit: '',
    closingDay: '1',
    dueDay: '5',
    color: '#6366f1',
    icon: 'credit-card',
    is_active: true,
    account_id: '',
    card_type: 'visa'
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [limitError, setLimitError] = useState<string>('');
  const [accounts, setAccounts] = useState<any[]>([]);
  const [saveAndCreateNew, setSaveAndCreateNew] = useState<boolean>(false);

  const cardTypes = [
    { value: 'visa', label: 'VISA Visa', icon: 'credit-card' },
    { value: 'mastercard', label: 'Mastercard', icon: 'credit-card' },
    { value: 'elo', label: 'ELO', icon: 'credit-card' },
    { value: 'amex', label: 'American Express', icon: 'credit-card' },
    { value: 'other', label: 'Outro', icon: 'credit-card' }
  ];

  // Carrega contas para o dropdown
  useEffect(() => {
    if (show) {
      loadAccounts();
    }
  }, [show]);

  const loadAccounts = async () => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/accounts`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        // Filtra apenas contas que não são cartões de crédito
        const filteredAccounts = data.filter((acc: any) => 
          acc.type !== 'credit_card' && acc.is_active
        );
        setAccounts(filteredAccounts);
        // Seleciona a primeira conta automaticamente se houver
        if (filteredAccounts.length > 0 && !formData.account_id) {
          setFormData(prev => ({ ...prev, account_id: filteredAccounts[0].id }));
        }
      }
    } catch (err) {
      console.error('Load accounts error:', err);
    }
  };

  // Preenche o formulário se estiver editando
  useEffect(() => {
    if (card && show) {
      setFormData({
        name: card.name || '',
        limit: card.limit?.toString() || '',
        closingDay: card.closingDay?.toString() || '1',
        dueDay: card.dueDay?.toString() || '5',
        color: card.color || '#6366f1',
        icon: card.icon || 'credit-card',
        is_active: card.is_active !== false,
        account_id: card.account_id || '',
        card_type: card.card_type || 'visa'
      });
    } else if (!card && show) {
      // Reset form for new card
      setFormData({
        name: '',
        limit: '',
        closingDay: '1',
        dueDay: '5',
        color: '#6366f1',
        icon: 'credit-card',
        is_active: true,
        account_id: accounts.length > 0 ? accounts[0].id : '',
        card_type: 'visa'
      });
    }
  }, [card, show, accounts]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const target = e.target;
    const fieldName = target.name as keyof CreditCardFormData;

    let nextValue: string | boolean = target.value;
    if (target instanceof HTMLInputElement && target.type === 'checkbox') {
      nextValue = target.checked;
    }

    setFormData(prev => ({
      ...prev,
      [fieldName]: (typeof nextValue === 'boolean' ? nextValue : String(nextValue)) as CreditCardFormData[typeof fieldName]
    }));
  };

  const handleLimitChange = (value?: string) => {
    const nextValue = value ?? '';
    setFormData(prev => ({ ...prev, limit: nextValue }));
    const numericValue = parseCurrencyString(nextValue);
    if (nextValue && numericValue <= 0) {
      setLimitError('Deve ter um valor diferente de 0');
    } else {
      setLimitError('');
    }
  };

  const handleSubmit = async (e?: React.FormEvent<HTMLFormElement>) => {
    if (e) {
      e.preventDefault();
    }
    setLoading(true);
    setError('');

    try {
      // Validações
      if (!formData.name.trim()) {
        throw new Error('Nome do cartão é obrigatório');
      }

      if (!formData.limit || parseCurrencyString(formData.limit) <= 0) {
        throw new Error('Limite deve ser um número válido maior que zero');
      }

      const closingDay = parseInt(formData.closingDay);
      const dueDay = parseInt(formData.dueDay);

      if (closingDay < 1 || closingDay > 31) {
        throw new Error('Dia de fechamento deve estar entre 1 e 31');
      }

      if (dueDay < 1 || dueDay > 31) {
        throw new Error('Dia de vencimento deve estar entre 1 e 31');
      }

      // Prepara dados para envio
      const submitData: CreditCardPayload = {
        name: formData.name.trim(),
        limit: parseCurrencyString(formData.limit),
        closingDay: closingDay,
        dueDay: dueDay,
        color: formData.color,
        icon: formData.icon,
        is_active: formData.is_active,
        account_id: formData.account_id,
        card_type: formData.card_type
      };

      await onSubmit(submitData);
      
      // Se "Salvar e criar novo" foi clicado, reseta o formulário
      if (saveAndCreateNew) {
        setFormData({
          name: '',
          limit: '',
          closingDay: '1',
          dueDay: '5',
          color: '#6366f1',
          icon: 'credit-card',
          is_active: true,
          account_id: accounts.length > 0 ? accounts[0].id : '',
          card_type: 'visa'
        });
        setLimitError('');
        setError('');
        setSaveAndCreateNew(false);
      }
    } catch (err) {
      setError((err as Error).message || 'Erro ao salvar cartão');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setError('');
      onHide();
    }
  };

  if (!show) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="modal-backdrop"
        onClick={handleClose}
      ></div>

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="modal-content pointer-events-auto max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <form onSubmit={handleSubmit}>
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700/50">
              <h2 className="text-xl font-semibold text-primary">
                {card ? 'Editar Cartão de Crédito' : 'Novo Cartão de Crédito'}
              </h2>
              <button
                type="button"
                onClick={handleClose}
                disabled={loading}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors disabled:opacity-50"
                aria-label="Fechar"
              >
                <i className="bi bi-x-lg text-xl"></i>
              </button>
            </div>

            {/* Body */}
            <div className="p-6">
              {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
                  <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
                  <span className="text-red-800 dark:text-red-200 text-sm">{error}</span>
                </div>
              )}

              <div className="space-y-5">
                {/* Limite */}
                <div>
                  <label htmlFor="card-limit" className="block text-sm font-medium text-secondary mb-2">
                    Limite
                  </label>
                  <div className="relative">
                    <CurrencyInput
                      id="card-limit"
                      name="limit"
                      className={`input-base ${limitError ? 'border-orange-500 dark:border-orange-500 focus:border-orange-500 focus:ring-orange-500' : ''}`}
                      value={formData.limit}
                      onValueChange={handleLimitChange}
                      required
                      disabled={loading}
                      placeholder="0,00"
                      autoComplete="off"
                      aria-required="true"
                    />
                    {limitError && (
                      <p className="mt-1 text-sm text-orange-600 dark:text-orange-400">{limitError}</p>
                    )}
                  </div>
                </div>

                {/* Descrição/Nome */}
                <div>
                  <label htmlFor="card-name" className="block text-sm font-medium text-secondary mb-2">
                    Descrição
                  </label>
                  <div className="relative">
                    <i className="bi bi-file-text absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"></i>
                    <input
                      type="text"
                      id="card-name"
                      name="name"
                      className="input-base pl-10"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      disabled={loading}
                      placeholder="Ex: Nubank, Inter, Itaú"
                      autoComplete="off"
                      aria-required="true"
                    />
                  </div>
                </div>

                {/* Tipo de Cartão */}
                <div>
                  <label htmlFor="card-type" className="block text-sm font-medium text-secondary mb-2">
                    Tipo de Cartão
                  </label>
                  <div className="relative">
                    <i className="bi bi-credit-card absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"></i>
                    <select
                      id="card-type"
                      name="card_type"
                      className="select-base pl-10"
                      value={formData.card_type}
                      onChange={handleChange}
                      disabled={loading}
                      aria-required="true"
                    >
                      {cardTypes.map(type => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Carteira/Conta */}
                <div>
                  <label htmlFor="card-account" className="block text-sm font-medium text-secondary mb-2">
                    Carteira
                  </label>
                  <div className="relative">
                    <i className="bi bi-building absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"></i>
                    <select
                      id="card-account"
                      name="account_id"
                      className="select-base pl-10"
                      value={formData.account_id}
                      onChange={handleChange}
                      disabled={loading || accounts.length === 0}
                      required
                      aria-required="true"
                    >
                      {accounts.length === 0 ? (
                        <option value="">Nenhuma conta disponível</option>
                      ) : (
                        accounts.map(account => (
                          <option key={account.id} value={account.id}>
                            {account.icon && <i className={`bi bi-${account.icon}`}></i>} {account.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>

                {/* Dia de Fechamento e Vencimento */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="card-closing-day" className="block text-sm font-medium text-secondary mb-2">
                      Dia de fechamento
                    </label>
                    <div className="relative">
                      <i className="bi bi-calendar absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"></i>
                      <select
                        id="card-closing-day"
                        name="closingDay"
                        className="select-base pl-10"
                        value={formData.closingDay}
                        onChange={handleChange}
                        required
                        disabled={loading}
                        aria-required="true"
                      >
                        {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                          <option key={day} value={day.toString()}>{day}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label htmlFor="card-due-day" className="block text-sm font-medium text-secondary mb-2">
                      Dia do vencimento
                    </label>
                    <div className="relative">
                      <i className="bi bi-calendar absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"></i>
                      <select
                        id="card-due-day"
                        name="dueDay"
                        className="select-base pl-10"
                        value={formData.dueDay}
                        onChange={handleChange}
                        required
                        disabled={loading}
                        aria-required="true"
                      >
                        {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                          <option key={day} value={day.toString()}>{day}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200 dark:border-slate-700/50">
              <button
                type="button"
                onClick={handleClose}
                disabled={loading}
                className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition-colors disabled:opacity-50"
              >
                <i className="bi bi-x-lg text-xl"></i>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSaveAndCreateNew(true);
                  handleSubmit();
                }}
                disabled={loading || !!limitError}
                className="px-4 py-2 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                SALVAR E CRIAR NOVO
              </button>
              <button
                type="submit"
                disabled={loading || !!limitError}
                onClick={() => setSaveAndCreateNew(false)}
                className="px-4 py-2 bg-slate-300 dark:bg-slate-600 hover:bg-slate-400 dark:hover:bg-slate-500 text-slate-800 dark:text-slate-100 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <i className="bi bi-hourglass-split animate-spin mr-2"></i>
                    Salvando...
                  </>
                ) : (
                  'SALVAR'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
};

export default CreditCardForm;

