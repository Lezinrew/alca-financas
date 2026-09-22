import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Import from './Import';
import { accountsAPI, transactionsAPI } from '../../utils/api';
import type { ImportBatchRecord } from '../../types/transaction';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('../../utils/api', () => ({
  transactionsAPI: { import: vi.fn(), getImportBatches: vi.fn(), rollbackImportBatch: vi.fn() },
  accountsAPI: { getAll: vi.fn(), import: vi.fn() },
}));

const batch: ImportBatchRecord = {
  id: 'batch-12345678', filename: 'extrato-setembro.ofx', file_format: 'ofx', total_parsed: 12, imported_count: 10,
  ignored_count: 0, duplicate_count: 2, unclassified_count: 0, total_income: 100, total_expense: 50, total_transfer: 0,
  status: 'completed', created_at: '2026-09-20T10:00:00Z',
};
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const pickFile = async (name = 'extrato.ofx') => {
  const input = document.getElementById('importFile') as HTMLInputElement;
  await userEvent.upload(input, new File(['OFXHEADER'], name, { type: 'text/plain' }));
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'error').mockImplementation(() => undefined);
  vi.mocked(accountsAPI.getAll).mockResolvedValue(response([
    { id: 'acc-1', name: 'Conta Nubank', type: 'checking' },
    { id: 'acc-2', name: 'Conta Itaú', type: 'checking' },
  ]));
  vi.mocked(transactionsAPI.getImportBatches).mockResolvedValue(response({ batches: [batch] }));
  vi.mocked(transactionsAPI.rollbackImportBatch).mockResolvedValue(response({ message: 'Lote desfeito' }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Import', () => {
  it('tabs usam rótulos claros e semântica de tablist', async () => {
    render(<Import />);
    const tablist = screen.getByRole('tablist', { name: 'Tipo de importação' });
    const tabs = within(tablist).getAllByRole('tab');
    expect(tabs.map(tab => tab.textContent)).toEqual(['Conta corrente', 'Cartão de crédito', 'Histórico de importações']);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'import-panel-debit');
    expect(await screen.findByRole('button', { name: 'Escolher arquivo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Importar' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Saiba como funciona' })).not.toBeInTheDocument();
  });

  it('desfazer importação só chama a API depois de confirmar no diálogo', async () => {
    render(<Import />);
    await userEvent.click(screen.getByRole('tab', { name: 'Histórico de importações' }));
    const undo = await screen.findByRole('button', { name: `Desfazer importação de ${batch.filename}` });
    await userEvent.click(undo);
    let dialog = within(screen.getByRole('dialog', { name: 'Desfazer importação' }));
    expect(dialog.getByText(batch.filename)).toBeInTheDocument();
    expect(dialog.getByText('10')).toBeInTheDocument();
    expect(transactionsAPI.rollbackImportBatch).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(transactionsAPI.rollbackImportBatch).not.toHaveBeenCalled();

    const pending = deferred<ReturnType<typeof response>>();
    vi.mocked(transactionsAPI.rollbackImportBatch).mockImplementationOnce(() => pending.promise);
    await userEvent.click(undo);
    dialog = within(screen.getByRole('dialog', { name: 'Desfazer importação' }));
    const confirm = dialog.getByRole('button', { name: 'Desfazer importação' });
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(transactionsAPI.rollbackImportBatch).toHaveBeenCalledExactlyOnceWith(batch.id);
    expect(dialog.getByRole('button', { name: 'Confirmando…' })).toBeDisabled();
    await act(async () => pending.resolve(response({ message: 'Lote desfeito' })));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(await screen.findByText('Lote desfeito')).toBeInTheDocument();
    expect(transactionsAPI.getImportBatches).toHaveBeenCalledTimes(2);
  });

  it('falha ao carregar contas mostra banner com retry e bloqueia o envio', async () => {
    vi.mocked(accountsAPI.getAll).mockRejectedValueOnce(new Error('offline'));
    render(<Import />);
    const banner = await screen.findByRole('alert');
    expect(within(banner).getByText(/Não foi possível carregar suas contas/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Importar' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Escolher arquivo' })).toBeDisabled();
    expect(screen.getByRole('option', { name: 'Contas indisponíveis' })).toBeInTheDocument();

    await userEvent.click(within(banner).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('option', { name: /Conta Nubank/ })).toBeInTheDocument();
    expect(accountsAPI.getAll).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Escolher arquivo' })).toBeEnabled();
  });

  it('resposta sem a forma esperada vira erro fixo, sem card de resultado', async () => {
    vi.mocked(transactionsAPI.import).mockResolvedValueOnce(response('<html>erro</html>'));
    render(<Import />);
    await screen.findByRole('option', { name: /Conta Nubank/ });
    await pickFile();
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    expect(await screen.findByText(/Não foi possível importar o arquivo/)).toBeInTheDocument();
    expect(screen.queryByText('Resultado da importação')).not.toBeInTheDocument();
  });

  it('envio duplicado é bloqueado e o resultado lista erros com "Mostrar todos"', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    vi.mocked(transactionsAPI.import).mockImplementationOnce(() => pending.promise);
    render(<Import />);
    await screen.findByRole('option', { name: /Conta Nubank/ });
    await pickFile();
    const submit = screen.getByRole('button', { name: 'Importar' });
    fireEvent.click(submit); fireEvent.click(submit);
    expect(transactionsAPI.import).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
    const errors = Array.from({ length: 12 }, (_, i) => `Linha ${i + 1}: valor inválido`);
    await act(async () => pending.resolve(response({ imported_count: 3, error_count: 12, errors })));
    expect(await screen.findByText('Resultado da importação')).toBeInTheDocument();
    expect(screen.getByText('Linha 10: valor inválido')).toBeInTheDocument();
    expect(screen.getByText('Mostrar todos (2 restantes)')).toBeInTheDocument();
    expect(screen.getByText('Linha 12: valor inválido')).toBeInTheDocument();
  });
});
