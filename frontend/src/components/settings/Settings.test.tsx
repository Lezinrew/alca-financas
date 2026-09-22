import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Settings from './Settings';
import { authAPI } from '../../utils/api';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key, i18n: { changeLanguage: vi.fn() } }) }));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', name: 'Ana', email: 'ana@example.com' }, updateUser: vi.fn() }) }));
vi.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'light', setTheme: vi.fn() }) }));
vi.mock('../../utils/api', () => ({
  authAPI: { getSettings: vi.fn(), updateSettings: vi.fn(), exportBackup: vi.fn(), importBackup: vi.fn(), clearAllData: vi.fn() },
  categoriesAPI: { import: vi.fn() },
  invalidateLookupCache: vi.fn(),
}));

const response = <T,>(data: T) => ({ data }) as never;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authAPI.getSettings).mockResolvedValue(response({ currency: 'EUR', theme: 'light', language: 'pt' }));
});
afterEach(cleanup);

describe('Settings', () => {
  it('limpar dados só habilita a exclusão após digitar EXCLUIR e bloqueia envio duplicado', async () => {
    let resolve!: () => void;
    vi.mocked(authAPI.clearAllData).mockImplementation(() => new Promise(done => { resolve = () => done(response({ deleted: { transactions: 3, goals: 1 } })); }));
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText('settings.currency')).toHaveValue('EUR'));
    await userEvent.click(screen.getByRole('button', { name: 'Limpar Todos os Dados' }));
    const dialog = screen.getByRole('dialog', { name: 'Limpar todos os dados' });
    expect(dialog).toHaveTextContent('contas a pagar');
    expect(dialog).toHaveTextContent('conversas do assistente');
    const confirm = screen.getByRole('button', { name: 'Excluir todos os dados' });
    expect(confirm).toBeDisabled();
    const input = screen.getByLabelText('Digite EXCLUIR para confirmar');
    expect(input).toHaveFocus();
    await userEvent.type(input, 'excluir');
    expect(confirm).toBeDisabled();
    await userEvent.clear(input);
    await userEvent.type(input, 'EXCLUIR');
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(authAPI.clearAllData).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Limpando…' })).toBeDisabled();
    resolve();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('status')).toHaveTextContent('Limpeza concluída: 3 transações, 1 metas.');
  });

  it('falha ao carregar preferências mostra banner e desabilita Salvar sem sobrescrever com padrões', async () => {
    vi.mocked(authAPI.getSettings).mockRejectedValue(new Error('offline'));
    render(<Settings />);
    await screen.findByText('Preferências indisponíveis.');
    expect(screen.getByRole('button', { name: 'settings.save' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'settings.save' }));
    expect(authAPI.updateSettings).not.toHaveBeenCalled();
    vi.mocked(authAPI.getSettings).mockResolvedValueOnce(response({ currency: 'GBP', theme: 'light', language: 'en' }));
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'settings.save' })).toBeEnabled());
    expect(screen.getByLabelText('settings.currency')).toHaveValue('GBP');
  });

  it('arquivo de backup inválido é rejeitado antes de qualquer confirmação; válido pede confirmação', async () => {
    render(<Settings />);
    const input = screen.getByLabelText('Selecionar arquivo de backup');
    await userEvent.upload(input, new File(['isto não é json'], 'ruim.json', { type: 'application/json' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('O arquivo não é um backup válido.');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(authAPI.importBackup).not.toHaveBeenCalled();

    vi.mocked(authAPI.importBackup).mockResolvedValue(response({ imported: { categories: 2, accounts: 1, transactions: 0 } }));
    await userEvent.upload(input, new File([JSON.stringify({ categories: [{}, {}], accounts: [{}] })], 'bom.json', { type: 'application/json' }));
    const dialog = await screen.findByRole('dialog', { name: 'Importar backup' });
    expect(dialog).toHaveTextContent('bom.json');
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    await waitFor(() => expect(authAPI.importBackup).toHaveBeenCalledOnce());
    expect(await screen.findByRole('status')).toHaveTextContent('2 categorias, 1 contas e 0 transações importadas');
  });
});
