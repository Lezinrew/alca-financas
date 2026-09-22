import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import FinancialExpensesPage from './FinancialExpensesPage';
import { financialExpensesAPI, type ExpenseOverview, type FinancialExpense, type FinancialExpenseListResponse } from '../../utils/api';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  financialExpensesAPI: { list: vi.fn(), overview: vi.fn(), markPaid: vi.fn(), delete: vi.fn(), create: vi.fn(), update: vi.fn(), createFromTransactions: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
  formatDateTime: (value: string) => value,
}));

const account: FinancialExpense = { id: 'account-1', user_id: 'user', tenant_id: 'tenant', title: 'Conta setembro', category: 'moradia', amount_expected: 120, amount_paid: 20, status: 'partial', is_recurring: false, competency_month: 9, competency_year: 2026, due_date: '2026-09-25' };
const groups = { before: { count: 0, remaining: 0 }, month: { count: 15, remaining: 3739.80 }, after: { count: 0, remaining: 0 }, undated: { count: 0, remaining: 0 } };
const overview: ExpenseOverview = { expected: 9506.43, paid: 5766.63, remaining: 3739.80, total: 21, counts: { paid: 6, pending: 15, partial: 0, canceled: 0, overdue: 10 }, due_groups: groups, competency_groups: groups, complete: true, as_of: '2026-09-21' };
const list: FinancialExpenseListResponse = { data: [account], pagination: { total: 21, page: 1, per_page: 25, pages: 1 } };
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const mount = () => render(<MemoryRouter><FinancialExpensesPage /></MemoryRouter>);
const summary = () => within(screen.getByRole('region', { name: 'Resumo das contas filtradas' }));
const ready = () => screen.findByText('21 contas', { selector: 'strong' });

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-21T12:00:00-03:00'));
  vi.mocked(financialExpensesAPI.list).mockResolvedValue(response(list));
  vi.mocked(financialExpensesAPI.overview).mockResolvedValue(response(overview));
  vi.mocked(financialExpensesAPI.markPaid).mockResolvedValue(response(account));
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('FinancialExpensesPage integration', () => {
  it('abre setembro e mostra resumo completo e contagens do filtro', async () => {
    mount(); await ready();
    expect(screen.getByLabelText('Competência')).toHaveValue('2026-09');
    expect(summary().getByText(/9\.506,43/)).toBeInTheDocument();
    expect(summary().getByText(/5\.766,63/)).toBeInTheDocument();
    expect(summary().getByText(/3\.739,80/)).toBeInTheDocument();
    expect(summary().getByText('6 pagas')).toBeInTheDocument();
    expect(summary().getByText('15 pendentes')).toBeInTheDocument();
    expect(financialExpensesAPI.list).toHaveBeenCalledWith(expect.objectContaining({ month: 9, year: 2026, page: 1, limit: 25 }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it('visão geral retira competência da consulta mantendo mês de referência', async () => {
    mount(); await ready();
    await userEvent.click(screen.getByRole('button', { name: 'Visão geral' }));
    await waitFor(() => expect(financialExpensesAPI.list).toHaveBeenCalledTimes(2));
    const filters = vi.mocked(financialExpensesAPI.list).mock.calls[vi.mocked(financialExpensesAPI.list).mock.calls.length - 1][0]!;
    expect(filters.month).toBeUndefined(); expect(filters.year).toBeUndefined();
    expect(filters.reference_month).toBe(9); expect(filters.reference_year).toBe(2026);
    expect(screen.getByText('Todas as competências, incluindo contas sem competência')).toBeInTheDocument();
  });

  it('digitar responsável conserva foco e consulta somente após Aplicar', async () => {
    mount(); await ready();
    const input = screen.getByRole('textbox', { name: 'Responsável' });
    await userEvent.type(input, 'Maria');
    expect(input).toHaveFocus(); expect(input).toHaveValue('Maria');
    expect(financialExpensesAPI.list).toHaveBeenCalledOnce();
    expect(financialExpensesAPI.overview).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }));
    await waitFor(() => expect(financialExpensesAPI.list).toHaveBeenCalledTimes(2));
    expect(financialExpensesAPI.list).toHaveBeenLastCalledWith(expect.objectContaining({ responsible: 'Maria' }), expect.anything());
  });

  it('falha de rede mostra indisponibilidade, sem saldo zero ou lista vazia falsa', async () => {
    vi.mocked(financialExpensesAPI.list).mockRejectedValueOnce(new Error('offline'));
    vi.mocked(financialExpensesAPI.overview).mockRejectedValueOnce(new Error('offline'));
    mount();
    await waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2));
    expect(summary().queryByText(/R\$.*0,00/)).not.toBeInTheDocument();
    expect(summary().getAllByText('—')).toHaveLength(3);
    expect(screen.queryByText('Nenhuma conta nesta competência')).not.toBeInTheDocument();
  });

  it('falha só no resumo preserva a lista disponível', async () => {
    vi.mocked(financialExpensesAPI.overview).mockRejectedValueOnce(new Error('offline'));
    mount();
    await screen.findByRole('alert');
    expect(screen.getAllByText(account.title).length).toBeGreaterThan(0);
    expect(summary().getAllByText('—')).toHaveLength(3);
  });

  it('descarta respostas de setembro que chegam depois das de outubro', async () => {
    const oldList = deferred<ReturnType<typeof response>>();
    const oldOverview = deferred<ReturnType<typeof response>>();
    vi.mocked(financialExpensesAPI.list).mockImplementationOnce(() => oldList.promise);
    vi.mocked(financialExpensesAPI.overview).mockImplementationOnce(() => oldOverview.promise);
    mount();
    const oldSignal = vi.mocked(financialExpensesAPI.list).mock.calls[0][1]!.signal!;
    vi.mocked(financialExpensesAPI.list).mockResolvedValue(response({ ...list, data: [{ ...account, title: 'Conta outubro' }] }));
    vi.mocked(financialExpensesAPI.overview).mockResolvedValue(response({ ...overview, remaining: 100 }));
    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }));
    await waitFor(() => expect(summary().getByText(/100,00/)).toBeInTheDocument());
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { oldList.resolve(response(list)); oldOverview.resolve(response(overview)); });
    expect(screen.queryByText('Conta setembro')).not.toBeInTheDocument();
    expect(screen.getAllByText('Conta outubro').length).toBeGreaterThan(0);
    expect(summary().getByText(/100,00/)).toBeInTheDocument();
    expect(summary().queryByText(/3\.739,80/)).not.toBeInTheDocument();
  });

  it('paginação além de 25 registros mantém resumo de todas as páginas', async () => {
    vi.mocked(financialExpensesAPI.list).mockImplementation(async filters => response({ data: [{ ...account, title: `Conta página ${filters?.page}` }], pagination: { total: 51, page: filters?.page, per_page: 25, pages: 3 } }));
    vi.mocked(financialExpensesAPI.overview).mockResolvedValue(response({ ...overview, total: 51 }));
    mount(); await screen.findByText('51 contas', { selector: 'strong' });
    await userEvent.click(screen.getByRole('button', { name: 'Próxima' }));
    await waitFor(() => expect(screen.getAllByText('Conta página 2').length).toBeGreaterThan(0));
    expect(financialExpensesAPI.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }), expect.anything());
    expect(financialExpensesAPI.overview).toHaveBeenCalledOnce();
    expect(summary().getByText(/9\.506,43/)).toBeInTheDocument();
    expect(summary().getByText(/3\.739,80/)).toBeInTheDocument();
  });

  it('cancelar pagamento não escreve e confirmar impede envio duplicado', async () => {
    mount(); await ready();
    const pay = () => screen.getAllByRole('button', { name: `Registrar pagamento de ${account.title}` })[0];
    await userEvent.click(pay());
    let dialog = within(screen.getByRole('dialog', { name: 'Registrar pagamento integral' }));
    expect(dialog.getByText(/100,00/)).toBeInTheDocument();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(financialExpensesAPI.markPaid).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const payment = deferred<ReturnType<typeof response>>();
    vi.mocked(financialExpensesAPI.markPaid).mockImplementationOnce(() => payment.promise);
    await userEvent.click(pay());
    dialog = within(screen.getByRole('dialog'));
    const confirm = dialog.getByRole('button', { name: 'Confirmar registro' });
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(financialExpensesAPI.markPaid).toHaveBeenCalledExactlyOnceWith(account.id);
    expect(dialog.getByRole('button', { name: 'Confirmando…' })).toBeDisabled();
    await act(async () => payment.resolve(response(account)));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(await screen.findByText('Pagamento registrado na conta.')).toBeInTheDocument();
  });
});
