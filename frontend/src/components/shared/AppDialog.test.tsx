import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppDialog } from './AppDialog';
import { ConfirmDialog } from './ConfirmDialog';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';

afterEach(cleanup);

describe('AppDialog', () => {
  it('foca o primeiro controle, cicla o Tab, fecha com Escape e devolve o foco', async () => {
    const opener = document.createElement('button');
    opener.textContent = 'Abrir';
    document.body.appendChild(opener);
    opener.focus();
    const onClose = vi.fn();
    const { unmount } = render(<AppDialog title="Confirmação" onClose={onClose}><button>Primeira</button><button>Última</button></AppDialog>);
    expect(screen.getByRole('dialog', { name: 'Confirmação' })).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Fechar diálogo' })).toHaveFocus();
    screen.getByRole('button', { name: 'Última' }).focus();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Fechar diálogo' })).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledOnce();
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(opener).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
    opener.remove();
  });

  it('ignora Escape enquanto ocupado', async () => {
    const onClose = vi.fn();
    render(<AppDialog title="Salvando" busy onClose={onClose}><p>Aguarde</p></AppDialog>);
    await userEvent.keyboard('{Escape}');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Fechar diálogo' })).toBeDisabled();
  });
});

describe('ConfirmDialog', () => {
  it('nomeia o item, impede envio duplicado e mantém aberto com erro', async () => {
    let resolve!: () => void;
    let reject!: (error: Error) => void;
    const onConfirm = vi.fn(() => new Promise<void>((done, fail) => { resolve = done; reject = fail; }));
    const onClose = vi.fn();
    render(<ConfirmDialog title="Excluir conta" subject="Banco Nubank" details={[['Saldo', 'R$ 10,00']]}
      consequence={<p>As transações continuam registradas.</p>} confirmLabel="Confirmar exclusão" danger onConfirm={onConfirm} onClose={onClose} />);
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
    expect(screen.getByText('Banco Nubank')).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Confirmar exclusão' });
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Confirmando…' })).toBeDisabled();
    await act(async () => reject(new Error('offline')));
    expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível concluir');
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar exclusão' }));
    await act(async () => resolve());
    expect(onConfirm).toHaveBeenCalledTimes(2);
  });
});

describe('useKeyedRequest', () => {
  it('descarta a resposta antiga quando a chave muda e nunca mostra erro como vazio', async () => {
    const pending: Record<string, { resolve: (value: number) => void; reject: (error: Error) => void; signal: AbortSignal }> = {};
    const request = (key: string) => (signal: AbortSignal) => new Promise<{ data: number }>((resolve, reject) => {
      pending[key] = { resolve: value => resolve({ data: value }), reject, signal };
    });
    const { result, rerender } = renderHook(({ key }) => useKeyedRequest<number>(key, true, request(key)), { initialProps: { key: 'a' } });
    expect(result.current.loading).toBe(true);
    rerender({ key: 'b' });
    expect(pending.a.signal.aborted).toBe(true);
    await act(async () => pending.a.resolve(1));
    expect(result.current.data).toBeNull();
    await act(async () => pending.b.resolve(2));
    expect(result.current.data).toBe(2);
    rerender({ key: 'c' });
    await act(async () => pending.c.reject(new Error('offline')));
    await waitFor(() => expect(result.current.error).not.toBe(''));
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });
});
