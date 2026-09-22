import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Profile from './Profile';
import { supabase } from '../../utils/supabaseClient';
import { authAPI } from '../../utils/api';

const updateUser = vi.fn();
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'u1', name: 'Ana', email: 'ana@example.com' }, updateUser }),
}));
vi.mock('../../utils/api', () => ({ authAPI: { updateProfile: vi.fn() } }));
vi.mock('../../utils/supabaseClient', () => ({
  supabase: { auth: { signInWithPassword: vi.fn(), updateUser: vi.fn(), refreshSession: vi.fn() } },
}));

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

describe('Profile', () => {
  it('e-mail é somente leitura com orientação honesta; nome é editável', () => {
    render(<Profile />);
    expect(screen.queryByText(/ainda não está disponível/)).not.toBeInTheDocument();
    const email = screen.getByLabelText('Email');
    expect(email).toHaveAttribute('readonly');
    expect(email).toHaveValue('ana@example.com');
    expect(email).toHaveAccessibleDescription('Para alterar o e-mail, fale com o suporte.');
    const name = screen.getByLabelText('Nome Completo');
    expect(name).not.toHaveAttribute('readonly');
    expect(name).toHaveValue('Ana');
    expect(screen.getByRole('button', { name: 'Salvar nome' })).toBeDisabled();
    expect(screen.queryByText('Membro desde')).not.toBeInTheDocument();
  });

  it('salva o nome e mostra sucesso só após a resposta da API', async () => {
    let resolve!: () => void;
    const saved = { id: 'u1', name: 'Ana Souza', email: 'ana@example.com', role: 'user' };
    vi.mocked(authAPI.updateProfile).mockImplementation(
      () => new Promise(done => { resolve = () => done({ data: saved } as never); }),
    );
    render(<Profile />);
    const name = screen.getByLabelText('Nome Completo');
    await userEvent.clear(name);
    await userEvent.type(name, '  Ana Souza ');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nome' }));
    expect(authAPI.updateProfile).toHaveBeenCalledWith({ name: 'Ana Souza' });
    expect(screen.queryByText('Nome atualizado com sucesso!')).not.toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
    resolve();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Nome atualizado com sucesso!'));
    expect(updateUser).toHaveBeenCalledWith(saved);
  });

  it('erro da API mostra texto fixo e nunca sucesso falso', async () => {
    vi.mocked(authAPI.updateProfile).mockRejectedValue({ response: { status: 500, data: { error: 'stack trace interno' } } });
    render(<Profile />);
    const name = screen.getByLabelText('Nome Completo');
    await userEvent.clear(name);
    await userEvent.type(name, 'Ana Souza');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nome' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível salvar o nome. Tente novamente.'));
    expect(screen.queryByText('stack trace interno')).not.toBeInTheDocument();
    expect(screen.queryByText('Nome atualizado com sucesso!')).not.toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
    expect(name).toHaveValue('Ana Souza');
  });

  it('bloqueia envio duplicado do nome', async () => {
    let resolve!: () => void;
    vi.mocked(authAPI.updateProfile).mockImplementation(
      () => new Promise(done => { resolve = () => done({ data: { id: 'u1', name: 'Ana Souza', email: 'ana@example.com' } } as never); }),
    );
    render(<Profile />);
    const name = screen.getByLabelText('Nome Completo');
    await userEvent.clear(name);
    await userEvent.type(name, 'Ana Souza');
    const form = name.closest('form')!;
    fireEvent.submit(form); fireEvent.submit(form);
    expect(authAPI.updateProfile).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Salvando...' })).toBeDisabled();
    resolve();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Salvar nome' })).toBeInTheDocument());
    expect(authAPI.updateProfile).toHaveBeenCalledOnce();
  });

  it('valida o nome inline com aria-describedby e não chama a API', async () => {
    render(<Profile />);
    const name = screen.getByLabelText('Nome Completo');
    await userEvent.clear(name);
    await userEvent.type(name, ' A ');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nome' }));
    expect(name).toHaveAttribute('aria-invalid', 'true');
    expect(name).toHaveAccessibleDescription(/pelo menos 2 caracteres/);
    expect(name).toHaveFocus();
    expect(authAPI.updateProfile).not.toHaveBeenCalled();
  });

  it('valida a senha inline com aria-describedby e não chama o Supabase', async () => {
    render(<Profile />);
    await userEvent.type(screen.getByLabelText('Senha Atual'), 'antiga1');
    await userEvent.type(screen.getByLabelText('Nova Senha'), '123');
    await userEvent.type(screen.getByLabelText('Confirmar Nova Senha'), '456');
    await userEvent.click(screen.getByRole('button', { name: 'Alterar Senha' }));
    const newPassword = screen.getByLabelText('Nova Senha');
    expect(newPassword).toHaveAttribute('aria-invalid', 'true');
    expect(newPassword).toHaveAccessibleDescription(/pelo menos 6 caracteres/);
    expect(newPassword).toHaveFocus();
    expect(screen.getByLabelText('Confirmar Nova Senha')).toHaveAccessibleDescription('As senhas não coincidem.');
    expect(supabase.auth.signInWithPassword).not.toHaveBeenCalled();
  });

  it('bloqueia envio duplicado enquanto a troca de senha está em andamento', async () => {
    let resolve!: () => void;
    vi.mocked(supabase.auth.signInWithPassword).mockImplementation(() => new Promise(done => { resolve = () => done({ error: null } as never); }));
    vi.mocked(supabase.auth.updateUser).mockResolvedValue({ error: null } as never);
    vi.mocked(supabase.auth.refreshSession).mockResolvedValue({} as never);
    render(<Profile />);
    await userEvent.type(screen.getByLabelText('Senha Atual'), 'antiga1');
    await userEvent.type(screen.getByLabelText('Nova Senha'), 'nova123');
    await userEvent.type(screen.getByLabelText('Confirmar Nova Senha'), 'nova123');
    const form = screen.getByLabelText('Senha Atual').closest('form')!;
    fireEvent.submit(form); fireEvent.submit(form);
    expect(supabase.auth.signInWithPassword).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'common.loading' })).toBeDisabled();
    resolve();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Senha alterada com sucesso!'));
    expect(supabase.auth.updateUser).toHaveBeenCalledWith({ password: 'nova123' });
    expect(screen.getByLabelText('Nova Senha')).toHaveValue('');
  });
});
