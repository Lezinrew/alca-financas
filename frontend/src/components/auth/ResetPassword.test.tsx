import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ResetPassword from './ResetPassword';

const authState = { isAuthenticated: false };
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => authState }));
vi.mock('./LoginVisualPanel', () => ({ default: () => null }));

const exchangeCodeForSession = vi.fn();
const getSession = vi.fn();
const updateUser = vi.fn();
vi.mock('../../utils/supabaseClient', () => ({
  supabase: {
    auth: {
      exchangeCodeForSession: (...args: unknown[]) => exchangeCodeForSession(...args),
      getSession: (...args: unknown[]) => getSession(...args),
      updateUser: (...args: unknown[]) => updateUser(...args),
    },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  authState.isAuthenticated = false;
  exchangeCodeForSession.mockResolvedValue({ error: null });
  getSession.mockResolvedValue({ data: { session: { user: {} } } });
  updateUser.mockResolvedValue({ error: null });
});
afterEach(() => cleanup());

const renderReset = (path = '/reset-password?code=abc') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/dashboard" element={<div>DASHBOARD</div>} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>
  );

describe('ResetPassword', () => {
  it('renderiza o formulário mesmo autenticado, sem redirecionar', async () => {
    authState.isAuthenticated = true;
    renderReset();
    expect(screen.getByRole('status')).toHaveTextContent('Validando link');
    expect(screen.getByLabelText('Nova senha')).toBeDisabled();
    await waitFor(() => expect(screen.getByLabelText('Nova senha')).toBeEnabled());
    expect(exchangeCodeForSession).toHaveBeenCalledOnce();
    expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Redefinir senha' })).toBeEnabled();
  });

  it('após sucesso, autenticado leva ao painel', async () => {
    authState.isAuthenticated = true;
    renderReset();
    await waitFor(() => expect(screen.getByLabelText('Nova senha')).toBeEnabled());
    await userEvent.type(screen.getByLabelText('Nova senha'), 'novasenha1');
    await userEvent.type(screen.getByLabelText('Confirmar senha'), 'novasenha1');
    await userEvent.click(screen.getByRole('button', { name: 'Redefinir senha' }));
    expect(await screen.findByRole('link', { name: 'Ir para o painel' })).toHaveAttribute('href', '/dashboard');
    expect(updateUser).toHaveBeenCalledWith({ password: 'novasenha1' });
  });

  it('após sucesso, não autenticado leva ao login', async () => {
    renderReset('/reset-password');
    await waitFor(() => expect(screen.getByLabelText('Nova senha')).toBeEnabled());
    await userEvent.type(screen.getByLabelText('Nova senha'), 'novasenha1');
    await userEvent.type(screen.getByLabelText('Confirmar senha'), 'novasenha1');
    await userEvent.click(screen.getByRole('button', { name: 'Redefinir senha' }));
    expect(await screen.findByRole('link', { name: 'Ir para o login' })).toHaveAttribute('href', '/login');
  });

  it('cada campo tem seu próprio toggle e o erro de confirmação marca só o campo certo', async () => {
    renderReset();
    await waitFor(() => expect(screen.getByLabelText('Nova senha')).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar confirmação de senha' }));
    expect(screen.getByLabelText('Confirmar senha')).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText('Nova senha')).toHaveAttribute('type', 'password');

    await userEvent.type(screen.getByLabelText('Nova senha'), 'novasenha1');
    await userEvent.type(screen.getByLabelText('Confirmar senha'), 'outra');
    await userEvent.click(screen.getByRole('button', { name: 'Redefinir senha' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('As senhas não coincidem.');
    expect(screen.getByLabelText('Confirmar senha')).toHaveAttribute('aria-describedby', alert.id);
    expect(screen.getByLabelText('Nova senha')).not.toHaveAttribute('aria-invalid');
    expect(updateUser).not.toHaveBeenCalled();
  });

  it('erro na troca do código passa pelo formatador', async () => {
    exchangeCodeForSession.mockResolvedValueOnce({ error: { message: 'Failed to fetch' } });
    renderReset();
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar');
  });
});
