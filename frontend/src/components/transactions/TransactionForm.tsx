import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import CurrencyInput from '../ui/CurrencyInput';
import {
  TransactionCategory,
  TransactionRecord,
  TransactionSubmitPayload,
  TransactionStatus,
  TransactionType,
} from '../../types/transaction';
import { parseCurrencyString } from '../../lib/utils';
import { accountsAPI } from '../../utils/api';

interface TransactionFormData {
  description: string;
  amount: string;
  type: TransactionType;
  category_id: string;
  account_id: string;
  date: string;
  is_recurring: boolean;
  installments: number;
  status: TransactionStatus;
  responsible_person: string;
}

interface TransactionFormProps {
  show: boolean;
  onHide: () => void;
  onSubmit: (transaction: TransactionSubmitPayload) => Promise<void>;
  categories: TransactionCategory[];
  transaction?: TransactionRecord | null;
  defaultType?: TransactionType;
}

const TransactionForm: React.FC<TransactionFormProps> = ({
  show,
  onHide,
  onSubmit,
  categories,
  transaction,
  defaultType = 'expense',
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<TransactionFormData>({
    description: '',
    amount: '',
    type: defaultType,
    category_id: '',
    account_id: '',
    date: new Date().toISOString().split('T')[0],
    is_recurring: false,
    installments: 1,
    status: 'pending',
    responsible_person: 'Leandro'
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [accounts, setAccounts] = useState<any[]>([]);

  // Carrega contas ao montar o componente
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const response = await accountsAPI.getAll();
        if (response.data) {
          const data = response.data;
          console.log('TransactionForm: Dados brutos da API:', data);
          
          // Garante que data seja um array
          const accountsArray = Array.isArray(data) ? data : [];
          console.log('TransactionForm: Total de contas recebidas:', accountsArray.length);
          
          // Filtra apenas contas ativas e exclui cartões de crédito
          // O backend já converte _id para id, mas vamos garantir
          const activeAccounts = accountsArray
            .filter((acc: any) => {
              // Considera is_active como true se não estiver definido (compatibilidade)
              const isActive = acc.is_active !== false;
              const isNotCreditCard = acc.type !== 'credit_card';
              return isActive && isNotCreditCard;
            })
            .map((acc: any) => ({
              ...acc,
              id: acc.id || acc._id || '',
              name: acc.name || 'Sem nome'
            }))
            .filter((acc: any) => acc.id); // Remove contas sem ID válido
          
          console.log('TransactionForm: Contas filtradas e normalizadas:', activeAccounts);
          console.log('TransactionForm: Número de contas disponíveis:', activeAccounts.length);
          setAccounts(activeAccounts);
        } else {
          console.error('Erro ao carregar contas: resposta não OK', response.status);
          const errorText = await response.text();
          console.error('Erro detalhado:', errorText);
        }
      } catch (err) {
        console.error('Erro ao carregar contas:', err);
        setAccounts([]); // Garante que accounts seja sempre um array
      }
    };
    
    if (show) {
      loadAccounts();
    }
  }, [show]);

  // Preenche o formulário se estiver editando
  useEffect(() => {
    if (transaction) {
      // Normaliza a data para garantir formato ISO
      let normalizedDate = '';
      if (transaction.date) {
        try {
          // Se já está no formato ISO (YYYY-MM-DD), usa diretamente
          if (/^\d{4}-\d{2}-\d{2}$/.test(transaction.date)) {
            normalizedDate = transaction.date;
          } else {
            // Tenta criar uma data a partir do valor
            const dateObj = new Date(transaction.date);
            if (!isNaN(dateObj.getTime())) {
              normalizedDate = dateObj.toISOString().split('T')[0];
            } else {
              // Se falhar, tenta normalizar usando a função normalizeDate
              try {
                normalizedDate = normalizeDate(transaction.date);
              } catch (normalizeErr) {
                console.error('Erro ao normalizar data:', normalizeErr);
                normalizedDate = new Date().toISOString().split('T')[0];
              }
            }
          }
        } catch (err) {
          console.error('Erro ao processar data:', err);
          normalizedDate = new Date().toISOString().split('T')[0];
        }
      } else {
        normalizedDate = new Date().toISOString().split('T')[0];
      }

      setFormData({
        description: transaction.description || '',
        amount: transaction.amount?.toString() || '',
        type: transaction.type || defaultType,
        category_id: transaction.category_id || '',
        account_id: transaction.account_id || '',
        date: normalizedDate,
        is_recurring: transaction.is_recurring || false,
        installments: transaction.installment_info?.total || 1,
        status: transaction.status || 'pending',
        responsible_person: transaction.responsible_person || 'Leandro',
      });
    } else {
      setFormData({
        description: '',
        amount: '',
        type: defaultType,
        category_id: '',
        account_id: '',
        date: new Date().toISOString().split('T')[0],
        is_recurring: false,
        installments: 1,
        status: 'pending',
        responsible_person: 'Leandro',
      });
    }
  }, [transaction, defaultType]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const target = e.target;
    const { name, value } = target;
    let nextValue: string | boolean | number = value;

    if (target instanceof HTMLInputElement && target.type === 'checkbox') {
      nextValue = target.checked;
    } else if (name === 'installments') {
      nextValue = Number(value) || 1;
    }

    setFormData(prev => ({
      ...prev,
      [name]: nextValue as TransactionFormData[keyof TransactionFormData],
    }));

    setError('');
  };

  const handleAmountChange = (value?: string) => {
    setFormData(prev => ({
      ...prev,
      amount: value ?? '',
    }));
    setError('');
  };

  // Função para normalizar a data para formato ISO (YYYY-MM-DD)
  const normalizeDate = (dateString: string): string => {
    if (!dateString) {
      throw new Error('Data é obrigatória');
    }

    // Se já está no formato ISO (YYYY-MM-DD), retorna como está
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
      return dateString;
    }

    // Tenta converter formato brasileiro (DD/MM/YYYY) para ISO
    const brazilianFormat = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dateString);
    if (brazilianFormat) {
      const [, day, month, year] = brazilianFormat;
      return `${year}-${month}-${day}`;
    }

    // Tenta criar uma data e converter para ISO
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      throw new Error('Data inválida. Use o formato DD/MM/YYYY ou selecione uma data válida.');
    }

    // Retorna no formato ISO (YYYY-MM-DD)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    
    // Se o input type="date" retornar um valor vazio, permite (será validado no submit)
    if (!value) {
      setFormData(prev => ({
        ...prev,
        date: value,
      }));
      setError('');
      return;
    }

    // O input type="date" sempre retorna no formato ISO (YYYY-MM-DD)
    // Mas vamos validar para garantir
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      setFormData(prev => ({
        ...prev,
        date: value,
      }));
      setError('');
    } else {
      // Se por algum motivo não estiver no formato correto, tenta normalizar
      try {
        const normalized = normalizeDate(value);
        setFormData(prev => ({
          ...prev,
          date: normalized,
        }));
        setError('');
      } catch (err) {
        setError('Data inválida. Por favor, selecione uma data válida usando o calendário.');
      }
    }
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
      
      const amountValue = parseCurrencyString(formData.amount);

      if (amountValue <= 0) {
        throw new Error('Valor deve ser positivo');
      }
      
      if (!formData.category_id) {
        throw new Error('Categoria é obrigatória');
      }
      
      // Normaliza a data para formato ISO (YYYY-MM-DD)
      const normalizedDate = normalizeDate(formData.date);
      
      // Valida se a data normalizada é válida
      const dateObj = new Date(normalizedDate + 'T00:00:00');
      if (isNaN(dateObj.getTime())) {
        throw new Error('Data inválida. Por favor, selecione uma data válida.');
      }

      // Garante que a data está no formato YYYY-MM-DD (sem hora)
      // O backend espera apenas a data, não o ISO completo
      const dateString = normalizedDate; // Já está no formato YYYY-MM-DD

      // Prepara dados para envio
      const submitData: TransactionSubmitPayload = {
        description: formData.description.trim(),
        amount: amountValue,
        type: formData.type,
        category_id: formData.category_id,
        account_id: formData.account_id || undefined,
        date: dateString, // Envia apenas YYYY-MM-DD
        is_recurring: formData.is_recurring,
        installments: parseInt(formData.installments.toString()) || 1,
        status: formData.status,
        responsible_person: formData.responsible_person
      };

      await onSubmit(submitData);
      // Se chegou aqui, o submit foi bem-sucedido
      // O componente pai (Transactions) deve fechar o modal
    } catch (err: any) {
      console.error('Erro ao salvar transação:', err);
      const errorMessage = err?.response?.data?.error || err?.message || 'Erro ao salvar transação';
      setError(errorMessage);
      // Não fecha o modal em caso de erro para o usuário ver a mensagem
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
    <>
      <div className="modal-backdrop fade show" style={{ position: 'fixed', zIndex: 1040 }}></div>
      <div className="modal fade show" style={{ display: 'block', zIndex: 1050 }} tabIndex={-1} role="dialog">
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
                  <label htmlFor="transaction-category" className="form-label">
                    <i className="bi bi-tag me-2"></i>
                    {t('transactions.category')}
                  </label>
                  <select
                    id="transaction-category"
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

                {/* Conta - Campo destacado */}
                <div className="col-md-6">
                  <label htmlFor="transaction-account" className="form-label">
                    <i className="bi bi-wallet2 me-2"></i>
                    Conta {formData.account_id && <span className="text-success">✓</span>}
                  </label>
                  <select
                    id="transaction-account"
                    name="account_id"
                    className={`form-select ${formData.account_id ? 'border-success' : 'border-warning'}`}
                    value={formData.account_id}
                    onChange={handleChange}
                    disabled={loading}
                  >
                    <option value="">Selecione uma conta</option>
                    {accounts.length > 0 ? (
                      accounts.map((account) => (
                        <option key={account.id || account._id} value={account.id || account._id}>
                          {account.name} {account.type && `(${account.type === 'checking' ? 'Conta Corrente' : account.type === 'savings' ? 'Poupança' : account.type === 'wallet' ? 'Carteira' : account.type === 'investment' ? 'Investimento' : account.type})`}
                        </option>
                      ))
                    ) : (
                      <option value="" disabled>Carregando contas...</option>
                    )}
                  </select>
                  {formData.account_id ? (
                    <div className="form-text text-success">
                      <i className="bi bi-check-circle me-1"></i>
                      Transação será associada à conta selecionada
                    </div>
                  ) : (
                    <div className="form-text text-warning">
                      <i className="bi bi-exclamation-triangle me-1"></i>
                      Recomendado: Associe a transação a uma conta para melhor controle
                    </div>
                  )}
                  {formData.account_id && accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id) && (
                    <div className="mt-2 p-2 bg-light rounded">
                      <small className="text-muted">
                        <i className={`bi bi-${accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id)?.icon || 'wallet2'} me-1`}></i>
                        <strong>{accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id)?.name}</strong>
                        {accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id)?.institution && (
                          <span className="ms-2">• {accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id)?.institution}</span>
                        )}
                      </small>
                    </div>
                  )}
                </div>

                {/* Descrição */}
                <div className="col-12">
                  <label htmlFor="transaction-description" className="form-label">{t('transactions.description')}</label>
                  <input
                    type="text"
                    id="transaction-description"
                    name="description"
                    className="form-control"
                    value={formData.description}
                    onChange={handleChange}
                    required
                    disabled={loading}
                    placeholder="Ex: Compras no supermercado"
                    autoComplete="transaction-description"
                  />
                </div>

                {/* Valor */}
                <div className="col-md-6">
                  <label htmlFor="transaction-amount" className="form-label">{t('transactions.amount')}</label>
                  <CurrencyInput
                    id="transaction-amount"
                    name="amount"
                    className="form-control"
                    value={formData.amount}
                    onValueChange={handleAmountChange}
                    placeholder="0,00"
                    disabled={loading}
                    required
                    autoComplete="transaction-amount"
                  />
                </div>

                {/* Data */}
                <div className="col-md-6">
                  <label htmlFor="transaction-date" className="form-label">{t('transactions.date')}</label>
                  <input
                    type="date"
                    id="transaction-date"
                    name="date"
                    className="form-control"
                    value={formData.date}
                    onChange={handleDateChange}
                    required
                    disabled={loading}
                    max={new Date().toISOString().split('T')[0]} // Opcional: limita a data máxima
                  />
                  {formData.date && (
                    <div className="form-text text-muted">
                      Data selecionada: {new Date(formData.date + 'T00:00:00').toLocaleDateString('pt-BR')}
                    </div>
                  )}
                </div>

                {/* Parcelamento */}
                <div className="col-md-6">
                  <label htmlFor="transaction-installments" className="form-label">{t('transactions.installments')}</label>
                  <input
                    type="number"
                    id="transaction-installments"
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

                {/* Responsável */}
                <div className="col-md-6">
                  <label htmlFor="transaction-responsible" className="form-label">Responsável</label>
                  <select
                    id="transaction-responsible"
                    name="responsible_person"
                    className="form-select"
                    value={formData.responsible_person}
                    onChange={handleChange}
                    disabled={loading}
                  >
                    <option value="Leandro">Leandro</option>
                    <option value="Glenda">Glenda</option>
                    <option value="Ambos">Ambos</option>
                  </select>
                </div>

                {/* Status (apenas visualização por enquanto) */}
                <div className="col-md-6">
                  <label htmlFor="transaction-status" className="form-label">Status</label>
                  <select
                    id="transaction-status"
                    name="status"
                    className="form-select"
                    value={formData.status}
                    onChange={handleChange}
                    disabled={loading}
                  >
                    <option value="pending">Pendente</option>
                    <option value="paid">Pago</option>
                    <option value="overdue">Atrasado</option>
                    <option value="cancelled">Cancelado</option>
                  </select>
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
    </>
  );
};

export default TransactionForm;