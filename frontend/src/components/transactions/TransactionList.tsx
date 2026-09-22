import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency, formatDate } from '../../utils/api';
import { TransactionRecord } from '../../types/transaction';
import './transactions.css';

interface TransactionListProps {
  transactions: TransactionRecord[];
  onEdit: (transaction: TransactionRecord) => void;
  onDelete: (transaction: TransactionRecord) => void;
  loading?: boolean;
  /** Nome das contas por id, para os cartões (o registro traz apenas `account_id`). */
  accountNames?: Record<string, string>;
}

const STATUS_LABEL: Record<string, string> = { paid: 'Pago', overdue: 'Atrasado', cancelled: 'Cancelado', pending: 'Pendente' };
const STATUS_CLASS: Record<string, string> = {
  paid: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300',
  overdue: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
  cancelled: 'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-300',
  pending: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300',
};
const statusKey = (transaction: TransactionRecord) => transaction.status && STATUS_LABEL[transaction.status] ? transaction.status : 'pending';
const amountClass = (type: TransactionRecord['type']) => type === 'income'
  ? 'text-emerald-600 dark:text-emerald-400' : type === 'transfer' ? 'text-blue-600 dark:text-blue-400' : 'text-red-600 dark:text-red-400';
const amountText = (transaction: TransactionRecord) =>
  `${transaction.type === 'income' ? '+' : transaction.type === 'transfer' ? '⇄ ' : '-'}${formatCurrency(Math.abs(Number(transaction.amount) || 0))}`;

function Status({ transaction }: { transaction: TransactionRecord }) {
  const key = statusKey(transaction);
  return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium ${STATUS_CLASS[key]}`}>{STATUS_LABEL[key]}</span>;
}

function Origin({ transaction }: { transaction: TransactionRecord }) {
  if (!transaction.entry_source || transaction.entry_source === 'manual') return <span className="text-slate-400 dark:text-slate-500">—</span>;
  return <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200" title="Importada do banco">
    {transaction.entry_source === 'ofx' ? 'OFX' : 'CSV'}
  </span>;
}

function CategoryBadge({ transaction }: { transaction: TransactionRecord }) {
  const { t } = useTranslation();
  const color = transaction.category?.color || '#6b7280';
  return <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium" style={{ backgroundColor: `${color}15`, color }}>
    {transaction.category?.name || t('transactions.uncategorized')}
  </span>;
}

/** Botão "⋯" com menu de ações; fecha com Escape, clique fora ou ao escolher uma ação. */
function RowActions({ transaction, disabled, onEdit, onDelete }: {
  transaction: TransactionRecord; disabled: boolean;
  onEdit: (transaction: TransactionRecord) => void; onDelete: (transaction: TransactionRecord) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); toggle.current?.focus(); }
    };
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('click', onClick); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const choose = (action: () => void) => { setOpen(false); action(); };

  return <div ref={root} className="tx-actions">
    <button ref={toggle} type="button" className="tx-button tx-actions-toggle" aria-haspopup="menu" aria-expanded={open}
      aria-label={`Mais ações para ${transaction.description}`} disabled={disabled} onClick={() => setOpen(value => !value)}>
      <span aria-hidden="true">⋯</span>
    </button>
    {open && <div role="menu" className="tx-actions-menu" aria-label={`Ações para ${transaction.description}`}>
      <button type="button" role="menuitem" onClick={() => choose(() => onEdit(transaction))}>
        <i className="bi bi-pencil" aria-hidden="true" /> {t('common.edit')}
      </button>
      <button type="button" role="menuitem" className="tx-menu-danger" onClick={() => choose(() => onDelete(transaction))}>
        <i className="bi bi-trash" aria-hidden="true" /> {t('common.delete')}
      </button>
    </div>}
  </div>;
}

const skeletonRows = Array.from({ length: 6 });

/** Tabela a partir de 1024px; abaixo, cartões sem rolagem horizontal. */
const TransactionList: React.FC<TransactionListProps> = ({ transactions, onEdit, onDelete, loading = false, accountNames = {} }) => {
  const { t } = useTranslation();
  const rows = Array.isArray(transactions) ? transactions : [];

  if (rows.length === 0) {
    if (loading) return <div className="tx card-base tx-empty" role="status" aria-busy="true">Carregando transações…</div>;
    return (
      <div className="card-base p-12 text-center" role="status">
        <i className="bi bi-inbox text-6xl text-slate-300 dark:text-slate-600 mb-4 block" aria-hidden="true"></i>
        <h5 className="text-lg font-semibold text-slate-700 dark:text-white mb-2">{t('transactions.noTransactions')}</h5>
        <p className="text-slate-500 dark:text-slate-300">Comece adicionando sua primeira transação</p>
      </div>
    );
  }

  const th = 'px-4 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider';

  return (
    <div className="tx tx-list" aria-busy={loading}>
      <div className="tx-desktop-list table-container">
        <table className="w-full">
          <caption className="sr-only">Transações correspondentes aos filtros selecionados. Valores em reais.</caption>
          <thead className="table-header">
            <tr>
              <th scope="col" className={th}>{t('transactions.description')}</th>
              <th scope="col" className={th}>{t('transactions.category')}</th>
              <th scope="col" className={th}>Situação</th>
              <th scope="col" className={th}>Responsável</th>
              <th scope="col" className={`${th} text-right`}>{t('transactions.amount')}</th>
              <th scope="col" className={th}>{t('transactions.date')}</th>
              <th scope="col" className={th}>Origem</th>
              <th scope="col" className={`${th} text-right`}>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
            {loading && skeletonRows.map((_, idx) => (
              <tr key={`skeleton-${idx}`} className="animate-pulse" aria-hidden="true">
                {Array.from({ length: 8 }).map((__, cell) => (
                  <td key={cell} className="px-4 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-3/4" /></td>
                ))}
              </tr>
            ))}
            {rows.map((transaction) => {
              const color = transaction.category?.color || '#6b7280';
              const icon = transaction.category?.icon || 'circle';
              return (
                <tr key={transaction.id} className="table-row group">
                  <th scope="row" className="px-4 py-4 text-left font-normal">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: color }}>
                        <i className={`bi bi-${icon} text-white`} aria-hidden="true"></i>
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900 dark:text-white break-words">{transaction.description}</div>
                        {transaction.installment_info && (
                          <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Parcela {transaction.installment_info.current}/{transaction.installment_info.total}</div>
                        )}
                      </div>
                    </div>
                  </th>
                  <td className="px-4 py-4"><CategoryBadge transaction={transaction} /></td>
                  <td className="px-4 py-4"><Status transaction={transaction} /></td>
                  <td className="px-4 py-4"><span className="text-sm text-slate-600 dark:text-slate-300">{transaction.responsible_person || '—'}</span></td>
                  <td className="px-4 py-4 text-right"><span className={`text-sm font-semibold tabular-nums ${amountClass(transaction.type)}`}>{amountText(transaction)}</span></td>
                  <td className="px-4 py-4 text-sm text-slate-600 dark:text-slate-300">{formatDate(transaction.date)}</td>
                  <td className="px-4 py-4 text-sm"><Origin transaction={transaction} /></td>
                  <td className="px-4 py-2 text-right"><RowActions transaction={transaction} disabled={loading} onEdit={onEdit} onDelete={onDelete} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="tx-mobile-list" aria-label="Transações correspondentes aos filtros selecionados">
        {rows.map((transaction) => (
          <li key={transaction.id} className="tx-card">
            <div className="tx-card-heading">
              <h3>{transaction.description}</h3>
              <Status transaction={transaction} />
            </div>
            {transaction.installment_info && <p className="tx-muted text-xs mt-1">Parcela {transaction.installment_info.current}/{transaction.installment_info.total}</p>}
            <p className={`tx-card-amount ${amountClass(transaction.type)}`}>{amountText(transaction)}</p>
            <dl className="tx-card-grid">
              <div><dt>{t('transactions.category')}</dt><dd><CategoryBadge transaction={transaction} /></dd></div>
              <div><dt>{t('transactions.date')}</dt><dd>{formatDate(transaction.date)}</dd></div>
              <div><dt>Conta</dt><dd>{(transaction.account_id && accountNames[transaction.account_id]) || (transaction.account_id ? 'Conta vinculada' : 'Sem conta')}</dd></div>
              <div><dt>Responsável</dt><dd>{transaction.responsible_person || '—'}</dd></div>
            </dl>
            <div className="tx-card-footer">
              <span className="text-sm"><span className="tx-muted">Origem: </span><Origin transaction={transaction} /></span>
              <RowActions transaction={transaction} disabled={loading} onEdit={onEdit} onDelete={onDelete} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default TransactionList;
