import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

// Type definitions
interface Category {
  id: string;
  name: string;
  type: 'income' | 'expense';
  color?: string;
}

interface InstallmentInfo {
  total: number;
  current: number;
}

interface Transaction {
  id?: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  category_id: string;
  date: string;
  is_recurring?: boolean;
  installment_info?: InstallmentInfo;
}

interface TransactionFormData {
  description: string;
  amount: string;
  type: 'income' | 'expense';
  category_id: string;
  date: string;
  is_recurring: boolean;
  installments: number;
}

interface TransactionFormProps {
  show: boolean;
  onHide: () => void;
  onSubmit: (transaction: Omit<Transaction, 'id'> & { installments: number }) => Promise<void>;
  categories: Category[];
  transaction?: Transaction | null;
}

const TransactionForm: React.FC<TransactionFormProps> = ({ show, onHide, onSubmit, categories, transaction }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<TransactionFormData>({
    description: '',
    amount: '',
    type: 'expense',
    category_id: '',
    date: new Date().toISOString().split('T')[0],
    is_recurring: false,
    installments: 1
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  // Preenche o formulário se estiver editando
  useEffect(() => {
    if (transaction) {
      setFormData({
        description: transaction.description || '',
        amount: transaction.amount?.toString() || '',
        type: transaction.type || 'expense',
        category_id: transaction.category_id?.toString() || '',
        date: transaction.date ? new Date(transaction.date).toISOString().split('T')[0] : '',
        is_recurring: transaction.is_recurring || false,
        installments: transaction.installment_info?.total || 1
      });
    } else {
      // Reset form for new transaction
      setFormData({
        description: '',
        amount: '',
        type: 'expense',
        category_id: '',
        date: new Date().toISOString().split('T')[0],
        is_recurring: false,
        installments: 1
      });
    }
  }, [transaction]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type, checked } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Validações
      if (!formData.description.trim()) {
        throw new Error('Descrição é obrigatória');
      }
      
      if (!formData.amount || parseFloat(formData.amount) <= 0) {
        throw new Error('Valor deve ser positivo');
      }
      
      if (!formData.category_id) {
        throw new Error('Categoria é obrigatória');
      }
      
      if (!formData.date) {
        throw new Error('Data é obrigatória');
      }

      // Prepara dados para envio
      const submitData = {
        description: formData.description.trim(),
        amount: parseFloat(formData.amount),
        type: formData.type,
        category_id: formData.category_id,
        date: new Date(formData.date).toISOString(),
        is_recurring: formData.is_recurring,
        installments: parseInt(formData.installments) || 1
      };

      await onSubmit(submitData);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao salvar transação');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onHide();
    }
  };

  // Filtra categorias baseado no tipo selecionado
  const filteredCategories = categories.filter(cat => cat.type === formData.type);

  if (!show) return null;

  return (
    <div className="modal fade show" style={{ display: 'block' }} tabIndex="-1" role="dialog">
      <div className="modal-backdrop fade show" onClick={handleClose}></div>
      <div className="modal-dialog modal-lg" role="document">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">
              {transaction ? t('transactions.edit') : t('transactions.add')}
            </h5>
            <button
              type="button"
              className="btn-close"
              onClick={handleClose}
              disabled={loading}
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
                {/* Tipo */}
                <div className="col-md-6">
                  <label className="form-label">{t('transactions.type')}</label>
                  <div className="btn-group w-100" role="group">
                    <input
                      type="radio"
                      className="btn-check"
                      name="type"
                      id="income"
                      value="income"
                      checked={formData.type === 'income'}
                      onChange={handleChange}
                      disabled={loading}
                    />
                    <label className="btn btn-outline-success" htmlFor="income">
                      <i className="bi bi-arrow-up-circle me-2"></i>
                      {t('transactions.income')}
                    </label>

                    <input
                      type="radio"
                      className="btn-check"
                      name="type"
                      id="expense"
                      value="expense"
                      checked={formData.type === 'expense'}
                      onChange={handleChange}
                      disabled={loading}
                    />
                    <label className="btn btn-outline-danger" htmlFor="expense">
                      <i className="bi bi-arrow-down-circle me-2"></i>
                      {t('transactions.expense')}
                    </label>
                  </div>
                </div>

                {/* Categoria */}
                <div className="col-md-6">
                  <label className="form-label">{t('transactions.category')}</label>
                  <select
                    name="category_id"
                    className="form-select"
                    value={formData.category_id}
                    onChange={handleChange}
                    required
                    disabled={loading}
                  >
                    <option value="">Selecionar categoria</option>
                    {filteredCategories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Descrição */}
                <div className="col-12">
                  <label className="form-label">{t('transactions.description')}</label>
                  <input
                    type="text"
                    name="description"
                    className="form-control"
                    value={formData.description}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    placeholder="Ex: Compras no supermercado"
                  />
                </div>

                {/* Valor */}
                <div className="col-md-6">
                  <label className="form-label">{t('transactions.amount')}</label>
                  <div className="input-group">
                    <span className="input-group-text">R$</span>
                    <input
                      type="number"
                      name="amount"
                      className="form-control"
                      value={formData.amount}
                      onChange={handleChange}
                      step="0.01"
                      min="0.01"
                      required
                      disabled={loading}
                      placeholder="0,00"
                    />
                  </div>
                </div>

                {/* Data */}
                <div className="col-md-6">
                  <label className="form-label">{t('transactions.date')}</label>
                  <input
                    type="date"
                    name="date"
                    className="form-control"
                    value={formData.date}
                    onChange={handleChange}
                    required
                    disabled={loading}
                  />
                </div>

                {/* Parcelamento */}
                <div className="col-md-6">
                  <label className="form-label">{t('transactions.installments')}</label>
                  <input
                    type="number"
                    name="installments"
                    className="form-control"
                    value={formData.installments}
                    onChange={handleChange}
                    min="1"
                    max="60"
                    disabled={loading}
                  />
                  <div className="form-text">
                    Para parcelar, defina um valor maior que 1
                  </div>
                </div>

                {/* Recorrente */}
                <div className="col-md-6">
                  <div className="form-check mt-4">
                    <input
                      type="checkbox"
                      name="is_recurring"
                      className="form-check-input"
                      id="is_recurring"
                      checked={formData.is_recurring}
                      onChange={handleChange}
                      disabled={loading}
                    />
                    <label className="form-check-label" htmlFor="is_recurring">
                      {t('transactions.recurring')}
                    </label>
                  </div>
                  <div className="form-text">
                    Transação se repete mensalmente
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleClose}
                disabled={loading}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="loading-spinner me-2"></span>
                    {t('common.loading')}
                  </>
                ) : (
                  t('common.save')
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default TransactionForm;