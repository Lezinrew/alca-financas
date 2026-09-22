import React from 'react';
import { useNavigate } from 'react-router-dom';
import { formatCurrency } from '../../utils/api';
import { Account } from '../../types/account';
import { MENU_ITEM_CLASS, MENU_TRIGGER_CLASS, useActionMenu } from './useActionMenu';
import { getAccountTypeName } from './accountLabels';

interface AccountCardProps {
  account: Account;
  onEdit: (account: Account) => void;
  onDelete: (account: Account) => void;
}

const typeIcons: Record<Account['type'], string> = {
  wallet: 'bi-wallet2', checking: 'bi-bank', savings: 'bi-piggy-bank', credit_card: 'bi-credit-card', investment: 'bi-graph-up-arrow',
};

const balanceTone = (value: number) =>
  value > 0 ? 'text-emerald-600 dark:text-emerald-400' : value < 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-600 dark:text-slate-400';

const AccountCard: React.FC<AccountCardProps> = ({ account, onEdit, onDelete }) => {
  const navigate = useNavigate();
  const menu = useActionMenu();

  const isCreditCard = account.type === 'credit_card';
  const currentBalance = account.current_balance ?? 0;
  const projectedBalance = account.projected_balance ?? currentBalance;
  // Cartões: initial_balance/limit é o limite total e current_balance o valor gasto.
  const creditLimit = account.limit ?? account.initial_balance ?? 0;
  const creditUsed = Math.abs(currentBalance);
  const creditAvailable = creditLimit - creditUsed;

  const handleAddExpense = () => {
    if (!account.id) return;
    navigate('/transactions', { state: { openForm: true, transactionType: 'expense', accountId: account.id } });
  };

  const run = (action: () => void) => { menu.close(); action(); };

  return (
    <article className="card-base p-4 hover:shadow-md" aria-label={account.name}>
      <div className="mb-4 flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-white" style={{ backgroundColor: account.color || '#6366f1' }} aria-hidden="true">
            <i className={`bi ${account.icon || typeIcons[account.type] || 'bi-wallet2'} text-lg`}></i>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{account.name}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">{getAccountTypeName(account.type)}</p>
          </div>
        </div>

        <div ref={menu.container} className="relative flex-shrink-0">
          <button ref={menu.trigger} type="button" onClick={menu.toggle} aria-haspopup="menu" aria-expanded={menu.open}
            aria-label={`Mais ações para ${account.name}`} className={MENU_TRIGGER_CLASS}>
            <i className="bi bi-three-dots-vertical" aria-hidden="true"></i>
          </button>

          {menu.open && (
            <div role="menu" aria-label={`Ações de ${account.name}`} className="dropdown-menu absolute right-0 top-full z-50 mt-1 w-48 py-1">
              <button type="button" role="menuitem" onClick={() => run(() => onEdit(account))} className={MENU_ITEM_CLASS}>
                <i className="bi bi-pencil text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
                <span>Editar</span>
              </button>
              <button type="button" role="menuitem" onClick={() => run(() => navigate(`/transactions?account_id=${account.id}`))} className={MENU_ITEM_CLASS}>
                <i className="bi bi-list-ul text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
                <span>Transações</span>
              </button>
              <div className="my-1 border-t border-slate-200 dark:border-slate-700" role="separator"></div>
              <button type="button" role="menuitem" onClick={() => run(() => onDelete(account))} className={`${MENU_ITEM_CLASS} text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20`}>
                <i className="bi bi-trash" aria-hidden="true"></i>
                <span>Excluir</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mb-4 space-y-3">
        {isCreditCard ? (
          <>
            <div>
              <p className="mb-1 text-xs text-slate-500 dark:text-slate-400">Limite total</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{formatCurrency(creditLimit)}</p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-500 dark:text-slate-400">Limite disponível</p>
              <p className={`text-lg font-semibold ${balanceTone(creditAvailable)}`}>{formatCurrency(creditAvailable)}</p>
              {creditUsed > 0 && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Gasto: {formatCurrency(creditUsed)} de {formatCurrency(creditLimit)}</p>}
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="mb-1 text-xs text-slate-500 dark:text-slate-400">Saldo atual (transações pagas)</p>
              <p className={`text-xl font-bold ${balanceTone(currentBalance)}`}>{formatCurrency(currentBalance)}</p>
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-500 dark:text-slate-400">Saldo previsto (inclui pendentes e futuras)</p>
              <p className={`text-lg font-semibold ${balanceTone(projectedBalance)}`}>{formatCurrency(projectedBalance)}</p>
              {projectedBalance !== currentBalance && (
                <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
                  {projectedBalance > currentBalance ? '↑' : '↓'} {formatCurrency(Math.abs(projectedBalance - currentBalance))} de diferença
                </p>
              )}
            </div>
          </>
        )}
      </div>

      <button type="button" onClick={handleAddExpense}
        className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600">
        <i className="bi bi-plus-circle text-sm" aria-hidden="true"></i>
        Adicionar despesa
      </button>
    </article>
  );
};

export default AccountCard;
