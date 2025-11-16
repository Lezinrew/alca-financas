import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatCurrency } from '../../utils/api';

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

interface AccountCardProps {
  account: Account;
  onEdit: (account: Account) => void;
  onDelete: (accountId: number) => void;
}

const AccountCard: React.FC<AccountCardProps> = ({ account, onEdit, onDelete }) => {
  const navigate = useNavigate();
  const [openMenu, setOpenMenu] = useState(false);

  // Fecha o menu ao clicar fora
  useEffect(() => {
    if (!openMenu) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      
      // Não fecha se o clique foi dentro do menu dropdown ou no botão do menu
      const clickedInsideMenu = target.closest('.dropdown-menu');
      const clickedOnMenuButton = target.closest('.account-menu');
      const clickedOnDropdownItem = target.closest('.dropdown-item');
      
      if (clickedInsideMenu || clickedOnMenuButton || clickedOnDropdownItem) {
        return;
      }
      
      // Fecha o menu se o clique foi fora
      setOpenMenu(false);
    };

    // Adiciona o listener no próximo tick para não interferir com o clique do botão
    const timeoutId = setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);
    
    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('click', handleClickOutside);
    };
  }, [openMenu]);

  const getAccountTypeIcon = (type: Account['type']): string => {
    switch (type) {
      case 'wallet':
        return 'bi-wallet2';
      case 'checking':
        return 'bi-bank';
      case 'savings':
        return 'bi-piggy-bank';
      case 'credit_card':
        return 'bi-credit-card';
      case 'investment':
        return 'bi-graph-up-arrow';
      default:
        return 'bi-wallet2';
    }
  };

  const getAccountTypeName = (type: Account['type']): string => {
    switch (type) {
      case 'wallet':
        return 'Carteira';
      case 'checking':
        return 'Conta Corrente';
      case 'savings':
        return 'Poupança';
      case 'credit_card':
        return 'Cartão de Crédito';
      case 'investment':
        return 'Investimento';
      default:
        return 'Conta';
    }
  };

  const variance = (account.current_balance || 0) - (account.initial_balance || 0);
  const isPositiveVariance = variance >= 0;
  // Saldo previsto = saldo atual (pode ser melhorado com transações futuras)
  const projectedBalance = account.current_balance || 0;

  const handleAddExpense = () => {
    navigate('/transactions', {
      state: {
        openForm: true,
        transactionType: 'expense',
        accountId: account.id
      }
    });
  };

  return (
          <div className="card-base p-4 hover:shadow-md">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-1">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0"
            style={{ backgroundColor: account.color }}
          >
            <i className={`bi ${account.icon || getAccountTypeIcon(account.type)} text-lg`}></i>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm truncate">{account.name}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">{getAccountTypeName(account.type)}</p>
          </div>
        </div>

        {/* Actions Menu */}
        <div className="relative account-menu flex-shrink-0">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpenMenu(!openMenu);
            }}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Opções da conta"
          >
            <i className="bi bi-three-dots-vertical text-sm"></i>
          </button>
          
          {openMenu && (
                            <div className="dropdown-menu absolute right-0 top-full mt-1 w-48 py-1 z-50">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('AccountCard: Botão editar clicado para conta:', account.id);
                  setOpenMenu(false);
                  // Usa setTimeout para garantir que o menu seja fechado antes de chamar onEdit
                  setTimeout(() => {
                    onEdit(account);
                  }, 0);
                }}
                className="dropdown-item w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
              >
                <i className="bi bi-pencil text-blue-600 dark:text-blue-400"></i>
                <span>Editar</span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('AccountCard: Botão transações clicado para conta:', account.id);
                  setOpenMenu(false);
                  // Usa setTimeout para garantir que o menu seja fechado antes de navegar
                  setTimeout(() => {
                    navigate(`/transactions?account_id=${account.id}`);
                  }, 0);
                }}
                className="dropdown-item w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
              >
                <i className="bi bi-list-ul text-blue-600 dark:text-blue-400"></i>
                <span>Transações</span>
              </button>
              <div className="border-t border-slate-200 dark:border-slate-700 my-1"></div>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('AccountCard: Botão excluir clicado para conta:', account.id);
                  setOpenMenu(false);
                  // Usa setTimeout para garantir que o menu seja fechado antes de chamar onDelete
                  setTimeout(() => {
                    onDelete(account.id);
                  }, 0);
                }}
                className="dropdown-item w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
              >
                <i className="bi bi-trash"></i>
                <span>Excluir</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Saldos */}
      <div className="space-y-3 mb-4">
        {/* Saldo Atual */}
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Saldo atual</p>
          <p className={`text-xl font-bold ${
            account.current_balance > 0 ? 'text-emerald-600 dark:text-emerald-400' :
            account.current_balance < 0 ? 'text-red-600 dark:text-red-400' :
            'text-slate-600 dark:text-slate-400'
          }`}>
            {formatCurrency(account.current_balance || 0)}
          </p>
        </div>

        {/* Saldo Previsto */}
        <div>
          <div className="flex items-center gap-1 mb-1">
            <p className="text-xs text-slate-500 dark:text-slate-400">Saldo previsto</p>
            <i className="bi bi-info-circle text-xs text-slate-400 dark:text-slate-500" title="Projeção do saldo futuro"></i>
          </div>
          <p className={`text-lg font-semibold ${
            projectedBalance > 0 ? 'text-emerald-600 dark:text-emerald-400' :
            projectedBalance < 0 ? 'text-red-600 dark:text-red-400' :
            'text-slate-600 dark:text-slate-400'
          }`}>
            {formatCurrency(projectedBalance)}
          </p>
        </div>
      </div>

      {/* Botão Adicionar Despesa */}
      <button
        type="button"
        onClick={handleAddExpense}
        className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
      >
        <i className="bi bi-plus-circle text-sm"></i>
        Adicionar Despesa
      </button>
    </div>
  );
};

export default AccountCard;
