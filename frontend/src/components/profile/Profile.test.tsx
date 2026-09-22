import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Profile from './Profile';
import { supabase } from '../../utils/supabaseClient';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', name: 'Ana', email: 'ana@example.com' } }) }));
vi.mock('../../utils/supabaseClient', () => ({
  supabase: { auth: { signInWithPassword: vi.fn(), updateUser: vi.fn(), refreshSession: vi.fn() } },
}));

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

describe('Profile', () => {
  it('não simula atualização de perfil: campos somente leitura com aviso e sem sucesso falso', () => {
    render(<Profile />);
    expect(screen.queryByRole('button', { name: /Atualizar Perfil/ })).not.toBeInTheDocument();
    expect(screen.getByText(/A edição do perfil ainda não está disponível/)).toBeInTheDocument();
    const name = screen.getByLabelText('Nome Completo');
    expect(name).toHaveAttribute('readonly');
    expect(name).toHaveValue('Ana');
    expect(screen.queryByText('Perfil atualizado com sucesso!')).not.toBeInTheDocument();
    expect(screen.queryByText('Membro desde')).not.toBeInTheDocument();
    expect(screen.queryByText('Último acesso')).not.toBeInTheDocument();
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
