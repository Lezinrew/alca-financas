import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExpenseFormDialog } from './ExpenseFormDialog';
import { ExpenseDialog } from './ExpenseDialog';
import { financialExpensesAPI, type FinancialExpense } from '../../utils/api';

vi.mock('../../utils/api', () => ({ financialExpensesAPI: { create: vi.fn(), update: vi.fn() } }));
const expense = {
  id: 'expense-1', user_id: 'user', tenant_id: 'tenant', title: 'Energia', category: 'moradia',
  amount_expected: 120, amount_paid: 40, status: 'partial', is_recurring: false,
  paid_at: '2026-09-12T15:20:30.123Z', competency_month: 9, competency_year: 2026,
} satisfies FinancialExpense;
const props = () => ({ expense, onClose: vi.fn(), onSaved: vi.fn(), defaultMonth: 9, defaultYear: 2026 });
beforeEach(() => vi.clearAllMocks());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ExpenseFormDialog', () => {
  it('preserva exatamente o instante original ao salvar sem editar pagamento', async () => {
    const callbacks = props();
    render(<ExpenseFormDialog {...callbacks} />);
    expect(screen.getByRole('dialog', { name: 'Editar conta' })).toBeInTheDocument();
    expect(screen.getByLabelText('Título *')).toHaveFocus();
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    await waitFor(() => expect(callbacks.onSaved).toHaveBeenCalledOnce());
    expect(financialExpensesAPI.update).toHaveBeenCalledWith(expense.id, expect.objectContaining({ paid_at: expense.paid_at, amount_paid: 40, status: 'partial' }));
  });

  it('converte horário local editado em instante ISO', async () => {
    render(<ExpenseFormDialog {...props()} />);
    fireEvent.change(screen.getByLabelText('Pago em'), { target: { value: '2026-09-13T11:45' } });
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    expect(financialExpensesAPI.update).toHaveBeenCalledWith(expense.id, expect.objectContaining({ paid_at: new Date('2026-09-13T11:45').toISOString() }));
  });

  it('solicita confirmação antes de descartar alterações por Escape', async () => {
    const callbacks = props();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<ExpenseFormDialog {...callbacks} />);
    fireEvent.change(screen.getByLabelText('Título *'), { target: { value: 'Novo título' } });
    await userEvent.keyboard('{Escape}');
    expect(confirm).toHaveBeenCalledOnce();
    expect(callbacks.onClose).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await userEvent.keyboard('{Escape}');
    expect(callbacks.onClose).toHaveBeenCalledOnce();
  });

  it('mantém valores e mostra erro inline quando salvar falha', async () => {
    vi.mocked(financialExpensesAPI.update).mockRejectedValueOnce(new Error('private details'));
    const callbacks = props();
    render(<ExpenseFormDialog {...callbacks} />);
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível salvar');
    expect(screen.getByRole('alert')).not.toHaveTextContent('private details');
    expect(screen.getByLabelText('Título *')).toHaveValue('Energia');
    expect(callbacks.onSaved).not.toHaveBeenCalled();
  });

  it('bloqueia fechar e reenviar enquanto salva', async () => {
    let finish!: () => void;
    vi.mocked(financialExpensesAPI.update).mockImplementationOnce(() => new Promise(resolve => { finish = () => resolve({} as never); }));
    const callbacks = props();
    render(<ExpenseFormDialog {...callbacks} />);
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    expect(screen.getByRole('button', { name: 'Salvando…' })).toBeDisabled();
    await userEvent.keyboard('{Escape}');
    expect(callbacks.onClose).not.toHaveBeenCalled();
    expect(financialExpensesAPI.update).toHaveBeenCalledOnce();
    finish();
    await waitFor(() => expect(callbacks.onSaved).toHaveBeenCalledOnce());
  });

  it('valida título obrigatório antes da API', async () => {
    render(<ExpenseFormDialog {...props()} expense={null} />);
    await userEvent.click(screen.getByRole('button', { name: 'Salvar conta' }));
    expect(screen.getByLabelText('Título *')).toBeInvalid();
    expect(financialExpensesAPI.create).not.toHaveBeenCalled();
  });
});

describe('ExpenseDialog', () => {
  it('mantém Tab no diálogo e restaura foco ao fechar', async () => {
    const trigger = document.createElement('button');
    document.body.append(trigger); trigger.focus();
    const { unmount } = render(<ExpenseDialog title="Confirmação" onClose={vi.fn()}><button>Última ação</button></ExpenseDialog>);
    const close = screen.getByRole('button', { name: 'Fechar diálogo' });
    expect(close).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Última ação' })).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    unmount(); expect(trigger).toHaveFocus(); trigger.remove();
  });
});
