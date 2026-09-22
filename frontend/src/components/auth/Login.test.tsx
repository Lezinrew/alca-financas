import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Login from './Login';

const login = vi.fn();
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ login }) }));
vi.mock('./LoginVisualPanel', () => ({ default: () => null }));

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

const renderLogin = (state?: unknown) =>
  render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
      <Login />
    </MemoryRouter>
  );

describe('Login', () => {
  it('toggle de senha é acessível e alterna o tipo do campo', async () => {
    renderLogin();
    const toggle = screen.getByRole('button', { name: 'Mostrar senha' });
    expect(toggle).not.toHaveAttribute('tabindex', '-1');
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    expect(toggle.className).toMatch(/min-h-\[44px\]/);
    expect(screen.getByLabelText('Senha')).toHaveAttribute('type', 'password');

    await userEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('type', 'text');

    // Alcançável por teclado: o próximo tab a partir do campo de senha é o toggle.
    screen.getByLabelText('Senha').focus();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveFocus();
  });

  it('erro de servidor não marca os campos como inválidos', async () => {
    login.mockResolvedValueOnce({ success: false, message: 'E-mail ou senha incorretos.' });
    renderLogin();
    await userEvent.type(screen.getByLabelText('E-mail'), 'a@b.com');
    await userEvent.type(screen.getByLabelText('Senha'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('E-mail ou senha incorretos.');
    expect(screen.getByLabelText('E-mail')).not.toHaveAttribute('aria-invalid');
    expect(screen.getByLabelText('Senha')).not.toHaveAttribute('aria-invalid');
  });

  it('erro de validação marca apenas o campo vazio', async () => {
    renderLogin();
    await userEvent.type(screen.getByLabelText('E-mail'), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    const alert = await screen.findByRole('alert');
    expect(screen.getByLabelText('E-mail')).not.toHaveAttribute('aria-invalid');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-describedby', alert.id);
    expect(login).not.toHaveBeenCalled();
  });

  it('mantém o aviso pós-cadastro ao digitar e oculta "Lembrar-me"', async () => {
    renderLogin({ registrationNotice: 'Conta criada. Verifique seu e-mail.' });
    expect(await screen.findByRole('status')).toHaveTextContent('Conta criada');
    await userEvent.type(screen.getByLabelText('E-mail'), 'a');
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByLabelText(/lembrar/i)).not.toBeInTheDocument();
  });
});
