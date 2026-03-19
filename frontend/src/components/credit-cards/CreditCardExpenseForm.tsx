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

      // Validação de data obrigatória
      if (!formData.date || formData.date === 'other') {
        throw new Error('Data é obrigatória');
      }

      const submitData = {
        ...formData,
        amount: amountValue,
        date: formData.date === 'today' ? new Date().toISOString() :
              formData.date === 'yesterday' ? new Date(Date.now() - 86400000).toISOString() :
              new Date(formData.date).toISOString(),
        // compatibilidade com backend: usa account_id como vínculo, não card_id
        account_id: formData.card_id,
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
      {/* Backdrop com blur */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[1040] animate-fade-in"
        onClick={onHide}
      ></div>

      {/* Modal */}
      <div className="fixed inset-0 z-[1050] flex items-center justify-center p-4 pointer-events-none">
        <div className="modal-content pointer-events-auto max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-scale-in">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700/50">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
              Nova despesa cartão de crédito
            </h2>
            <button
              type="button"
              onClick={onHide}
              disabled={loading}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors disabled:opacity-50"
              aria-label="Fechar"
            >
              <i className="bi bi-x-lg text-xl"></i>
            </button>
          </div>

            <form onSubmit={handleSubmit}>
              <div className="p-6">
                {error && (
                  <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2 animate-shake" role="alert">
                    <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
                    <span className="text-red-800 dark:text-red-200 text-sm">{error}</span>
                  </div>
                )}

                <div className="space-y-4">
                  {/* Valor */}
                  <div>
                    <label htmlFor="expense-amount" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Valor
                    </label>
                    <div className="relative">
                      <i className="bi bi-currency-dollar absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xl pointer-events-none"></i>
                      <CurrencyInput
                        id="expense-amount"
                        name="amount"
                        className="w-full h-14 pl-12 pr-4 text-2xl font-bold text-slate-900 dark:text-white bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all"
                        value={formData.amount}
                        onValueChange={handleAmountChange}
                        placeholder="0,00"
                        disabled={loading}
                        required
                        autoComplete="transaction-amount"
                      />
                    </div>
                  </div>

                  {/* Data - Botões de Seleção Rápida */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Data
                    </label>
                    <div className="flex gap-2" role="group">
                      {dateOptions.map((option) => (
                        <React.Fragment key={option.value}>
                          <input
                            type="radio"
                            className="sr-only"
                            name="date"
                            id={`date-${option.value}`}
                            value={option.value}
                            checked={formData.date === option.value || (option.value === 'other' && !['today', 'yesterday'].includes(formData.date))}
                            onChange={handleChange}
                            disabled={loading}
                          />
                          <label
                            htmlFor={`date-${option.value}`}
                            className={`flex-1 px-4 py-2 text-sm font-medium text-center rounded-lg border transition-all cursor-pointer ${
                              formData.date === option.value || (option.value === 'other' && !['today', 'yesterday'].includes(formData.date))
                                ? 'bg-blue-600 dark:bg-blue-500 border-blue-600 dark:border-blue-500 text-white'
                                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                            }`}
                          >
                            {option.label}
                          </label>
                        </React.Fragment>
                      ))}
                    </div>
                    {!['today', 'yesterday'].includes(formData.date) && (
                      <input
                        type="date"
                        name="date"
                        className="mt-2 w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all"
                        value={formData.date === 'other' ? '' : formData.date}
                        onChange={handleChange}
                        disabled={loading}
                        required
                      />
                    )}
                  </div>

                  {/* Descrição */}
                  <div>
                    <label htmlFor="expense-description" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Descrição
                    </label>
                    <div className="relative">
                      <i className="bi bi-chat-left-text absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                      <input
                        type="text"
                        id="expense-description"
                        name="description"
                        className="w-full h-11 pl-10 pr-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all"
                        value={formData.description}
                        onChange={handleChange}
                        placeholder="Digite a descrição"
                        disabled={loading}
                        autoComplete="off"
                      />
                    </div>
                  </div>

                  {/* Categoria */}
                  <div>
                    <label htmlFor="expense-category" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Categoria
                    </label>
                    <div className="relative">
                      <i className="bi bi-tag absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                      <select
                        id="expense-category"
                        name="category_id"
                        className="w-full h-11 pl-10 pr-10 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all appearance-none"
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
                      <i className="bi bi-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                    </div>
                  </div>

                  {/* Cartão de Crédito - Exibição apenas */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Cartão de crédito
                    </label>
                    <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div
                          className="rounded-lg flex items-center justify-center"
                          style={{
                            width: '48px',
                            height: '32px',
                            backgroundColor: card.color
                          }}
                        >
                          <i className="bi bi-credit-card-fill text-white text-lg"></i>
                        </div>
                        <div>
                          <div className="font-medium text-slate-900 dark:text-white">{card.name}</div>
                          <div className="text-xs text-slate-600 dark:text-slate-400">Fecha dia {card.closingDay}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Data de Vencimento */}
                  <div>
                    <label htmlFor="expense-due-date" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Data de vencimento
                    </label>
                    <div className="relative">
                      <i className="bi bi-calendar-check absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                      <select
                        id="expense-due-date"
                        className="w-full h-11 pl-10 pr-10 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all appearance-none"
                        disabled={loading}
                      >
                        <option>15 de dez de 2025</option>
                      </select>
                      <i className="bi bi-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"></i>
                    </div>
                  </div>

                  {/* Toggle: Ignorar transação */}
                  <div>
                    <label className="flex items-center gap-3 cursor-pointer group">
                      <input
                        type="checkbox"
                        id="ignore-transaction"
                        name="ignore_transaction"
                        checked={formData.ignore_transaction}
                        onChange={handleChange}
                        disabled={loading}
                        className="w-5 h-5 rounded border-slate-300 dark:border-slate-600 text-blue-600 focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">
                        Ignorar transação
                      </span>
                    </label>
                  </div>

                  {/* Botão Mais/Menos Detalhes */}
                  <div>
                    <button
                      type="button"
                      className="flex items-center gap-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                      onClick={() => setShowMoreDetails(!showMoreDetails)}
                    >
                      {showMoreDetails ? 'Menos detalhes' : 'Mais detalhes'}
                      <i className={`bi bi-chevron-${showMoreDetails ? 'up' : 'down'}`}></i>
                    </button>
                  </div>

                  {/* Seção de Mais Detalhes */}
                  {showMoreDetails && (
                    <>
                      {/* Tags */}
                      <div>
                        <label htmlFor="expense-tags" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                          Tags
                        </label>
                        <input
                          type="text"
                          id="expense-tags"
                          name="tags"
                          className="w-full h-11 px-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all"
                          value={formData.tags}
                          onChange={handleChange}
                          placeholder="Digite as tags"
                          disabled={loading}
                          autoComplete="off"
                        />
                      </div>

                      {/* Observação */}
                      <div>
                        <label htmlFor="expense-observation" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                          Observação
                        </label>
                        <textarea
                          id="expense-observation"
                          name="observation"
                          className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all resize-none"
                          rows={3}
                          value={formData.observation}
                          onChange={handleChange}
                          placeholder="Digite a observação"
                          disabled={loading}
                        ></textarea>
                      </div>

                      {/* Despesa Fixa */}
                      <div>
                        <label className="flex items-center gap-3 cursor-pointer group">
                          <input
                            type="checkbox"
                            id="is-fixed"
                            name="is_fixed"
                            checked={formData.is_fixed}
                            onChange={handleChange}
                            disabled={loading}
                            className="w-5 h-5 rounded border-slate-300 dark:border-slate-600 text-blue-600 focus:ring-2 focus:ring-blue-500/20 transition-all"
                          />
                          <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">
                            Despesa fixa
                          </span>
                        </label>
                      </div>

                      {/* Parcelado */}
                      <div>
                        <label className="flex items-center gap-3 cursor-pointer group">
                          <input
                            type="checkbox"
                            id="is-installment"
                            name="is_installment"
                            checked={formData.is_installment}
                            onChange={handleChange}
                            disabled={loading}
                            className="w-5 h-5 rounded border-slate-300 dark:border-slate-600 text-blue-600 focus:ring-2 focus:ring-blue-500/20 transition-all"
                          />
                          <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">
                            Parcelado
                          </span>
                        </label>
                      </div>

                      {/* Número de Parcelas */}
                      {formData.is_installment && (
                        <div>
                          <label htmlFor="expense-installments" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                            Número de parcelas
                          </label>
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              id="expense-installments"
                              name="installments"
                              className="flex-1 h-11 px-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all"
                              value={formData.installments}
                              onChange={handleChange}
                              min="2"
                              max="60"
                              disabled={loading}
                            />
                            <span className="px-3 py-2 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600 rounded-lg text-sm font-medium">
                              vezes
                            </span>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200 dark:border-slate-700/50">
                <button
                  type="button"
                  onClick={onHide}
                  disabled={loading}
                  className="px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? (
                    <>
                      <i className="bi bi-hourglass-split animate-spin"></i>
                      Salvando...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-check-lg"></i>
                      Salvar
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
    </>
  );
};

export default CreditCardExpenseForm;
