import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency } from '../../utils/api';
import AccountForm from './AccountForm';
import AccountCard from './AccountCard';

const Accounts = () => {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/accounts`, {
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

  const handleEditAccount = (account) => {
    setEditingAccount(account);
    setShowForm(true);
  };

  const handleDeleteAccount = async (accountId) => {
    if (!window.confirm('Tem certeza que deseja excluir esta conta?')) return;

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/accounts/${accountId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao deletar conta');
      }

      await loadAccounts(); // Recarrega lista
    } catch (err) {
      setError(err.message || 'Erro ao deletar conta');
      console.error('Delete account error:', err);
    }
  };

  const handleFormSubmit = async (formData) => {
    try {
      const url = editingAccount 
        ? `${process.env.REACT_APP_BACKEND_URL}/api/accounts/${editingAccount.id}`
        : `${process.env.REACT_APP_BACKEND_URL}/api/accounts`;
        
      const method = editingAccount ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
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
      await loadAccounts(); // Recarrega lista
    } catch (err) {
      throw err; // Deixa o formulário lidar com o erro
    }
  };

  // Agrupa contas por tipo
  const walletAccounts = accounts.filter(acc => acc.type === 'wallet');
  const checkingAccounts = accounts.filter(acc => acc.type === 'checking');
  const savingsAccounts = accounts.filter(acc => acc.type === 'savings');
  const creditCardAccounts = accounts.filter(acc => acc.type === 'credit_card');
  const investmentAccounts = accounts.filter(acc => acc.type === 'investment');

  const totalBalance = accounts.reduce((sum, acc) => sum + (acc.current_balance || 0), 0);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner mb-3"></div>
          <p className="text-muted">Carregando contas...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="accounts">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">Contas</h2>
        
        <button
          onClick={handleAddAccount}
          className="btn btn-primary d-flex align-items-center"
        >
          <i className="bi bi-plus-circle me-2"></i>
          Nova Conta
        </button>
      </div>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}
        </div>
      )}

      {/* Resumo Total */}
      <div className="row mb-4">
        <div className="col-12">
          <div className="card bg-primary text-white">
            <div className="card-body text-center">
              <h5 className="card-title">Saldo Total</h5>
              <h2 className="display-4">{formatCurrency(totalBalance)}</h2>
              <p className="card-text opacity-75">
                {accounts.length} {accounts.length === 1 ? 'conta' : 'contas'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Carteiras */}
      {walletAccounts.length > 0 && (
        <div className="mb-4">
          <h5 className="mb-3">
            <i className="bi bi-wallet2 me-2"></i>
            Carteiras ({walletAccounts.length})
          </h5>
          <div className="row">
            {walletAccounts.map(account => (
              <div key={account.id} className="col-lg-4 col-md-6 mb-3">
                <AccountCard
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contas Correntes */}
      {checkingAccounts.length > 0 && (
        <div className="mb-4">
          <h5 className="mb-3">
            <i className="bi bi-bank me-2"></i>
            Contas Correntes ({checkingAccounts.length})
          </h5>
          <div className="row">
            {checkingAccounts.map(account => (
              <div key={account.id} className="col-lg-4 col-md-6 mb-3">
                <AccountCard
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Poupanças */}
      {savingsAccounts.length > 0 && (
        <div className="mb-4">
          <h5 className="mb-3">
            <i className="bi bi-piggy-bank me-2"></i>
            Poupanças ({savingsAccounts.length})
          </h5>
          <div className="row">
            {savingsAccounts.map(account => (
              <div key={account.id} className="col-lg-4 col-md-6 mb-3">
                <AccountCard
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cartões de Crédito */}
      {creditCardAccounts.length > 0 && (
        <div className="mb-4">
          <h5 className="mb-3">
            <i className="bi bi-credit-card me-2"></i>
            Cartões de Crédito ({creditCardAccounts.length})
          </h5>
          <div className="row">
            {creditCardAccounts.map(account => (
              <div key={account.id} className="col-lg-4 col-md-6 mb-3">
                <AccountCard
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Investimentos */}
      {investmentAccounts.length > 0 && (
        <div className="mb-4">
          <h5 className="mb-3">
            <i className="bi bi-graph-up-arrow me-2"></i>
            Investimentos ({investmentAccounts.length})
          </h5>
          <div className="row">
            {investmentAccounts.map(account => (
              <div key={account.id} className="col-lg-4 col-md-6 mb-3">
                <AccountCard
                  account={account}
                  onEdit={handleEditAccount}
                  onDelete={handleDeleteAccount}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Estado Vazio */}
      {accounts.length === 0 && (
        <div className="text-center py-5">
          <i className="bi bi-wallet2 display-1 text-muted mb-4"></i>
          <h4 className="text-muted">Nenhuma conta cadastrada</h4>
          <p className="text-muted mb-4">
            Comece adicionando sua primeira conta ou carteira
          </p>
          <button
            onClick={handleAddAccount}
            className="btn btn-primary btn-lg"
          >
            <i className="bi bi-plus-circle me-2"></i>
            Adicionar Primeira Conta
          </button>
        </div>
      )}

      {/* Modal do Formulário */}
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