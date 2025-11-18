import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency, formatDate } from '../../utils/api';
import { TransactionRecord } from '../../types/transaction';

interface TransactionListProps {
  transactions: TransactionRecord[];
  onEdit: (transaction: TransactionRecord) => void;
  onDelete: (transactionId: string) => void;
}

const TransactionList: React.FC<TransactionListProps> = ({ transactions, onEdit, onDelete }) => {
  const { t } = useTranslation();
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Fecha o menu ao clicar fora
  useEffect(() => {
    if (!openMenuId) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      
      // Não fecha se o clique foi dentro do menu dropdown ou no botão do menu
      const clickedInsideMenu = target.closest('.dropdown-menu');
      const clickedOnMenuButton = target.closest('.transaction-menu');
      const clickedOnDropdownItem = target.closest('.dropdown-item');
      
      if (clickedInsideMenu || clickedOnMenuButton || clickedOnDropdownItem) {
        return;
      }
      
      // Fecha o menu se o clique foi fora
      setOpenMenuId(null);
    };

    // Adiciona o listener no próximo tick para não interferir com o clique do botão
    const timeoutId = setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);
    
    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('click', handleClickOutside);
    };
  }, [openMenuId]);

  if (!transactions || transactions.length === 0) {
          return (
            <div className="card-base p-12 text-center">
              <i className="bi bi-inbox text-6xl text-slate-300 dark:text-slate-600 mb-4 block"></i>
              <h5 className="text-lg font-semibold text-slate-700 dark:text-white mb-2">{t('transactions.noTransactions')}</h5>
              <p className="text-slate-500 dark:text-slate-300">Comece adicionando sua primeira transação</p>
            </div>
          );
  }

  return (
          <div className="table-container">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">{t('transactions.description')}</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">{t('transactions.category')}</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">Responsável</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">{t('transactions.amount')}</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">{t('transactions.date')}</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">{t('common.actions')}</th>
            </tr>
          </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
            {transactions.map((transaction) => {
              const categoryColor = transaction.category?.color || '#6b7280';
              const categoryIcon = transaction.category?.icon || 'circle';

              return (
              <tr key={transaction.id} className="table-row">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{
                        backgroundColor: categoryColor
                      }}
                    >
                      <i className={`bi bi-${categoryIcon} text-white`}></i>
                    </div>
                    <div>
                      <div className="font-medium text-slate-900 dark:text-white">{transaction.description}</div>
                      {transaction.installment_info && (
                        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          Parcela {transaction.installment_info.current}/{transaction.installment_info.total}
                        </div>
                      )}
                    </div>
                  </div>
                </td>

                <td className="px-6 py-4">
                    <span
                    className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium"
                    style={{
                      backgroundColor: `${categoryColor}15`,
                      color: categoryColor,
                    }}
                  >
                    {transaction.category?.name || t('transactions.uncategorized')}
                  </span>
                </td>

                <td className="px-6 py-4">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium ${
                    transaction.status === 'paid' ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300' :
                    transaction.status === 'overdue' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300' :
                    transaction.status === 'cancelled' ? 'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-300' :
                    'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300'
                  }`}>
                    {transaction.status === 'paid' ? 'Pago' :
                     transaction.status === 'overdue' ? 'Atrasado' :
                     transaction.status === 'cancelled' ? 'Cancelado' :
                     'Pendente'}
                  </span>
                </td>

                <td className="px-6 py-4">
                  <span className="text-sm text-slate-600 dark:text-slate-300">{transaction.responsible_person || 'Leandro'}</span>
                </td>

                <td className="px-6 py-4">
                  <span className={`text-sm font-semibold ${transaction.type === 'income' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                    {transaction.type === 'income' ? '+' : '-'}
                    {formatCurrency(transaction.amount)}
                  </span>
                </td>

                <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-300">
                  {formatDate(transaction.date)}
                </td>

                <td className="px-6 py-4 text-right">
                  <div className="relative transaction-menu flex items-center justify-end">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('TransactionList: Botão menu clicado, openMenuId atual:', openMenuId, 'transaction.id:', transaction.id);
                        setOpenMenuId(openMenuId === transaction.id ? null : transaction.id);
                      }}
                      className="p-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                      aria-label="Opções da transação"
                    >
                      <i className="bi bi-three-dots-vertical text-sm"></i>
                    </button>
                    
                    {openMenuId === transaction.id && (
                            <div className="dropdown-menu absolute right-0 top-full mt-1 w-40 py-1" style={{ zIndex: 9999, position: 'absolute' }}>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('TransactionList: Botão editar clicado para transação:', transaction.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar onEdit
                            setTimeout(() => {
                              onEdit(transaction);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                        >
                          <i className="bi bi-pencil text-blue-600 dark:text-blue-400"></i>
                          <span>{t('common.edit')}</span>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('TransactionList: Botão excluir clicado para transação:', transaction.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar onDelete
                            setTimeout(() => {
                              onDelete(transaction.id);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                        >
                          <i className="bi bi-trash"></i>
                          <span>{t('common.delete')}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransactionList;
