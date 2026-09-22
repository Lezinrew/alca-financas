import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CreditCardExpenseForm from './CreditCardExpenseForm';
import CreditCardImportModal from './CreditCardImportModal';
import { accountsAPI } from '../../utils/api';

vi.mock('../../utils/api', () => ({ accountsAPI: { import: vi.fn() } }));

const card = { id: 'card-1', name: 'Cartão Roxo', limit: 5000, closingDay: 10, dueDay: 17, color: '#111' };
const categories = [{ id: 'cat-1', name: 'Mercado', type: 'expense', color: '#0f0', icon: 'cart' }];
const props = () => ({ card, categories, onHide: vi.fn(), onSubmit: vi.fn<(data: unknown) => Promise<void>>() });

beforeEach(() => vi.clearAllMocks());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const fill = async () => {
  fireEvent.change(screen.getByLabelText('Valor *'), { target: { value: '150' } });
  await userEvent.selectOptions(screen.getByLabelText('Categoria *'), 'cat-1');
};

describe('CreditCardExpenseForm', () => {
  it('bloqueia duplo envio e fechar enquanto salva', async () => {
    let finish!: () => void;
    const callbacks = props();
    callbacks.onSubmit.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve; }));
    render(<CreditCardExpenseForm {...callbacks} />);
    expect(screen.getByLabelText('Valor *')).toHaveFocus();
    await fill();
    const save = screen.getByRole('button', { name: 'Salvar despesa' });
    await userEvent.click(save);
    await userEvent.click(screen.getByRole('button', { name: 'Salvando…' }));
    fireEvent.submit(save.closest('form')!);
    expect(callbacks.onSubmit).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Salvando…' })).toBeDisabled();
    await userEvent.keyboard('{Escape}');
    expect(callbacks.onHide).not.toHaveBeenCalled();
    finish();
    await waitFor(() => expect(callbacks.onHide).toHaveBeenCalledOnce());
    expect(callbacks.onSubmit).toHaveBeenCalledWith(expect.objectContaining({ amount: 150, category_id: 'cat-1', account_id: 'card-1', is_recurring: false }));
  });

  it('pede confirmação antes de descartar dados não salvos', async () => {
    const callbacks = props();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<CreditCardExpenseForm {...callbacks} />);
    await fill();
    await userEvent.keyboard('{Escape}');
    expect(confirm).toHaveBeenCalledOnce();
    expect(callbacks.onHide).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(callbacks.onHide).toHaveBeenCalledOnce();
  });

  it('mantém dados e mostra erro quando salvar falha', async () => {
    const callbacks = props();
    callbacks.onSubmit.mockRejectedValueOnce(new Error('boom'));
    render(<CreditCardExpenseForm {...callbacks} />);
    await fill();
    await userEvent.click(screen.getByRole('button', { name: 'Salvar despesa' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByLabelText('Categoria *')).toHaveValue('cat-1');
    expect(callbacks.onHide).not.toHaveBeenCalled();
  });

  it('valida valor e categoria antes de enviar', async () => {
    const callbacks = props();
    render(<CreditCardExpenseForm {...callbacks} />);
    await userEvent.click(screen.getByRole('button', { name: 'Salvar despesa' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Deve ter um valor diferente de 0');
    expect(callbacks.onSubmit).not.toHaveBeenCalled();
  });
});

describe('CreditCardImportModal', () => {
  it('importa uma vez, mostra resultado e só fecha pelo botão Fechar', async () => {
    let finish!: () => void;
    vi.mocked(accountsAPI.import).mockImplementationOnce(() => new Promise(resolve => {
      finish = () => resolve({ data: { imported_count: 3, duplicates_skipped: 1 } } as never);
    }));
    const onHide = vi.fn();
    const onSuccess = vi.fn();
    render(<CreditCardImportModal cardId="card-1" onHide={onHide} onSuccess={onSuccess} />);
    const file = new File(['ofx'], 'fatura.ofx', { type: 'application/octet-stream' });
    await userEvent.upload(screen.getByLabelText('Selecione o arquivo da fatura'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Importando…' }));
    expect(accountsAPI.import).toHaveBeenCalledOnce();
    finish();
    expect(await screen.findByRole('status')).toHaveTextContent('3 transação(ões) adicionada(s). 1 duplicada(s) ignorada(s).');
    expect(onSuccess).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }));
    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onHide).not.toHaveBeenCalled();
  });
});
