import React, { useState, useEffect, useRef } from 'react';
import { AppDialog } from '../shared/AppDialog';
import { useTranslation } from 'react-i18next';
import CurrencyInput from '../ui/CurrencyInput';
import {
  TransactionCategory,
  TransactionRecord,
  TransactionSubmitPayload,
  TransactionStatus,
  TransactionType,
} from '../../types/transaction';
import { parseCurrencyString, formatNumberToBR } from '../../lib/utils';
import { accountsAPI } from '../../utils/api';
import './transactions.css';

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
  responsiblePersons?: Array<{ name: string; count: number }>;
}

const TransactionForm: React.FC<TransactionFormProps> = ({
  show,
  onHide,
  onSubmit,
  categories,
  transaction,
  defaultType = 'expense',
  responsiblePersons = [],
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
    responsible_person: ''
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountsLoading, setAccountsLoading] = useState<boolean>(false);
  const [accountsError, setAccountsError] = useState<string>('');
  const submitLock = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  // Carrega contas ao montar o componente
  const loadAccounts = async () => {
    try {
      setAccountsLoading(true);
      setAccountsError('');
      const response = await accountsAPI.getAll();
      if (response.data) {
        const data = response.data;

        // Garante que data seja um array
        const accountsArray = Array.isArray(data) ? data : [];

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

        setAccounts(activeAccounts);
      } else {
        setAccountsError('Erro ao carregar contas. Tente novamente.');
      }
    } catch {
      setAccounts([]); // Garante que accounts seja sempre um array
      setAccountsError('Erro ao carregar contas. Verifique sua conexão.');
    } finally {
      setAccountsLoading(false);
    }
  };

  useEffect(() => {
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
              } catch {
                normalizedDate = new Date().toISOString().split('T')[0];
              }
            }
          }
        } catch {
          normalizedDate = new Date().toISOString().split('T')[0];
        }
      } else {
        normalizedDate = new Date().toISOString().split('T')[0];
      }

      setFormData({
        description: transaction.description || '',
        amount: formatNumberToBR(transaction.amount),
        type: transaction.type || defaultType,
        category_id: transaction.category_id || '',
        account_id: transaction.account_id || '',
        date: normalizedDate,
        is_recurring: transaction.is_recurring || false,
        installments: transaction.installment_info?.total || 1,
        status: transaction.status || 'pending',
        responsible_person: transaction.responsible_person || '',
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
        responsible_person: '',
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
      } catch {
        setError('Data inválida. Por favor, selecione uma data válida usando o calendário.');
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submitLock.current) return; // bloqueia duplo envio
    submitLock.current = true;
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

      if (!formData.account_id) {
        throw new Error('Conta é obrigatória');
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
        account_id: formData.account_id, // Validado como obrigatório acima
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
      const errorMessage = err?.response?.data?.error || err?.message || 'Erro ao salvar transação';
      setError(errorMessage);
      // Não fecha o modal em caso de erro para o usuário ver a mensagem
    } finally {
      submitLock.current = false;
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
  const selectedAccount = accounts.find((acc: any) => (acc.id || acc._id) === formData.account_id);
  const accountTypeLabel = (type?: string) => type === 'checking' ? 'Conta Corrente' : type === 'savings' ? 'Poupança' : type === 'wallet' ? 'Carteira' : type === 'investment' ? 'Investimento' : type;

  if (!show) return null;

  return (
    <AppDialog title={transaction ? t('transactions.edit') : t('transactions.add')} onClose={handleClose} busy={loading} initialFocus={firstFieldRef} size="lg">
      <form onSubmit={handleSubmit} className="app-dialog-body tx" noValidate>
        {error && (
          <div className="tx-form-error" role="alert">
            <i className="bi bi-exclamation-triangle-fill" aria-hidden="true"></i> {error}
          </div>
        )}

        <div className="tx-form-grid">
          {/* Tipo */}
          <fieldset className="tx-field" disabled={loading}>
            <legend className="tx-legend">{t('transactions.type')}</legend>
            <div className="tx-type-group">
              <label className="tx-type-option" htmlFor="income">
                <input
                  ref={formData.type === 'income' ? firstFieldRef : undefined}
                  type="radio"
                  name="type"
                  id="income"
                  value="income"
                  checked={formData.type === 'income'}
                  onChange={handleChange}
                />
                <i className="bi bi-arrow-up-circle" aria-hidden="true"></i>
                {t('transactions.income')}
              </label>
              <label className="tx-type-option" htmlFor="expense">
                <input
                  ref={formData.type !== 'income' ? firstFieldRef : undefined}
                  type="radio"
                  name="type"
                  id="expense"
                  value="expense"
                  checked={formData.type === 'expense'}
                  onChange={handleChange}
                />
                <i className="bi bi-arrow-down-circle" aria-hidden="true"></i>
                {t('transactions.expense')}
              </label>
            </div>
          </fieldset>

          {/* Categoria */}
          <div className="tx-field">
            <label htmlFor="transaction-category">{t('transactions.category')}</label>
            <select
              id="transaction-category"
              name="category_id"
              className="select-base"
              value={formData.category_id}
              onChange={handleChange}
              required
              disabled={loading}
            >
              <option value="">Selecionar categoria</option>
              {filteredCategories.map((category) => (
                <option key={category.id} value={category.id}>{category.name}</option>
              ))}
            </select>
          </div>

          {/* Conta */}
          <div className="tx-field">
            <label htmlFor="transaction-account">Conta {formData.account_id && <span className="tx-hint-success" aria-hidden="true">✓</span>}</label>
            <select
              id="transaction-account"
              name="account_id"
              className="select-base"
              value={formData.account_id}
              onChange={handleChange}
              disabled={loading || accountsLoading}
              aria-describedby="transaction-account-hint"
            >
              <option value="">Selecione uma conta</option>
              {accountsLoading ? (
                <option value="" disabled>Carregando contas...</option>
              ) : accounts.length > 0 ? (
                accounts.map((account) => (
                  <option key={account.id || account._id} value={account.id || account._id}>
                    {account.name} {account.type && `(${accountTypeLabel(account.type)})`}
                  </option>
                ))
              ) : (
                <option value="" disabled>Nenhuma conta disponível</option>
              )}
            </select>
            {accountsError && (
              <p className="tx-hint tx-hint-warning" role="alert">
                <i className="bi bi-exclamation-circle" aria-hidden="true"></i> {accountsError}{' '}
                <button type="button" onClick={loadAccounts} className="tx-button" disabled={accountsLoading}>
                  <i className="bi bi-arrow-clockwise" aria-hidden="true"></i> Tentar novamente
                </button>
              </p>
            )}
            <p id="transaction-account-hint" className={`tx-hint ${formData.account_id ? 'tx-hint-success' : 'tx-hint-warning'}`}>
              {formData.account_id
                ? 'Transação será associada à conta selecionada'
                : 'Recomendado: associe a transação a uma conta para melhor controle'}
            </p>
            {selectedAccount && (
              <p className="tx-hint">
                <i className={`bi bi-${selectedAccount.icon || 'wallet2'}`} aria-hidden="true"></i>{' '}
                <strong>{selectedAccount.name}</strong>
                {selectedAccount.institution && <span> • {selectedAccount.institution}</span>}
              </p>
            )}
          </div>

          {/* Descrição */}
          <div className="tx-field tx-form-full">
            <label htmlFor="transaction-description">{t('transactions.description')}</label>
            <input
              type="text"
              id="transaction-description"
              name="description"
              className="input-base"
              value={formData.description}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Ex: Compras no supermercado"
              autoComplete="off"
            />
          </div>

          {/* Valor */}
          <div className="tx-field">
            <label htmlFor="transaction-amount">{t('transactions.amount')}</label>
            <CurrencyInput
              id="transaction-amount"
              name="amount"
              className="input-base"
              value={formData.amount}
              onValueChange={handleAmountChange}
              placeholder="0,00"
              disabled={loading}
              required
              autoComplete="off"
            />
          </div>

          {/* Data */}
          <div className="tx-field">
            <label htmlFor="transaction-date">{t('transactions.date')}</label>
            <input
              type="date"
              id="transaction-date"
              name="date"
              className="input-base"
              value={formData.date}
              onChange={handleDateChange}
              required
              disabled={loading}
              max={new Date().toISOString().split('T')[0]}
            />
            {formData.date && (
              <p className="tx-hint">Data selecionada: {new Date(formData.date + 'T00:00:00').toLocaleDateString('pt-BR')}</p>
            )}
          </div>

          {/* Parcelamento */}
          <div className="tx-field">
            <label htmlFor="transaction-installments">{t('transactions.installments')}</label>
            <input
              type="number"
              id="transaction-installments"
              name="installments"
              className="input-base"
              value={formData.installments}
              onChange={handleChange}
              min="1"
              max="60"
              disabled={loading}
            />
            <p className="tx-hint">Para parcelar, defina um valor maior que 1</p>
          </div>

          {/* Recorrente */}
          <div className="tx-field">
            <label className="tx-check" htmlFor="is_recurring">
              <input
                type="checkbox"
                name="is_recurring"
                id="is_recurring"
                checked={formData.is_recurring}
                onChange={handleChange}
                disabled={loading}
              />
              {t('transactions.recurring')}
            </label>
            <p className="tx-hint">Transação se repete mensalmente</p>
          </div>

          {/* Responsável */}
          <div className="tx-field">
            <label htmlFor="transaction-responsible">Responsável</label>
            <input
              id="transaction-responsible"
              name="responsible_person"
              className="input-base"
              list="transaction-responsible-suggestions"
              value={formData.responsible_person}
              onChange={handleChange}
              disabled={loading}
              placeholder="Quem é o responsável?"
            />
            <datalist id="transaction-responsible-suggestions">
              {responsiblePersons.map((rp) => (
                <option key={rp.name} value={rp.name} />
              ))}
            </datalist>
          </div>

          {/* Status */}
          <div className="tx-field">
            <label htmlFor="transaction-status">Situação</label>
            <select
              id="transaction-status"
              name="status"
              className="select-base"
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

        <div className="app-dialog-actions">
          <button type="button" className="app-dialog-button" onClick={handleClose} disabled={loading}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="app-dialog-button app-dialog-button-primary" disabled={loading}>
            {loading ? 'Salvando…' : t('common.save')}
          </button>
        </div>
      </form>
    </AppDialog>
  );
};

export default TransactionForm;
