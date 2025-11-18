import { useTranslation } from 'react-i18next';
import { formatCurrency, formatDate } from '../../utils/api';

interface TransactionCategory {
  name?: string;
  color?: string;
  icon?: string;
}

interface RecentTransaction {
  id: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  date: string;
  category?: TransactionCategory;
}

interface RecentTransactionsProps {
  transactions: RecentTransaction[];
}

const RecentTransactions: React.FC<RecentTransactionsProps> = ({ transactions }) => {
  const { t } = useTranslation();

  if (!transactions || transactions.length === 0) {
    return (
      <div className="text-center text-muted py-4">
        <i className="bi bi-inbox display-4 d-block mb-3"></i>
        <p className="mb-0">{t('dashboard.noTransactions')}</p>
      </div>
    );
  }

  return (
    <div className="recent-transactions">
      {transactions.slice(0, 5).map((transaction) => (
        <div key={transaction.id} className="transaction-item d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center">
            <div 
              className="rounded-circle d-flex align-items-center justify-content-center me-3"
              style={{
                width: '40px',
                height: '40px',
                backgroundColor: transaction.category?.color || '#6c757d'
              }}
            >
              <i className={`bi bi-${transaction.category?.icon || 'circle'} text-white`}></i>
            </div>
            
            <div>
              <h6 className="mb-1">{transaction.description}</h6>
              <small className="text-muted">
                {transaction.category?.name} • {formatDate(transaction.date)}
              </small>
            </div>
          </div>
          
          <div className="text-end">
            <div className={`fw-bold ${transaction.type === 'income' ? 'text-success' : 'text-danger'}`}>
              {transaction.type === 'income' ? '+' : '-'}
              {formatCurrency(transaction.amount)}
            </div>
          </div>
        </div>
      ))}

      {transactions.length > 5 && (
        <div className="text-center mt-3">
          <small className="text-muted">
            E mais {transactions.length - 5} transações...
          </small>
        </div>
      )}
    </div>
  );
};

export default RecentTransactions;