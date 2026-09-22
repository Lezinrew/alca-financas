import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import { accountsAPI, dashboardAPI, financialExpensesAPI } from '../../utils/api';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => navigate,
}));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  dashboardAPI: { getAdvanced: vi.fn() },
  accountsAPI: { getAll: vi.fn() },
  financialExpensesAPI: { overview: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
}));

// jsdom não implementa ResizeObserver, exigido pelo ResponsiveContainer do recharts.
vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });

const response = <T,>(data: T) => ({ data }) as never;
const dashboardData = {
  summary: { total_income: 5000, total_expense: 1234.56 },
  monthly_evolution: [{ year: 2026, month: 9, income: 5000, expense: 1234.56 }],
  expense_by_category: [{ category_name: 'Moradia', total: 1234.56, category_color: '#123456', percentage: 100 }],
  recent_transactions: [{ id: 'tx-1', description: 'Aluguel', amount: 1234.56, type: 'expense', category: { name: 'Moradia' }, date: '2026-09-10' }],
};
const accounts = [
  { id: 'a1', type: 'checking', current_balance: 800.5, is_active: true },
  { id: 'a2', type: 'credit_card', current_balance: 0, is_active: true },
  { id: 'a3', type: 'credit_card', current_balance: 0, is_active: false },
];
const overview = { expected: 900, paid: 300, remaining: 600, total: 3, counts: { paid: 1, pending: 2, partial: 0, canceled: 0, overdue: 1 }, complete: true };

const mount = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);
const kpi = (title: string) => within(screen.getByText(title).closest('.card-base') as HTMLElement);

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-21T12:00:00-03:00'));
  vi.mocked(dashboardAPI.getAdvanced).mockResolvedValue(response(dashboardData));
  vi.mocked(accountsAPI.getAll).mockResolvedValue(response(accounts));
  vi.mocked(financialExpensesAPI.overview).mockResolvedValue(response(overview));
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('Dashboard', () => {
  it('sucesso mostra valores com escopo rotulado e sem variação percentual fixa', async () => {
    mount();
    expect(await screen.findByText('R$ 5.000,00')).toBeInTheDocument();
    expect(screen.getByText('Saldo hoje (contas)')).toBeInTheDocument();
    expect(screen.getByText('Receitas · setembro de 2026')).toBeInTheDocument();
    expect(screen.getByText('Despesas · setembro de 2026')).toBeInTheDocument();
    expect(screen.getByText('Cartões de crédito')).toBeInTheDocument();
    expect(kpi('Saldo hoje (contas)').getByText('R$ 800,50')).toBeInTheDocument();
    expect(kpi('Despesas · setembro de 2026').getByText('R$ 1.234,56')).toBeInTheDocument();
    expect(kpi('Cartões de crédito').getByText('1')).toBeInTheDocument();
    expect(screen.queryByText(/vs mês anterior/)).not.toBeInTheDocument();
    expect(screen.getByText('Aluguel')).toBeInTheDocument();
    expect(await screen.findByText('2 em aberto')).toBeInTheDocument();
    expect(dashboardAPI.getAdvanced).toHaveBeenCalledWith('9', '2026', true, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(financialExpensesAPI.overview).toHaveBeenCalledWith(expect.objectContaining({ month: 9, year: 2026 }), expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it('erro do dashboard não mostra R$ 0,00 nem listas vazias; contas seguem disponíveis', async () => {
    vi.mocked(dashboardAPI.getAdvanced).mockRejectedValueOnce(new Error('offline'));
    mount();
    expect(await kpi('Receitas · setembro de 2026').findByText('—')).toBeInTheDocument();
    expect(kpi('Despesas · setembro de 2026').getByText('—')).toBeInTheDocument();
    expect(screen.queryByText(/R\$\s?0,00/)).not.toBeInTheDocument();
    expect(screen.queryByText('Nenhum dado disponível')).not.toBeInTheDocument();
    expect(screen.queryByText('Nenhuma categoria disponível')).not.toBeInTheDocument();
    expect(screen.queryByText('Nenhuma transação recente')).not.toBeInTheDocument();
    expect(screen.getAllByText('Indisponível.').length).toBeGreaterThanOrEqual(5);
    expect(await kpi('Saldo hoje (contas)').findByText('R$ 800,50')).toBeInTheDocument();
  });

  it('erro só de contas mostra "—" e "Contas indisponíveis" mantendo receitas', async () => {
    vi.mocked(accountsAPI.getAll).mockRejectedValueOnce(new Error('offline'));
    mount();
    expect(await kpi('Saldo hoje (contas)').findByText('—')).toBeInTheDocument();
    expect(kpi('Cartões de crédito').getByText('—')).toBeInTheDocument();
    expect(screen.getAllByText(/Contas indisponíveis/)).toHaveLength(2);
    expect(await screen.findByText('R$ 5.000,00')).toBeInTheDocument();
    expect(screen.queryByText(/R\$\s?0,00/)).not.toBeInTheDocument();
  });

  it('"Tentar novamente" refaz as requisições e recupera os valores', async () => {
    vi.mocked(dashboardAPI.getAdvanced).mockRejectedValueOnce(new Error('offline'));
    mount();
    const retry = (await screen.findAllByRole('button', { name: 'Tentar novamente' }))[0];
    expect(dashboardAPI.getAdvanced).toHaveBeenCalledTimes(1);
    await userEvent.click(retry);
    await waitFor(() => expect(dashboardAPI.getAdvanced).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('R$ 5.000,00')).toBeInTheDocument();
    expect(screen.queryByText('Indisponível.')).not.toBeInTheDocument();
  });

  it('clique em receitas abre Transações filtradas pelo mês exibido', async () => {
    mount();
    await screen.findByText('R$ 5.000,00');
    await userEvent.click(screen.getByText('Receitas · setembro de 2026'));
    expect(navigate).toHaveBeenCalledWith('/transactions', { state: { filterType: 'income', datePreset: 'this_month' } });
  });

  it('menu "+" fecha com Escape e devolve o foco ao botão', async () => {
    mount();
    await screen.findByText('R$ 5.000,00');
    const fab = screen.getByRole('button', { name: 'Nova transação' });
    await userEvent.click(fab);
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Despesa Nova despesa' })).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(fab).toHaveFocus();
  });
});
