import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Transactions from './Transactions';
import { transactionsAPI, categoriesAPI, accountsAPI } from '../../utils/api';
import type { TransactionRecord } from '../../types/transaction';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../../utils/api', () => ({
  transactionsAPI: { getAll: vi.fn(), getFacets: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  categoriesAPI: { getAll: vi.fn() },
  accountsAPI: { getAll: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
}));

const row: TransactionRecord = { id: 'tx-1', description: 'Mercado da esquina', amount: 150.5, type: 'expense', category_id: 'cat-1', account_id: 'acc-1', date: '2026-09-10', status: 'paid' };
const listPayload = (rows: TransactionRecord[], total = rows.length, pages = 1, page = 1) => ({ data: rows, pagination: { total, page, pages, limit: 50 } });
const facetsPayload = { categories: [], accounts: [], types: [], summary: { paid_income: 1000, paid_expense: 150.5, net_paid: 849.5, transaction_count: 1, uncategorized_count: 0 } };
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const mount = (path = '/transactions') => render(<MemoryRouter initialEntries={[path]}><Transactions /></MemoryRouter>);
const summary = () => within(screen.getByRole('region', { name: 'Resumo das transações filtradas' }));
const ready = () => screen.findAllByText(row.description);

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(transactionsAPI.getAll).mockResolvedValue(response(listPayload([row])));
  vi.mocked(transactionsAPI.getFacets).mockResolvedValue(response(facetsPayload));
  vi.mocked(transactionsAPI.delete).mockResolvedValue(response({}));
  vi.mocked(categoriesAPI.getAll).mockResolvedValue(response([{ id: 'cat-1', name: 'Alimentação', type: 'expense' }]));
  vi.mocked(accountsAPI.getAll).mockResolvedValue(response([{ id: 'acc-1', name: 'Conta corrente', is_active: true }]));
});
afterEach(() => cleanup());

describe('Transactions page', () => {
  it('paginação avança e chama a API com page 2', async () => {
    vi.mocked(transactionsAPI.getAll).mockImplementation(async (filters) => response(listPayload([{ ...row, description: `Item página ${filters?.page}` }], 120, 3, filters?.page)));
    mount();
    await screen.findAllByText('Item página 1');
    const nav = within(screen.getByRole('navigation', { name: 'Paginação das transações' }));
    expect(nav.getByText('120 transações · página 1 de 3')).toBeInTheDocument();
    expect(nav.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    await userEvent.click(nav.getByRole('button', { name: 'Próxima' }));
    await screen.findAllByText('Item página 2');
    expect(transactionsAPI.getAll).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }), expect.anything());
    expect(screen.getByText('120 transações · página 2 de 3')).toBeInTheDocument();
    // Facets não dependem da página: uma única consulta.
    expect(transactionsAPI.getFacets).toHaveBeenCalledOnce();
  });

  it('erro de facets mostra "Resumo indisponível" e nunca R$ 0,00', async () => {
    vi.mocked(transactionsAPI.getFacets).mockRejectedValue(new Error('offline'));
    mount();
    await ready();
    await screen.findByRole('alert');
    expect(summary().getByRole('alert')).toHaveTextContent(/Resumo indisponível/);
    expect(summary().getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(summary().queryByText(/R\$\s?0,00/)).not.toBeInTheDocument();
    expect(summary().getAllByText('—').length).toBeGreaterThanOrEqual(3);
  });

  it('erro na lista mostra "Lista indisponível", não "nenhuma transação"', async () => {
    vi.mocked(transactionsAPI.getAll).mockRejectedValue(new Error('offline'));
    mount();
    expect(await screen.findByText(/Lista indisponível/)).toBeInTheDocument();
    expect(screen.queryByText('transactions.noTransactions')).not.toBeInTheDocument();
  });

  it('exclusão abre diálogo nomeando a transação e só chama delete após confirmar', async () => {
    mount();
    await ready();
    await userEvent.click(screen.getAllByRole('button', { name: `Mais ações para ${row.description}` })[0]);
    await userEvent.click(screen.getAllByRole('menuitem', { name: 'common.delete' })[0]);
    const dialog = within(screen.getByRole('dialog', { name: 'Excluir transação' }));
    expect(dialog.getByText(row.description)).toBeInTheDocument();
    expect(dialog.getByText(/150,50/)).toBeInTheDocument();
    expect(dialog.getByText('2026-09-10')).toBeInTheDocument();
    expect(dialog.getByText('Esta ação não pode ser desfeita.')).toBeInTheDocument();
    expect(transactionsAPI.delete).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(transactionsAPI.delete).not.toHaveBeenCalled();

    await userEvent.click(screen.getAllByRole('button', { name: `Mais ações para ${row.description}` })[0]);
    await userEvent.click(screen.getAllByRole('menuitem', { name: 'common.delete' })[0]);
    const confirm = within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir' });
    fireEvent.click(confirm); fireEvent.click(confirm);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(transactionsAPI.delete).toHaveBeenCalledExactlyOnceWith(row.id);
    expect(transactionsAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('erro na exclusão mostra texto fixo sem expor a resposta do servidor', async () => {
    vi.mocked(transactionsAPI.delete).mockRejectedValue({ response: { data: { error: 'stack trace secreto' } } });
    mount();
    await ready();
    await userEvent.click(screen.getAllByRole('button', { name: `Mais ações para ${row.description}` })[0]);
    await userEvent.click(screen.getAllByRole('menuitem', { name: 'common.delete' })[0]);
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir' }));
    expect(await screen.findByText('Não foi possível excluir a transação. Tente novamente.')).toBeInTheDocument();
    expect(screen.queryByText(/stack trace secreto/)).not.toBeInTheDocument();
  });

  it('ao excluir a última transação da página volta uma página', async () => {
    vi.mocked(transactionsAPI.getAll).mockImplementation(async (filters) => response(listPayload([{ ...row, description: `Item página ${filters?.page}` }], 51, 2, filters?.page)));
    mount('/transactions?page=2');
    await screen.findAllByText('Item página 2');
    await userEvent.click(screen.getAllByRole('button', { name: 'Mais ações para Item página 2' })[0]);
    await userEvent.click(screen.getAllByRole('menuitem', { name: 'common.delete' })[0]);
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Excluir' }));
    await screen.findAllByText('Item página 1');
    expect(transactionsAPI.getAll).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }), expect.anything());
  });

  it('descarta a resposta antiga quando o filtro muda antes de ela chegar', async () => {
    const oldList = deferred<ReturnType<typeof response>>();
    const oldFacets = deferred<ReturnType<typeof response>>();
    vi.mocked(transactionsAPI.getAll).mockImplementationOnce(() => oldList.promise);
    vi.mocked(transactionsAPI.getFacets).mockImplementationOnce(() => oldFacets.promise);
    mount();
    vi.mocked(transactionsAPI.getAll).mockResolvedValue(response(listPayload([{ ...row, description: 'Receita nova' }])));
    vi.mocked(transactionsAPI.getFacets).mockResolvedValue(response({ ...facetsPayload, summary: { ...facetsPayload.summary, net_paid: 777 } }));
    await userEvent.click(screen.getByRole('button', { name: '+ Receitas' }));
    await waitFor(() => expect(summary().getByText(/777,00/)).toBeInTheDocument());
    await act(async () => { oldList.resolve(response(listPayload([row]))); oldFacets.resolve(response(facetsPayload)); });
    expect(screen.queryByText(row.description)).not.toBeInTheDocument();
    expect(screen.getAllByText('Receita nova').length).toBeGreaterThan(0);
    expect(summary().getByText(/777,00/)).toBeInTheDocument();
    expect(summary().queryByText(/849,50/)).not.toBeInTheDocument();
  });

  it('menu "⋯" fecha com Escape e tem alvo de toque mínimo', async () => {
    mount();
    await ready();
    const toggle = screen.getAllByRole('button', { name: `Mais ações para ${row.description}` })[0];
    expect(toggle).toHaveClass('tx-actions-toggle');
    await userEvent.click(toggle);
    expect(screen.getAllByRole('menu').length).toBeGreaterThan(0);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });
});
