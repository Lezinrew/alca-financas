import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Accounts from './Accounts';
import { accountsAPI } from '../../utils/api';
import type { Account } from '../../types/account';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../../utils/api', () => ({
  accountsAPI: { getAll: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  formatCurrency: (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value),
}));

const wallet: Account = { id: 'acc-1', name: 'Carteira Principal', type: 'wallet', current_balance: 150.5, projected_balance: 150.5, is_active: true };
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const mount = () => render(<MemoryRouter><Accounts /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(accountsAPI.getAll).mockResolvedValue(response([wallet]));
  vi.mocked(accountsAPI.delete).mockResolvedValue(response({}));
  vi.mocked(accountsAPI.create).mockResolvedValue(response(wallet));
});
afterEach(cleanup);

describe('Accounts', () => {
  it('falha de rede mostra indisponibilidade, sem saldo zero nem estado vazio falso', async () => {
    vi.mocked(accountsAPI.getAll).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Indisponível.');
    expect(within(alert).getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(screen.queryByText('Network Error')).not.toBeInTheDocument();
    expect(screen.queryByText(/R\$.*0,00/)).not.toBeInTheDocument();
    expect(screen.queryByText('Nenhuma conta cadastrada')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Resumo das contas' })).getAllByText('—')).toHaveLength(2);
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    await screen.findByRole('article', { name: wallet.name });
    expect(accountsAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('exclusão só chama a API após confirmar no diálogo que nomeia a conta', async () => {
    mount();
    await screen.findByRole('article', { name: wallet.name });
    await userEvent.click(screen.getByRole('button', { name: `Mais ações para ${wallet.name}` }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Excluir' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Excluir conta' }));
    expect(dialog.getByText(wallet.name)).toBeInTheDocument();
    expect(dialog.getByText('Carteira')).toBeInTheDocument();
    expect(dialog.getByText(/150,50/)).toBeInTheDocument();
    expect(accountsAPI.delete).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(accountsAPI.delete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: `Mais ações para ${wallet.name}` }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Excluir' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirmar exclusão' }));
    await waitFor(() => expect(accountsAPI.delete).toHaveBeenCalledExactlyOnceWith(wallet.id));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(accountsAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('menu de ações fecha com Escape e devolve o foco ao botão', async () => {
    mount();
    await screen.findByRole('article', { name: wallet.name });
    const trigger = screen.getByRole('button', { name: `Mais ações para ${wallet.name}` });
    await userEvent.click(trigger);
    expect(screen.getByRole('menu')).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('formulário foca o nome, bloqueia duplo envio e mostra erro fixo em falha', async () => {
    mount();
    await screen.findByRole('article', { name: wallet.name });
    await userEvent.click(screen.getByRole('button', { name: /Nova conta/ }));
    const dialog = within(screen.getByRole('dialog', { name: 'Nova conta' }));
    const name = dialog.getByLabelText('Nome da conta *');
    expect(name).toHaveFocus();
    await userEvent.type(name, 'Nubank');
    const pending = deferred<ReturnType<typeof response>>();
    vi.mocked(accountsAPI.create).mockImplementationOnce(() => pending.promise);
    const save = dialog.getByRole('button', { name: 'Salvar conta' });
    fireEvent.click(save); fireEvent.click(save);
    expect(accountsAPI.create).toHaveBeenCalledTimes(1);
    expect(accountsAPI.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Nubank', type: 'wallet' }));
    expect(dialog.getByRole('button', { name: 'Salvando…' })).toBeDisabled();
    await act(async () => pending.resolve(response(wallet)));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    vi.mocked(accountsAPI.create).mockRejectedValueOnce(new Error('Network Error'));
    await userEvent.click(screen.getByRole('button', { name: /Nova conta/ }));
    await userEvent.type(screen.getByLabelText('Nome da conta *'), 'Inter');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível salvar a conta.');
    expect(screen.queryByText('Network Error')).not.toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
