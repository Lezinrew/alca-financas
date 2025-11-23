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
      // Formata o limite com vírgula decimal
      const formatLimit = (limit?: number): string => {
        if (!limit && limit !== 0) return '';
        return limit.toLocaleString('pt-BR', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        });
      };

      setFormData({
        name: card.name || '',
        limit: formatLimit(card.limit),
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
      <div className="modal-backdrop fade show" style={{ position: 'fixed', zIndex: 1040 }} onClick={handleClose}></div>
      <div className="modal fade show" style={{ display: 'block', zIndex: 1050 }} tabIndex={-1} role="dialog">
        <div className="modal-dialog modal-lg" role="document" onClick={(e) => e.stopPropagation()}>
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                {card ? 'Editar Cartão de Crédito' : 'Novo Cartão de Crédito'}
              </h5>
              <button
                type="button"
                className="btn-close"
                onClick={handleClose}
                disabled={loading}
                aria-label="Fechar"
              ></button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {error && (
                  <div className="alert alert-danger" role="alert">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    {error}
                  </div>
                )}

                <div className="row g-3">
                  {/* Limite */}
                  <div className="col-12">
                    <label htmlFor="card-limit" className="form-label">
                      <i className="bi bi-currency-dollar me-2"></i>
                      Limite
                    </label>
                    <CurrencyInput
                      id="card-limit"
                      name="limit"
                      className={`form-control ${limitError ? 'border-warning' : ''}`}
                      value={formData.limit}
                      onValueChange={handleLimitChange}
                      required
                      disabled={loading}
                      placeholder="0,00"
                      autoComplete="off"
                      aria-required="true"
                    />
                    {limitError && (
                      <div className="form-text text-warning">
                        <i className="bi bi-exclamation-triangle-fill me-1"></i>
                        {limitError}
                      </div>
                    )}
                  </div>

                  {/* Descrição/Nome */}
                  <div className="col-12">
                    <label htmlFor="card-name" className="form-label">
                      <i className="bi bi-file-text me-2"></i>
                      Descrição
                    </label>
                    <input
                      type="text"
                      id="card-name"
                      name="name"
                      className="form-control"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      disabled={loading}
                      placeholder="Ex: Nubank, Inter, Itaú"
                      autoComplete="off"
                      aria-required="true"
                    />
                  </div>

                  {/* Tipo de Cartão */}
                  <div className="col-md-6">
                    <label htmlFor="card-type" className="form-label">
                      <i className="bi bi-credit-card me-2"></i>
                      Tipo de Cartão
                    </label>
                    <select
                      id="card-type"
                      name="card_type"
                      className="form-select"
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

                  {/* Carteira/Conta */}
                  <div className="col-md-6">
                    <label htmlFor="card-account" className="form-label">
                      <i className="bi bi-wallet2 me-2"></i>
                      Carteira
                    </label>
                    <select
                      id="card-account"
                      name="account_id"
                      className="form-select"
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
                            {account.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  {/* Dia de Fechamento e Vencimento */}
                  <div className="col-md-6">
                    <label htmlFor="card-closing-day" className="form-label">
                      <i className="bi bi-calendar me-2"></i>
                      Dia de fechamento
                    </label>
                    <select
                      id="card-closing-day"
                      name="closingDay"
                      className="form-select"
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

                  <div className="col-md-6">
                    <label htmlFor="card-due-day" className="form-label">
                      <i className="bi bi-calendar-check me-2"></i>
                      Dia do vencimento
                    </label>
                    <select
                      id="card-due-day"
                      name="dueDay"
                      className="form-select"
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

              {/* Footer */}
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleClose}
                  disabled={loading}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="btn btn-outline-primary"
                  onClick={() => {
                    setSaveAndCreateNew(true);
                    handleSubmit();
                  }}
                  disabled={loading || !!limitError}
                >
                  Salvar e Criar Novo
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !!limitError}
                  onClick={() => setSaveAndCreateNew(false)}
                >
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                      Salvando...
                    </>
                  ) : (
                    'Salvar'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default CreditCardForm;

