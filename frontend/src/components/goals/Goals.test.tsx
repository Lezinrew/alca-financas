import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Goals from './Goals';
import { goalsAPI, type Goal } from '../../utils/api';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  goalsAPI: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), listContributions: vi.fn(), addContribution: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
  formatDate: (value: string) => value,
  formatDateTime: (value: string) => value,
}));

const goal: Goal = { id: 'goal-1', tenant_id: 't', user_id: 'u', title: 'Viagem', target_amount: 5000, current_amount: 1000, status: 'active', progress_percent: 20 } as Goal;
const response = <T,>(data: T) => ({ data }) as never;
const mount = () => render(<MemoryRouter><Goals /></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); });
afterEach(() => { cleanup(); });

describe('Goals', () => {
  it('lista metas carregadas', async () => {
    vi.mocked(goalsAPI.list).mockResolvedValue(response([goal]));
    mount();
    expect(await screen.findByText('Viagem')).toBeInTheDocument();
    expect(screen.queryByText('Nenhuma meta ainda')).not.toBeInTheDocument();
  });

  it('erro de rede mostra bloco com retry e nunca "Nenhuma meta ainda"', async () => {
    vi.mocked(goalsAPI.list).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar as metas');
    expect(alert).not.toHaveTextContent('Network Error');
    expect(screen.queryByText('Nenhuma meta ainda')).not.toBeInTheDocument();
    expect(screen.queryByText('Criar primeira meta')).not.toBeInTheDocument();

    vi.mocked(goalsAPI.list).mockResolvedValueOnce(response([goal]));
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByText('Viagem')).toBeInTheDocument();
    await waitFor(() => expect(goalsAPI.list).toHaveBeenCalledTimes(2));
  });

  it('lista vazia sem erro mostra estado vazio', async () => {
    vi.mocked(goalsAPI.list).mockResolvedValue(response([]));
    mount();
    expect(await screen.findByText('Nenhuma meta ainda')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('filtro de status tem rótulo acessível', async () => {
    vi.mocked(goalsAPI.list).mockResolvedValue(response([]));
    mount();
    await screen.findByText('Nenhuma meta ainda');
    expect(screen.getByLabelText('Filtrar por status')).toBeInTheDocument();
  });
});
