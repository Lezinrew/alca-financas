import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import GoalDetail from './GoalDetail';
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
const mount = () => render(
  <MemoryRouter initialEntries={['/goals/goal-1']}>
    <Routes>
      <Route path="/goals" element={<h1>Lista de metas</h1>} />
      <Route path="/goals/:goalId" element={<GoalDetail />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(goalsAPI.get).mockResolvedValue(response(goal));
  vi.mocked(goalsAPI.listContributions).mockResolvedValue(response([]));
});
afterEach(() => { cleanup(); });

describe('GoalDetail', () => {
  it('exclusão só chama a API após confirmar e volta para a lista', async () => {
    vi.mocked(goalsAPI.delete).mockResolvedValue(response({}));
    mount();
    await screen.findByRole('heading', { name: 'Viagem' });
    await userEvent.click(screen.getByRole('button', { name: 'Excluir meta' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Excluir meta?');
    expect(goalsAPI.delete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(goalsAPI.delete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Excluir meta' }));
    const reopened = await screen.findByRole('dialog');
    await userEvent.click(within(reopened).getByRole('button', { name: 'Excluir meta' }));
    await waitFor(() => expect(goalsAPI.delete).toHaveBeenCalledWith('goal-1'));
    expect(await screen.findByText('Lista de metas')).toBeInTheDocument();
  });

  it('falha de rede mostra bloco de erro com retry em vez de "Meta não encontrada"', async () => {
    vi.mocked(goalsAPI.get).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar a meta');
    expect(alert).not.toHaveTextContent('Network Error');
    expect(screen.queryByText('Meta não encontrada.')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('heading', { name: 'Viagem' })).toBeInTheDocument();
  });

  it('aporte inválido mostra mensagem inline e não chama a API', async () => {
    mount();
    await screen.findByRole('heading', { name: 'Viagem' });
    await userEvent.click(screen.getByRole('button', { name: 'Adicionar aporte' }));
    const input = screen.getByLabelText('Valor (R$)');
    await userEvent.type(input, '0');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    expect(screen.getByText('Informe um valor maior que zero')).toBeInTheDocument();
    expect(input).toHaveAccessibleDescription('Informe um valor maior que zero');
    expect(goalsAPI.addContribution).not.toHaveBeenCalled();

    vi.mocked(goalsAPI.addContribution).mockResolvedValue(response({}));
    await userEvent.clear(input);
    await userEvent.type(input, '1.500,50');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(goalsAPI.addContribution).toHaveBeenCalledWith('goal-1', { amount: 1500.5, notes: undefined }));
  });
});
