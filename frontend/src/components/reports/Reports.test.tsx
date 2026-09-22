import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Reports from './Reports';
import { accountsAPI, reportsAPI, type ReportOverviewResponse } from '../../utils/api';
import { loadPayablesSummary } from '../../utils/payablesSummary';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  reportsAPI: { getOverview: vi.fn() },
  accountsAPI: { getAll: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
}));
vi.mock('../../utils/payablesSummary', () => ({ loadPayablesSummary: vi.fn() }));
vi.mock('./ReportChart', () => ({ default: () => <div data-testid="report-chart" /> }));

const overview: ReportOverviewResponse = {
  data: [{ category_name: 'Mercado', category_color: '#123456', total: 250.5, percentage: 100, count: 3, category_id: 'cat-1' } as never],
  total_amount: 250.5,
  period: { month: 9, year: 2026 },
};
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const mount = () => render(<MemoryRouter><Reports /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'error').mockImplementation(() => undefined);
  vi.mocked(reportsAPI.getOverview).mockResolvedValue(response(overview));
  vi.mocked(accountsAPI.getAll).mockResolvedValue(response([{ id: 'acc-1', name: 'Nubank', type: 'checking' }]));
  vi.mocked(loadPayablesSummary).mockResolvedValue({ month: 9, year: 2026, monthLabel: 'setembro de 2026', openCount: 1, overdueCount: 0, paidCount: 2, partialCount: 0, canceledCount: 0, openRemainingSum: 10, paidSum: 20, expectedSum: 30, totalInMonth: 3 });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Reports', () => {
  it('erro no relatório mostra indisponibilidade fixa, sem zeros nem "nenhum dado"', async () => {
    vi.mocked(reportsAPI.getOverview).mockRejectedValueOnce(Object.assign(new Error('boom'), { response: { data: { error: 'detalhe interno' } } }));
    mount();
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/Indisponível/)).toBeInTheDocument();
    expect(screen.queryByText('detalhe interno')).not.toBeInTheDocument();
    expect(screen.queryByText('boom')).not.toBeInTheDocument();
    expect(screen.queryByText(/R\$\s?0,00/)).not.toBeInTheDocument();
    expect(screen.queryByText('Nenhum dado encontrado')).not.toBeInTheDocument();
    expect(screen.queryByText('Resumo do Período')).not.toBeInTheDocument();

    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    await waitFor(() => expect(reportsAPI.getOverview).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Mercado')).toBeInTheDocument();
  });

  it('total zero é exibido e não escondido', async () => {
    vi.mocked(reportsAPI.getOverview).mockResolvedValue(response({ ...overview, total_amount: 0 }));
    mount();
    await screen.findByText('Mercado');
    expect(screen.getByText('Total:')).toBeInTheDocument();
    expect(screen.getAllByText(/R\$\s?0,00/).length).toBeGreaterThan(0);
  });

  it('falha ao carregar contas mostra "Contas indisponíveis" com retry', async () => {
    vi.mocked(accountsAPI.getAll).mockRejectedValueOnce(new Error('offline'));
    mount();
    expect(await screen.findByRole('option', { name: 'Contas indisponíveis' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Carregando contas...' })).not.toBeInTheDocument();
    const alert = screen.getByRole('alert');
    expect(within(alert).getByText(/Contas indisponíveis/)).toBeInTheDocument();
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('option', { name: /Nubank/ })).toBeInTheDocument();
    expect(accountsAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('descarta resposta antiga quando o tipo de relatório muda rapidamente', async () => {
    const old = deferred<ReturnType<typeof response>>();
    vi.mocked(reportsAPI.getOverview).mockImplementationOnce(() => old.promise);
    mount();
    vi.mocked(reportsAPI.getOverview).mockResolvedValue(response({ ...overview, data: [{ ...overview.data[0], category_name: 'Salário' }] }));
    const button = screen.getByRole('button', { name: 'Receitas por categorias' });
    await userEvent.click(button);
    expect(button).toHaveAttribute('aria-pressed', 'true');
    expect(await screen.findByText('Salário')).toBeInTheDocument();
    await act(async () => old.resolve(response(overview)));
    expect(screen.queryByText('Mercado')).not.toBeInTheDocument();
    expect(screen.getByText('Salário')).toBeInTheDocument();
  });

  it('itens da legenda são botões acionáveis e botões de gráfico têm aria-pressed', async () => {
    mount();
    await screen.findByText('Mercado');
    expect(screen.getByRole('button', { name: 'Ver transações de Mercado' })).toBeInTheDocument();
    const pie = screen.getByRole('button', { name: 'Gráfico de pizza' });
    const bar = screen.getByRole('button', { name: 'Gráfico de barras' });
    expect(pie).toHaveAttribute('aria-pressed', 'true');
    expect(bar).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(bar);
    expect(bar).toHaveAttribute('aria-pressed', 'true');
  });
});
