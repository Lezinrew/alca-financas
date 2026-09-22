import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import CreditCardDetail from './CreditCardDetail';
import { accountsAPI, categoriesAPI, transactionsAPI } from '../../utils/api';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  accountsAPI: { getById: vi.fn(), import: vi.fn() },
  categoriesAPI: { getAll: vi.fn() },
  transactionsAPI: { getAll: vi.fn(), create: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
}));

const account = { id: 'card-1', name: 'Cartão Roxo', type: 'credit_card', is_active: true, initial_balance: 5000, current_balance: -1250, closing_day: 10, due_day: 17, color: '#111' };
const expense = (id: string, amount: number, status = 'paid') => ({ id, description: `Compra ${id}`, amount, date: '2026-09-15', status, category: { name: 'Mercado', color: '#0f0', icon: 'cart' } });
const response = <T,>(data: T) => ({ data }) as never;
const mount = () => render(
  <MemoryRouter initialEntries={['/credit-cards/card-1']}>
    <Routes><Route path="/credit-cards/:cardId" element={<CreditCardDetail />} /></Routes>
  </MemoryRouter>,
);
const invoice = async () => within(await screen.findByRole('region', { name: 'Valor da fatura' }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(accountsAPI.getById).mockResolvedValue(response(account));
  vi.mocked(categoriesAPI.getAll).mockResolvedValue(response([]));
  vi.mocked(transactionsAPI.getAll).mockResolvedValue(response({ data: [expense('a', 100), expense('b', 50.5, 'pending')], pagination: { total: 2, page: 1, per_page: 500, pages: 1 } }));
});
afterEach(cleanup);

describe('CreditCardDetail', () => {
  it('mostra o total dos lançamentos e a situação real de cada um', async () => {
    mount();
    expect(await (await invoice()).findByText('R$ 150,50')).toBeInTheDocument();
    expect(screen.getAllByText('Pendente').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Pago').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Total calculado sobre/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeInTheDocument();
  });

  it('em erro das despesas não mostra R$ 0,00 nem lista vazia, e permite tentar novamente', async () => {
    vi.mocked(transactionsAPI.getAll).mockRejectedValueOnce(new Error('offline'));
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('Despesas indisponíveis');
    expect((await invoice()).getByText('Indisponível')).toBeInTheDocument();
    expect(screen.queryByText('R$ 0,00')).not.toBeInTheDocument();
    expect(screen.queryByText(/Você não possui despesas/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await (await invoice()).findByText('R$ 150,50')).toBeInTheDocument();
    expect(transactionsAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('avisa quando o total é parcial (há mais lançamentos do que os carregados)', async () => {
    vi.mocked(transactionsAPI.getAll).mockResolvedValue(response({ data: [expense('a', 100)], pagination: { total: 750, page: 1, per_page: 500, pages: 2 } }));
    mount();
    expect(await (await invoice()).findByText('R$ 100,00')).toBeInTheDocument();
    expect((await invoice()).getByText('Total calculado sobre os 1 lançamentos carregados (de 750).')).toBeInTheDocument();
  });

  it('em erro do cartão mostra indisponível com tentar novamente, sem dados inventados', async () => {
    vi.mocked(accountsAPI.getById).mockRejectedValueOnce(new Error('offline'));
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('Cartão indisponível');
    expect(screen.queryByText('R$ 0,00')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(transactionsAPI.getAll).not.toHaveBeenCalled();
  });

  it('setas de mês têm nome acessível e mudam o período consultado', async () => {
    mount();
    await (await invoice()).findByText('R$ 150,50');
    await userEvent.click(screen.getByRole('button', { name: 'Por mês' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Mês anterior' }));
    expect(screen.getByRole('button', { name: 'Próximo mês' })).toBeInTheDocument();
    const calls = vi.mocked(transactionsAPI.getAll).mock.calls;
    const last = calls[calls.length - 1][0]!;
    expect(last.account_ids).toBe('card-1');
    expect(last.date_from).toMatch(/-01$/);
  });
});
