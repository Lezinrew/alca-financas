import { useTranslation } from 'react-i18next';
import { formatCurrency, formatDate } from '../../utils/api';

const TransactionList = ({ transactions, onEdit, onDelete }) => {
  const { t } = useTranslation();

  if (!transactions || transactions.length === 0) {
    return (
      <div className="card">
        <div className="card-body text-center py-5">
          <i className="bi bi-inbox display-4 text-muted mb-3"></i>
          <h5 className="text-muted">{t('transactions.noTransactions')}</h5>
          <p className="text-muted">Comece adicionando sua primeira transação</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-body p-0">
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead className="table-light">
              <tr>
                <th className="ps-4">{t('transactions.description')}</th>
                <th>{t('transactions.category')}</th>
                <th>{t('transactions.amount')}</th>
                <th>{t('transactions.date')}</th>
                <th className="text-end pe-4">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td className="ps-4">
                    <div className="d-flex align-items-center">
                      <div 
                        className="rounded-circle d-flex align-items-center justify-content-center me-3"
                        style={{
                          width: '32px',
                          height: '32px',
                          backgroundColor: transaction.category?.color || '#6c757d'
                        }}
                      >
                        <i className={`bi bi-${transaction.category?.icon || 'circle'} text-white`}></i>
                      </div>
                      <div>
                        <div className="fw-medium">{transaction.description}</div>
                        {transaction.installment_info && (
                          <small className="text-muted">
                            Parcela {transaction.installment_info.current}/{transaction.installment_info.total}
                          </small>
                        )}
                      </div>
                    </div>
                  </td>
                  
                  <td>
                    <span 
                      className="badge"
                      style={{ 
                        backgroundColor: `${transaction.category?.color}20`,
                        color: transaction.category?.color,
                        border: `1px solid ${transaction.category?.color}40`
                      }}
                    >
                      {transaction.category?.name}
                    </span>
                  </td>
                  
                  <td>
                    <span className={`fw-bold ${transaction.type === 'income' ? 'text-success' : 'text-danger'}`}>
                      {transaction.type === 'income' ? '+' : '-'}
                      {formatCurrency(transaction.amount)}
                    </span>
                  </td>
                  
                  <td className="text-muted">
                    {formatDate(transaction.date)}
                  </td>
                  
                  <td className="text-end pe-4">
                    <div className="btn-group" role="group">
                      <button
                        onClick={() => onEdit(transaction)}
                        className="btn btn-outline-primary btn-sm"
                        title={t('common.edit')}
                      >
                        <i className="bi bi-pencil"></i>
                      </button>
                      <button
                        onClick={() => onDelete(transaction.id)}
                        className="btn btn-outline-danger btn-sm"
                        title={t('common.delete')}
                      >
                        <i className="bi bi-trash"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Resumo */}
      <div className="card-footer bg-light">
        <div className="row text-center">
          <div className="col-4">
            <div className="text-muted small">Total de Transações</div>
            <div className="fw-bold">{transactions.length}</div>
          </div>
          <div className="col-4">
            <div className="text-muted small">Receitas</div>
            <div className="fw-bold text-success">
              {formatCurrency(
                transactions
                  .filter(t => t.type === 'income')
                  .reduce((sum, t) => sum + t.amount, 0)
              )}
            </div>
          </div>
          <div className="col-4">
            <div className="text-muted small">Despesas</div>
            <div className="fw-bold text-danger">
              {formatCurrency(
                transactions
                  .filter(t => t.type === 'expense')
                  .reduce((sum, t) => sum + t.amount, 0)
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TransactionList;