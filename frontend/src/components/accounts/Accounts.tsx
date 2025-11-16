import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency } from '../../utils/api';
import AccountForm from './AccountForm';
import AccountCard from './AccountCard';

interface Account {
  id: number;
  name: string;
  type: 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';
  current_balance: number;
  initial_balance: number;
  institution?: string;
  color: string;
  icon?: string;
  is_active: boolean;
}

const Accounts: React.FC = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [showForm, setShowForm] = useState<boolean>(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      loadAccounts();
    }
  }, [isAuthenticated, authLoading]);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      setError('');

      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/accounts`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Erro ao carregar contas');
      }

      const data = await response.json();
      setAccounts(data);
    } catch (err) {
      setError('Erro ao carregar contas');
      console.error('Load accounts error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddAccount = () => {
    setEditingAccount(null);
    setShowForm(true);
  };

  const handleEditAccount = (account: Account) => {
    setEditingAccount(account);
    setShowForm(true);
  };

  const handleDeleteAccount = async (accountId: number) => {
    if (!window.confirm('Tem certeza que deseja excluir esta conta?')) return;

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/accounts/${accountId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao deletar conta');
      }

      await loadAccounts();
    } catch (err: any) {
      setError(err.message || 'Erro ao deletar conta');
      console.error('Delete account error:', err);
    }
  };

  const handleFormSubmit = async (formData: any) => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const url = editingAccount
        ? `${API_URL}/api/accounts/${editingAccount.id}`
        : `${API_URL}/api/accounts`;

      const response = await fetch(url, {
        method: editingAccount ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao salvar conta');
      }

      setShowForm(false);
      setEditingAccount(null);
      await loadAccounts();
    } catch (err: any) {
      throw err;
    }
  };

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600">Carregando contas...</p>
        </div>
      </div>
    );
  }

  const activeAccounts = accounts.filter(acc => acc.is_active);
  const totalBalance = activeAccounts.reduce((sum, acc) => sum + (acc.current_balance || 0), 0);
  const projectedBalance = activeAccounts.reduce((sum, acc) => {
    // Saldo previsto = saldo atual (por enquanto, pode ser melhorado com transações futuras)
    return sum + (acc.current_balance || 0);
  }, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Contas</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie suas contas bancárias e carteiras</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {/* Layout Principal */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Coluna Esquerda - Contas */}
        <div className="lg:col-span-3 space-y-3">
          {/* Card Nova Conta */}
          <div
            onClick={handleAddAccount}
            className="card-base border-2 border-dashed border-slate-300 dark:border-slate-700 p-8 text-center cursor-pointer hover:border-purple-500 dark:hover:border-purple-500 hover:bg-purple-50/50 dark:hover:bg-purple-900/10"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-purple-600 to-blue-600 rounded-full flex items-center justify-center mx-auto mb-3">
              <i className="bi bi-plus-lg text-white text-2xl"></i>
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-1">Nova conta</h3>
            <p className="text-xs text-slate-500 dark:text-slate-300">Adicione uma nova conta bancária ou carteira</p>
          </div>

          {/* Lista de Contas */}
          {activeAccounts.length === 0 ? (
            <div className="card-base p-8 text-center">
              <i className="bi bi-wallet2 text-5xl text-slate-300 dark:text-slate-600 mb-3 block"></i>
              <h5 className="text-base font-semibold text-slate-700 dark:text-white mb-1">Nenhuma conta cadastrada</h5>
              <p className="text-sm text-slate-500 dark:text-slate-300">Comece adicionando sua primeira conta</p>
            </div>
          ) : (
            <div className="space-y-3">
              {activeAccounts.map((account) => (
                <AccountCard
                  key={account.id}
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              ))}
            </div>
          )}
        </div>

        {/* Coluna Direita - Resumo */}
        <div className="space-y-3">
          {/* Saldo Atual */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-slate-600 dark:text-slate-400 uppercase tracking-wide">Saldo atual</p>
              <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                <i className="bi bi-currency-dollar text-blue-600 dark:text-blue-400 text-sm"></i>
              </div>
            </div>
            <p className="text-xl font-bold text-slate-900 dark:text-white mb-1">{formatCurrency(totalBalance)}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Valor total em contas ativas
            </p>
          </div>

          {/* Saldo Previsto */}
          <div className="card-base p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-slate-600 dark:text-slate-400 uppercase tracking-wide">Saldo previsto</p>
              <div className="w-8 h-8 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center">
                <i className="bi bi-currency-dollar text-purple-600 dark:text-purple-400 text-sm"></i>
              </div>
            </div>
            <p className="text-xl font-bold text-slate-900 dark:text-white mb-1">{formatCurrency(projectedBalance)}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Projeção do saldo futuro
            </p>
          </div>
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <AccountForm
          show={showForm}
          onHide={() => {
            setShowForm(false);
            setEditingAccount(null);
          }}
          onSubmit={handleFormSubmit}
          account={editingAccount}
        />
      )}
    </div>
  );
};

export default Accounts;
