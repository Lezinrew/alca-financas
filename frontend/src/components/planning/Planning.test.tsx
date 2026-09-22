import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Planning from './Planning';
import { planningAPI, type PlanningMonthResponse } from '../../utils/api';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  planningAPI: { getMonth: vi.fn(), getMonthCategories: vi.fn(), saveMonth: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
}));

const planning = {
  summary: { planned_income: 5000, planned_expenses: 3000, planned_balance: 2000, real_income: 4800, real_expenses: 2500, real_balance: 2300, savings_rate: 40 },
  expense_categories: [],
  income_categories: [],
  alerts: [],
} as unknown as PlanningMonthResponse;
const response = <T,>(data: T) => ({ data }) as never;
const mount = () => render(<MemoryRouter><Planning /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(planningAPI.getMonth).mockResolvedValue(response(planning));
  vi.mocked(planningAPI.getMonthCategories).mockResolvedValue(response({ expense: [], income: [] }));
  vi.mocked(planningAPI.saveMonth).mockResolvedValue(response({}));
});
afterEach(() => { cleanup(); });

describe('Planning', () => {
  it('erro de carregamento mostra bloco com retry e nunca "Nenhum planejamento"', async () => {
    vi.mocked(planningAPI.getMonth).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar o planejamento');
    expect(alert).not.toHaveTextContent('Network Error');
    expect(screen.queryByText('Nenhum planejamento encontrado')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByText('Receita planejada')).toBeInTheDocument();
    await waitFor(() => expect(planningAPI.getMonth).toHaveBeenCalledTimes(2));
  });

  it('setas de mês têm rótulo e consultam o mês certo', async () => {
    mount();
    await screen.findByText('Receita planejada');
    const [month, year] = vi.mocked(planningAPI.getMonth).mock.calls[0];
    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }));
    await waitFor(() => expect(planningAPI.getMonth).toHaveBeenCalledTimes(2));
    const [nextMonth, nextYear] = vi.mocked(planningAPI.getMonth).mock.calls[1];
    expect(nextMonth).toBe(month === 12 ? 1 : month + 1);
    expect(nextYear).toBe(month === 12 ? year + 1 : year);
  });

  it('"Usar mês anterior como base" com plano existente pede confirmação antes de sobrescrever', async () => {
    mount();
    await screen.findByText('Receita planejada');
    await userEvent.click(screen.getByRole('button', { name: /Como usar seu planejamento/ }));
    await userEvent.click(screen.getByRole('button', { name: /Usar mês anterior como base/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Substituir planejamento do mês?');
    expect(planningAPI.saveMonth).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Substituir' }));
    await waitFor(() => expect(planningAPI.saveMonth).toHaveBeenCalledTimes(1));
  });
});
