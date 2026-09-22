import { Fragment } from 'react';
import { formatCurrency, formatDate, formatDateTime, type FinancialExpense } from '../../utils/api';
import './financial-expenses.css';

export interface ExpenseListProps {
  rows: FinancialExpense[];
  loading: boolean;
  onEdit: (row: FinancialExpense) => void;
  onPay: (row: FinancialExpense) => void;
  onDelete: (row: FinancialExpense) => void;
}

const amount = (value: number | string) => Number.isFinite(Number(value)) ? Number(value) : 0;
const balance = (row: FinancialExpense) => row.status === 'canceled' || row.status === 'paid'
  ? 0 : Math.max(0, amount(row.amount_expected) - amount(row.amount_paid));
const isLate = (row: FinancialExpense) => row.status !== 'paid' && row.status !== 'canceled'
  && (row.is_overdue || row.display_status === 'overdue');

function Status({ row }: { row: FinancialExpense }) {
  const labels = { pending: 'Pendente', partial: 'Parcial', paid: 'Paga', canceled: 'Cancelada' };
  return <span className="payables-badges">
    <span className={`payables-badge payables-badge-${row.status}`}>{labels[row.status]}</span>
    {isLate(row) && <span className="payables-badge payables-badge-overdue">Vencida</span>}
  </span>;
}

function ExtraDetails({ row }: { row: FinancialExpense }) {
  const origin = row.source_transaction_id || row.source_type === 'transaction'
    ? 'Importada de transação' : row.source_type === 'manual' ? 'Cadastro manual' : row.source_type || 'Não informada';
  return <details className="payables-row-details">
    <summary aria-label={`Ver detalhes de ${row.title}`}>Detalhes da conta</summary>
    <dl className="payables-details-grid">
      <div><dt>Origem</dt><dd>{origin}</dd></div>
      <div><dt>Responsável</dt><dd>{row.responsible_person || 'Não informado'}</dd></div>
      <div><dt>Competência</dt><dd>{row.competency_month && row.competency_year
        ? `${String(row.competency_month).padStart(2, '0')}/${row.competency_year}` : 'Não informada'}</dd></div>
      <div><dt>Pago em</dt><dd>{row.paid_at ? formatDateTime(row.paid_at) : 'Não informado'}</dd></div>
      {row.description && <div><dt>Descrição</dt><dd>{row.description}</dd></div>}
    </dl>
  </details>;
}

function Actions({ row, loading, onEdit, onPay, onDelete }: Omit<ExpenseListProps, 'rows'> & { row: FinancialExpense }) {
  const canPay = row.status !== 'paid' && row.status !== 'canceled';
  return <div className="payables-row-actions">
    {canPay && <button type="button" disabled={loading} className="payables-button payables-button-primary"
      aria-label={`Registrar pagamento de ${row.title}`} onClick={() => onPay(row)}>Registrar pagamento</button>}
    <button type="button" disabled={loading} className="payables-button"
      aria-label={`Editar ${row.title}`} onClick={() => onEdit(row)}>Editar</button>
    <details className="payables-more-actions">
      <summary aria-label={`Mais ações para ${row.title}`}>Mais ações</summary>
      <button type="button" disabled={loading} className="payables-button payables-button-danger"
        aria-label={`Excluir ${row.title}`} onClick={() => onDelete(row)}>Excluir conta</button>
    </details>
  </div>;
}

/** Both responsive views use the same rows; CSS hides the inactive view from accessibility APIs. */
export default function ExpenseList({ rows, loading, ...actions }: ExpenseListProps) {
  if (!rows.length) return <div className="payables-empty" role="status">
    {loading ? 'Carregando contas…' : 'Nenhuma conta corresponde aos filtros selecionados.'}
  </div>;

  return <div className="payables-list" aria-busy={loading}>
    <div className="payables-desktop-list">
      <table className="payables-table">
        <caption className="payables-sr-only">Contas correspondentes aos filtros selecionados. Valores em reais.</caption>
        <thead><tr>
          <th scope="col">Conta</th><th scope="col">Vencimento</th>
          <th scope="col" className="payables-money">Previsto</th>
          <th scope="col" className="payables-money">Pago</th>
          <th scope="col" className="payables-money">Saldo</th>
          <th scope="col">Situação</th><th scope="col">Ações</th>
        </tr></thead>
        <tbody>{rows.map(row => <Fragment key={row.id}>
          <tr className={isLate(row) ? 'payables-row-overdue' : undefined}>
            <th scope="row"><span className="payables-account-title">{row.title}</span><span className="payables-muted payables-category">{row.category}</span></th>
            <td>{row.due_date ? formatDate(row.due_date) : 'Sem vencimento'}</td>
            <td className="payables-money">{formatCurrency(amount(row.amount_expected))}</td>
            <td className="payables-money">{formatCurrency(amount(row.amount_paid))}</td>
            <td className="payables-money payables-balance">{formatCurrency(balance(row))}</td>
            <td><Status row={row} /></td>
            <td><Actions row={row} loading={loading} {...actions} /></td>
          </tr>
          <tr className="payables-details-row"><td colSpan={7}><ExtraDetails row={row} /></td></tr>
        </Fragment>)}</tbody>
      </table>
    </div>
    <ul className="payables-mobile-list" aria-label="Contas correspondentes aos filtros selecionados">
      {rows.map(row => <li key={row.id} className={`payables-account-card ${isLate(row) ? 'payables-row-overdue' : ''}`}>
        <div className="payables-card-heading"><h3>{row.title}</h3><Status row={row} /></div>
        <p className="payables-muted">{row.category}</p>
        <p>{row.due_date ? `Vencimento: ${formatDate(row.due_date)}` : 'Sem vencimento'}</p>
        <dl className="payables-card-amounts">
          <div><dt>Saldo em aberto</dt><dd className="payables-card-balance">{formatCurrency(balance(row))}</dd></div>
          <div><dt>Previsto</dt><dd>{formatCurrency(amount(row.amount_expected))}</dd></div>
          <div><dt>Pago</dt><dd>{formatCurrency(amount(row.amount_paid))}</dd></div>
        </dl>
        <Actions row={row} loading={loading} {...actions} />
        <ExtraDetails row={row} />
      </li>)}
    </ul>
  </div>;
}
