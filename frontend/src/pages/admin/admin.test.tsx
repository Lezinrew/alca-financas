import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AdminLogs from './AdminLogs';
import AdminDashboard from './AdminDashboard';
import UserManagement from './UserManagement';
import UserDetail from './UserDetail';
import { adminAPI } from '../../utils/api';

vi.mock('../../contexts/AuthContext', () => {
  // Objeto estável: um `user` novo a cada render dispararia o efeito de carregamento em loop.
  const auth = { user: { id: 'admin-1', role: 'admin', is_admin: true }, isAuthenticated: true, loading: false };
  return { useAuth: () => auth };
});
vi.mock('../../utils/api', () => ({
  adminAPI: {
    getStats: vi.fn(), getUserStats: vi.fn(), getUsers: vi.fn(), getUserDetails: vi.fn(), getLogs: vi.fn(),
    exportUserData: vi.fn(), patchUserRole: vi.fn(), patchUserStatus: vi.fn(), sendInactiveWarning: vi.fn(),
    reactivateUser: vi.fn(), deleteUser: vi.fn(), purgeUser: vi.fn(),
  },
}));

const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};

const row = {
  id: 'user-1', name: 'Maria Silva', email: 'Maria@Exemplo.com', role: 'user', status: 'active',
  created_at: '2026-01-01T00:00:00Z', auth_providers: [{ provider: 'email' }],
};
const details = {
  user: { id: 'user-1', name: 'Maria Silva', email: 'maria@exemplo.com', role: 'user', is_admin: false, is_blocked: false, created_at: '2026-01-01T00:00:00Z', auth_provider: 'email' },
  stats: { transactions: 1, categories: 1, accounts: 1, total_income: 10, total_expense: 5, balance: 5 },
  recent_transactions: [], accounts: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(adminAPI.getUsers).mockResolvedValue(response({ users: [row], pages: 1 }));
  vi.mocked(adminAPI.getUserStats).mockResolvedValue(response({ total_users: 1, active: 1, inactive: 0, pending_deletion: 0, disabled: 0, admins: 1 }));
  vi.mocked(adminAPI.getUserDetails).mockResolvedValue(response(details));
  vi.mocked(adminAPI.patchUserStatus).mockResolvedValue(response({}));
  vi.mocked(adminAPI.purgeUser).mockResolvedValue(response({}));
});
afterEach(() => cleanup());

describe('AdminLogs', () => {
  it('falha de carregamento mostra indisponibilidade em vez de "Nenhum log"', async () => {
    vi.mocked(adminAPI.getLogs).mockRejectedValueOnce(new Error('offline'));
    render(<MemoryRouter><AdminLogs /></MemoryRouter>);
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText('Indisponível.')).toBeInTheDocument();
    expect(within(alert).getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
    expect(screen.queryByText('Nenhum log registrado ainda')).not.toBeInTheDocument();
    vi.mocked(adminAPI.getLogs).mockResolvedValueOnce(response({ logs: [] }));
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByText('Nenhum log registrado ainda')).toBeInTheDocument();
    expect(adminAPI.getLogs).toHaveBeenCalledTimes(2);
  });

  it('descarta a resposta da página 1 que chega depois da página 2', async () => {
    const first = deferred<ReturnType<typeof response>>();
    const log = (id: string, admin_email: string) => ({ id, admin_id: 'a', admin_email, action: 'purge_user', target_id: null, details: {}, ip_address: null, timestamp: '2026-09-01T10:00:00Z' });
    vi.mocked(adminAPI.getLogs).mockImplementationOnce(() => first.promise);
    render(<MemoryRouter><AdminLogs /></MemoryRouter>);
    await act(async () => { first.resolve(response({ logs: Array.from({ length: 50 }, (_, i) => log(`p1-${i}`, 'pagina1@exemplo.com')) })); });
    const second = deferred<ReturnType<typeof response>>();
    vi.mocked(adminAPI.getLogs).mockImplementationOnce(() => second.promise);
    await userEvent.click(screen.getByRole('button', { name: 'Próxima' }));
    await act(async () => { second.resolve(response({ logs: [log('p2-0', 'pagina2@exemplo.com')] })); });
    expect(screen.getByText('pagina2@exemplo.com')).toBeInTheDocument();
    expect(screen.queryByText('pagina1@exemplo.com')).not.toBeInTheDocument();
  });
});

describe('AdminDashboard', () => {
  it('falha mostra bloco indisponível sem cartões vazios', async () => {
    vi.mocked(adminAPI.getStats).mockRejectedValueOnce(new Error('offline'));
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Indisponível.');
    expect(screen.queryByText('Total de Usuários')).not.toBeInTheDocument();
  });
});

describe('UserManagement', () => {
  const mount = () => render(<MemoryRouter><UserManagement /></MemoryRouter>);
  const ready = async () => { await screen.findAllByText('Maria Silva'); };

  it('botão Apagar só habilita quando o e-mail digitado é igual ao do usuário', async () => {
    mount(); await ready();
    await userEvent.click(screen.getAllByRole('button', { name: 'Excluir total' })[0]);
    const dialog = within(screen.getByRole('dialog', { name: 'Exclusão total da conta' }));
    const input = dialog.getByLabelText('Digite o e-mail do usuário para confirmar');
    expect(input).toHaveFocus();
    const apagar = dialog.getByRole('button', { name: 'Apagar' });
    expect(apagar).toBeDisabled();
    fireEvent.change(input, { target: { value: 'outra@exemplo.com' } });
    expect(apagar).toBeDisabled();
    fireEvent.change(input, { target: { value: '  MARIA@exemplo.COM ' } });
    expect(apagar).toBeEnabled();
    const purge = deferred<ReturnType<typeof response>>();
    vi.mocked(adminAPI.purgeUser).mockImplementationOnce(() => purge.promise);
    fireEvent.click(apagar); fireEvent.click(apagar);
    expect(adminAPI.purgeUser).toHaveBeenCalledExactlyOnceWith('user-1', { confirm_email: 'MARIA@exemplo.COM' });
    expect(dialog.getByRole('button', { name: 'Apagando…' })).toBeDisabled();
    await act(async () => purge.resolve(response({})));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('mudança de estado só chama a API após confirmar', async () => {
    mount(); await ready();
    await userEvent.click(screen.getAllByRole('button', { name: 'Inativo' }).slice(-1)[0]);
    let dialog = within(screen.getByRole('dialog', { name: 'Marcar como inativo' }));
    expect(dialog.getByText('Maria Silva (Maria@Exemplo.com)')).toBeInTheDocument();
    expect(adminAPI.patchUserStatus).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(adminAPI.patchUserStatus).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByRole('button', { name: 'Pend. exclusão' }).slice(-1)[0]);
    dialog = within(screen.getByRole('dialog', { name: 'Marcar para exclusão' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Marcar para exclusão' }));
    await waitFor(() => expect(adminAPI.patchUserStatus).toHaveBeenCalledExactlyOnceWith('user-1', 'pending_deletion'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('campo de busca tem rótulo acessível', async () => {
    mount(); await ready();
    expect(screen.getByRole('textbox', { name: 'Buscar por nome ou e-mail' })).toBeInTheDocument();
  });
});

describe('UserDetail', () => {
  it('bloquear só chama a API após confirmar', async () => {
    render(<MemoryRouter initialEntries={['/admin/users/user-1']}><Routes><Route path="/admin/users/:userId" element={<UserDetail />} /></Routes></MemoryRouter>);
    await screen.findByText('Detalhes do Usuário');
    await userEvent.click(screen.getByRole('button', { name: 'Bloquear' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Bloquear usuário' }));
    expect(adminAPI.patchUserStatus).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Bloquear' }));
    await waitFor(() => expect(adminAPI.patchUserStatus).toHaveBeenCalledExactlyOnceWith('user-1', 'disabled'));
  });
});
