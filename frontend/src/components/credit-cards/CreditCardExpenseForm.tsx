import React, { useState, useEffect } from 'react';
import CurrencyInput from '../ui/CurrencyInput';
import { parseCurrencyString } from '../../lib/utils';
import { CreditCard } from '../../types/credit-card';

interface Category {
  id: string;
  name: string;
  type: string;
  color: string;
  icon: string;
}

interface CreditCardExpenseFormProps {
  show: boolean;
  onHide: () => void;
  onSubmit: (data: any) => Promise<void>;
  card: CreditCard;
  categories: Category[];
}

interface CreditCardExpenseFormData {
  amount: string;
  date: string;
  description: string;
  category_id: string;
  card_id: string;
  tags: string;
  observation: string;
  is_fixed: boolean;
  is_installment: boolean;
  installments: number;
  ignore_transaction: boolean;
}

const CreditCardExpenseForm: React.FC<CreditCardExpenseFormProps> = ({
  show,
  onHide,
  onSubmit,
  card,
  categories
}) => {
  const initialFormState: CreditCardExpenseFormData = {
    amount: '',
    date: 'today',
    description: '',
    category_id: '',
    card_id: card.id,
    tags: '',
    observation: '',
    is_fixed: false,
    is_installment: false,
    installments: 2,
    ignore_transaction: false
  };

  const [formData, setFormData] = useState<CreditCardExpenseFormData>(initialFormState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  useEffect(() => {
    if (show) {
      setFormData({
        ...initialFormState,
        card_id: card.id
      });
      setError('');
      setShowMoreDetails(false);
    }
  }, [show, card.id]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const target = e.target;
    const { name, value } = target;
    const fieldName = name as keyof CreditCardExpenseFormData;

    let nextValue: string | number | boolean = value;
    if (target instanceof HTMLInputElement && target.type === 'checkbox') {
      nextValue = target.checked;
    } else if (fieldName === 'installments') {
      nextValue = Number(value) || 0;
    }

    setFormData(prev => ({
      ...prev,
      [fieldName]: nextValue as CreditCardExpenseFormData[typeof fieldName]
    }));
    setError('');
  };

  const handleAmountChange = (value?: string) => {
    setFormData(prev => ({
      ...prev,
      amount: value ?? ''
    }));
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Validações
      const amountValue = parseCurrencyString(formData.amount);

      if (amountValue <= 0) {
        throw new Error('Deve ter um valor diferente de 0');
      }

      if (!formData.category_id) {
        throw new Error('Categoria é obrigatória');
      }

      const submitData = {
        ...formData,
        amount: amountValue,
        date: formData.date === 'today' ? new Date().toISOString() :
              formData.date === 'yesterday' ? new Date(Date.now() - 86400000).toISOString() :
              new Date(formData.date).toISOString()
      };

      await onSubmit(submitData);
    } catch (err: any) {
      console.error('Erro ao salvar despesa:', err);
      setError(err.message || 'Erro ao salvar despesa');
    } finally {
      setLoading(false);
    }
  };

  const dateOptions = [
    { value: 'today', label: 'Hoje' },
    { value: 'yesterday', label: 'Ontem' },
    { value: 'other', label: 'Outros...' }
  ];

  const expenseCategories = categories.filter(cat => cat.type === 'expense');

  if (!show) return null;

  return (
    <>
      <div className="modal-backdrop fade show" style={{ position: 'fixed', zIndex: 1040 }}></div>
      <div className="modal fade show" style={{ display: 'block', zIndex: 1050 }} tabIndex={-1} role="dialog">
        <div className="modal-dialog modal-lg" role="document">
          <div className="modal-content">
            {/* Header */}
            <div className="modal-header">
              <h5 className="modal-title">Nova despesa cartão de crédito</h5>
              <button
                type="button"
                className="btn-close"
                onClick={onHide}
                disabled={loading}
                aria-label="Fechar"
              ></button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {error && (
                  <div className="alert alert-danger mb-3" role="alert">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    {error}
                  </div>
                )}

                <div className="row g-3">
                  {/* Valor */}
                  <div className="col-12">
                    <label htmlFor="expense-amount" className="form-label">Valor</label>
                    <CurrencyInput
                      id="expense-amount"
                      name="amount"
                      className="form-control form-control-lg border-0 border-bottom rounded-0 px-0 text-primary fw-bold fs-3"
                      value={formData.amount}
                      onValueChange={handleAmountChange}
                      placeholder="0,00"
                      disabled={loading}
                      required
                      autoComplete="transaction-amount"
                    />
                  </div>

                  {/* Data - Botões de Seleção Rápida */}
                  <div className="col-12">
                    <label className="form-label">Data</label>
                    <div className="btn-group w-100" role="group">
                      {dateOptions.map((option) => (
                        <React.Fragment key={option.value}>
                          <input
                            type="radio"
                            className="btn-check"
                            name="date"
                            id={`date-${option.value}`}
                            value={option.value}
                            checked={formData.date === option.value || (option.value === 'other' && !['today', 'yesterday'].includes(formData.date))}
                            onChange={handleChange}
                            disabled={loading}
                          />
                          <label className="btn btn-outline-primary" htmlFor={`date-${option.value}`}>
                            {option.label}
                          </label>
                        </React.Fragment>
                      ))}
                    </div>
                    {!['today', 'yesterday'].includes(formData.date) && (
                      <input
                        type="date"
                        name="date"
                        className="form-control mt-2"
                        value={formData.date === 'other' ? '' : formData.date}
                        onChange={handleChange}
                        disabled={loading}
                      />
                    )}
                  </div>

                  {/* Descrição */}
                  <div className="col-12">
                    <label htmlFor="expense-description" className="form-label">Descrição</label>
                    <input
                      type="text"
                      id="expense-description"
                      name="description"
                      className="form-control"
                      value={formData.description}
                      onChange={handleChange}
                      placeholder="Digite a descrição"
                      disabled={loading}
                      autoComplete="off"
                    />
                  </div>

                  {/* Categoria */}
                  <div className="col-12">
                    <label htmlFor="expense-category" className="form-label">Categoria</label>
                    <select
                      id="expense-category"
                      name="category_id"
                      className="form-select"
                      value={formData.category_id}
                      onChange={handleChange}
                      required
                      disabled={loading}
                    >
                      <option value="">Selecionar categoria</option>
                      {expenseCategories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Cartão de Crédito - Exibição apenas */}
                  <div className="col-12">
                    <label className="form-label">Cartão de crédito</label>
                    <div className="p-3 bg-light dark:bg-slate-700 rounded">
                      <div className="d-flex align-items-center gap-3">
                        <div
                          className="rounded"
                          style={{
                            width: '40px',
                            height: '26px',
                            backgroundColor: card.color,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                        >
                          <i className="bi bi-credit-card-fill text-white"></i>
                        </div>
                        <div>
                          <div className="fw-medium">{card.name}</div>
                          <div className="small text-muted">Fecha dia {card.closingDay}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Data de Vencimento */}
                  <div className="col-12">
                    <label htmlFor="expense-due-date" className="form-label">Data de vencimento</label>
                    <select
                      id="expense-due-date"
                      className="form-select"
                      disabled={loading}
                    >
                      <option>15 de dez de 2025</option>
                    </select>
                  </div>

                  {/* Toggle: Ignorar transação */}
                  <div className="col-12">
                    <div className="form-check form-switch">
                      <input
                        type="checkbox"
                        className="form-check-input"
                        id="ignore-transaction"
                        name="ignore_transaction"
                        checked={formData.ignore_transaction}
                        onChange={handleChange}
                        disabled={loading}
                      />
                      <label className="form-check-label" htmlFor="ignore-transaction">
                        Ignorar transação
                      </label>
                    </div>
                  </div>

                  {/* Botão Mais/Menos Detalhes */}
                  <div className="col-12">
                    <button
                      type="button"
                      className="btn btn-link text-decoration-none p-0"
                      onClick={() => setShowMoreDetails(!showMoreDetails)}
                    >
                      {showMoreDetails ? 'Menos detalhes' : 'Mais detalhes'}
                      <i className={`bi bi-chevron-${showMoreDetails ? 'up' : 'down'} ms-2`}></i>
                    </button>
                  </div>

                  {/* Seção de Mais Detalhes */}
                  {showMoreDetails && (
                    <>
                      {/* Tags */}
                      <div className="col-12">
                        <label htmlFor="expense-tags" className="form-label">Tags</label>
                        <input
                          type="text"
                          id="expense-tags"
                          name="tags"
                          className="form-control"
                          value={formData.tags}
                          onChange={handleChange}
                          placeholder="Digite as tags"
                          disabled={loading}
                          autoComplete="off"
                        />
                      </div>

                      {/* Observação */}
                      <div className="col-12">
                        <label htmlFor="expense-observation" className="form-label">Observação</label>
                        <textarea
                          id="expense-observation"
                          name="observation"
                          className="form-control"
                          rows={3}
                          value={formData.observation}
                          onChange={handleChange}
                          placeholder="Digite a observação"
                          disabled={loading}
                        ></textarea>
                      </div>

                      {/* Despesa Fixa */}
                      <div className="col-12">
                        <div className="form-check form-switch">
                          <input
                            type="checkbox"
                            className="form-check-input"
                            id="is-fixed"
                            name="is_fixed"
                            checked={formData.is_fixed}
                            onChange={handleChange}
                            disabled={loading}
                          />
                          <label className="form-check-label" htmlFor="is-fixed">
                            Despesa fixa
                          </label>
                        </div>
                      </div>

                      {/* Parcelado */}
                      <div className="col-12">
                        <div className="form-check form-switch">
                          <input
                            type="checkbox"
                            className="form-check-input"
                            id="is-installment"
                            name="is_installment"
                            checked={formData.is_installment}
                            onChange={handleChange}
                            disabled={loading}
                          />
                          <label className="form-check-label" htmlFor="is-installment">
                            Parcelado
                          </label>
                        </div>
                      </div>

                      {/* Número de Parcelas */}
                      {formData.is_installment && (
                        <div className="col-12">
                          <label htmlFor="expense-installments" className="form-label">Número de parcelas</label>
                          <div className="input-group">
                            <input
                              type="number"
                              id="expense-installments"
                              name="installments"
                              className="form-control"
                              value={formData.installments}
                              onChange={handleChange}
                              min="2"
                              max="60"
                              disabled={loading}
                            />
                            <span className="input-group-text">vezes</span>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onHide}
                  disabled={loading}
                >
                  Salvar e criar nova
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="loading-spinner me-2"></span>
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

export default CreditCardExpenseForm;
