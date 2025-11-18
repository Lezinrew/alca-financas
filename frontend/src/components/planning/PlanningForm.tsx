import React, { useState, useEffect } from 'react';
import { formatCurrency } from '../../utils/api';
import { parseCurrencyString } from '../../lib/utils';
import CurrencyInput from '../ui/CurrencyInput';

interface Budget {
  monthly_income: number;
  savings_percentage: number;
  category_budgets?: Array<{ category_id: string; amount: number }>;
  credit_card_visualization?: 'purchase_date' | 'invoice_date';
}

interface PlanningFormProps {
  show: boolean;
  onHide: () => void;
  onSubmit: (data: any) => Promise<void>;
  categories: any[];
  budget: Budget | null;
  defaultIncome?: number;
}

const PlanningForm: React.FC<PlanningFormProps> = ({
  show,
  onHide,
  onSubmit,
  categories,
  budget,
  defaultIncome = 0
}) => {
  const [formData, setFormData] = useState({
    monthly_income: (budget?.monthly_income ?? defaultIncome ?? 0).toString(),
    savings_percentage: budget?.savings_percentage || 20,
    category_budgets: budget?.category_budgets || [],
    credit_card_visualization: budget?.credit_card_visualization || 'invoice_date'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(1);

  useEffect(() => {
    if (budget) {
      setFormData({
        monthly_income: budget.monthly_income?.toString() || '0',
        savings_percentage: budget.savings_percentage || 20,
        category_budgets: budget.category_budgets || [],
        credit_card_visualization: budget.credit_card_visualization || 'invoice_date'
      });
    } else {
      setFormData(prev => ({
        ...prev,
        monthly_income: (defaultIncome ?? 0).toString()
      }));
    }
  }, [budget, defaultIncome]);

  const handleChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleMonthlyIncomeChange = (value?: string) => {
    setFormData(prev => ({
      ...prev,
      monthly_income: value ?? ''
    }));
  };

  const handleCategoryBudgetChange = (categoryId: string, amountValue?: string) => {
    const amount = parseCurrencyString(amountValue ?? '');
    setFormData(prev => {
      const existing = prev.category_budgets.find(cb => cb.category_id === categoryId);
      const updated = existing
        ? prev.category_budgets.map(cb =>
            cb.category_id === categoryId ? { ...cb, amount } : cb
          )
        : [...prev.category_budgets, { category_id: categoryId, amount }];
      return { ...prev, category_budgets: updated };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (step === 1) {
      if (monthlyIncomeValue <= 0) {
          throw new Error('A renda mensal deve ser maior que zero');
        }
        setStep(2);
        setLoading(false);
        return;
      }

      if (step === 2) {
        setStep(3);
        setLoading(false);
        return;
      }

      await onSubmit({
        ...formData,
        monthly_income: monthlyIncomeValue,
      });
    } catch (err: any) {
      setError(err.message || 'Erro ao salvar planejamento');
    } finally {
      setLoading(false);
    }
  };

  const monthlyIncomeValue = parseCurrencyString(formData.monthly_income);
  const monthlyBudget = monthlyIncomeValue * (1 - formData.savings_percentage / 100);
  const monthlySavings = (monthlyIncomeValue * formData.savings_percentage) / 100;

  if (!show) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="modal-backdrop fixed inset-0 z-40"
        onClick={onHide}
      ></div>

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="modal-content w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="p-6 border-b border-slate-200 dark:border-slate-700/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={step === 1 ? onHide : () => setStep(1)}
                  className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                >
                  <i className="bi bi-arrow-left text-xl"></i>
                </button>
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                    Criação do planejamento mensal
                  </h2>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                    {step === 1 
                      ? 'Renda mensal' 
                      : step === 2 
                        ? 'Categorização de gastos' 
                        : 'Visualização das despesas do cartão'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onHide}
                className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                <i className="bi bi-x-lg"></i>
              </button>
            </div>
          </div>

          {/* Content */}
          <form onSubmit={handleSubmit} className="flex-1 overflow-auto">
            <div className="p-6">
              {error && (
                <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <p className="text-red-800 dark:text-red-200 text-sm">{error}</p>
                </div>
              )}

              {step === 1 ? (
                <div className="space-y-6">
                  {/* Renda Mensal */}
                  <div>
                    <label htmlFor="monthly_income" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Renda mensal
                    </label>
                    <div>
                      <label htmlFor="monthly_income_input" className="block text-sm text-slate-600 dark:text-slate-400 mb-2">
                        Quanto você ganha por mês?
                      </label>
                      {defaultIncome > 0 && !budget && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
                          Receita real identificada neste mês: <span className="font-semibold">{formatCurrency(defaultIncome)}</span>
                        </p>
                      )}
                      <CurrencyInput
                        id="monthly_income_input"
                        name="monthly_income"
                        value={formData.monthly_income}
                        onValueChange={handleMonthlyIncomeChange}
                        className="w-full px-4 py-3 text-2xl font-semibold text-purple-600 dark:text-purple-400 bg-transparent border-b-2 border-purple-600 dark:border-purple-400 focus:outline-none focus:border-purple-700 dark:focus:border-purple-300"
                        placeholder="0,00"
                      />
                    </div>
                  </div>

                  {/* Porcentagem de Economia */}
                  <div>
                    <label htmlFor="savings_percentage" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      E quanto você quer economizar por mês?
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      Essa porcentagem será utilizada para calcular seu orçamento mensal de gastos.
                    </p>
                    <div className="relative">
                      <input
                        type="number"
                        id="savings_percentage"
                        name="savings_percentage"
                        min="0"
                        max="100"
                        step="0.1"
                        value={formData.savings_percentage}
                        onChange={(e) => handleChange('savings_percentage', parseFloat(e.target.value) || 0)}
                        className="w-full px-4 py-3 text-2xl font-semibold text-purple-600 dark:text-purple-400 bg-transparent border-b-2 border-purple-600 dark:border-purple-400 focus:outline-none focus:border-purple-700 dark:focus:border-purple-300"
                        placeholder="20"
                      />
                      <span className="absolute right-0 top-3 text-2xl font-semibold text-purple-600 dark:text-purple-400">
                        %
                      </span>
                    </div>
                  </div>

                  {/* Resumo */}
                  <div className="bg-purple-600 dark:bg-purple-700 rounded-xl p-6 text-white">
                    <div className="flex items-center gap-3 mb-4">
                      <i className="bi bi-currency-dollar text-2xl"></i>
                      <div>
                        <p className="text-sm opacity-90">Seu orçamento mensal de gastos será:</p>
                        <p className="text-2xl font-bold text-emerald-300">{formatCurrency(monthlyBudget)}</p>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm opacity-90">E você economizará mensalmente:</p>
                      <p className="text-2xl font-bold text-emerald-300">{formatCurrency(monthlySavings)}</p>
                    </div>
                  </div>
                </div>
              ) : step === 2 ? (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-2">
                      Hora de planejar!
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                      Preencha os campos abaixo com seus limites de gastos para cada categoria.
                    </p>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-4">Categorias</p>
                  </div>

                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {categories.map((category: any) => {
                      const categoryBudget = formData.category_budgets.find(
                        cb => cb.category_id === String(category.id)
                      );
                      return (
                        <div
                          key={category.id}
                          className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className="w-10 h-10 rounded-lg flex items-center justify-center text-white"
                              style={{ backgroundColor: category.color }}
                            >
                              <i className={`bi bi-${category.icon || 'circle'}`}></i>
                            </div>
                            <div>
                              <p className="font-medium text-slate-900 dark:text-slate-100">{category.name}</p>
                              <p className="text-xs text-slate-500 dark:text-slate-400">Total</p>
                            </div>
                          </div>
                          <div className="relative w-36">
                            <CurrencyInput
                              name={`category-${category.id}`}
                              value={categoryBudget ? categoryBudget.amount.toString() : ''}
                              onValueChange={(value) => handleCategoryBudgetChange(category.id, value)}
                              className="w-full px-3 py-2 text-lg font-semibold text-purple-600 dark:text-purple-400 bg-transparent border-b-2 border-purple-600 dark:border-purple-400 focus:outline-none focus:border-purple-700 dark:focus:border-purple-300 text-right"
                              placeholder="0,00"
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Total Categorizado */}
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Total categorizado</p>
                        <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                          {formatCurrency(
                            formData.category_budgets.reduce((sum, cb) => sum + (cb.amount || 0), 0)
                          )}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          {formatCurrency(monthlyBudget - formData.category_budgets.reduce((sum, cb) => sum + (cb.amount || 0), 0))} sem categorização
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-2">
                      Como você quer visualizar suas despesas realizadas no cartão de crédito?
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                      Escolha a forma como você quer registrar suas compras realizadas no cartão.
                    </p>
                  </div>

                  <div className="space-y-4">
                    {/* Opção 1: Data da Compra */}
                    <label
                      className={`block p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        formData.credit_card_visualization === 'purchase_date'
                          ? 'border-purple-600 dark:border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                          : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 hover:border-purple-400 dark:hover:border-purple-600'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <input
                              type="radio"
                              name="credit_card_visualization"
                              value="purchase_date"
                              checked={formData.credit_card_visualization === 'purchase_date'}
                              onChange={(e) => handleChange('credit_card_visualization', e.target.value)}
                              className="w-5 h-5 text-purple-600 focus:ring-purple-500"
                            />
                            <h4 className="font-semibold text-slate-900 dark:text-slate-100">
                              Pela data da compra
                            </h4>
                          </div>
                          <p className="text-sm text-slate-600 dark:text-slate-400 ml-8">
                            As despesas realizadas no cartão serão contabilizadas no planejamento no dia em que forem realizadas.
                          </p>
                        </div>
                      </div>
                    </label>

                    {/* Opção 2: Data da Fatura */}
                    <label
                      className={`block p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        formData.credit_card_visualization === 'invoice_date'
                          ? 'border-purple-600 dark:border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                          : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 hover:border-purple-400 dark:hover:border-purple-600'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <input
                              type="radio"
                              name="credit_card_visualization"
                              value="invoice_date"
                              checked={formData.credit_card_visualization === 'invoice_date'}
                              onChange={(e) => handleChange('credit_card_visualization', e.target.value)}
                              className="w-5 h-5 text-purple-600 focus:ring-purple-500"
                            />
                            <h4 className="font-semibold text-slate-900 dark:text-slate-100">
                              Pela data da fatura
                            </h4>
                          </div>
                          <p className="text-sm text-slate-600 dark:text-slate-400 ml-8">
                            As despesas realizadas no cartão serão contabilizadas no planejamento apenas na data do vencimento da fatura.
                          </p>
                        </div>
                      </div>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
              <button
                type="button"
                onClick={onHide}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Salvando...
                  </>
                ) : step === 1 || step === 2 ? (
                  <>
                    Continuar
                    <i className="bi bi-arrow-right"></i>
                  </>
                ) : (
                  'Finalizar Planejamento'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
};

export default PlanningForm;

